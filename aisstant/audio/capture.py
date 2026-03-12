from __future__ import annotations

import asyncio
from dataclasses import dataclass

import numpy as np
import sounddevice as sd

from aisstant.config import (
    CHANNELS,
    CHUNK_SAMPLES,
    SAMPLE_RATE,
)
from aisstant.latency_tracker import LatencyTracker
from aisstant.platform import SYSTEM_AUDIO_DEVICE_INDEX, system_audio_available


@dataclass(frozen=True)
class AudioDevice:
    index: int
    name: str
    max_input_channels: int


def list_input_devices() -> list[AudioDevice]:
    result: list[AudioDevice] = []

    if system_audio_available():
        result.append(
            AudioDevice(
                index=SYSTEM_AUDIO_DEVICE_INDEX,
                name="System Audio",
                max_input_channels=2,
            )
        )

    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            result.append(
                AudioDevice(
                    index=i,
                    name=dev["name"],
                    max_input_channels=dev["max_input_channels"],
                )
            )
    return result


class AudioCapture:
    def __init__(self, loop: asyncio.AbstractEventLoop, tracker: LatencyTracker | None = None) -> None:
        self._loop = loop
        self._stream: sd.InputStream | None = None
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=200)
        self._tracker = tracker or LatencyTracker()

    @property
    def queue(self) -> asyncio.Queue[np.ndarray]:
        return self._queue

    def _enqueue(self, chunk: np.ndarray) -> None:
        try:
            self._queue.put_nowait(chunk)
            self._tracker.on_audio_chunk_enqueued()
        except asyncio.QueueFull:
            self._tracker.on_queue_drop()

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            logger.info("[audio] status: %s", status)
        chunk = indata.copy().flatten()
        self._tracker.on_audio_chunk_captured()
        self._loop.call_soon_threadsafe(self._enqueue, chunk)

    def start(self, device_index: int) -> None:
        self.stop()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SAMPLES,
            device=device_index,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def switch_device(self, device_index: int) -> None:
        was_running = self._stream is not None and self._stream.active
        self.stop()
        if was_running:
            self.start(device_index)
