"""
Shared HTTP + JSON cache helpers for ATLAS data scrapers (no LLM).

Used by crypto_scraper, bond/macro pipelines, tests (monkeypatch requests_get_json).
"""

from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

REQUEST_TIMEOUT_S = 30.0
_DEFAULT_UA = (
    "ATLAS-DataAgent/1.0 (+https://localhost; research; contact atlas@localhost) "
    "python-requests"
)

_RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def sleep_backoff(attempt: int, *, base: float = 0.35, cap: float = 8.0) -> None:
    """Sleep with jitter for rate limits / transient errors."""
    t = min(cap, base * (2 ** max(0, attempt - 1)))
    jitter = random.uniform(0.0, min(0.5, base * 0.5))
    time.sleep(t + jitter)


def _merged_headers(extra: dict[str, str] | None) -> dict[str, str]:
    h = {"User-Agent": _DEFAULT_UA, "Accept": "application/json, */*"}
    if extra:
        h.update(extra)
    return h


def requests_get_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 3,
    timeout_s: float = REQUEST_TIMEOUT_S,
) -> str:
    """GET response body as text (Atom/RSS/HTML). Retries like requests_get_json."""
    last_exc: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            resp = requests.get(
                url,
                params=params,
                headers=_merged_headers(headers),
                timeout=timeout_s,
            )
            if resp.status_code in _RETRY_STATUS:
                sleep_backoff(attempt)
                continue
            resp.raise_for_status()
            return resp.text or ""
        except Exception as e:
            last_exc = e
            if attempt >= retries:
                break
            sleep_backoff(attempt)
    raise last_exc if last_exc else RuntimeError("requests_get_text failed")


def requests_get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 3,
    timeout_s: float = REQUEST_TIMEOUT_S,
) -> Any:
    """GET JSON from url; tolerant decode + retries."""
    last_exc: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            resp = requests.get(
                url,
                params=params,
                headers=_merged_headers(headers),
                timeout=timeout_s,
            )
            if resp.status_code in _RETRY_STATUS:
                sleep_backoff(attempt)
                continue
            resp.raise_for_status()
            text = resp.text or ""
            if not text.strip():
                return {}
            try:
                return resp.json()
            except ValueError:
                # Strip BOM / salvage single JSON object
                t = text.lstrip("\ufeff").strip()
                m = re.search(r"[{\[].+", t, re.S)
                if m:
                    return json.loads(m.group(0))
                raise ValueError("response not valid JSON")
        except Exception as e:
            last_exc = e
            if attempt >= retries:
                break
            sleep_backoff(attempt)
    raise last_exc if last_exc else RuntimeError("requests_get_json failed")


def requests_post_json(
    url: str,
    *,
    json_body: dict[str, Any] | list[Any],
    headers: dict[str, str] | None = None,
    retries: int = 3,
    timeout_s: float = REQUEST_TIMEOUT_S,
) -> Any:
    """POST JSON body; decode JSON response with retries."""
    h = _merged_headers(headers)
    h.setdefault("Content-Type", "application/json")
    last_exc: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            resp = requests.post(
                url, json=json_body, headers=h, timeout=timeout_s
            )
            if resp.status_code in _RETRY_STATUS:
                sleep_backoff(attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_exc = e
            if attempt >= retries:
                break
            sleep_backoff(attempt)
    raise last_exc if last_exc else RuntimeError("requests_post_json failed")


def write_cache_json_pair(
    cache_dir: Path,
    payload: dict[str, Any],
    *,
    stable_filename: str,
    stamped_prefix: str,
) -> tuple[Path, Path]:
    """
    Write stable `latest` JSON plus timestamped sibling under cache_dir.

    Matches atlas_agents/crypto/crypto_scraper.write_outputs convention.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    stamped_name = f"{stamped_prefix}{ts}.json"
    stable_path = cache_dir / stable_filename
    stamped_path = cache_dir / stamped_name
    text = json.dumps(payload, indent=2, default=str) + "\n"
    stable_path.write_text(text, encoding="utf-8")
    stamped_path.write_text(text, encoding="utf-8")
    return stable_path, stamped_path
