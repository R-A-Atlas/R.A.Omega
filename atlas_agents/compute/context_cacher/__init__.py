"""Context cacher."""

from __future__ import annotations

import hashlib
from typing import Any


def cache_key(payload: Any) -> str:
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()[:24]


def make_cache_record(payload: Any, value: Any) -> dict[str, Any]:
    return {"key": cache_key(payload), "payload": payload, "value": value}
