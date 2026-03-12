"""
AIsstant overlay app.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop

from aisstant.audio import AudioCapture, list_input_devices
from aisstant.config import (
    build_agent_instructions,
    build_initial_history,
    get_api_key,
    load_agent_model,
    load_expansion_settings,
    load_few_shot_examples,
    load_silence_duration_ms,
    load_vad_threshold,
    load_vad_type,
)
from aisstant.latency_tracker import LatencyTracker
from aisstant.pipeline import AgentPipeline, ExpansionResult, ExpansionService
from aisstant.platform import (
    IS_MACOS,
    SYSTEM_AUDIO_DEVICE_INDEX,
    stealth,
    system_audio_available,
)
from aisstant.ui import ExpansionWindow, OverlayWindow, SettingsWindow


class App:
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._recording = False
        self._tracker = LatencyTracker()

        self._window = OverlayWindow()
        self._settings_window = SettingsWindow()
        self._expansion_window = ExpansionWindow()
        self._audio = AudioCapture(loop, self._tracker)
        self._system_audio = None
        if system_audio_available():
            from aisstant.audio.system_capture import SystemAudioCapture
            self._system_audio = SystemAudioCapture(loop, self._tracker)
        self._using_system_audio = False
        self._pipeline: AgentPipeline | None = None
        self._pending_transcription: str | None = None

        self._apply_expansion_settings()

        self._populate_devices()
        self._window.toggle_requested.connect(self._on_toggle)
        self._window.clear_requested.connect(self._on_clear_requested)
        self._window.commit_requested.connect(self._on_commit)
        self._window.device_changed.connect(self._on_device_changed)
        self._window.settings_requested.connect(self._on_settings)
        self._window.skip_requested.connect(self._on_skip)
        self._window.close_requested.connect(self._on_close)
        self._window.expansion_requested.connect(self._on_expansion_requested)
        self._settings_window.saved.connect(self._on_settings_saved)
        self._window.show()
        stealth.make_window_stealthy(self._window)

    def _populate_devices(self) -> None:
        devices = list_input_devices()
        items = [(dev.index, dev.name) for dev in devices]
        self._window.set_devices(items)

    def _on_text(self, text: str) -> None:
        self._window.append_text(text)

    def _apply_expansion_settings(self) -> None:
        exp = load_expansion_settings()
        self._expansion_enabled = exp["enabled"]
        self._expansion_service = ExpansionService(
            model=exp["model"],
            system_prompt=exp["prompt"],
            user_prompt=exp["user_prompt"],
        )

    def _on_settings_saved(self) -> None:
        self._apply_expansion_settings()

    def _on_transcription(self, text: str) -> None:
        self._pending_transcription = text
        self._window.show_user_message(text)

    def _on_response_start(self) -> None:
        self._window.begin_response()
        self._window.set_responding(True)
        if not self._expansion_enabled:
            return
        block_id = self._window.current_block_id
        transcription = self._pending_transcription
        if block_id and transcription:
            self._window.mark_current_block_complete()
            history = self._pipeline.get_history() if self._pipeline else []
            self._expansion_service.request_expansion(
                block_id, transcription, history=history,
            )
            self._expansion_service.add_listener(
                block_id, self._make_expansion_listener(block_id),
            )
            self._pending_transcription = None

    def _on_turn_ended(self) -> None:
        self._window.set_responding(False)

    def _on_skip(self) -> None:
        if self._pipeline is not None:
            self._window.set_responding(False)
            self._window.set_status("Listening...")
            self._loop.create_task(self._pipeline.skip())

    def _make_expansion_listener(
        self, block_id: str,
    ):
        def on_update(result: ExpansionResult) -> None:
            self._window.set_block_expansion_status(block_id, result.status.value)
            if (
                self._expansion_window.isVisible()
                and self._expansion_window.current_block_id == block_id
            ):
                self._expansion_window.update_content(result)
        return on_update

    def _on_expansion_requested(self, block_id: str) -> None:
        result = self._expansion_service.get_result(block_id)
        self._expansion_window.show_for_block(block_id, result)
        stealth.make_window_stealthy(self._expansion_window)

    def _on_status(self, status: str) -> None:
        self._window.set_status(status)

    def _on_toggle(self) -> None:
        if self._recording:
            self._loop.create_task(self._stop())
        else:
            self._loop.create_task(self._start())

    def _on_clear_requested(self) -> None:
        self._window.clear_dialogue()
        if self._pipeline is not None:
            self._pipeline.clear_context()

    def _on_commit(self) -> None:
        if self._recording and self._pipeline is not None:
            self._loop.create_task(self._pipeline.commit())

    def _on_settings(self) -> None:
        self._settings_window.show()
        stealth.make_window_stealthy(self._settings_window)
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _on_close(self) -> None:
        self._loop.create_task(self._shutdown())

    def _on_device_changed(self, device_index: int) -> None:
        if not self._recording:
            return
        # Switching between system and mic audio while recording
        # requires a full restart of the capture
        is_system = device_index == SYSTEM_AUDIO_DEVICE_INDEX
        if is_system != self._using_system_audio:
            self._loop.create_task(self._restart_with_device(device_index))
        elif not is_system:
            self._audio.switch_device(device_index)

    async def _restart_with_device(self, device_index: int) -> None:
        await self._stop()
        self._loop.create_task(self._start())

    async def _start(self) -> None:
        device_index = self._window.get_selected_device_index()
        if device_index is None:
            self._on_status("No audio device selected")
            return

        try:
            get_api_key()
        except RuntimeError as exc:
            self._on_status(str(exc))
            return

        self._using_system_audio = device_index == SYSTEM_AUDIO_DEVICE_INDEX
        capture = self._system_audio if self._using_system_audio else self._audio
        audio_queue = capture.queue

        self._recording = True
        self._window.set_recording(True)

        self._pipeline = AgentPipeline(
            audio_queue=audio_queue,
            on_text_delta=self._on_text,
            on_status=self._on_status,
            on_response_start=self._on_response_start,
            on_turn_ended=self._on_turn_ended,
            on_transcription=self._on_transcription,
            tracker=self._tracker,
            instructions=build_agent_instructions(),
            initial_history=build_initial_history(load_few_shot_examples()),
            model=load_agent_model(),
            vad_type=load_vad_type(),
            vad_threshold=load_vad_threshold(),
            silence_duration_ms=load_silence_duration_ms(),
        )

        if self._using_system_audio:
            capture.start()
        else:
            capture.start(device_index)

        try:
            await self._pipeline.start()
        except Exception:
            capture.stop()
            self._recording = False
            self._window.set_recording(False)

    async def _stop(self) -> None:
        self._recording = False
        self._window.set_recording(False)
        self._window.set_responding(False)
        self._audio.stop()
        if self._system_audio is not None:
            self._system_audio.stop()
        if self._pipeline is not None:
            await self._pipeline.stop()
            self._pipeline = None
        await self._expansion_service.cancel_all()

    async def _shutdown(self) -> None:
        if self._recording:
            await self._stop()
        self._window.close()
        self._loop.stop()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Show full WebSocket messages (websockets truncates at 75 chars by default)
    try:
        from websockets.frames import Frame
        Frame.MAX_LOG_SIZE = 2048
    except (ImportError, AttributeError):
        pass

    if IS_MACOS:
        from aisstant.platform.darwin import ensure_system_audio_binary
        ensure_system_audio_binary()

    qt_app = QApplication(sys.argv)
    stealth.hide_from_dock()
    loop = QEventLoop(qt_app)
    asyncio.set_event_loop(loop)

    app = App(loop)  # noqa: F841 — prevent GC

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: loop.create_task(app._shutdown()))

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
