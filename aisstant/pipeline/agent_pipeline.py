from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Callable

import numpy as np

from agents import Agent, Runner
from agents.voice import (
    STTModelSettings,
    SingleAgentVoiceWorkflow,
    StreamedAudioInput,
    TTSModel,
    TTSModelSettings,
    VoicePipeline,
    VoicePipelineConfig,
    VoiceWorkflowHelper,
)

from aisstant.config import CHUNK_SAMPLES, DEFAULT_INSTRUCTIONS
from aisstant.latency_tracker import LatencyTracker

log = logging.getLogger("agent_pipeline")


class _NoOpTTS(TTSModel):
    @property
    def model_name(self) -> str:
        return "noop"

    async def run(self, text: str, settings: TTSModelSettings) -> AsyncIterator[bytes]:
        return
        yield  # noqa: unreachable — makes this an async generator


class AgentPipeline:
    def __init__(
        self,
        audio_queue: asyncio.Queue[np.ndarray],
        on_text_delta: Callable[[str], None],
        on_status: Callable[[str], None],
        on_response_start: Callable[[], None],
        on_turn_ended: Callable[[], None],
        on_transcription: Callable[[str], None] | None = None,
        tracker: LatencyTracker | None = None,
        instructions: str = DEFAULT_INSTRUCTIONS,
        initial_history: list[dict] | None = None,
        model: str = "gpt-4.1-nano",
        vad_type: str = "server_vad",
        vad_threshold: float = 0.5,
        silence_duration_ms: int = 400,
        vad_eagerness: str = "auto",
    ) -> None:
        self._audio_queue = audio_queue
        self._on_text_delta = on_text_delta
        self._on_status = on_status
        self._on_turn_ended = on_turn_ended
        self._tracker = tracker or LatencyTracker()

        agent = Agent(
            name="AIsstant",
            instructions=instructions,
            model=model,
        )
        self._workflow = _TextCapturingWorkflow(
            agent, on_text_delta, on_response_start, self._tracker,
            initial_history,
            on_transcription=on_transcription,
        )

        if vad_type == "semantic_vad":
            turn_detection = {
                "type": "semantic_vad",
                "eagerness": vad_eagerness,
            }
        else:
            turn_detection = {
                "type": "server_vad",
                "threshold": vad_threshold,
                "silence_duration_ms": silence_duration_ms,
            }

        self._pipeline = VoicePipeline(
            workflow=self._workflow,
            tts_model=_NoOpTTS(),
            config=VoicePipelineConfig(
                stt_settings=STTModelSettings(
                    turn_detection=turn_detection,
                ),
                tracing_disabled=True,
            ),
        )
        self._audio_input: StreamedAudioInput | None = None
        self._tasks: list[asyncio.Task] = []
        self._committing = False

    def get_history(self) -> list[dict]:
        """Return a copy of the conversation history (user/assistant text messages only)."""
        return [
            {"role": item["role"], "content": item["content"]}
            for item in self._workflow._input_history
            if item.get("role") in ("user", "assistant")
            and isinstance(item.get("content"), str)
        ]

    def clear_context(self) -> None:
        """Reset the conversation context."""
        self._workflow.clear_context()

    async def start(self) -> None:
        self._on_status("Connecting...")
        self._audio_input = StreamedAudioInput()

        log.info("Starting pipeline...")
        try:
            result = await self._pipeline.run(self._audio_input)
        except Exception as exc:
            log.error("Pipeline connection failed: %s", exc, exc_info=True)
            self._on_status(f"Connection failed: {exc}")
            raise

        log.info("Pipeline started, launching audio forward + event consumer tasks")
        self._tasks = [
            asyncio.create_task(self._forward_audio_loop()),
            asyncio.create_task(self._consume_events(result)),
        ]
        self._on_status("Connected")

    async def stop(self) -> None:
        log.info("Stopping pipeline...")
        if self._audio_input is not None:
            await self._audio_input.add_audio(None)
            self._audio_input = None

        for task in self._tasks:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()
        self._on_status("Disconnected")
        log.info("Pipeline stopped")

    async def send_text(self, text: str) -> None:
        """Send a text message directly, bypassing STT."""
        self._on_status("Thinking...")
        try:
            async for _chunk in self._workflow.run(text):
                pass
        except Exception as exc:
            log.error("Text send error: %s", exc, exc_info=True)
            self._on_status(f"Error: {exc}")
            return
        self._on_turn_ended()
        self._on_status("Listening...")

    async def commit(self) -> None:
        if self._audio_input is None:
            return
        log.info("Commit: injecting silence to trigger VAD")
        silence = np.zeros(CHUNK_SAMPLES, dtype=np.int16)
        self._committing = True
        for _ in range(17):
            await self._audio_input.add_audio(silence)
        self._committing = False

    async def skip(self) -> None:
        log.info("Skip: requesting workflow skip")
        self._workflow.request_skip()

    async def _forward_audio_loop(self) -> None:
        log.info("Forward loop started")
        chunks_sent = 0
        while self._audio_input is not None:
            try:
                audio_chunk = await asyncio.wait_for(
                    self._audio_queue.get(), timeout=0.5
                )
            except asyncio.TimeoutError:
                log.debug("Forward loop: no audio in queue (timeout)")
                continue
            if self._committing:
                continue
            if chunks_sent == 0:
                log.info(
                    "First audio chunk: shape=%s dtype=%s min=%d max=%d",
                    audio_chunk.shape, audio_chunk.dtype,
                    audio_chunk.min(), audio_chunk.max(),
                )
            self._tracker.on_audio_chunk_forwarded()
            await self._audio_input.add_audio(audio_chunk)
            chunks_sent += 1
            if chunks_sent % 50 == 0:
                log.info("Audio chunks forwarded: %d (queue size: %d)", chunks_sent, self._audio_queue.qsize())

    async def _consume_events(self, result) -> None:
        try:
            async for event in result.stream():
                log.debug("Pipeline event: type=%s", event.type)
                if event.type == "voice_stream_event_lifecycle":
                    log.info("Lifecycle event: %s", event.event)
                    if event.event == "turn_started":
                        self._tracker.on_turn_started()
                        self._on_status("Thinking...")
                    elif event.event == "turn_ended":
                        self._tracker.on_turn_ended()
                        self._on_turn_ended()
                        self._on_status("Listening...")
                    elif event.event == "session_ended":
                        self._on_status("Session ended")
                        break
                elif event.type == "voice_stream_event_audio":
                    log.debug("Audio event: data=%s", type(event.data).__name__ if event.data is not None else "None")
        except asyncio.CancelledError:
            log.info("Event consumer cancelled")
        except Exception as exc:
            log.error("Pipeline error: %s", exc, exc_info=True)
            self._on_status(f"Pipeline error: {exc}")


class _TextCapturingWorkflow(SingleAgentVoiceWorkflow):
    def __init__(
        self,
        agent: Agent,
        on_text_delta: Callable[[str], None],
        on_response_start: Callable[[], None],
        tracker: LatencyTracker,
        initial_history: list[dict] | None = None,
        on_transcription: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(agent)
        self._initial_history = list(initial_history) if initial_history else []
        self._input_history = list(self._initial_history)
        self._on_text_delta = on_text_delta
        self._on_response_start = on_response_start
        self._on_transcription = on_transcription
        self._tracker = tracker
        self._skip_event = asyncio.Event()

    def clear_context(self) -> None:
        log.info("Clearing context")
        self._input_history = list(self._initial_history)

    def request_skip(self) -> None:
        log.info("Skip requested")
        self._skip_event.set()

    async def run(self, transcription: str) -> AsyncIterator[str]:
        self._tracker.on_transcription_received(transcription)
        log.info("Workflow run called with transcription: %r", transcription)
        if self._on_transcription is not None:
            self._on_transcription(transcription)
        self._skip_event.clear()

        self._input_history.append({"role": "user", "content": transcription})

        result = Runner.run_streamed(self._current_agent, self._input_history)

        chunk_count = 0
        partial_text = ""
        completed = False

        log.info("Running agent with model: %s", self._current_agent.model)

        try:
            async for chunk in VoiceWorkflowHelper.stream_text_from(result):
                if self._skip_event.is_set():
                    log.info("Skip detected after %d chunks, breaking out", chunk_count)
                    result.cancel()
                    break

                chunk_count += 1
                if chunk_count == 1:
                    self._tracker.on_first_text_chunk()
                    self._on_response_start()
                partial_text += chunk
                log.debug("Text chunk #%d: %r", chunk_count, chunk[:80] if len(chunk) > 80 else chunk)
                self._on_text_delta(chunk)
                yield chunk
            else:
                completed = True
        finally:
            if chunk_count > 0:
                self._tracker.on_last_text_chunk()

            if completed:
                log.info("Workflow finished, total text chunks: %d", chunk_count)
                self._input_history = result.to_input_list()
                self._current_agent = result.last_agent
            else:
                log.info(
                    "Turn interrupted, saving partial response (%d chars) to history",
                    len(partial_text),
                )
                if partial_text:
                    self._input_history.append({
                        "role": "assistant",
                        "content": partial_text,
                    })


