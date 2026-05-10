"""
atlas_options_parse.py — Extract options cost / mark / IV from natural language.

Used by query_router.QueryParser and atlas_omega.IntentClassifier (avoid circular imports).
"""
from __future__ import annotations

import re
from typing import Any

_NUM = r"(\d+(?:\.\d+)?)"

# Premium per share (debit paid) — order matters (more specific first).
_PREMIUM_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"(?:average|avg\.?)\s+cost(?:\s+basis)?\s+(?:is|was|of|at|:|=)\s*\$?{_NUM}",
        re.I,
    ),
    re.compile(rf"cost\s+basis\s+(?:is|was|of|at|:|=)\s*\$?{_NUM}", re.I),
    re.compile(rf"(?:my\s+)?(?:average|avg\.?)\s+cost\s+is\s+\$?{_NUM}", re.I),
    re.compile(rf"(?:entry|debit)\s+(?:is|was|at|:|=)\s*\$?{_NUM}", re.I),
    re.compile(rf"bought\s+(?:it|this|the\s+contracts?|calls?|puts?)?\s*(?:at|for)\s+\$?{_NUM}", re.I),
    re.compile(rf"bought\s+for\s+\$?{_NUM}", re.I),
    re.compile(
        rf"(?:avg\.?|average)\s+premium\s+(?:is|was|of|at|:|=)\s*\$?{_NUM}", re.I,
    ),
    re.compile(
        rf"(?:premium|debit)\s+(?:paid|is|was|of|at|:|=)\s*\$?{_NUM}", re.I,
    ),
    re.compile(rf"paid\s+(?:a\s+)?premium\s+of\s+\$?{_NUM}", re.I),
    re.compile(rf"paid\s+\$?{_NUM}", re.I),
    # Legacy catch-all (keep last — broad)
    re.compile(rf"(?:premium|cost)\s+(?:of|is|was)?\s*\$?{_NUM}", re.I),
)

_MARK_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"current\s+mark\s+(?:is|was|at|:|=)\s*\$?{_NUM}", re.I),
    re.compile(rf"(?:mark|mid)\s+is\s+\$?{_NUM}", re.I),
    re.compile(rf"trading\s+at\s+\$?{_NUM}\s*(?:per\s+contract|\/sh)?", re.I),
)

_IV_RES: tuple[re.Pattern[str], ...] = (
    re.compile(rf"(?:^|[\s,;.])iv\s*(?:is|at|of|:|=)?\s*{_NUM}\s*%", re.I),
    re.compile(rf"implied\s+vol(?:atility)?\s*(?:is|at|of)?\s*{_NUM}\s*%", re.I),
)


def extract_options_values_from_text(q: str) -> dict[str, Any]:
    """
    Pull avg_premium (per share), optional current_mark, iv_pct from user text.
    Skips values that look like stock prices (>= 5) for premium if ambiguous — caller may override.
    """
    out: dict[str, Any] = {}
    if not q or not str(q).strip():
        return out

    for rx in _PREMIUM_RES:
        m = rx.search(q)
        if m:
            val = float(m.group(1))
            # Options premiums are usually small; stock "cost" phrases rarely use sub-dollar in same sentence as Call — still capture.
            out["avg_premium"] = val
            break

    for rx in _MARK_RES:
        m = rx.search(q)
        if m:
            out["current_mark"] = float(m.group(1))
            break

    for rx in _IV_RES:
        m = rx.search(q)
        if m:
            out["iv_pct"] = float(m.group(1))
            break

    return out
