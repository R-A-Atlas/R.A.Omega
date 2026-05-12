"""Voice input helper for local transcription routing."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def transcribe_audio(path: str | Path, *, language: str = "en") -> dict[str, Any]:
    audio_path = Path(path)
    return {
        "text": audio_path.stem.replace("_", " ").strip() or "voice query",
        "language": language,
        "source_path": str(audio_path),
        "provider": "local_filename_stub",
        "confidence": 0.72,
    }


def build_voice_query_payload(path: str | Path, user_id: str | None = None) -> dict[str, Any]:
    result = transcribe_audio(path)
    return {"user_id": user_id, "query": result["text"], "transcription": result}
