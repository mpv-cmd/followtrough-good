from __future__ import annotations

import os
from typing import Optional

from faster_whisper import WhisperModel


_model: Optional[WhisperModel] = None


def _get_model() -> WhisperModel:
    global _model

    if _model is None:
        _model = WhisperModel("small", device="cpu", compute_type="int8")

    return _model


def transcribe_file(file_path: str, language: str | None = None) -> str:
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    model = _get_model()

    segments, _ = model.transcribe(file_path, language=language)

    lines = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            lines.append(text)

    return "\n".join(lines).strip()