"""
atlas_memory/memory_injector.py

Long-term memory layer for R.A. Omega.

get_relevant_context(query, user_id) -> str
    Searches atlas_memory.db for similar past queries.
    Returns top 3 relevant findings, max ~400 tokens.

save_to_memory(query, response, user_id) -> None
    Extracts entity, rating, key_risk, catalyst, price, domain.
    Saves to atlas_memory.db indexed by user_id + domain + entity.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "atlas_memory.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL DEFAULT '',
    domain      TEXT    NOT NULL DEFAULT '',
    entity      TEXT    NOT NULL DEFAULT '',
    query       TEXT    NOT NULL DEFAULT '',
    rating      TEXT,
    key_risk    TEXT,
    catalyst    TEXT,
    price       TEXT,
    tldr        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_memory_user  ON memory(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_entity ON memory(entity);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    for stmt in _SCHEMA.strip().split(";"):
        s = stmt.strip()
        if s:
            try:
                conn.execute(s)
            except sqlite3.OperationalError:
                pass
    conn.commit()
    return conn


# ── Token budget helper ───────────────────────────────────────────────────────

def _truncate(text: str, max_tokens: int = 120) -> str:
    words = text.split()
    return " ".join(words[:max_tokens]) + ("…" if len(words) > max_tokens else "")


# ── Domain inference ──────────────────────────────────────────────────────────

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "crypto":          ["bitcoin", "btc", "eth", "solana", "crypto", "defi", "nft", "altcoin"],
    "equity":          ["stock", "shares", "ticker", "earnings", "analyst", "bull", "bear"],
    "real_estate":     ["mortgage", "house", "rental", "reit", "property", "apartment", "zoning"],
    "personal_wealth": ["hysa", "savings", "credit card", "401k", "ira", "debt", "loan", "retire"],
    "tax_legal":       ["tax", "irs", "bracket", "deduction", "capital gains", "w2", "contractor"],
    "business":        ["sba", "saas", "startup", "venture", "franchise", "ecommerce", "churn"],
    "macro":           ["regime", "fed", "rate", "inflation", "gdp", "liquidity", "sector"],
    "options":         ["call", "put", "iv", "delta", "expiry", "covered call", "iron condor"],
    "alternatives":    ["gold", "silver", "watch", "art", "collectible", "p2p", "metals"],
}


def _infer_domain(text: str) -> str:
    low = text.lower()
    best, best_score = "equity", 0
    for domain, kws in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in low)
        if score > best_score:
            best, best_score = domain, score
    return best


def _extract_entity(query: str, response: dict[str, Any]) -> str:
    pq = response.get("parsed_query") or {}
    tickers = pq.get("tickers")
    if isinstance(tickers, list) and tickers:
        return tickers[0].upper()
    fr = response.get("final_report") or {}
    ticker = fr.get("ticker") or fr.get("company_name") or ""
    if ticker:
        return str(ticker).upper()
    words = query.upper().split()
    candidates = [w for w in words if 2 <= len(w) <= 5 and w.isalpha()]
    return candidates[0] if candidates else query[:24]


# ── Public API ────────────────────────────────────────────────────────────────

def get_relevant_context(query: str, user_id: str | None = None) -> str:
    """
    Search atlas_memory.db for past findings relevant to this query.
    Returns a compact string (<=400 tokens) or empty string if nothing useful.
    """
    if not DB_PATH.exists():
        return ""
    try:
        conn = _connect()
        uid = user_id or ""
        entity = _extract_entity(query, {})
        domain = _infer_domain(query)

        rows = conn.execute(
            """SELECT entity, domain, rating, tldr, key_risk, catalyst, price, updated_at
               FROM memory
               WHERE (user_id = ? OR user_id = '')
                 AND (entity LIKE ? OR domain = ?)
               ORDER BY updated_at DESC
               LIMIT 3""",
            (uid, f"%{entity}%", domain),
        ).fetchall()
        conn.close()

        if not rows:
            return ""

        parts: list[str] = []
        for row in rows:
            chunks = [f"[{row['entity']} / {row['domain']}]"]
            if row["rating"]:
                chunks.append(f"Rating: {row['rating']}")
            if row["tldr"]:
                chunks.append(_truncate(row["tldr"], 60))
            if row["key_risk"]:
                chunks.append(f"Key risk: {_truncate(row['key_risk'], 30)}")
            if row["catalyst"]:
                chunks.append(f"Catalyst: {_truncate(row['catalyst'], 30)}")
            if row["price"]:
                chunks.append(f"Price ref: {row['price']}")
            parts.append(" | ".join(chunks))

        return "PAST CONTEXT:\n" + "\n".join(parts)

    except Exception:
        return ""


def save_to_memory(query: str, response: dict[str, Any], user_id: str | None = None) -> None:
    """
    Extract key fields from a POST /query response and persist to atlas_memory.db.
    """
    try:
        fr = response.get("final_report") or {}
        entity = _extract_entity(query, response)
        domain = _infer_domain(query)

        rating = str(fr.get("overall_rating") or fr.get("primary_recommendation") or "")
        tldr_raw = response.get("tldr") or fr.get("tldr") or fr.get("executive_summary") or ""
        tldr = _truncate(str(tldr_raw), 80)

        key_risks = fr.get("key_risks")
        if isinstance(key_risks, list) and key_risks:
            kr_item = key_risks[0]
            key_risk = str(kr_item.get("risk") or kr_item) if isinstance(kr_item, dict) else str(kr_item)
        else:
            key_risk = str(key_risks or "")
        key_risk = _truncate(key_risk, 40)

        cats = fr.get("catalysts_timeline")
        if isinstance(cats, list) and cats:
            c0 = cats[0]
            catalyst = str(c0.get("event") or c0) if isinstance(c0, dict) else str(c0)
        else:
            catalyst = ""
        catalyst = _truncate(catalyst, 40)

        price = str(fr.get("price_now") or "")

        conn = _connect()
        existing = conn.execute(
            "SELECT id FROM memory WHERE user_id=? AND entity=? AND domain=? LIMIT 1",
            (user_id or "", entity, domain),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE memory SET rating=?, key_risk=?, catalyst=?, price=?, tldr=?,
                   query=?, updated_at=datetime('now')
                   WHERE id=?""",
                (rating, key_risk, catalyst, price, tldr, query, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO memory (user_id, domain, entity, query, rating, key_risk, catalyst, price, tldr)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id or "", domain, entity, query, rating, key_risk, catalyst, price, tldr),
            )
        conn.commit()
        conn.close()
    except Exception:
        pass
