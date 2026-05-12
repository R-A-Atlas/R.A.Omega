"""Voice output helper for text-to-speech job envelopes."""

from __future__ import annotations

from hashlib import sha256
from typing import Any


def build_tts_request(text: str, *, voice: str = "omega", format: str = "mp3") -> dict[str, Any]:
    clean = " ".join(str(text or "").split())
    return {
        "id": sha256(clean.encode("utf-8")).hexdigest()[:16],
        "text": clean,
        "voice": voice,
        "format": format,
        "status": "READY" if clean else "EMPTY",
    }
