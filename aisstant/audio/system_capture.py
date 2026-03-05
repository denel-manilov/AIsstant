from __future__ import annotations

import asyncio
import logging
import subprocess
import threading

import numpy as np

from aisstant.config import CHUNK_SAMPLES
from aisstant.latency_tracker import LatencyTracker
from aisstant.platform.darwin import SYSTEM_AUDIO_BINARY

log = logging.getLogger("system_audio")

# SystemAudioDump outputs: 24kHz, int16, stereo (2ch), interleaved
_STEREO_CHANNELS = 2
_BYTES_PER_SAMPLE = 2
_CHUNK_BYTES = CHUNK_SAMPLES * _STEREO_CHANNELS * _BYTES_PER_SAMPLE


class SystemAudioCapture:
    def __init__(self, loop: asyncio.AbstractEventLoop, tracker: LatencyTracker | None = None) -> None:
        self._loop = loop
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=200)
        self._tracker = tracker or LatencyTracker()

    @property
    def queue(self) -> asyncio.Queue[np.ndarray]:
        return self._queue

    def start(self) -> None:
        self.stop()
        log.info("Starting SystemAudioDump: %s", SYSTEM_AUDIO_BINARY)
        self._process = subprocess.Popen(
            [str(SYSTEM_AUDIO_BINARY)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._thread = threading.Thread(
            target=self._read_loop, daemon=True, name="system-audio-reader",
        )
        self._thread.start()

    def stop(self) -> None:
        if self._process is not None:
            log.info("Stopping SystemAudioDump (pid=%d)", self._process.pid)
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._thread = None
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _enqueue(self, chunk: np.ndarray) -> None:
        try:
            self._queue.put_nowait(chunk)
            self._tracker.on_audio_chunk_enqueued()
        except asyncio.QueueFull:
            self._tracker.on_queue_drop()

    def _read_loop(self) -> None:
        log.info("System audio read loop started")
        process = self._process
        if process is None or process.stdout is None:
            return

        chunks_read = 0
        buf = b""

        while process.poll() is None:
            data = process.stdout.read(_CHUNK_BYTES - len(buf))
            if not data:
                break
            buf += data
            if len(buf) < _CHUNK_BYTES:
                continue

            stereo = np.frombuffer(buf[:_CHUNK_BYTES], dtype=np.int16)
            buf = buf[_CHUNK_BYTES:]

            # stereo interleaved → mono: average left + right channels
            mono = (
                stereo.reshape(-1, _STEREO_CHANNELS)
                .astype(np.int32)
                .mean(axis=1)
                .astype(np.int16)
            )

            chunks_read += 1
            if chunks_read == 1:
                log.info(
                    "First system audio chunk: shape=%s dtype=%s min=%d max=%d",
                    mono.shape, mono.dtype, mono.min(), mono.max(),
                )
            if chunks_read % 50 == 0:
                log.info(
                    "System audio chunks read: %d (queue size: %d)",
                    chunks_read, self._queue.qsize(),
                )

            self._tracker.on_audio_chunk_captured()
            self._loop.call_soon_threadsafe(self._enqueue, mono)

        log.info("System audio read loop ended (chunks_read=%d)", chunks_read)
