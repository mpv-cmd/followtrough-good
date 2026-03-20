from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from faster_whisper import WhisperModel


_model: Optional[WhisperModel] = None


def _get_model() -> WhisperModel:
    global _model

    if _model is None:
        # Good speed/quality balance for CPU deployments
        _model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
            cpu_threads=max(1, os.cpu_count() or 1),
            num_workers=1,
        )

    return _model


def ensure_wav(input_path: str) -> str:
    source = Path(input_path)

    if not source.exists():
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    wav_path = source.with_suffix(".wav")

    if wav_path.exists():
        return str(wav_path)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-ac",
                "1",
                "-ar",
                "16000",
                str(wav_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as e:
        raise RuntimeError("ffmpeg is not installed or not available in PATH") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to convert audio to wav: {source.name}") from e

    if not wav_path.exists():
        raise RuntimeError(f"WAV conversion failed for: {source.name}")

    return str(wav_path)


def transcribe_file(file_path: str, language: str | None = None) -> str:
    if not file_path or not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    wav_path = ensure_wav(file_path)
    model = _get_model()

    segments, info = model.transcribe(
        wav_path,
        language=language,
        vad_filter=True,
        beam_size=1,
        best_of=1,
        temperature=0.0,
        condition_on_previous_text=False,
    )

    lines: list[str] = []
    for seg in segments:
        text = (seg.text or "").strip()
        if text:
            lines.append(text)

    transcript = "\n".join(lines).strip()

    if not transcript:
        detected = getattr(info, "language", None)
        lang_msg = f" (detected language: {detected})" if detected else ""
        raise RuntimeError(f"Transcription produced no text{lang_msg}")

    return transcript