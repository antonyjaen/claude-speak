"""Speech-to-text via faster-whisper (local, free)."""
from __future__ import annotations

import os
import threading
from typing import Optional

import numpy as np

_model_lock = threading.Lock()
_model = None  # lazy-loaded WhisperModel


def _model_name() -> str:
    return os.environ.get("CLAUDE_VOICE_MODEL", "base.en")


def _language() -> str:
    return os.environ.get("CLAUDE_VOICE_LANG", "en")


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from faster_whisper import WhisperModel

        # CPU + int8 = fast and low-memory; works on every machine.
        _model = WhisperModel(_model_name(), device="cpu", compute_type="int8")
    return _model


def warmup() -> None:
    """Load the model now so the first transcription isn't slow."""
    _get_model()


def transcribe(audio: np.ndarray, *, language: Optional[str] = None) -> str:
    """Transcribe a float32 mono 16kHz numpy array. Returns a single string."""
    if audio is None or len(audio) == 0:
        return ""
    # faster-whisper expects float32 mono in [-1, 1]
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)

    model = _get_model()
    segments, _info = model.transcribe(
        audio,
        language=language or _language(),
        vad_filter=True,
        beam_size=5,
    )
    return "".join(seg.text for seg in segments).strip()
