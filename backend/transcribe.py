import os
import subprocess
from faster_whisper import WhisperModel

def ensure_wav(input_path: str) -> str:
    base, _ = os.path.splitext(input_path)
    wav_path = base + ".wav"
    if os.path.exists(wav_path):
        return wav_path

    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-ac", "1", "-ar", "16000", wav_path],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return wav_path

def transcribe_file(file_path: str, language: str | None = None) -> str:
    wav_path = ensure_wav(file_path)
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(wav_path, language=language)

    return "\n".join(seg.text.strip() for seg in segments if seg.text.strip())