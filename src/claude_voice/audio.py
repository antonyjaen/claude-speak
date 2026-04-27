"""Microphone capture using sounddevice. Records 16kHz mono float32."""
from __future__ import annotations

import threading
from typing import Optional

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16_000
CHANNELS = 1


class Recorder:
    """Start/stop a microphone recording. Returns the captured numpy array.

    Usage:
        rec = Recorder()
        rec.start()
        # ... wait ...
        audio = rec.stop()  # np.ndarray, float32, mono, 16kHz
    """

    def __init__(self, samplerate: int = SAMPLE_RATE) -> None:
        self.samplerate = samplerate
        self._chunks: list[np.ndarray] = []
        self._stream: Optional[sd.InputStream] = None
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        if status:
            # Drop silently — overflows aren't fatal for short PTT segments
            pass
        with self._lock:
            self._chunks.append(indata.copy())

    def start(self) -> None:
        if self._stream is not None:
            return
        self._chunks = []
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=CHANNELS,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        with self._lock:
            chunks = self._chunks
            self._chunks = []
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).flatten().astype(np.float32, copy=False)


def list_input_devices() -> list[dict]:
    """Return a list of available input device descriptors."""
    return [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
