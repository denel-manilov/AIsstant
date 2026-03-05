from __future__ import annotations

import logging
import threading
import time
from collections import deque

log = logging.getLogger("latency")

_AUDIO_STATS_WINDOW = 50


class LatencyTracker:
    def __init__(self) -> None:
        self._turn_count = 0
        self._transcription_at: float | None = None
        self._first_text_at: float | None = None
        self._last_text_at: float | None = None
        self._response_ended_at: float | None = None
        self._transcription_text: str = ""
        self._got_first_text = False

        self._lock = threading.Lock()
        self._capture_to_enqueue: deque[float] = deque(maxlen=_AUDIO_STATS_WINDOW)
        self._last_capture_ts: float | None = None
        self._queue_drops = 0

        self._enqueue_to_forward: deque[float] = deque(maxlen=_AUDIO_STATS_WINDOW)
        self._last_enqueue_ts: float | None = None

    # ── audio path (called from audio threads) ────────────

    def on_audio_chunk_captured(self) -> None:
        with self._lock:
            self._last_capture_ts = time.monotonic()

    def on_audio_chunk_enqueued(self) -> None:
        with self._lock:
            now = time.monotonic()
            if self._last_capture_ts is not None:
                self._capture_to_enqueue.append(now - self._last_capture_ts)
            self._last_enqueue_ts = now

    def on_queue_drop(self) -> None:
        with self._lock:
            self._queue_drops += 1

    # ── forward loop (called from asyncio) ────────────────

    def on_audio_chunk_forwarded(self) -> None:
        with self._lock:
            now = time.monotonic()
            if self._last_enqueue_ts is not None:
                self._enqueue_to_forward.append(now - self._last_enqueue_ts)

    # ── turn lifecycle (called from asyncio) ──────────────

    def on_turn_started(self) -> None:
        pass

    def on_transcription_received(self, text: str) -> None:
        self._transcription_at = time.monotonic()
        self._first_text_at = None
        self._last_text_at = None
        self._response_ended_at = None
        self._transcription_text = text
        self._got_first_text = False

    def on_first_text_chunk(self) -> None:
        if not self._got_first_text:
            self._first_text_at = time.monotonic()
            self._got_first_text = True

    def on_last_text_chunk(self) -> None:
        self._last_text_at = time.monotonic()

    def on_turn_ended(self) -> None:
        self._response_ended_at = time.monotonic()
        self._turn_count += 1
        self._report_turn()

    # ── reporting ─────────────────────────────────────────

    def _report_turn(self) -> None:
        lines = [f"── Turn #{self._turn_count} ──────────────────────"]

        if self._transcription_text:
            preview = self._transcription_text[:80]
            lines.append(f'Transcription: "{preview}"')

        tr = self._transcription_at
        ft = self._first_text_at
        lt = self._last_text_at
        te = self._response_ended_at

        if tr is not None and ft is not None:
            lines.append(f"transcription → first_text:    {_ms(ft - tr):>8}  (LLM first token)")
        if ft is not None and lt is not None:
            lines.append(f"first_text → last_text:        {_ms(lt - ft):>8}  (LLM streaming)")
        if lt is not None and te is not None:
            lines.append(f"last_text → response_end:      {_ms(te - lt):>8}  (TTS)")
        if tr is not None and te is not None:
            lines.append(f"transcription → response_end:  {_ms(te - tr):>8}  (E2E response)")

        with self._lock:
            lines.append(f"── Audio stats (last {_AUDIO_STATS_WINDOW} chunks) ─")
            if self._capture_to_enqueue:
                vals = list(self._capture_to_enqueue)
                lines.append(
                    f"capture → enqueue:  avg {_ms(sum(vals) / len(vals)):>6}, "
                    f"max {_ms(max(vals)):>6}"
                )
            if self._enqueue_to_forward:
                vals = list(self._enqueue_to_forward)
                lines.append(
                    f"queue wait:         avg {_ms(sum(vals) / len(vals)):>6}, "
                    f"max {_ms(max(vals)):>6}"
                )
            lines.append(f"queue drops:        {self._queue_drops}")
            self._queue_drops = 0

        for line in lines:
            log.info(line)


def _ms(seconds: float) -> str:
    return f"{seconds * 1000:.1f} ms"
