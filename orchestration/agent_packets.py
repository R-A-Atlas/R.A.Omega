"""Compact specialist packet loader for active R.A. Omega agents."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from orchestration.agent_graph import AgentActivation, SpecialistAgent


MAX_LIST_ITEMS = 6
MAX_DICT_KEYS = 18
MAX_TEXT_CHARS = 600


def data_cache_root() -> Path:
    env = (os.environ.get("ATLAS_DATA_CACHE_DIR") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1] / "data_cache"


def build_specialist_packets(activation: AgentActivation) -> dict[str, Any]:
    packets: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for agent in activation.agents:
        packet, error = _packet_for_agent(agent)
        if error:
            errors[agent.agent_id] = error
        packets[agent.packet_key] = packet
    return {
        "route": activation.route,
        "agent_ids": [agent.agent_id for agent in activation.agents],
        "packets": packets,
        "errors": errors,
        "packet_count": len(packets),
    }


def _packet_for_agent(agent: SpecialistAgent) -> tuple[dict[str, Any], str | None]:
    base = {
        "agent_id": agent.agent_id,
        "agent_name": agent.name,
        "division": agent.division,
        "role": agent.role,
        "cache_file": agent.cache_file,
    }
    if not agent.cache_file:
        return {**base, "status": "metadata_only"}, None
    path = data_cache_root() / agent.cache_file
    if not path.is_file():
        return {**base, "status": "missing_cache"}, f"missing:{agent.cache_file}"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {**base, "status": "invalid_cache"}, f"invalid:{agent.cache_file}:{exc}"
    if not isinstance(raw, dict):
        return {**base, "status": "invalid_shape"}, f"invalid_shape:{agent.cache_file}"

    meta = raw.get("_meta") if isinstance(raw.get("_meta"), dict) else {}
    packet = {
        **base,
        "status": "ok",
        "generated_at": raw.get("generated_at"),
        "source": raw.get("source"),
        "record_count": raw.get("record_count"),
        "data_quality": meta.get("data_quality") or "live",
        "fallback_used": bool(meta.get("fallback_used") or meta.get("data_quality") == "fallback"),
        "summary": _compact_payload(raw),
    }
    if meta:
        packet["_meta"] = _compact_payload(meta)
    return packet, None


def _compact_payload(value: Any, depth: int = 0) -> Any:
    if depth >= 3:
        return _scalar(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if key == "_meta" and depth == 0:
                continue
            out[str(key)] = _compact_payload(item, depth + 1)
            if len(out) >= MAX_DICT_KEYS:
                out["_truncated_keys"] = True
                break
        return out
    if isinstance(value, list):
        out = [_compact_payload(item, depth + 1) for item in value[:MAX_LIST_ITEMS]]
        if len(value) > MAX_LIST_ITEMS:
            out.append({"_truncated_items": len(value) - MAX_LIST_ITEMS})
        return out
    return _scalar(value)


def _scalar(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_TEXT_CHARS:
        return value[:MAX_TEXT_CHARS] + "...[truncated]"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)[:MAX_TEXT_CHARS]


__all__ = ["build_specialist_packets", "data_cache_root"]
