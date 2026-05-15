#!/usr/bin/env python3
"""
ATLAS Deep Research Engine
---------------------------
Hybrid research pipeline: Python web scraping + Gemini AI synthesis.

How it works:
  1. web_scraper.py scrapes Finviz, Google News, StockAnalysis, SEC EDGAR,
     Reddit, Benzinga — all free, no API keys, no rate limits.
  2. All scraped data is compiled into a rich context text blob.
  3. Gemini (gemini-2.5-flash, no grounding needed) reads the real scraped
     data and synthesizes a structured trade recommendation.

Result: Zero grounding API calls. AI only does reasoning. Full quality.
No hallucination because AI is reading real scraped data, not inventing it.

Modes:
  1. TICKER DEEP DIVE  — full research on one stock
  2. STOCK DISCOVERY   — find high-potential stocks matching a theme/budget

Usage:
    python deep_research.py --ticker SOUN
    python deep_research.py --ticker SOUN --budget 100
    python deep_research.py --discover "AI penny stocks under 5 dollars"
    python deep_research.py --discover "biotech FDA catalyst Q2 2026" --max 5

Integrated into auto_bot.py via:
    python auto_bot.py --deep-research SOUN
    python auto_bot.py --discover "best small-cap AI plays 2026"
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time as _time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from gemini_limiter import wait_for_slot

# Web scraper — free data from Finviz, Google News, SEC EDGAR, Reddit, etc.
try:
    import web_scraper
    _SCRAPER_AVAILABLE = True
except ImportError:
    _SCRAPER_AVAILABLE = False
    logging.warning("web_scraper.py not found — will fall back to grounded search only.")

# Options P/L simulator — pure math, no API needed
try:
    import options_simulator as _opts_sim
    _OPTS_SIM_AVAILABLE = True
except ImportError:
    _opts_sim           = None   # type: ignore
    _OPTS_SIM_AVAILABLE = False

# Memory system — persistent knowledge store
try:
    import memory as _memory
    _MEMORY_AVAILABLE = True
except ImportError:
    _memory           = None   # type: ignore
    _MEMORY_AVAILABLE = False

# Win-rate tracker + setup pattern library
try:
    import tracker as _tracker
    _TRACKER_AVAILABLE = True
except ImportError:
    _tracker           = None   # type: ignore
    _TRACKER_AVAILABLE = False

# Real-time price alert monitor
try:
    import alerts as _alerts
    _ALERTS_AVAILABLE = True
except ImportError:
    _alerts           = None   # type: ignore
    _ALERTS_AVAILABLE = False

# Position sizing engine
try:
    import position_sizer as _position_sizer
    _SIZER_AVAILABLE = True
except ImportError:
    _position_sizer  = None   # type: ignore
    _SIZER_AVAILABLE = False

# Volume profile (Level 2 approximation)
try:
    import volume_profile as _vp
    _VP_AVAILABLE = True
except ImportError:
    _vp           = None   # type: ignore
    _VP_AVAILABLE = False

# Sector rotation / portfolio correlation
try:
    import sector_tracker as _sector
    _SECTOR_AVAILABLE = True
except ImportError:
    _sector           = None   # type: ignore
    _SECTOR_AVAILABLE = False

# Hyper-awareness engine (squeeze, gaps, regime, earnings history, velocity)
try:
    import market_scanner as _market_scanner
    _MARKET_SCANNER_AVAILABLE = True
except ImportError:
    _market_scanner              = None   # type: ignore
    _MARKET_SCANNER_AVAILABLE    = False

# Auto-tuner — loads self-tuned weights and thresholds
try:
    import auto_tuner as _auto_tuner
    _AUTO_TUNER_AVAILABLE = True
except ImportError:
    _auto_tuner           = None   # type: ignore
    _AUTO_TUNER_AVAILABLE = False

# Congressional trade intelligence (Phase 2A)
try:
    import congress_tracker as _congress
    _CONGRESS_AVAILABLE = True
except ImportError:
    _congress           = None   # type: ignore
    _CONGRESS_AVAILABLE = False

# Tradier options API — replaces Barchart scraping when token is configured
try:
    import broker_tradier as _tradier
    _TRADIER_AVAILABLE = bool(getattr(_tradier, "_TOKEN", ""))
except ImportError:
    _tradier           = None   # type: ignore
    _TRADIER_AVAILABLE = False

# SEC Filing RAG — ChromaDB vector search over 10-K/8-K documents
try:
    import rag_engine as _rag
    _RAG_AVAILABLE = True
except ImportError:
    _rag           = None   # type: ignore
    _RAG_AVAILABLE = False

# Paper trading state machine — auto-propose trades after research
try:
    import paper_trader as _paper_trader
    _PAPER_TRADER_AVAILABLE = True
except ImportError:
    _paper_trader           = None   # type: ignore
    _PAPER_TRADER_AVAILABLE = False

# Dynamic backtest sandbox — Gemini writes pandas code, runs in subprocess
try:
    import backtest_sandbox as _backtest
    _BACKTEST_AVAILABLE = True
except ImportError:
    _backtest           = None   # type: ignore
    _BACKTEST_AVAILABLE = False

SCRIPT_DIR   = Path(__file__).resolve().parent
REPORTS_DIR  = SCRIPT_DIR / "reports"
DR_DIR       = SCRIPT_DIR / "deep_reports"
load_dotenv(SCRIPT_DIR / ".env")
load_dotenv()


class AtlasSynthesisReport(BaseModel):
    """
    Target JSON shape for Gemini structured output (response_json_schema).
    Nested sections stay as generic objects/arrays so minor model deviations still parse.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    ticker: str = ""
    company_name: str = ""
    sector: str = ""
    overall_rating: str = "hold"
    confidence: int = Field(default=5)
    price_now: float | None = None
    executive_summary: str = ""
    bull_thesis: str = ""
    bear_thesis: str = ""
    trade_plan: dict[str, Any] = Field(default_factory=dict)
    options_play: dict[str, Any] = Field(default_factory=dict)
    catalysts_timeline: list[Any] = Field(default_factory=list)
    key_risks: list[Any] = Field(default_factory=list)
    price_levels: dict[str, Any] = Field(default_factory=dict)
    earnings_analysis: dict[str, Any] = Field(default_factory=dict)
    analyst_consensus: dict[str, Any] = Field(default_factory=dict)
    x100_potential: dict[str, Any] = Field(default_factory=dict, alias="100x_potential")
    last_researched: str = ""

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence_bounds(cls, v: Any) -> int:
        try:
            n = int(round(float(v)))
        except Exception:
            return 5
        return max(1, min(10, n))


_SYNTHESIS_JSON_SCHEMA: dict[str, Any] | None = None


def _synthesis_json_schema() -> dict[str, Any]:
    global _SYNTHESIS_JSON_SCHEMA
    if _SYNTHESIS_JSON_SCHEMA is None:
        _SYNTHESIS_JSON_SCHEMA = AtlasSynthesisReport.model_json_schema()
    return _SYNTHESIS_JSON_SCHEMA

try:
    from google import genai as _genai
    from google.genai import types as _gtypes
    _GENAI_OK = True
except ImportError:
    _GENAI_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Gemini helpers
# ─────────────────────────────────────────────────────────────────────────────
def _client():
    if not _GENAI_OK:
        return None
    key = os.environ.get("GOOGLE_API_KEY", "")
    return _genai.Client(api_key=key) if key else None


@contextmanager
def _gemini_slot(caller: str = "deep_research"):
    """Global Gemini spacing via gemini_limiter (coordinates all ATLAS modules)."""
    wait_for_slot(caller)
    yield


_RESEARCH_RUN_LOCK = threading.Lock()


def _search(client, prompt: str, label: str = "") -> str:
    """
    Gemini grounded search — uses Google Search grounding for real web data.
    Always uses gemini-2.0-flash (NOT lite) for full reasoning quality.
    Retries with exponential backoff on rate limits.
    """
    if not client:
        return ""
    model = "gemini-2.0-flash"   # best model that supports grounding — never downgrade
    with _gemini_slot():
        for _attempt in range(4):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=_gtypes.GenerateContentConfig(
                        tools=[_gtypes.Tool(google_search=_gtypes.GoogleSearch())]
                    ),
                )
                text = (resp.text or "").strip()
                if label:
                    logging.info("    [%s] %d chars returned", label, len(text))
                return text
            except Exception as _e:
                if ("429" in str(_e)
                        or "quota" in str(_e).lower()
                        or "RESOURCE_EXHAUSTED" in str(_e)):
                    wait = 25 * (2 ** _attempt)  # 25s, 50s, 100s, 200s
                    logging.warning("[gemini] 429 rate limit — waiting %ss before retry", wait)
                    _time.sleep(wait)
                else:
                    logging.debug("Search failed [%s]: %s", label, _e)
                    return ""
    logging.error("[gemini] All retries exhausted — skipping this synthesis")
    return ""


def _think(client, prompt: str, label: str = "") -> str:
    """Gemini synthesis — no search, free-form text."""
    if not client:
        return ""
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    resp = None
    with _gemini_slot():
        for _attempt in range(4):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                break
            except Exception as _e:
                if ("429" in str(_e)
                        or "quota" in str(_e).lower()
                        or "RESOURCE_EXHAUSTED" in str(_e)):
                    wait = 25 * (2 ** _attempt)
                    logging.warning("[gemini] 429 rate limit — waiting %ss before retry", wait)
                    _time.sleep(wait)
                else:
                    logging.debug("Think failed [%s]: %s", label, _e)
                    return ""
    if resp is None:
        logging.error("[gemini] All retries exhausted — skipping this synthesis")
        return ""
    text = (resp.text or "").strip()
    if label:
        logging.info("    [%s] %d chars", label, len(text))
    return text


def _think_json(client, prompt: str, label: str = "") -> str:
    """
    Gemini call with response_mime_type=application/json so the API enforces JSON.
    Falls back to plain _think on transport/schema errors, then optional second model.
    """
    if not client:
        return ""
    primary = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    fallback = os.environ.get("GEMINI_MODEL_FALLBACK", "gemini-2.0-flash")
    models_to_try = [primary] + ([fallback] if fallback != primary else [])

    last_err = None
    with _gemini_slot():
        for model in models_to_try:
            resp = None
            for _attempt in range(4):
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=_gtypes.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.35,
                        ),
                    )
                    break
                except Exception as _e:
                    last_err = _e
                    if ("429" in str(_e)
                            or "quota" in str(_e).lower()
                            or "RESOURCE_EXHAUSTED" in str(_e)):
                        wait = 25 * (2 ** _attempt)
                        logging.warning("[gemini-json] 429 — waiting %ss (%s)", wait, label)
                        _time.sleep(wait)
                    else:
                        logging.debug("JSON mode failed [%s] model=%s: %s", label, model, _e)
                        break
            if resp is not None:
                text = (resp.text or "").strip()
                if label:
                    logging.info("    [%s] json %d chars (model=%s)", label, len(text), model)
                if text:
                    return text
            # try next model
            if model != models_to_try[-1]:
                logging.warning("    [%s] empty/invalid JSON pass on %s — trying %s",
                              label, model,
                              fallback if model == primary else "plain prompt")

    logging.warning("    [%s] JSON mode unusable (%s) — last error: %s",
                    label, primary, last_err)
    return ""


def _extract_balanced_json_object(text: str) -> str | None:
    """First complete `{...}` object in text — fixes Gemini trailing commentary."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t).strip()
    start = t.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(t)):
        c = t[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return t[start : i + 1]
    return None


def _clip_text(s: str, max_len: int) -> str:
    s = (s or "").strip()
    if not s or max_len <= 0:
        return s
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _sanitize_json_text(text: str) -> str:
    """Light repairs before json.loads (trailing commas, fenced blocks, NaN)."""
    t = (text or "").strip()
    if not t:
        return t
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_+-]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t).strip()
    t = re.sub(r",\s*([}\]])", r"\1", t)
    t = re.sub(r"\bNaN\b", "null", t, flags=re.IGNORECASE)
    t = re.sub(r"\bInfinity\b", "null", t, flags=re.IGNORECASE)
    t = re.sub(r"-Infinity\b", "null", t, flags=re.IGNORECASE)
    return t


def _parse_json(text: str) -> dict | list | None:
    if not text:
        return None
    t = _sanitize_json_text(text)
    try:
        return json.loads(t)
    except Exception:
        pass
    balanced = _extract_balanced_json_object(t)
    if balanced:
        try:
            return json.loads(_sanitize_json_text(balanced))
        except Exception:
            pass
    m = re.search(r"(\{[\s\S]+\}|\[[\s\S]+\])", t)
    if m:
        try:
            return json.loads(_sanitize_json_text(m.group(0)))
        except Exception:
            pass
    return None


def _coerce_to_synthesis_dict(data: Any) -> dict | None:
    """Pydantic-validate and normalize to the canonical synthesis dict (incl. 100x_potential key)."""
    if not isinstance(data, dict):
        return None
    try:
        m = AtlasSynthesisReport.model_validate(data)
        return m.model_dump(by_alias=True)
    except ValidationError:
        return None


def _repair_synthesis_with_llm(client: Any, broken_text: str, label: str) -> dict | None:
    """Ask the model to emit only valid JSON fixing a broken payload."""
    if not client or not broken_text.strip():
        return None
    snippet = broken_text.strip()
    if len(snippet) > 16000:
        snippet = snippet[:16000] + "\n…[truncated]"
    fix_prompt = f"""You are a JSON repair tool. The text below was meant to be ONE JSON object for a stock research report.

Output exactly ONE valid UTF-8 JSON object. No markdown fences, no comments, no text before or after.

Required top-level keys (use null / [] / {{}} when unknown):
ticker, company_name, sector, overall_rating, confidence, price_now, executive_summary,
bull_thesis, bear_thesis, trade_plan, options_play, catalysts_timeline, key_risks,
price_levels, earnings_analysis, analyst_consensus, 100x_potential, last_researched

Preserve factual content from the broken input where possible.

BROKEN_INPUT:
{snippet}
"""
    raw = _think_json(client, fix_prompt, label + "_json_repair")
    parsed = _parse_json(raw or "")
    return _coerce_to_synthesis_dict(parsed) if isinstance(parsed, dict) else None


def _think_synthesis_structured(client: Any, prompt: str, label: str) -> dict | None:
    """Single synthesis call constrained by JSON schema (Gemini structured output)."""
    if not client or not _GENAI_OK:
        return None
    primary = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    fallback = os.environ.get("GEMINI_MODEL_FALLBACK", "gemini-2.0-flash")
    models_to_try = [primary] + ([fallback] if fallback != primary else [])
    schema = _synthesis_json_schema()
    out_tokens = int(os.environ.get("GEMINI_SYNTHESIS_MAX_TOKENS", "8192"))

    for model in models_to_try:
        with _gemini_slot():
            for _attempt in range(4):
                try:
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=_gtypes.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_json_schema=schema,
                            temperature=0.25,
                            max_output_tokens=out_tokens,
                        ),
                    )
                    text = (resp.text or "").strip()
                    if not text:
                        break
                    parsed = _parse_json(text)
                    coerced = _coerce_to_synthesis_dict(parsed)
                    if coerced and str(coerced.get("executive_summary") or "").strip():
                        logging.info("    [%s] structured synthesis OK (model=%s)", label, model)
                        return coerced
                except Exception as _e:
                    if ("429" in str(_e)
                            or "quota" in str(_e).lower()
                            or "RESOURCE_EXHAUSTED" in str(_e)):
                        wait = 25 * (2 ** _attempt)
                        logging.warning("[gemini-structured] 429 — waiting %ss (%s)", wait, label)
                        _time.sleep(wait)
                    else:
                        logging.debug("Structured synthesis failed [%s] model=%s: %s", label, model, _e)
                        break
    return None


def _synthesis_retry_prompt(
    ticker: str,
    today: str,
    mktdata: dict,
    price: float,
    budget: float,
    scraped_tail: str,
) -> str:
    """Smaller follow-up when the primary JSON parse fails (quota / formatting)."""
    return f"""You are ATLAS. Today is {today}.
Respond with ONE raw JSON object only. No markdown fences, no text before or after.

Stock: {ticker}
Live price: ${price}
User budget: ${budget}
Analyst target (yfinance): {mktdata.get("analyst_target")} | Rating: {mktdata.get("analyst_rating")}
Next earnings: {mktdata.get("next_earnings")}

SCRAPED DATA EXCERPT (use facts from here; do not invent):
{scraped_tail[:5000]}

Required JSON shape (all keys present; use null where unknown):
{{
  "ticker": "{ticker}",
  "company_name": "<from data>",
  "sector": "<from data>",
  "overall_rating": "strong_buy | buy | hold | sell | strong_sell",
  "confidence": <1-10>,
  "price_now": <number>,
  "executive_summary": "<4 sentences>",
  "bull_thesis": "<2-3 sentences, newline between points>",
  "bear_thesis": "<2-3 sentences>",
  "trade_plan": {{
    "action": "buy_stock | buy_calls | buy_puts | sell | avoid",
    "entry_price": null,
    "stop_loss": null,
    "target_1": null,
    "target_2": null,
    "target_pct_gain": null,
    "hold_period": "<string>",
    "position_size_suggestion": "<string>"
  }},
  "options_play": {{
    "recommended": false,
    "why_options": "<string>",
    "best_contract": {{
      "expiry": "",
      "strike": null,
      "type": "call",
      "ask_estimate": null,
      "cost_1_contract": null
    }},
    "alternative_contract": {{}}
  }},
  "catalysts_timeline": [],
  "key_risks": [],
  "price_levels": {{
    "immediate_support": null,
    "strong_support": null,
    "immediate_resistance": null,
    "strong_resistance": null,
    "analyst_target": null
  }},
  "earnings_analysis": {{
    "next_date": "",
    "expected_move": "",
    "beat_probability": "",
    "play_earnings": false,
    "earnings_strategy": ""
  }},
  "analyst_consensus": {{}},
  "100x_potential": {{"score": 0, "why": "", "realistic_upside": ""}},
  "last_researched": ""
}}"""


def _minimal_synthesis_prompt(
    ticker: str,
    today: str,
    mktdata: dict,
    price: float,
    budget: float,
    excerpt: str,
) -> str:
    """Ultra-compact prompt when primary + retry JSON both fail (quota/format)."""
    ex = _clip_text(excerpt, 4500)
    return f"""Today is {today}. You are ATLAS equity research.

Output ONE JSON object only (no markdown).

Ticker: {ticker}
Price: {price}
User budget: ${budget}
Analyst target (yfinance): {mktdata.get("analyst_target")} | rating: {mktdata.get("analyst_rating")}
Next earnings: {mktdata.get("next_earnings")}

SCRAPED FACTS (use only what appears here; otherwise null):
{ex}

Build a full report with these exact top-level keys:
ticker, company_name, sector, overall_rating (one of: strong_buy, buy, hold, sell, strong_sell),
confidence (integer 1-10), price_now (number), executive_summary (string, 4–6 sentences: what the company does,
key partnerships/customers/supply chain if mentioned, and near-term setup),
bull_thesis (string), bear_thesis (string),
trade_plan (object: action, entry_price, stop_loss, target_1, target_2, target_pct_gain, hold_period, position_size_suggestion),
options_play (object: recommended bool, why_options string, best_contract object, alternative_contract object),
catalysts_timeline (array of objects: date, event, impact [high|medium|low], direction [bullish|bearish|neutral]) —
populate from partnerships, product launches, earnings, regulatory, and customer news in the excerpt,
not from generic market commentary,
key_risks (array: risk, severity, mitigation),
price_levels (object with numeric fields where known),
earnings_analysis (object: next_date, expected_move, beat_probability, play_earnings bool, earnings_strategy),
analyst_consensus (object: rating, avg_target, count),
100x_potential (object: score 1-10, why, realistic_upside),
last_researched (string, ISO-8601 UTC).

Use null for unknown numbers. Use [] only if truly no catalysts or risks can be named from the excerpt."""


def _ensure_ticker_on_synthesis(syn: dict, ticker: str) -> dict:
    if not syn.get("ticker"):
        syn = {**syn, "ticker": ticker.upper().strip()}
    return syn


def _run_full_synthesis(
    client: Any,
    synthesis_prompt: str,
    ticker: str,
    today: str,
    mktdata: dict,
    budget: float,
    scraped_context: str,
    scrape_text: str,
    price: float,
) -> tuple[dict, str]:
    """
    Structured JSON synthesis with fallbacks and LLM-assisted repair.
    Returns (synthesis dict, quality: ok | repaired | fallback).
    """
    ticker_u = ticker.upper().strip()

    def _usable(s: dict | None) -> bool:
        return bool(s and str(s.get("executive_summary") or "").strip())

    synthesis = _think_synthesis_structured(client, synthesis_prompt, "synthesis")
    if _usable(synthesis):
        return _ensure_ticker_on_synthesis(synthesis, ticker_u), "ok"

    # Unstructured JSON mode (older path) + Pydantic coerce
    synth_raw = _think_json(client, synthesis_prompt, "synthesis_plainjson")
    last_raw = synth_raw or ""
    if not synth_raw:
        synth_raw = _think(
            client,
            synthesis_prompt + "\n\nCRITICAL: Respond with ONLY a raw JSON object. No markdown fences.",
            "synthesis_plain",
        )
        last_raw = synth_raw or last_raw
    parsed = _parse_json(synth_raw or "")
    synthesis = _coerce_to_synthesis_dict(parsed) if isinstance(parsed, dict) else None
    if not _usable(synthesis):
        repaired = _repair_synthesis_with_llm(client, last_raw or (synth_raw or ""), "synthesis")
        if _usable(repaired):
            return _ensure_ticker_on_synthesis(repaired, ticker_u), "repaired"
    elif _usable(synthesis):
        return _ensure_ticker_on_synthesis(synthesis, ticker_u), "repaired"

    logging.warning(
        "  [synthesis] Primary pass weak (raw=%d chars). Retry compact structured prompt...",
        len(synth_raw or ""),
    )
    retry_prompt = _synthesis_retry_prompt(
        ticker_u, today, mktdata, float(price or 0), budget, scraped_context
    )
    synthesis = _think_synthesis_structured(client, retry_prompt, "synthesis_retry")
    if _usable(synthesis):
        return _ensure_ticker_on_synthesis(synthesis, ticker_u), "ok"

    synth_raw2 = _think_json(client, retry_prompt, "synthesis_retry_plainjson")
    last_raw = synth_raw2 or last_raw
    if not synth_raw2:
        synth_raw2 = _think(
            client,
            retry_prompt + "\n\nCRITICAL: ONLY raw JSON. No markdown.",
            "synthesis_retry_plain",
        )
        last_raw = synth_raw2 or last_raw
    parsed2 = _parse_json(synth_raw2 or "")
    synthesis = _coerce_to_synthesis_dict(parsed2) if isinstance(parsed2, dict) else None
    if _usable(synthesis):
        return _ensure_ticker_on_synthesis(synthesis, ticker_u), "repaired"
    if synth_raw2:
        repaired2 = _repair_synthesis_with_llm(client, synth_raw2, "synthesis_retry")
        if _usable(repaired2):
            return _ensure_ticker_on_synthesis(repaired2, ticker_u), "repaired"

    logging.warning(
        "  [synthesis] Retry failed — minimal prompt (raw2=%d chars).",
        len(synth_raw2 or ""),
    )
    mini = _minimal_synthesis_prompt(
        ticker_u, today, mktdata, float(price or 0), budget, scraped_context
    )
    synthesis = _think_synthesis_structured(client, mini, "synthesis_minimal")
    if _usable(synthesis):
        return _ensure_ticker_on_synthesis(synthesis, ticker_u), "ok"

    synth_raw3 = _think_json(client, mini, "synthesis_minimal_plainjson")
    last_raw = synth_raw3 or last_raw
    if not synth_raw3:
        synth_raw3 = _think(
            client,
            mini + "\n\nONLY raw JSON.",
            "synthesis_minimal_plain",
        )
        last_raw = synth_raw3 or last_raw
    parsed3 = _parse_json(synth_raw3 or "")
    synthesis = _coerce_to_synthesis_dict(parsed3) if isinstance(parsed3, dict) else None
    if _usable(synthesis):
        return _ensure_ticker_on_synthesis(synthesis, ticker_u), "repaired"
    if synth_raw3:
        repaired3 = _repair_synthesis_with_llm(client, synth_raw3, "synthesis_minimal")
        if _usable(repaired3):
            return _ensure_ticker_on_synthesis(repaired3, ticker_u), "repaired"

    logging.error(
        "  [synthesis] Gemini returned no usable JSON after repair passes. Using minimal shell."
    )
    if last_raw:
        final_try = _repair_synthesis_with_llm(client, last_raw, "synthesis_last_chance")
        if _usable(final_try):
            return _ensure_ticker_on_synthesis(final_try, ticker_u), "repaired"

    fb = _fallback_synthesis_shell(ticker_u, mktdata, scrape_text, float(price or 0))
    return fb, "fallback"


def _fallback_synthesis_shell(
    ticker: str,
    mktdata: dict,
    scrape_text: str,
    price: float,
) -> dict:
    """Last-resort minimal structured report (no raw scrape dump in executive summary)."""
    return {
        "ticker":            ticker,
        "company_name":      mktdata.get("company_name") or ticker,
        "sector":            mktdata.get("sector") or "—",
        "overall_rating":    "hold",
        "confidence":        4,
        "price_now":         price or mktdata.get("price"),
        "executive_summary": (
            "We could not format an AI narrative for this run (API quota, model output, or JSON validation). "
            "Your data was still scraped — open the **Research waves** section at the bottom of this report for raw context, "
            "then try **Search** again in a minute."
        ),
        "bull_thesis":       "—",
        "bear_thesis":       "—",
        "trade_plan":        {"action": "avoid", "hold_period": "until synthesis succeeds"},
        "options_play":      {"recommended": False, "why_options": "No validated synthesis JSON."},
        "catalysts_timeline": [],
        "key_risks":         [],
        "price_levels":      {},
        "earnings_analysis": {
            "next_date":      str(mktdata.get("next_earnings") or "TBD"),
            "expected_move":  "",
            "beat_probability": "",
            "play_earnings":  False,
            "earnings_strategy": "",
        },
        "analyst_consensus": {},
        "100x_potential":    {"score": 0, "why": "", "realistic_upside": "—"},
        "last_researched":   datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Market data helpers
# ─────────────────────────────────────────────────────────────────────────────
def _stock_data(ticker: str) -> dict:
    """Pull live market data from yfinance."""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}
        hist = tk.history(period="3mo")
        price = info.get("currentPrice") or info.get("regularMarketPrice") or \
                (hist["Close"].iloc[-1] if not hist.empty else None)

        # Options chain — nearest 2 expiries
        options_data: list[dict] = []
        try:
            exps = tk.options[:4]  # nearest 4 expiries
            for exp in exps:
                chain = tk.option_chain(exp)
                calls = chain.calls
                if calls.empty:
                    continue
                # Near-ATM calls
                if price:
                    calls = calls[
                        (calls["strike"] >= price * 0.85) &
                        (calls["strike"] <= price * 1.30)
                    ]
                for _, row in calls.head(5).iterrows():
                    options_data.append({
                        "expiry":        exp,
                        "strike":        row["strike"],
                        "ask":           row.get("ask"),
                        "bid":           row.get("bid"),
                        "iv":            row.get("impliedVolatility"),
                        "volume":        row.get("volume"),
                        "openInterest":  row.get("openInterest"),
                        "inTheMoney":    row.get("inTheMoney"),
                        "cost_1_contract": round((row.get("ask") or 0) * 100, 2),
                    })
        except Exception:
            pass

        # Earnings calendar
        next_earnings = None
        try:
            cal = tk.calendar
            if cal is not None and hasattr(cal, "to_dict"):
                cd = cal.to_dict()
                ed = cd.get("Earnings Date")
                if ed:
                    dates = sorted([str(d)[:10] for d in list(ed) if d])
                    next_earnings = dates[0] if dates else None
        except Exception:
            pass

        return {
            "ticker":          ticker.upper(),
            "price":           price,
            "market_cap":      info.get("marketCap"),
            "52w_high":        info.get("fiftyTwoWeekHigh"),
            "52w_low":         info.get("fiftyTwoWeekLow"),
            "volume":          info.get("volume"),
            "avg_volume":      info.get("averageVolume"),
            "short_pct":       info.get("shortPercentOfFloat"),
            "beta":            info.get("beta"),
            "forward_pe":      info.get("forwardPE"),
            "revenue_growth":  info.get("revenueGrowth"),
            "sector":          info.get("sector"),
            "industry":        info.get("industry"),
            "company_name":    info.get("longName") or info.get("shortName") or ticker,
            "description":     (info.get("longBusinessSummary") or "")[:500],
            "analyst_target":  info.get("targetMeanPrice"),
            "analyst_rating":  (info.get("recommendationKey") or "").replace("_", " ").title(),
            "analyst_count":   info.get("numberOfAnalystOpinions"),
            "next_earnings":   next_earnings,
            "options":         options_data[:20],
        }
    except Exception:
        logging.debug("Stock data fetch failed for %s.", ticker, exc_info=True)
        return {"ticker": ticker.upper()}


# ─────────────────────────────────────────────────────────────────────────────
# Deep Research — 3-wave consolidated pipeline
# (3 comprehensive grounded searches instead of 7 shallow ones —
#  same depth, 3x fewer API calls, stays well within rate limits)
# ─────────────────────────────────────────────────────────────────────────────
RESEARCH_STEPS = [
    ("wave1", "Business, News & Financial Deep Dive"),
    ("wave2", "Technical Analysis, Catalysts & Risks"),
    ("wave3", "Options Flow, Insider Activity & Trade Setup"),
]


def _build_wave_prompts(ticker: str, mktdata: dict, today: str) -> dict[str, str]:
    price   = mktdata.get("price") or "unknown"
    company = mktdata.get("company_name") or ticker
    sector  = mktdata.get("sector") or "unknown"
    w52_lo  = mktdata.get("52w_low", "?")
    w52_hi  = mktdata.get("52w_high", "?")
    shrt    = mktdata.get("short_pct", "?")
    next_e  = mktdata.get("next_earnings", "unknown")

    wave1 = f"""
Today is {today}. You are a professional equity analyst.
Do a DEEP, COMPREHENSIVE, FACTUAL research sweep on {ticker} ({company}), a {sector} stock.
Current price: ${price}. 52-week range: ${w52_lo}–${w52_hi}.

Search the web and provide REAL, CITED data on ALL of the following — no guessing:

=== PART A: COMPANY FUNDAMENTALS ===
1. What exactly does this company do? Core products/services, revenue model, customer base.
2. Stage of business: pre-revenue / growth / profitable?
3. Top 3 direct competitors and how {ticker} compares (market share, technology advantage).
4. Total addressable market (TAM) with source and year.
5. Key management team — CEO background, any recent leadership changes.

=== PART B: LATEST NEWS (past 7 days — include EXACT dates) ===
6. All press releases and company announcements — date, headline, significance.
7. Analyst rating changes — firm name, old rating, new rating, price target, date.
8. Any partnerships, contracts, government deals, product launches.
9. Social media / Reddit / StockTwits momentum — is retail piling in or out?
10. Any short-seller reports or positive research reports published.

=== PART C: FINANCIAL PERFORMANCE ===
11. Last 4 quarters EPS: (Q4/Q3/Q2/Q1) — actual vs estimate, beat or miss by how much.
12. Revenue last 4 quarters with YoY and QoQ growth %.
13. Gross margin and operating margin — trend improving or deteriorating?
14. Cash on hand and monthly burn rate (if pre-profitable).
15. Debt-to-equity, any upcoming debt maturities.
16. Next earnings date AND TIME confirmed (pre-market or after-market).
17. Analyst consensus EPS and revenue estimate for next quarter.
18. Has the company raised, maintained, or lowered guidance recently?

For every number you state, cite the source (SEC filing, earnings call, Bloomberg, etc.).
If you cannot find a data point, explicitly say "Not found" — do NOT fabricate.
"""

    wave2 = f"""
Today is {today}. Continue deep research on {ticker} at ${price}.
52W: ${w52_lo}–${w52_hi}. Short interest: {shrt} of float. Next earnings: {next_e}.

=== PART D: TECHNICAL ANALYSIS ===
1. Primary trend direction (uptrend / downtrend / sideways) with evidence.
2. Key SUPPORT levels: list 2-3 specific price levels with reasoning.
3. Key RESISTANCE levels: list 2-3 specific price levels with reasoning.
4. Current RSI reading — overbought / oversold / neutral?
5. MACD — bullish or bearish crossover? Divergence?
6. 50-day MA: ${mktdata.get("price","?")} vs 50MA — above or below?
7. 200-day MA: above or below? Golden cross / death cross recently?
8. Volume pattern — is volume confirming the price trend?
9. Any recognizable chart pattern (breakout, flag, wedge, cup-and-handle)?
10. Short squeeze potential given {shrt} short interest?

=== PART E: UPCOMING CATALYSTS (next 90 days) — EXACT DATES WHERE POSSIBLE ===
11. Next earnings date/time (CONFIRM from IR calendar or financial sites).
12. Any product launch, demo day, or major conference presentation.
13. FDA approval dates (if applicable).
14. Government contract or RFP decision dates.
15. Index rebalancing — could {ticker} be added to Russell/S&P small cap?
16. Share lockup expiry dates.
17. Any expected analyst day or investor day.
Rate each catalyst: HIGH / MEDIUM / LOW impact, and BULLISH / BEARISH / NEUTRAL direction.

=== PART F: RISK FACTORS ===
18. Biggest single company-specific risk right now — be specific.
19. Competitive threat — name the competitor that could eat {ticker}'s market.
20. Dilution risk — has the company issued new shares recently? How much cash runway?
21. Regulatory / legal risks — any active lawsuits, SEC inquiries, compliance issues?
22. Insider selling — have executives sold shares in the past 90 days? How much?
23. Macro sensitivity — interest rates, sector rotation, recession risk for {ticker}.
24. Options-specific: IV crush risk post-earnings, theta decay rate, pin risk.
25. Worst realistic downside scenario in next 30 days with a specific price target.

Cite sources for every claim. Say "Not found" if data is unavailable.
"""

    wave3 = f"""
Today is {today}. Final research wave for {ticker} at ${price}.
Next earnings: {next_e}.

=== PART G: OPTIONS MARKET INTELLIGENCE ===
1. Unusual options activity this week — any large block calls or puts? Specific strikes?
2. Put/call ratio today vs 30-day average — bullish or bearish skew?
3. Implied volatility (IV) rank/percentile — is IV historically high or low right now?
4. Which strikes have the highest open interest? What does smart money appear to be positioning for?
5. Any notable dark pool or institutional block trades reported?
6. What is the options market implying as the expected move for next earnings?
7. Is there a volatility event risk (earnings IV spike) that would crush options value?

=== PART H: INSIDER & INSTITUTIONAL ACTIVITY ===
8. Recent insider transactions (last 90 days) — who bought/sold, how many shares, at what price?
9. Major institutional holders — have any 13F filings shown new large positions or exits?
10. Short interest trend — is it increasing (bearish) or decreasing (covering, bullish)?

=== PART I: TRADE SETUP SUMMARY ===
11. What is the single best STOCK trade setup right now? Entry, stop, target, timeframe.
12. What is the single best OPTIONS trade? Specific strike and expiry, with reasoning tied to a catalyst.
13. What is the risk/reward ratio for this trade?
14. Is this a momentum play, earnings play, or fundamental value play?
15. On a scale of 1-10, what is the conviction level for a bullish trade, and why?

Be specific. Use real numbers. Cite sources. Do not speculate beyond what the data supports.
"""

    return {"wave1": wave1, "wave2": wave2, "wave3": wave3}


_RESEARCH_CACHE_DIR = Path(__file__).parent / "deep_reports" / "_cache"


def _load_wave_cache(ticker: str) -> dict[str, str]:
    """Load partially-completed waves from disk so a restart resumes mid-research."""
    cache_file = _RESEARCH_CACHE_DIR / f"{ticker}_waves.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            # Only use cache if it's from today (to avoid stale data)
            from datetime import date
            if data.get("date") == str(date.today()):
                logging.info("  Resuming from wave cache (%d waves completed).",
                             len([k for k in data if k.startswith("wave")]))
                return {k: v for k, v in data.items() if k.startswith("wave")}
        except Exception:
            pass
    return {}


def _save_wave_cache(ticker: str, waves: dict[str, str]) -> None:
    """Persist completed waves to disk so crashes or interruptions don't lose work."""
    _RESEARCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import date
    cache_file = _RESEARCH_CACHE_DIR / f"{ticker}_waves.json"
    try:
        cache_file.write_text(
            json.dumps({"date": str(date.today()), **waves}, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass


def research_ticker(ticker: str, budget: float = 100.0,
                    position: dict | None = None,
                    client=None,
                    output_mode: str = "trade_plan",
                    progress=None) -> dict:
    """
    Hybrid deep research: Python scraping + Gemini synthesis.

    Pipeline:
      1. yfinance       — live price, options chain, earnings date
      2. web_scraper    — Finviz, Google News, StockAnalysis, SEC EDGAR, Reddit
      3. (optional)     — 1 grounded search wave for anything scraping missed
      4. Gemini 2.5-flash — reads ALL scraped data, writes structured report

    Gemini grounding calls: 0 (scraping handles data gathering)
    Gemini synthesis calls: 1 (reads real data, pure reasoning)

    Args:
        output_mode: one of trade_plan | company_report | finance_answer | chat | document
        progress: optional JobProgress instance from progress_state.py
    """
    if client is None:
        client = _client()
    if client is None:
        logging.error("No Gemini client — GOOGLE_API_KEY required.")
        return {}

    with _RESEARCH_RUN_LOCK:
        return _research_ticker_impl(ticker, budget, position, client,
                                     output_mode=output_mode, progress=progress)


def _research_ticker_impl(ticker: str, budget: float, position: dict | None, client,
                          output_mode: str = "trade_plan", progress=None) -> dict:
    ticker = ticker.upper().strip()
    today  = datetime.now(timezone.utc).strftime("%B %d, %Y")
    logging.info("Deep research started: %s (budget=$%.0f, output_mode=%s)", ticker, budget, output_mode)

    if progress is not None:
        progress.advance("RETRIEVING_CONTEXT", 5, "Starting deep research")

    # Step 1: pull live options + earnings from yfinance
    logging.info("  [1/3] Fetching live market data (yfinance)...")
    mktdata = _stock_data(ticker)
    price   = mktdata.get("price") or 0

    if progress is not None:
        progress.advance("TOOL_CALLING", 25, "Market data fetched — scraping web sources")

    # Step 2: scrape all public sources
    scraped: dict = {}
    scrape_text = ""
    if _SCRAPER_AVAILABLE:
        logging.info("  [2/3] Web scraping: Finviz, Google News, StockAnalysis, SEC EDGAR, Reddit...")
        try:
            scraped     = web_scraper.gather_all(ticker)
            scrape_text = scraped.get("context_text", "")
            logging.info("      Scraped %d chars of raw data from %d news items",
                         scraped.get("char_count", 0), len(scraped.get("news", [])))
        except Exception:
            logging.exception("Web scraping failed — will proceed with yfinance data only")
    else:
        logging.warning("  [2/3] web_scraper.py not available — skipping scraping step")

    # If scraping got very little (e.g. Finviz blocked), fall back to 1 grounded search wave
    step_results: dict[str, str] = {}
    if len(scrape_text) < 500:
        logging.info("  [2/3] Scrape returned minimal data — running 1 grounded search as backup...")
        wave_prompts = _build_wave_prompts(ticker, mktdata, today)
        # Do all 3 waves but warn user this is the fallback path
        cache = _load_wave_cache(ticker)
        for i, (key, label) in enumerate(RESEARCH_STEPS, 1):
            if key in cache and cache[key]:
                step_results[key] = cache[key]
                continue
            step_results[key] = _search(client, wave_prompts[key], label)
            _save_wave_cache(ticker, step_results)
            if i < len(RESEARCH_STEPS):
                _time.sleep(20)
    else:
        # Map scraped data into the wave structure for the report renderer
        step_results["wave1"] = scrape_text[:3000]
        step_results["wave2"] = scrape_text[3000:6000]
        step_results["wave3"] = scrape_text[6000:9000]

    if progress is not None:
        progress.advance("TOOL_CALLING", 45, "Web scraping complete — building synthesis prompt")

    # Step 3: single Gemini synthesis call — reads real scraped data
    logging.info("  [3/3] Synthesizing with gemini-2.5-flash (reading real scraped data)...")
    options_str = ""
    if mktdata.get("options"):
        opts = mktdata["options"][:10]
        options_str = "\n".join(
            f"  {o['expiry']}  ${o['strike']}C  ask=${o.get('ask','?')}  "
            f"cost/contract=${o.get('cost_1_contract','?')}  IV={o.get('iv','?'):.1%}"
            if o.get('iv') else
            f"  {o['expiry']}  ${o['strike']}C  ask=${o.get('ask','?')}  "
            f"cost/contract=${o.get('cost_1_contract','?')}"
            for o in opts
        )

    # Give the AI the full scraped context — cap size so JSON mode stays reliable
    scraped_context = _clip_text(scrape_text, 10000) if scrape_text else (
        _clip_text("\n".join(f"{k}: {v}" for k, v in step_results.items()), 4500)
    )

    # Retrieve relevant memories before synthesis — anti-hallucination layer
    memory_context = ""
    if _MEMORY_AVAILABLE and _memory:
        memory_context = _memory.build_ai_context(ticker=ticker)
        logging.info("  Memory context: %d chars of prior knowledge injected",
                     len(memory_context))

    # Retrieve setup pattern history — gives ATLAS a real track record
    pattern_context = ""
    if _TRACKER_AVAILABLE and _tracker:
        try:
            _pre_result = {
                "ticker":  ticker,
                "budget":  budget,
                "mktdata": mktdata,
                "synthesis": {},
            }
            pattern_context = _tracker.pattern_context_for_research(_pre_result)
            if pattern_context:
                logging.info("  Pattern library: historical win rates injected")
        except Exception:
            logging.debug("Pattern context failed", exc_info=True)

    # ── CONGRESSIONAL TRADES: politicians buying this ticker? ──────────────────
    congress_context = ""
    congress_data    = {}
    if _CONGRESS_AVAILABLE and _congress:
        try:
            congress_data    = _congress.get_trades_for_ticker(ticker, days_back=180)
            congress_context = congress_data.get("context_text", "")
            conviction       = congress_data.get("conviction", "NONE")
            if conviction not in ("NONE", "LOW"):
                logging.info("  Congress: %s — conviction=%s (%d trades)",
                             ticker, conviction, len(congress_data.get("trades", [])))
        except Exception:
            logging.warning('Congress live fetch failed, trying cache')
            try:
                import json as _jj
                from pathlib import Path as _PP
                cf = _PP(__file__).parent / 'congress_cache' / 'all_trades.json'
                if cf.exists():
                    all_t = _jj.loads(cf.read_text('utf-8'))
                    hits = [t for t in all_t
                            if t.get('ticker','').upper() == ticker.upper()]
                    if hits:
                        congress_context = (
                            f'\n=== CONGRESSIONAL TRADES (cache) ===\n'
                            f'{len(hits)} trades for {ticker}:\n'
                            + '\n'.join(
                                f"  {t.get('politician','?')} "
                                f"({t.get('party','?')}) "
                                f"{t.get('transaction','?')} "
                                f"on {t.get('trade_date','?')}"
                                for t in hits[:5])
                        )
            except Exception:
                logging.debug('Congress cache fallback failed', exc_info=True)

    # ── TRADIER OPTIONS CHAIN (replaces Barchart scraping if token configured) ──
    tradier_options_context = ""
    if _TRADIER_AVAILABLE and _tradier:
        try:
            tradier_options_context = _tradier.get_options_context(ticker)
            if tradier_options_context:
                logging.info("  Tradier: real options chain injected for %s", ticker)
        except Exception:
            logging.debug("Tradier options failed", exc_info=True)

    # ── HYPER-AWARENESS: market regime, squeeze score, news velocity, earnings reactions ──
    awareness_context = ""
    awareness_data    = {}
    if _MARKET_SCANNER_AVAILABLE and _market_scanner:
        try:
            awareness_data = _market_scanner.full_awareness(
                ticker,
                scrape_data  = scraped,
                news_items   = (scraped or {}).get("news") if isinstance(scraped, dict) else None,
            )
            awareness_context = awareness_data.get("context_text", "")
            regime_mult       = awareness_data.get("confidence_multiplier", 1.0)
            if regime_mult != 1.0:
                logging.info("  Regime: %s (mult=%.2f)",
                             awareness_data.get("regime", {}).get("regime","?"), regime_mult)
            logging.info("  Squeeze score: %d/100  News velocity: %s",
                         awareness_data.get("squeeze",{}).get("score",0),
                         awareness_data.get("velocity",{}).get("velocity","?"))
        except Exception:
            logging.warning("Market scanner full_awareness failed — continuing without regime/squeeze block",
                            exc_info=True)

    # ── AUTO-TUNER: inject self-tuned weights and thresholds into synthesis context ──
    tuner_context = ""
    if _AUTO_TUNER_AVAILABLE and _auto_tuner:
        try:
            cfg = _auto_tuner.get_current_config()
            if not cfg.get("defaults_active"):
                tuner_context = (
                    "\n=== ATLAS SELF-TUNED PARAMETERS (from your own win/loss history) ===\n"
                    + "Scoring weights currently active: "
                    + ", ".join(f"{k}={v:.1f}" for k, v in cfg["weights"].items())
                    + "\n"
                    + "These weights were auto-optimized from graded outcomes. "
                    + "Weight the analysis dimensions accordingly.\n"
                )
                logging.info("  Auto-tuner: custom weights injected into synthesis")
        except Exception:
            logging.debug("Auto-tuner context failed", exc_info=True)

    # ── SEC FILING RAG: semantic retrieval from 10-K / 8-K documents ─────────
    rag_context = ""
    if _RAG_AVAILABLE and _rag:
        try:
            rag_context = _rag.get_rag_context(ticker, auto_ingest=True)
            if rag_context:
                logging.info("  RAG: SEC filing context injected for %s", ticker)
            else:
                logging.debug("  RAG: no filing context available for %s", ticker)
        except Exception:
            logging.debug("RAG context failed", exc_info=True)

    # ── DYNAMIC BACKTEST (uses draft research — no synthesis yet) ───────────
    backtest_context = ""
    if _BACKTEST_AVAILABLE and _backtest:
        try:
            _draft = {
                "ticker":    ticker,
                "budget":    budget,
                "mktdata":   mktdata,
                "synthesis": {},
                "steps":     step_results,
            }
            if scraped:
                _draft["scrape"] = scraped
            _tags: list[str] = []
            if _TRACKER_AVAILABLE and _tracker:
                try:
                    _tags = _tracker.detect_setup_tags(_draft, scraped if isinstance(scraped, dict) else None)
                except Exception:
                    pass
            backtest_context = _backtest.get_backtest_context(
                ticker     = ticker,
                setup_tags = _tags,
                research   = _draft,
                use_cache  = True,
            )
            if backtest_context:
                logging.info("  Backtest: historical pattern results injected for %s", ticker)
            else:
                logging.debug("  Backtest: no significant results for %s", ticker)
        except Exception:
            logging.debug("Backtest context failed", exc_info=True)

    # Volume profile injected BEFORE synthesis
    vp_context = ""
    if _VP_AVAILABLE and _vp:
        try:
            vp_data = _vp.calculate_volume_profile(ticker, lookback_days=30)
            if vp_data and not vp_data.get('error'):
                poc  = vp_data.get('poc', 'N/A')
                vah  = vp_data.get('vah', 'N/A')
                val  = vp_data.get('val', 'N/A')
                vwap = vp_data.get('vwap', 'N/A')
                hvn  = vp_data.get('hvn', [])[:3]
                lvn  = vp_data.get('lvn', [])[:2]
                cur  = vp_data.get('current_price', 0)
                rel  = 'ABOVE' if cur and poc and float(str(cur)) > float(str(poc)) else 'BELOW'
                vp_context = (
                    f'\n=== VOLUME PROFILE (30-day) ===\n'
                    f'POC (strongest magnet): ${poc}\n'
                    f'VAH: ${vah}\nVAL: ${val}\nVWAP: ${vwap}\n'
                    f'Current price is {rel} the POC\n'
                    f'HVN support levels: {hvn}\n'
                    f'LVN (price accelerates through): {lvn}\n'
                )
                logging.info('Volume Profile injected: POC=$%s %s POC', poc, rel)
        except Exception:
            logging.debug('VP context failed', exc_info=True)

    # Sector rotation injected BEFORE synthesis
    sector_context = ""
    if _SECTOR_AVAILABLE and _sector:
        try:
            wind = _sector.sector_wind(ticker)
            if wind:
                sector_context = f'\n=== SECTOR ROTATION ===\n{wind}\n'
                logging.info('Sector wind injected for %s', ticker)
        except Exception:
            logging.debug('Sector context failed', exc_info=True)

    # Shrink satellite context so the model reliably returns structured JSON
    memory_context = _clip_text(memory_context, 2200)
    pattern_context = _clip_text(pattern_context, 1500)
    tuner_context = _clip_text(tuner_context, 800)
    awareness_context = _clip_text(awareness_context, 2800)
    congress_context = _clip_text(congress_context, 1600)
    tradier_options_context = _clip_text(tradier_options_context, 2200)
    rag_context = _clip_text(rag_context, 5000)
    backtest_context = _clip_text(backtest_context, 2200)
    vp_context = _clip_text(vp_context, 1000)
    sector_context = _clip_text(sector_context, 800)

    synthesis_prompt = f"""
You are ATLAS, an elite institutional trading analyst. Today is {today}.

The data below was scraped from 10 financial websites using Python code.
This is REAL, LIVE data — not your training data, not guesses.
The cross-reference report shows which facts are CONFIRMED vs single-source.

IMPORTANT RULES:
- Only make claims supported by the scraped data OR the memory recall below
- For CONFIRMED facts: state them directly and confidently
- For SINGLE SOURCE facts: note "per [source]" but still use them
- For CONFLICT facts: flag the discrepancy and use the most recent source
- If data is missing entirely: use null — never fabricate numbers
- Memory facts labeled CONFIRMED are hard truth — do not contradict them
- The whisper EPS is what traders actually expect — weight it heavily
- Historical win rates from the ATLAS pattern library should calibrate your confidence
- The sector macro wind and volume profile POC/VAH/VAL are real data — use them for price level targets
- The HYPER-AWARENESS block below has live regime, squeeze score, and news velocity — factor these heavily
- Congressional trade data is a PREMIUM alpha signal — cluster buys from finance/intelligence committee members = high conviction
- If Tradier options data is present, use those real Greeks instead of approximated values
- If SEC Filing RAG context is present, cite specific risks, debt levels, and guidance from actual 10-K/8-K passages — these override any estimates
- If DYNAMIC BACKTEST RESULTS are present, cite the exact win rate and occurrence count — say "mathematically proven" if n>=20 and win_rate>=65%
- For catalysts_timeline and executive_summary, prioritize **company-specific** items visible in the scrape: partnerships, customers, integrations, competitors, supply chain, product launches, regulatory/legal, and earnings — not generic site navigation or third-party API ads

{memory_context}
{pattern_context}
{tuner_context}
{awareness_context}
{congress_context}
{tradier_options_context}
{rag_context}
{backtest_context}
{vp_context}
{sector_context}

=== REAL SCRAPED DATA FOR {ticker} ===
Current price (yfinance live): ${price}
User budget: ${budget}
Next earnings (yfinance): {mktdata.get("next_earnings","unknown")}
Analyst consensus (yfinance): ${mktdata.get("analyst_target","?")} target  |  {mktdata.get("analyst_rating","?")} rating

{scraped_context}

=== LIVE OPTIONS CHAIN (yfinance) ===
{options_str or "No options data available"}

=== YOUR TASK ===
Synthesize everything above into the most accurate, specific, actionable trade recommendation.
This report will be used for real trading decisions — be precise, honest about uncertainty.
Return ONLY valid JSON (no markdown, no prose outside the object):

{{
  "ticker": "{ticker}",
  "company_name": "<full company name>",
  "sector": "<sector>",
  "overall_rating": "strong_buy | buy | hold | sell | strong_sell",
  "confidence": <integer 1-10>,
  "price_now": {price or "null"},
  "executive_summary": "<4-5 sentences — what this company does, where it is NOW, and why NOW is or isn't a good entry>",
  "bull_thesis": "<2-3 specific bullet points why this could go up — with numbers and dates>",
  "bear_thesis": "<2-3 specific bullet points why this could go down — with numbers>",
  "trade_plan": {{
    "action": "buy_stock | buy_calls | buy_puts | sell | avoid",
    "entry_price": <number or null>,
    "stop_loss": <number or null>,
    "target_1": <number — conservative target>,
    "target_2": <number — aggressive target>,
    "target_pct_gain": <expected % gain to target_1>,
    "hold_period": "<e.g. 2-4 weeks, hold through earnings, etc.>",
    "position_size_suggestion": "<how much of $budget to deploy and why>"
  }},
  "options_play": {{
    "recommended": true | false,
    "why_options": "<why options are better than stock here, or why not>",
    "best_contract": {{
      "expiry": "<YYYY-MM-DD>",
      "strike": <number>,
      "type": "call | put",
      "ask_estimate": <number — cost per share>,
      "cost_1_contract": <number — total cost for 1 contract = ask * 100>,
      "contracts_with_budget": <how many contracts user can buy with their budget>,
      "breakeven": <number — stock price needed at expiry to break even>,
      "max_loss": <number — maximum loss = cost paid>,
      "profit_at_target_1": <estimated profit if stock hits target_1>,
      "rationale": "<specific reason this strike and expiry — e.g. captures earnings, good risk/reward, etc.>"
    }},
    "alternative_contract": {{
      "expiry": "<YYYY-MM-DD>",
      "strike": <number>,
      "type": "call | put",
      "ask_estimate": <number>,
      "cost_1_contract": <number>,
      "rationale": "<why this is a cheaper/safer alternative>"
    }}
  }},
  "catalysts_timeline": [
    {{"date": "<YYYY-MM-DD or 'Q2 2026'>", "event": "<event>", "impact": "high | medium | low", "direction": "bullish | bearish | neutral"}}
  ],
  "key_risks": [
    {{"risk": "<specific risk>", "severity": "high | medium | low", "mitigation": "<what to watch>"}}
  ],
  "price_levels": {{
    "immediate_support": <number>,
    "strong_support": <number>,
    "immediate_resistance": <number>,
    "strong_resistance": <number>,
    "analyst_target": {mktdata.get("analyst_target") or "null"}
  }},
  "earnings_analysis": {{
    "next_date": "{mktdata.get("next_earnings","unknown")}",
    "expected_move": "<e.g. ±15% based on IV>",
    "beat_probability": "<high/medium/low and why>",
    "play_earnings": true | false,
    "earnings_strategy": "<specific strategy: hold through, close before, straddle, etc.>"
  }},
  "analyst_consensus": {{
    "rating": "{mktdata.get("analyst_rating","unknown")}",
    "avg_target": {mktdata.get("analyst_target") or "null"},
    "count": {mktdata.get("analyst_count") or "null"}
  }},
  "100x_potential": {{
    "score": <integer 1-10 — how close is this to a 100x play>,
    "why": "<what would need to happen for 10-100x return>",
    "realistic_upside": "<realistic best case % gain in 6-12 months>"
  }},
  "last_researched": "{datetime.now(timezone.utc).isoformat()}"
}}
"""

    # ── output_mode constraints appended to synthesis prompt ──────────────────
    if output_mode != "trade_plan":
        synthesis_prompt += (
            "\n\nFORBIDDEN: Do not include entry_price, stop_loss, take_profit, "
            "execution_rules, trade_plan, risk_reward. This is not a trading query."
        )
    if output_mode == "company_report":
        synthesis_prompt += (
            "\n\nOUTPUT CONTRACT: Provide company overview, business model, revenue/AUM, "
            "key executives, recent news, risks, competitive position, sources. No trade plan."
        )
    if output_mode == "chat":
        synthesis_prompt += (
            "\n\nOUTPUT: Short casual conversational answer. No finance jargon unless asked."
        )

    if progress is not None:
        progress.advance("SYNTHESIZING", 55, "Running Gemini synthesis")

    synthesis, synthesis_quality = _run_full_synthesis(
        client,
        synthesis_prompt,
        ticker,
        today,
        mktdata,
        budget,
        scraped_context,
        scrape_text,
        float(price or 0),
    )

    if progress is not None:
        progress.advance("FINALIZING", 90, "Synthesis complete — building result")

    # ── quality firewall + one repair loop ───────────────────────────────────
    try:
        from quality_firewall import validate_response as _qfw_validate
        import json as _json_qfw
        _qfw = _qfw_validate(ticker, "MARKET_DEEP_DIVE", output_mode, _json_qfw.dumps(synthesis or {}))
        if not _qfw.passed:
            logging.warning("  [quality_firewall] %s — attempting repair synthesis", _qfw.reason[:80])
            _repair_prompt = synthesis_prompt + "\n\nREPAIR INSTRUCTION:\n" + _qfw.repair_instruction
            try:
                _repair_synthesis, _repair_quality = _run_full_synthesis(
                    client,
                    _repair_prompt,
                    ticker,
                    today,
                    mktdata,
                    budget,
                    scraped_context,
                    scrape_text,
                    float(price or 0),
                )
                if _repair_synthesis and str(_repair_synthesis.get("executive_summary") or "").strip():
                    synthesis = _repair_synthesis
                    synthesis_quality = "repaired_by_firewall"
                    logging.info("  [quality_firewall] repair synthesis succeeded")
                else:
                    logging.warning("  [quality_firewall] repair synthesis returned empty result")
            except Exception:
                logging.debug("  [quality_firewall] repair synthesis failed", exc_info=True)
    except Exception:
        logging.debug("quality_firewall check failed", exc_info=True)

    # ── per-query cost tracking ───────────────────────────────────────────────
    try:
        from gemini_limiter import (
            record_call as _gl_record,
            estimate_cost as _gl_estimate,
            get_model_for_tier as _gl_model,
        )
        import json as _json_cost
        _gl_model_name = _gl_model(output_mode)
        _in_tok  = len(synthesis_prompt) // 4
        _out_tok = len(_json_cost.dumps(synthesis or {})) // 4
        _gl_record(
            "deep_research",
            success=bool(synthesis),
            cost_usd=_gl_estimate(_in_tok, _out_tok, _gl_model_name),
        )
    except Exception:
        logging.debug("cost tracking failed", exc_info=True)

    # Clear the wave cache after successful completion
    try:
        cache_file = _RESEARCH_CACHE_DIR / f"{ticker}_waves.json"
        if cache_file.exists():
            cache_file.unlink()
    except Exception:
        pass

    result = {
        "ticker":             ticker,
        "budget":             budget,
        "mktdata":            mktdata,
        "steps":              step_results,
        "synthesis":          synthesis,
        "synthesis_quality":  synthesis_quality,
        "researched_at":      datetime.now(timezone.utc).isoformat(),
    }

    # Auto-learn: store key facts in persistent memory
    if _MEMORY_AVAILABLE and _memory and synthesis:
        try:
            n = _memory.learn_from_research(result)
            logging.info("  Memory: stored %d facts from research on %s", n, ticker)
            _memory.forget_expired()
        except Exception:
            logging.debug("Memory learning failed", exc_info=True)

    # Auto-record recommendation in win-rate tracker
    if _TRACKER_AVAILABLE and _tracker and synthesis:
        try:
            scrape_ref = result.get("scrape")  # pass scrape data if present
            rec_id = _tracker.record_recommendation(result, scrape_ref)
            result["tracker_rec_id"] = rec_id
            logging.info("  Tracker: recommendation #%d recorded for %s", rec_id, ticker)

            # Also inject historical pattern context into the result
            pattern_ctx = _tracker.pattern_context_for_research(result, scrape_ref)
            if pattern_ctx:
                result["pattern_context"] = pattern_ctx
        except Exception:
            logging.debug("Tracker record failed", exc_info=True)

    # Auto-setup price alerts from this recommendation
    if _ALERTS_AVAILABLE and _alerts and synthesis:
        try:
            n_alerts = _alerts.get_monitor().setup_from_research(result)
            if n_alerts:
                logging.info("  Alerts: %d price alerts set for %s", n_alerts, ticker)
        except Exception:
            logging.debug("Alert setup failed", exc_info=True)

    # Auto-calculate position size
    if _SIZER_AVAILABLE and _position_sizer and synthesis:
        try:
            sizing = _position_sizer.size_from_research(result)
            result["position_sizing"] = sizing
            logging.info("  Sizer: %s", sizing.get("summary","")[:80])
        except Exception:
            logging.debug("Position sizer failed", exc_info=True)

    # Volume profile — Level 2 approximation
    if _VP_AVAILABLE and _vp:
        try:
            vp_data = _vp.calculate_volume_profile(ticker, lookback_days=30)
            result["volume_profile"] = vp_data
            logging.info("  Volume Profile: POC=$%s  VAL=$%s  VAH=$%s",
                         vp_data.get("poc","?"), vp_data.get("val","?"), vp_data.get("vah","?"))
        except Exception:
            logging.debug("Volume profile failed", exc_info=True)

    # Sector macro wind
    if _SECTOR_AVAILABLE and _sector:
        try:
            wind = _sector.sector_wind(ticker)
            if wind:
                result["sector_wind"] = wind
                logging.info("  Sector: %s", wind[:80])
        except Exception:
            logging.debug("Sector wind failed", exc_info=True)

    # Attach hyper-awareness bundle
    if awareness_data:
        result["awareness"] = awareness_data
        sq = awareness_data.get("squeeze", {})
        if sq.get("score", 0) >= 60:
            result["squeeze_score"]  = sq["score"]
            result["squeeze_label"]  = sq.get("label","")

    # Auto-tune: every 5 new outcomes, trigger background self-tuning
    if _AUTO_TUNER_AVAILABLE and _auto_tuner:
        try:
            import tracker as _tr_check
            with _tr_check._connect() as _c:
                n = _c.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
            if n > 0 and n % 5 == 0:
                tune_res = _auto_tuner.run_full_tune(min_outcomes=5)
                if tune_res.get("changes"):
                    logging.info("  Auto-tuner: %s", tune_res["changes"][0][:80])
        except Exception:
            pass

    # Paper trading: auto-propose if conviction is high enough
    if _PAPER_TRADER_AVAILABLE and _paper_trader:
        if result.get("auto_paper_trade", False):
            try:
                trade = _paper_trader.propose_trade(result)
                if trade:
                    result["paper_trade"] = trade
                    logging.info("  Paper trade placed: %s %d shares @ $%.2f",
                                 trade["ticker"], trade["qty"], trade["entry_price"])
            except Exception:
                logging.debug("Paper trade proposal failed", exc_info=True)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Stock Discovery Engine
# ─────────────────────────────────────────────────────────────────────────────
def discover_stocks(theme: str, budget: float = 100.0,
                    max_results: int = 8,
                    client=None) -> list[dict]:
    """
    Find high-potential stocks matching a theme (e.g. 'AI penny stocks',
    'biotech FDA catalyst').  Returns list of deep-researched candidates.
    """
    if client is None:
        client = _client()
    if client is None:
        return []

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    logging.info("Stock discovery: theme='%s' budget=$%.0f max=%d", theme, budget, max_results)

    # Step 1: discover candidate tickers (generalized market scan: swing + growth)
    discovery_prompt = f"""
Today is {today}. You are an equity research analyst building a practical watchlist — not hype, not guaranteed returns.

The user scan theme / focus:
"{theme}"

If the theme is empty or very short, interpret it as:
"US-listed names for portfolio growth: a mix of (1) near-term actionable setups over the next few WEEKS,
(2) multi-month tactical ideas, and (3) at least one or two longer-term compounders with clear fundamentals —
plus liquid small caps / lower-priced stocks ONLY where volume and exchange listing are real (avoid pink sheets)."

Budget per position (for sizing context in reports): ~${budget:.0f}
Find the TOP {max_results + 3} candidates that fit BOTH near-term (2–6 weeks) and medium-term (1–3 month) opportunity,
with at least a third of the list suitable for longer holding if thesis plays out (6–18 month view where relevant).

For each candidate return:
- Ticker (real US major-exchange listing: NYSE, Nasdaq, etc.)
- Company name
- Current approximate price
- Market cap tier: micro/small/mid/large (approximate)
- Why it fits the theme AND why it could matter for portfolio growth
- Primary catalyst or thesis driver (earnings, product, margin, sector trend, restructuring, etc.)
- catalyst_date if known (else best estimate window)
- Risk level: low / medium / high / very_high
- time_horizon_primary: e.g. "2-6 weeks" | "1-3 months" | "6-18 months" (pick the best label)
- Liquidity note (avg volume / why it is tradeable)
- conviction 1-10 (higher only if evidence from recent sources supports the thesis)

RULES:
- Diversify: include some lower entry prices where liquid — e.g. at least 2 names under ~$12 if you can find real volume —
  and allow higher-priced quality growers if the setup is clearly undervalued or accelerating.
- No leveraged/inverse ETFs unless the theme explicitly asks. No binary scam/promotional penny names with no filings.
- Must have real trading volume and verifiable listing (no imaginary tickers).
- Be honest about dilution, debt, earnings risk, and retail crowded trades.
- Today is {today} — use current context from the web.

Return as JSON:
{{
  "theme": "{theme}",
  "candidates": [
    {{
      "ticker": "XXXX",
      "company": "Company Name",
      "price_approx": 3.50,
      "market_cap_tier": "small",
      "why_this_theme": "...",
      "catalyst": "...",
      "catalyst_date": "YYYY-MM-DD or Q2 2026 etc",
      "risk_level": "medium",
      "time_horizon_primary": "1-3 months",
      "liquidity_note": "...",
      "potential_upside_pct": 40,
      "conviction": 7
    }}
  ]
}}
"""

    # Discovery uses 1 grounded search — we need real current tickers, not AI guesses
    # This is the ONLY grounding call in the entire pipeline
    logging.info("  Searching web for candidates (1 grounded call)...")
    discovery_raw = _search(client, discovery_prompt, "discovery")
    discovery_data = _parse_json(discovery_raw)

    if not discovery_data or not discovery_data.get("candidates"):
        logging.warning("Discovery returned no candidates.")
        return []

    candidates = sorted(
        discovery_data["candidates"],
        key=lambda x: x.get("conviction", 5),
        reverse=True
    )[:max_results]

    logging.info("Found %d candidates: %s",
                 len(candidates),
                 [c.get("ticker","?") for c in candidates])

    # Step 2: deep research each candidate
    results = []
    for i, cand in enumerate(candidates):
        ticker = (cand.get("ticker") or "").upper().strip()
        if not ticker:
            continue
        logging.info("  Deep researching candidate %d/%d: %s", i+1, len(candidates), ticker)
        _time.sleep(3)
        try:
            research = research_ticker(ticker, budget=budget, client=client)
            research["discovery_context"] = cand
            research["theme"] = theme
            results.append(research)
        except Exception:
            logging.exception("Deep research failed for %s", ticker)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# HTML Report Renderer
# ─────────────────────────────────────────────────────────────────────────────
_RATING_STYLE = {
    "strong_buy":  ("#00c851", "#0a2a18", "STRONG BUY ▲▲"),
    "buy":         ("#4ade80", "#0a2010", "BUY ▲"),
    "hold":        ("#ffbb33", "#2a2000", "HOLD ⏸"),
    "sell":        ("#ff8800", "#2a1000", "SELL ▼"),
    "strong_sell": ("#ff4444", "#2a0a0a", "STRONG SELL ▼▼"),
}

_IMPACT_COLOR = {"high": "#ff4444", "medium": "#ffbb33", "low": "#4da6ff"}
_DIRECTION_COLOR = {"bullish": "#00c851", "bearish": "#ff4444", "neutral": "#888"}


def _fmt(v, prefix="$", suffix="", dec=2, empty="—"):
    if v is None or v == "" or v == "null":
        return empty
    try:
        return f"{prefix}{float(v):,.{dec}f}{suffix}"
    except Exception:
        return str(v)


def _pct_to_target(price, target) -> str:
    try:
        p, t = float(price), float(target)
        if p > 0:
            return f"+{(t/p - 1)*100:.0f}%"
    except Exception:
        pass
    return "—"


def _render_sizing_html(research: dict) -> str:
    """Render position sizing block for the HTML report."""
    sizing = research.get("position_sizing") or {}
    rec    = sizing.get("recommendation") or {}
    kelly  = sizing.get("kelly") or {}
    lines  = sizing.get("summary_lines") or []
    if not rec:
        return ""

    is_opts = sizing.get("is_options", False)
    action  = rec.get("action","BUY")
    qty_str = (f"{rec.get('contracts','?')} contract(s)" if is_opts
               else f"{rec.get('shares','?')} shares")
    cost    = rec.get("total_cost", 0)
    ml      = rec.get("max_loss", 0)
    ml_pct  = rec.get("max_loss_pct", 0)
    rr      = rec.get("rr_ratio_t1") or rec.get("rr_ratio_t2") or 0
    rr_color = "#4caf50" if rr >= 2.0 else ("#ff9800" if rr >= 1.0 else "#f44336")
    ev_label = sizing.get("ev_label","")

    bullets = "".join(f"<li style='margin-bottom:6px'>{l}</li>" for l in lines)
    kelly_note = (
        f"<div style='color:#666;font-size:11px;margin-top:8px'>"
        f"Kelly based on {kelly.get('based_on_n',0)} graded trades &nbsp;|&nbsp; "
        f"Win rate: {kelly.get('win_rate_used','?')} &nbsp;|&nbsp; "
        f"Half-Kelly: {kelly.get('half_kelly_pct','?')}%</div>"
        if kelly.get("based_on_n",0) > 0
        else f"<div style='color:#555;font-size:11px;margin-top:8px'>{kelly.get('note','')}</div>"
    )

    return f"""
<div style="background:#0e0e1a;border:1px solid #2a2a4a;border-radius:12px;padding:20px;margin-bottom:24px">
  <div style="font-size:14px;font-weight:700;color:#00d4ff;letter-spacing:1px;margin-bottom:14px">
    POSITION SIZING
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px">
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:11px;color:#666">Action</div>
      <div style="font-size:16px;font-weight:700;color:#00d4ff;margin-top:4px">{action}</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:11px;color:#666">Quantity</div>
      <div style="font-size:16px;font-weight:700;color:#fff;margin-top:4px">{qty_str}</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:11px;color:#666">Total Cost</div>
      <div style="font-size:16px;font-weight:700;color:#4caf50;margin-top:4px">${cost:.2f}</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center">
      <div style="font-size:11px;color:#666">Max Loss</div>
      <div style="font-size:16px;font-weight:700;color:#f44336;margin-top:4px">${ml:.2f} ({ml_pct:.1f}%)</div>
    </div>
    {f'<div style="background:#111;border-radius:8px;padding:12px;text-align:center"><div style="font-size:11px;color:#666">R/R Ratio</div><div style="font-size:16px;font-weight:700;color:{rr_color};margin-top:4px">{rr:.1f}:1</div></div>' if rr else ""}
  </div>
  <ul style="color:#ccc;font-size:13px;line-height:1.7;margin:0;padding-left:20px">
    {bullets}
  </ul>
  {f'<div style="margin-top:10px;color:#4da6ff;font-size:13px">{ev_label}</div>' if ev_label else ""}
  {kelly_note}
</div>"""


def _render_deep_report(research: dict, discovery_context: dict | None = None,
                        budget: float = 100.0, sim_html: str = "") -> str:
    syn   = research.get("synthesis") or {}
    mkt   = research.get("mktdata") or {}
    steps = research.get("steps") or {}
    qual  = (research.get("synthesis_quality") or "ok").lower()
    ticker     = syn.get("ticker") or research.get("ticker", "?")
    company    = syn.get("company_name") or mkt.get("company_name") or ticker
    sector     = syn.get("sector") or mkt.get("sector") or "—"
    rating_key = (syn.get("overall_rating") or "hold").lower()
    confidence = syn.get("confidence") or 5
    price      = syn.get("price_now") or mkt.get("price")
    r_color, r_bg, r_label = _RATING_STYLE.get(rating_key, ("#888", "#1a1a1a", "HOLD"))
    ts = (research.get("researched_at") or "")[:19].replace("T", " ")
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    # ── Trade plan ──────────────────────────────────────────────
    tp  = syn.get("trade_plan") or {}
    op  = syn.get("options_play") or {}
    bc  = op.get("best_contract") or {}
    alt = op.get("alternative_contract") or {}

    # ── Catalysts timeline ───────────────────────────────────────
    cat_rows = ""
    for c in (syn.get("catalysts_timeline") or []):
        dc = _DIRECTION_COLOR.get((c.get("direction") or "neutral").lower(), "#888")
        ic = _IMPACT_COLOR.get((c.get("impact") or "medium").lower(), "#888")
        cat_rows += (
            f'<tr>'
            f'<td style="padding:8px;color:#aaa;white-space:nowrap">{c.get("date","")}</td>'
            f'<td style="padding:8px;color:#ddd">{c.get("event","")}</td>'
            f'<td style="padding:8px"><span style="color:{ic};font-weight:700;font-size:.8rem">'
            f'{(c.get("impact") or "").upper()}</span></td>'
            f'<td style="padding:8px;color:{dc};font-weight:600">'
            f'{(c.get("direction") or "").upper()}</td>'
            f'</tr>'
        )

    # ── Risks ────────────────────────────────────────────────────
    risk_rows = ""
    for r in (syn.get("key_risks") or []):
        sev_color = _IMPACT_COLOR.get((r.get("severity") or "medium").lower(), "#888")
        risk_rows += (
            f'<tr>'
            f'<td style="padding:8px"><span style="color:{sev_color};font-weight:700;font-size:.8rem">'
            f'{(r.get("severity") or "").upper()}</span></td>'
            f'<td style="padding:8px;color:#ddd">{r.get("risk","")}</td>'
            f'<td style="padding:8px;color:#888;font-size:.85rem">{r.get("mitigation","")}</td>'
            f'</tr>'
        )

    # ── Price levels ─────────────────────────────────────────────
    pl = syn.get("price_levels") or {}

    # ── Earnings ─────────────────────────────────────────────────
    ea = syn.get("earnings_analysis") or {}
    ea_date = ea.get("next_date") or mkt.get("next_earnings") or "TBD"

    # ── 100x potential ───────────────────────────────────────────
    x100 = syn.get("100x_potential") or {}
    x100_score = x100.get("score") or 0
    x100_bar = f'<div style="background:#1e1e1e;border-radius:4px;height:10px;width:100%">' \
               f'<div style="background:linear-gradient(90deg,#ffbb33,#ff4444);' \
               f'width:{min(100, int(x100_score)*10)}%;height:10px;border-radius:4px"></div></div>'

    # ── Bull / Bear thesis ──────────────────────────────────────
    def _thesis_html(raw) -> str:
        if isinstance(raw, list):
            items = [str(x).strip() for x in raw if str(x).strip()]
        else:
            items = [pt.strip() for pt in str(raw or "").split("\n")
                     if pt.strip() and not pt.strip().startswith("{")]
        if items:
            return "".join(f"<li>{pt}</li>" for pt in items)
        if raw and str(raw).strip() and str(raw).strip() not in ("-", "\u2014"):
            return f"<li>{raw}</li>"
        return "<li style=\"color:#666\">No thesis text — synthesis was empty or invalid JSON. Re-run deep research.</li>"

    bull = syn.get("bull_thesis") or ""
    bear = syn.get("bear_thesis") or ""
    bull_html = _thesis_html(bull)
    bear_html = _thesis_html(bear)

    # ── Research wave accordions ──────────────────────────────────
    step_accordions = ""
    wave_icons = {
        "wave1": "📊",
        "wave2": "📈",
        "wave3": "🎯",
    }
    for key, label in RESEARCH_STEPS:
        content = steps.get(key) or "No data collected for this wave."
        icon    = wave_icons.get(key, "•")
        html_content = content.replace("\n\n", "</p><p>").replace("\n", "<br>")
        step_accordions += f"""
        <details class="step-drop">
          <summary class="step-title">{icon} {label}</summary>
          <div class="step-body"><p>{html_content}</p></div>
        </details>"""

    # ── Discovery context banner ──────────────────────────────
    disco_banner = ""
    if discovery_context:
        disco_banner = f"""
        <div style="background:#0a0a2a;border:1px solid #1a1a4a;border-radius:10px;
                    padding:14px 18px;margin-bottom:20px;font-size:.88rem;color:#aaa">
          <span style="color:#4da6ff;font-weight:700">🔍 Discovered via:</span>
          "{discovery_context.get('theme','')}"
          &nbsp;·&nbsp; Catalyst: <b style="color:#fff">{discovery_context.get('catalyst','')}</b>
          &nbsp;·&nbsp; Expected upside: <b style="color:#00c851">{discovery_context.get('potential_upside_pct','?')}%</b>
          &nbsp;·&nbsp; Conviction: <b>{discovery_context.get('conviction','?')}/10</b>
        </div>"""

    ac = syn.get("analyst_consensus") or {}

    meta_line = json.dumps(
        {"synthesis_quality": qual, "ticker": str(ticker)},
        ensure_ascii=True,
        separators=(",", ":"),
    )
    quality_banner = ""
    if qual == "fallback":
        quality_banner = """
  <div style="background:#2a1a0a;border:1px solid #663c00;border-radius:10px;padding:14px 18px;margin-bottom:20px;color:#e6c28b;font-size:.88rem;line-height:1.55">
    <strong style="color:#ffb74d">Structured report unavailable.</strong>
    Scraped research waves are still below — use them for facts, or run <strong>Search</strong> again after a short wait (quota / model timeouts can cause this).
  </div>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<!-- ATLAS_REPORT_META:{meta_line} -->
<title>ATLAS Deep Research — {ticker}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#080808;color:#e0e0e0;font-family:'Segoe UI','Inter',system-ui,sans-serif;padding:0}}
a{{color:#4da6ff;text-decoration:none}}
a:hover{{text-decoration:underline}}

.topbar{{background:#0f0f0f;border-bottom:1px solid #1e1e1e;padding:14px 28px;
         display:flex;align-items:center;gap:12px}}
.logo{{font-size:1rem;font-weight:800;color:#888}}
.logo b{{color:#fff}}

.hero{{background:{r_bg};border-bottom:2px solid {r_color};padding:32px 28px}}
.hero-grid{{display:grid;grid-template-columns:1fr auto;gap:20px;align-items:start;max-width:1400px;margin:0 auto}}
.ticker-big{{font-size:3.5rem;font-weight:900;color:{r_color};letter-spacing:-1px}}
.company-name{{font-size:1.1rem;color:#bbb;margin-top:4px}}
.sector-tag{{display:inline-block;background:#1a1a1a;color:#888;padding:3px 12px;
             border-radius:20px;font-size:.75rem;margin-top:8px}}
.rating-badge{{background:{r_color};color:#000;font-size:1.1rem;font-weight:800;
               padding:10px 22px;border-radius:10px;white-space:nowrap}}
.confidence-row{{display:flex;align-items:center;gap:8px;margin-top:8px}}
.conf-label{{color:#666;font-size:.75rem}}
.conf-bar{{flex:1;background:#1a1a1a;border-radius:4px;height:6px}}
.conf-fill{{background:{r_color};height:6px;border-radius:4px;width:{min(100,int(confidence)*10)}%}}
.price-row{{font-size:1.8rem;font-weight:700;color:#fff;margin-top:10px}}

.content{{max-width:1400px;margin:0 auto;padding:28px}}

.summary-box{{background:#111;border-left:4px solid {r_color};border-radius:8px;
              padding:20px;margin-bottom:24px;font-size:.96rem;line-height:1.8;color:#ccc}}

.grid-3{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-bottom:24px}}
.stat{{background:#111;border:1px solid #1e1e1e;border-radius:10px;padding:16px}}
.stat-label{{color:#555;font-size:.7rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}}
.stat-val{{font-size:1.5rem;font-weight:700;color:#fff}}
.stat-sub{{color:#888;font-size:.82rem;margin-top:4px}}

.trade-box{{background:#0a1a0a;border:2px solid #00c851;border-radius:14px;
            padding:22px;margin-bottom:24px}}
.trade-title{{color:#00c851;font-size:.75rem;text-transform:uppercase;letter-spacing:1px;
              font-weight:700;margin-bottom:16px}}
.trade-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}}
.tval{{font-size:1.3rem;font-weight:700;color:#fff}}
.tlabel{{color:#555;font-size:.7rem;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}}

.options-box{{background:#0a0a1a;border:2px solid #4da6ff;border-radius:14px;
              padding:22px;margin-bottom:24px}}
.options-title{{color:#4da6ff;font-size:.75rem;text-transform:uppercase;letter-spacing:1px;
                font-weight:700;margin-bottom:16px}}
.contract-card{{background:#111;border:1px solid #2a2a3a;border-radius:10px;padding:16px;
                margin-bottom:12px}}
.contract-badge{{display:inline-block;background:#4da6ff;color:#000;padding:2px 10px;
                 border-radius:20px;font-size:.75rem;font-weight:700;margin-bottom:10px}}
.alt-badge{{background:#555;color:#fff}}

.thesis-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:24px}}
.bull-box{{background:#0a1a0a;border:1px solid #1a3a1a;border-radius:10px;padding:18px}}
.bear-box{{background:#1a0a0a;border:1px solid #3a1a1a;border-radius:10px;padding:18px}}
.thesis-title{{font-size:.75rem;text-transform:uppercase;letter-spacing:1px;
               font-weight:700;margin-bottom:12px}}
.bull-box .thesis-title{{color:#00c851}}
.bear-box .thesis-title{{color:#ff4444}}
ul.thesis-list{{padding-left:18px;color:#ccc;line-height:1.9;font-size:.9rem}}

.section-title{{font-size:.75rem;text-transform:uppercase;letter-spacing:1.5px;
                color:#555;font-weight:700;margin-bottom:12px;padding-bottom:6px;
                border-bottom:1px solid #1e1e1e}}

table{{width:100%;border-collapse:collapse}}
tr:hover td{{background:rgba(255,255,255,.02)}}
th{{padding:8px;color:#555;font-size:.72rem;text-transform:uppercase;
    letter-spacing:.5px;text-align:left;border-bottom:1px solid #2a2a2a}}

.step-drop{{background:#111;border:1px solid #1e1e1e;border-radius:10px;
            margin-bottom:10px;overflow:hidden}}
.step-title{{padding:14px 18px;cursor:pointer;font-size:.88rem;font-weight:600;
             color:#bbb;list-style:none;display:flex;align-items:center;gap:8px;
             user-select:none}}
.step-title::-webkit-details-marker{{display:none}}
.step-title::after{{content:"▸";margin-left:auto;color:#444;transition:transform .2s}}
details[open] .step-title::after{{transform:rotate(90deg)}}
.step-body{{padding:16px 18px;border-top:1px solid #1e1e1e;color:#aaa;
            font-size:.87rem;line-height:1.7}}
.step-body p{{margin-bottom:10px}}

.x100-box{{background:#1a0f00;border:1px solid #3a2000;border-radius:10px;
           padding:18px;margin-bottom:24px}}
.x100-score{{font-size:2.5rem;font-weight:900;color:#ffbb33}}

.ts{{color:#333;font-size:.72rem;margin-top:30px;text-align:right}}
</style>
</head>
<body>

<div class="topbar">
  <div class="logo">⚡ <b>ATLAS</b> Deep Research</div>
  <span style="color:#444">|</span>
  <span style="color:#666;font-size:.82rem">3 research waves (scrape + synthesis) · {today}</span>
  <a href="../LIVE_REPORTS.html" style="margin-left:auto;font-size:.82rem">← Back to LIVE Reports</a>
</div>

<div class="hero">
  <div class="hero-grid">
    <div>
      <div class="ticker-big">{ticker}</div>
      <div class="company-name">{company}</div>
      <div class="sector-tag">{sector}</div>
      <div class="price-row">{_fmt(price)} <span style="font-size:.9rem;color:#555">current price</span></div>
      <div class="confidence-row">
        <span class="conf-label">Confidence: {confidence}/10</span>
        <div class="conf-bar"><div class="conf-fill"></div></div>
      </div>
    </div>
    <div style="text-align:right">
      <div class="rating-badge">{r_label}</div>
      <div style="color:#555;font-size:.72rem;margin-top:8px">Researched: {ts} UTC</div>
    </div>
  </div>
</div>

<div class="content">

  {disco_banner}
  {quality_banner}

  <!-- ── Executive Summary ── -->
  <div class="summary-box">{syn.get("executive_summary","No summary available.")}</div>

  <!-- ── Key stats ── -->
  <div class="grid-3">
    <div class="stat">
      <div class="stat-label">Current Price</div>
      <div class="stat-val">{_fmt(price)}</div>
      <div class="stat-sub">52W: {_fmt(mkt.get("52w_low"))} – {_fmt(mkt.get("52w_high"))}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Analyst Target</div>
      <div class="stat-val" style="color:#00c851">{_fmt(ac.get("avg_target") or mkt.get("analyst_target"))}</div>
      <div class="stat-sub">{ac.get("rating") or mkt.get("analyst_rating","—")} · {ac.get("count") or mkt.get("analyst_count","?")} analysts</div>
    </div>
    <div class="stat">
      <div class="stat-label">Next Earnings</div>
      <div class="stat-val" style="font-size:1.1rem;color:#ffbb33">{ea_date}</div>
      <div class="stat-sub">{ea.get("expected_move","")}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Short Interest</div>
      <div class="stat-val" style="color:#ff8800">{_fmt(mkt.get("short_pct"),"","%",1)}</div>
      <div class="stat-sub">of float</div>
    </div>
    <div class="stat">
      <div class="stat-label">Market Cap</div>
      <div class="stat-val" style="font-size:1.1rem">{_fmt(mkt.get("market_cap"),"$","",0)}</div>
      <div class="stat-sub">{mkt.get("industry","")}</div>
    </div>
    <div class="stat">
      <div class="stat-label">Price to Target</div>
      <div class="stat-val" style="color:#4da6ff">
        {_pct_to_target(price, ac.get("avg_target") or mkt.get("analyst_target"))}
      </div>
      <div class="stat-sub">to analyst consensus</div>
    </div>
  </div>

  <!-- ── Bull / Bear ── -->
  <div class="thesis-grid">
    <div class="bull-box">
      <div class="thesis-title">🟢 Bull Thesis</div>
      <ul class="thesis-list">{bull_html}</ul>
    </div>
    <div class="bear-box">
      <div class="thesis-title">🔴 Bear Thesis</div>
      <ul class="thesis-list">{bear_html}</ul>
    </div>
  </div>

  <!-- ── Trade Plan ── -->
  <div class="trade-box">
    <div class="trade-title">💰 Trade Plan — Action: {(tp.get("action") or "—").replace("_"," ").upper()}</div>
    <div class="trade-grid">
      <div><div class="tlabel">Entry Price</div><div class="tval">{_fmt(tp.get("entry_price"))}</div></div>
      <div><div class="tlabel">Stop Loss</div><div class="tval" style="color:#ff4444">{_fmt(tp.get("stop_loss"))}</div></div>
      <div><div class="tlabel">Target 1 (conservative)</div><div class="tval" style="color:#00c851">{_fmt(tp.get("target_1"))}</div></div>
      <div><div class="tlabel">Target 2 (aggressive)</div><div class="tval" style="color:#4ade80">{_fmt(tp.get("target_2"))}</div></div>
      <div><div class="tlabel">Expected Gain</div><div class="tval" style="color:#00c851">{_fmt(tp.get("target_pct_gain"),"","%" ,1)}</div></div>
      <div><div class="tlabel">Hold Period</div><div class="tval" style="font-size:.95rem">{tp.get("hold_period","—")}</div></div>
    </div>
    <div style="margin-top:14px;background:#0f1a0f;border-radius:8px;padding:12px;
                color:#9a9;font-size:.88rem;line-height:1.6">
      💡 Position sizing: {tp.get("position_size_suggestion","—")}
    </div>
  </div>

  <!-- ── Options Play ── -->
  <div class="options-box">
    <div class="options-title">🎯 Options Play — {"✅ RECOMMENDED" if op.get("recommended") else "⚠️ NOT RECOMMENDED FOR OPTIONS"}</div>
    <div style="color:#aaa;font-size:.88rem;margin-bottom:16px;line-height:1.6">
      {op.get("why_options","—")}
    </div>

    <div class="contract-card">
      <span class="contract-badge">🥇 BEST CONTRACT</span>
      <div class="trade-grid" style="gap:10px">
        <div><div class="tlabel">Expiry</div><div class="tval" style="font-size:1rem;color:#ffbb33">{bc.get("expiry","—")}</div></div>
        <div><div class="tlabel">Strike</div><div class="tval">{_fmt(bc.get("strike"))}</div></div>
        <div><div class="tlabel">Type</div><div class="tval" style="color:#00c851">{(bc.get("type") or "call").upper()}</div></div>
        <div><div class="tlabel">Ask (per share)</div><div class="tval">{_fmt(bc.get("ask_estimate"))}</div></div>
        <div><div class="tlabel">Cost (1 contract)</div><div class="tval" style="color:#4da6ff">{_fmt(bc.get("cost_1_contract"))}</div></div>
        <div><div class="tlabel">With ${budget:.0f} budget</div><div class="tval">{bc.get("contracts_with_budget","?") or "?"} contracts</div></div>
        <div><div class="tlabel">Breakeven</div><div class="tval">{_fmt(bc.get("breakeven"))}</div></div>
        <div><div class="tlabel">Max Loss</div><div class="tval" style="color:#ff4444">{_fmt(bc.get("max_loss"))}</div></div>
        <div><div class="tlabel">Profit at Target 1</div><div class="tval" style="color:#00c851">{_fmt(bc.get("profit_at_target_1"))}</div></div>
      </div>
      <div style="margin-top:12px;color:#888;font-size:.85rem;line-height:1.5">
        📝 {bc.get("rationale","—")}
      </div>
    </div>

    {"<div class='contract-card'><span class='contract-badge alt-badge'>🥈 ALTERNATIVE (cheaper)</span><div class='trade-grid' style='gap:10px'><div><div class='tlabel'>Expiry</div><div class='tval' style='font-size:1rem'>" + str(alt.get("expiry","—")) + "</div></div><div><div class='tlabel'>Strike</div><div class='tval'>" + _fmt(alt.get("strike")) + "</div></div><div><div class='tlabel'>Cost (1 contract)</div><div class='tval'>" + _fmt(alt.get("cost_1_contract")) + "</div></div></div><div style='margin-top:12px;color:#888;font-size:.85rem'>" + str(alt.get("rationale","—")) + "</div></div>" if alt.get("expiry") else ""}
  </div>

  <!-- ── Position Sizing ── -->
  {_render_sizing_html(research) if research.get("position_sizing") else ""}

  <!-- ── Volume Profile (Level 2 approx) ── -->
  {_vp.to_html(research["volume_profile"]) if research.get("volume_profile") and _VP_AVAILABLE and _vp else ""}

  <!-- ── Options P/L Simulator ── -->
  {sim_html if sim_html else ""}

  <!-- ── Earnings Analysis ── -->
  <div style="background:#0e0e1a;border:1px solid #2a2a4a;border-radius:12px;
              padding:20px;margin-bottom:24px">
    <div class="section-title">📅 Earnings Analysis</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px">
      <div><div class="tlabel">Next Earnings</div><div class="tval" style="color:#ffbb33;font-size:1.1rem">{ea_date}</div></div>
      <div><div class="tlabel">Expected Move</div><div class="tval" style="font-size:1rem">{ea.get("expected_move","—")}</div></div>
      <div><div class="tlabel">Beat Probability</div><div class="tval" style="font-size:1rem;color:#4da6ff">{ea.get("beat_probability","—")}</div></div>
      <div><div class="tlabel">Play Earnings?</div><div class="tval" style="color:{'#00c851' if ea.get('play_earnings') else '#ff4444'};font-size:1rem">{'✅ YES' if ea.get('play_earnings') else '❌ NO'}</div></div>
      <div style="grid-column:1/-1"><div class="tlabel">Earnings Strategy</div>
        <div style="color:#ccc;font-size:.9rem;line-height:1.6;margin-top:4px">{ea.get("earnings_strategy","—")}</div>
      </div>
    </div>
  </div>

  <!-- ── 100x Potential ── -->
  <div class="x100-box">
    <div class="section-title" style="color:#ffbb33">🔥 100x Potential Score</div>
    <div style="display:flex;align-items:center;gap:20px;margin-bottom:12px">
      <div class="x100-score">{x100_score}<span style="font-size:1rem;color:#555">/10</span></div>
      <div style="flex:1">{x100_bar}<div style="color:#888;font-size:.78rem;margin-top:6px">Explosive upside probability</div></div>
      <div style="text-align:right"><div style="color:#ffbb33;font-weight:700">{x100.get("realistic_upside","—")}</div><div style="color:#555;font-size:.72rem">realistic best case</div></div>
    </div>
    <div style="color:#aaa;font-size:.88rem;line-height:1.6">{x100.get("why","—")}</div>
  </div>

  <!-- ── Catalysts Timeline ── -->
  <div style="background:#111;border:1px solid #1e1e1e;border-radius:10px;padding:18px;margin-bottom:24px">
    <div class="section-title">🚀 Catalysts Timeline</div>
    <table>
      <thead><tr>
        <th>Date</th><th>Event</th><th>Impact</th><th>Direction</th>
      </tr></thead>
      <tbody>{cat_rows or '<tr><td colspan="4" style="padding:12px;color:#444">No catalysts identified.</td></tr>'}</tbody>
    </table>
  </div>

  <!-- ── Risk Factors ── -->
  <div style="background:#111;border:1px solid #1e1e1e;border-radius:10px;padding:18px;margin-bottom:24px">
    <div class="section-title">⚡ Risk Factors</div>
    <table>
      <thead><tr><th>Severity</th><th>Risk</th><th>Watch For</th></tr></thead>
      <tbody>{risk_rows or '<tr><td colspan="3" style="padding:12px;color:#444">No risks identified.</td></tr>'}</tbody>
    </table>
  </div>

  <!-- ── Price Levels ── -->
  <div style="background:#111;border:1px solid #1e1e1e;border-radius:10px;padding:18px;margin-bottom:24px">
    <div class="section-title">📏 Key Price Levels</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px">
      <div><div class="tlabel">Strong Support</div><div class="tval" style="color:#00c851">{_fmt(pl.get("strong_support"))}</div></div>
      <div><div class="tlabel">Immediate Support</div><div class="tval" style="color:#4ade80">{_fmt(pl.get("immediate_support"))}</div></div>
      <div><div class="tlabel">Current Price</div><div class="tval">{_fmt(price)}</div></div>
      <div><div class="tlabel">Immediate Resistance</div><div class="tval" style="color:#ff8800">{_fmt(pl.get("immediate_resistance"))}</div></div>
      <div><div class="tlabel">Strong Resistance</div><div class="tval" style="color:#ff4444">{_fmt(pl.get("strong_resistance"))}</div></div>
      <div><div class="tlabel">Analyst Target</div><div class="tval" style="color:#4da6ff">{_fmt(pl.get("analyst_target") or ac.get("avg_target"))}</div></div>
    </div>
  </div>

  <!-- ── Raw Research Steps ── -->
  <div class="section-title" style="margin-bottom:12px">🔬 Research waves (raw context fed to synthesis)</div>
  {step_accordions}

  <div class="ts">ATLAS Deep Research · Generated {ts} UTC · Data: Gemini Search + yfinance</div>
</div>
</body>
</html>"""


def write_report(research: dict, budget: float = 100.0) -> Path:
    """Write the deep research HTML and return the path."""
    DR_DIR.mkdir(exist_ok=True)
    ticker = (research.get("ticker") or "UNKNOWN").upper()
    path   = DR_DIR / f"{ticker}_deep.html"
    b      = research.get("budget") or budget

    # Run options simulator on the recommended contract
    sim_html    = ""
    sim_summary = ""
    if _OPTS_SIM_AVAILABLE and _opts_sim:
        try:
            sim = _opts_sim.simulate_from_research(research)
            if sim:
                sim_html    = sim.get("html_chart", "")
                sim_summary = sim.get("summary", "")
                logging.info("Options simulator: breakeven=$%s  IV=%.1f%%  "
                             "theta=$%.2f/day  contracts=%d",
                             sim["breakeven"], sim["iv"]*100,
                             abs(sim["theta_daily"]), sim["contracts"])
        except Exception:
            logging.debug("Options simulator failed", exc_info=True)

    # Also run simulator for the live yfinance options chain (top contract)
    if not sim_html:
        mkt  = research.get("mktdata") or {}
        opts = mkt.get("options") or []
        price = mkt.get("price") or 0
        if opts and price:
            o = opts[0]
            try:
                sim = _opts_sim.simulate(
                    ticker        = ticker,
                    strike        = float(o["strike"]),
                    expiry        = str(o["expiry"]),
                    ask           = float(o.get("ask") or o.get("cost_1_contract",50)/100),
                    current_price = float(price),
                    option_type   = "call",
                    budget        = float(b),
                    iv_crush_pct  = 0.30,
                )
                sim_html    = sim.get("html_chart","")
                sim_summary = sim.get("summary","")
            except Exception:
                pass

    html = _render_deep_report(
        research,
        discovery_context = research.get("discovery_context"),
        budget            = b,
        sim_html          = sim_html,
    )

    # Living report: persist a JSON timeline and inject it into the HTML so
    # repeat runs append history instead of discarding prior session context.
    import html as html_module

    log_path = DR_DIR / f"{ticker}_research_log.json"
    entries: list = []
    if log_path.is_file():
        try:
            entries = json.loads(log_path.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []
    syn = research.get("synthesis") or {}
    mkt = research.get("mktdata") or {}
    ts_iso = datetime.now(timezone.utc).isoformat()
    ts_disp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entries.insert(0, {
        "at":           ts_iso,
        "at_display":   ts_disp,
        "rating":       syn.get("overall_rating"),
        "confidence":   syn.get("confidence"),
        "price":        mkt.get("price") or syn.get("price_now"),
        "summary":      (syn.get("executive_summary") or "")[:6000],
        "source":       "deep_research",
    })
    entries = entries[:150]
    try:
        log_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    except Exception:
        logging.exception("Could not write research log for %s", ticker)

    parts: list[str] = [
        '<div id="atlas-research-timeline" style="margin-top:40px;padding:24px;border-top:2px solid #2a3444">',
        '<h2 style="color:#7a8aaa;font-size:0.95rem;letter-spacing:2px;text-transform:uppercase;margin-bottom:16px">Research timeline</h2>',
        '<p style="color:#666;font-size:0.85rem;margin-bottom:20px">Earlier passes are listed below. Content above is always the latest full research run.</p>',
    ]
    for e in entries[:40]:
        ad = html_module.escape(str(e.get("at_display") or e.get("at") or ""))
        rt = html_module.escape(str(e.get("rating") or "—"))
        pr = html_module.escape(str(e.get("price") if e.get("price") is not None else "—"))
        sm = html_module.escape(str(e.get("summary") or "")[:1200])
        src = html_module.escape(str(e.get("source") or "run"))
        parts.append(
            '<article style="margin-bottom:20px;padding:16px;background:#0f1419;border-radius:8px;border:1px solid #1c2535">'
            f'<div style="color:#4fc3f7;font-family:monospace;font-size:0.8rem">{ad} · <span style="color:#888">{src}</span></div>'
            f'<div style="margin-top:8px"><span style="color:#ffb300">{rt}</span> · Price ref: {pr}</div>'
            f'<p style="margin-top:10px;color:#bbb;line-height:1.55;font-size:0.88rem">{sm}</p>'
            "</article>"
        )
    parts.append("</div>")
    timeline_html = "\n".join(parts)
    if "</body>" in html:
        html = html.replace("</body>", timeline_html + "\n</body>", 1)
    else:
        html += timeline_html

    path.write_text(html, encoding="utf-8")
    logging.info("Deep report written -> %s", path)
    return path


def append_research_log_note(ticker: str, summary: str, source: str = "tracking_refresh") -> None:
    """Append a short automated note to the living research log (no full re-synthesis)."""
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return
    DR_DIR.mkdir(exist_ok=True)
    log_path = DR_DIR / f"{ticker}_research_log.json"
    entries: list = []
    if log_path.is_file():
        try:
            entries = json.loads(log_path.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []
    ts_iso = datetime.now(timezone.utc).isoformat()
    ts_disp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entries.insert(0, {
        "at":           ts_iso,
        "at_display":   ts_disp,
        "rating":       None,
        "confidence":   None,
        "price":        None,
        "summary":      (summary or "")[:4000],
        "source":       source,
    })
    entries = entries[:150]
    try:
        log_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    except Exception:
        logging.exception("append_research_log_note failed for %s", ticker)


def write_discovery_report(theme: str, all_research: list[dict]) -> Path:
    """Write a master discovery report listing all found stocks."""
    DR_DIR.mkdir(exist_ok=True)
    safe_theme = re.sub(r"[^a-zA-Z0-9_-]", "_", theme)[:40]
    path = DR_DIR / f"DISCOVERY_{safe_theme}.html"

    cards_html = ""
    for r in all_research:
        syn  = r.get("synthesis") or {}
        mkt  = r.get("mktdata")   or {}
        dc   = r.get("discovery_context") or {}
        ticker  = syn.get("ticker") or r.get("ticker","?")
        company = syn.get("company_name") or mkt.get("company_name") or ticker
        price   = syn.get("price_now") or mkt.get("price")
        rk      = (syn.get("overall_rating") or "hold").lower()
        r_color, r_bg, r_label = _RATING_STYLE.get(rk, ("#888", "#1a1a1a", "HOLD"))
        conf    = syn.get("confidence") or 5
        x100    = syn.get("100x_potential") or {}
        tp      = syn.get("trade_plan") or {}
        op      = syn.get("options_play") or {}
        bc      = op.get("best_contract") or {}
        ea      = syn.get("earnings_analysis") or {}
        report_link = f"{ticker}_deep.html"
        esum_raw = (syn.get("executive_summary") or "").strip()
        esum_disp = esum_raw[:1600] + ("…" if len(esum_raw) > 1600 else "")
        dc_horiz = dc.get("time_horizon_primary") or dc.get("time_horizon") or "—"
        dc_tier = dc.get("market_cap_tier") or "—"
        dc_liq = (dc.get("liquidity_note") or "")[:220]

        cards_html += f"""
        <div style="background:{r_bg};border:1px solid {r_color};border-radius:14px;
                    padding:22px;margin-bottom:20px">
          <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:14px">
            <span style="font-size:2rem;font-weight:900;color:{r_color}">{ticker}</span>
            <span style="color:#aaa;font-size:.9rem;flex:1">{company}</span>
            <span style="background:{r_color};color:#000;padding:4px 14px;border-radius:20px;
                         font-size:.82rem;font-weight:700">{r_label}</span>
          </div>
          <div style="color:#888;font-size:.78rem;margin-bottom:10px">
            Horizon: <strong style="color:#ccc">{dc_horiz}</strong>
            &nbsp;·&nbsp; Cap tier: <strong style="color:#ccc">{dc_tier}</strong>
            {f"&nbsp;·&nbsp; Liquidity: {dc_liq}" if dc_liq else ""}
          </div>
          <div style="color:#bbb;font-size:.88rem;line-height:1.65;margin-bottom:16px;white-space:pre-wrap">
            {esum_disp or "—"}
          </div>
          <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:14px">
            <div style="background:#0f0f0f;border-radius:8px;padding:10px">
              <div style="color:#555;font-size:.7rem">Price</div>
              <div style="color:#fff;font-weight:700">{_fmt(price)}</div>
            </div>
            <div style="background:#0f0f0f;border-radius:8px;padding:10px">
              <div style="color:#555;font-size:.7rem">Target 1</div>
              <div style="color:#00c851;font-weight:700">{_fmt(tp.get("target_1"))}</div>
            </div>
            <div style="background:#0f0f0f;border-radius:8px;padding:10px">
              <div style="color:#555;font-size:.7rem">Expected Gain</div>
              <div style="color:#4ade80;font-weight:700">{_fmt(tp.get("target_pct_gain"),"","%" ,1)}</div>
            </div>
            <div style="background:#0f0f0f;border-radius:8px;padding:10px">
              <div style="color:#555;font-size:.7rem">Best Call</div>
              <div style="color:#4da6ff;font-weight:700">
                {bc.get("expiry","—")} ${bc.get("strike","?")}C @ {_fmt(bc.get("cost_1_contract"))}
              </div>
            </div>
            <div style="background:#0f0f0f;border-radius:8px;padding:10px">
              <div style="color:#555;font-size:.7rem">100x Score</div>
              <div style="color:#ffbb33;font-weight:700">{x100.get("score","?")}/10</div>
            </div>
            <div style="background:#0f0f0f;border-radius:8px;padding:10px">
              <div style="color:#555;font-size:.7rem">Next Earnings</div>
              <div style="color:#ffbb33;font-weight:700">{ea.get("next_date","—")}</div>
            </div>
          </div>
          <div style="display:flex;gap:10px;align-items:center">
            <a href="{report_link}" style="background:#1a1a2a;color:#4da6ff;padding:8px 18px;
               border-radius:8px;font-size:.85rem;font-weight:600">Full Deep Report →</a>
            <span style="color:#555;font-size:.78rem">Catalyst: {dc.get("catalyst","—")}</span>
          </div>
        </div>"""

    now = datetime.now(timezone.utc).strftime("%B %d, %Y %H:%M UTC")
    scan_blurb = (
        "Each card summarizes one fully deep-researched name (full per-ticker HTML is linked). "
        "Horizons span near-term weeks, multi-month setups, and longer-term growth where noted — "
        "not financial advice; verify all data before acting."
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ATLAS Market scan — {theme}</title>
<meta name="description" content="ATLAS weekly market scan — multi-horizon stock research">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#080808;color:#e0e0e0;font-family:'Segoe UI','Inter',system-ui,sans-serif}}
a{{color:#4da6ff}}
.topbar{{background:#0f0f0f;border-bottom:1px solid #1e1e1e;padding:14px 28px;
         display:flex;align-items:center;gap:12px}}
.logo{{font-size:1rem;font-weight:800;color:#888}}
.logo b{{color:#fff}}
.content{{max-width:960px;margin:0 auto;padding:28px}}
h1{{font-size:1.6rem;font-weight:800;color:#fff;margin-bottom:6px}}
.subtitle{{color:#555;font-size:.85rem;margin-bottom:28px}}
.footer{{color:#333;font-size:.72rem;text-align:center;margin-top:30px}}
</style>
</head>
<body>
<div class="topbar">
  <div class="logo">⚡ <b>ATLAS</b> Market scan</div>
  <span style="color:#444">|</span>
  <span style="color:#666;font-size:.82rem">{now}</span>
  <a href="../LIVE_REPORTS.html" style="margin-left:auto;font-size:.82rem">← Back to LIVE Reports</a>
</div>
<div class="content">
  <h1>📊 Market scan: "{theme}"</h1>
  <div class="subtitle">{len(all_research)} names · full deep dive per ticker · generated {now}</div>
  <p style="color:#777;font-size:.88rem;line-height:1.6;margin-bottom:22px;max-width:820px">{scan_blurb}</p>
  {cards_html or '<p style="color:#555">No stocks found for this theme.</p>'}
  <div class="footer">ATLAS Deep Research · saved under deep_reports/ (dashboard → Weekly reports)</div>
</div>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")
    logging.info("Discovery report written → %s", path)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse, webbrowser

    ap = argparse.ArgumentParser(description="ATLAS Deep Research Engine")
    ap.add_argument("--ticker",   "-t",  help="Deep research a specific ticker, e.g. SOUN")
    ap.add_argument("--discover", "-d",  help='Discover stocks matching a theme, e.g. "AI penny stocks"')
    ap.add_argument("--options",  "-o",  help="Options-only play for a ticker")
    ap.add_argument("--budget",   "-b",  type=float, default=100.0,
                    help="Budget per trade in dollars (default $100)")
    ap.add_argument("--max",      "-m",  type=int,   default=6,
                    help="Max stocks to discover (default 6)")
    ap.add_argument("--open",     action="store_true",
                    help="Open report in browser when done")
    ap.add_argument("--verbose",  "-v",  action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not (args.ticker or args.discover or args.options):
        ap.print_help()
        raise SystemExit(1)

    c = _client()
    if c is None:
        print("ERROR: GOOGLE_API_KEY not set in .env or environment.")
        raise SystemExit(1)

    if args.ticker or args.options:
        t = (args.ticker or args.options).upper()
        research = research_ticker(t, budget=args.budget, client=c)
        if research:
            p = write_report(research, budget=args.budget)
            print(f"\nDone! Deep report written -> {p}")
            if args.open:
                webbrowser.open(p.as_uri())
        else:
            print("ERROR: Research returned no data.")

    elif args.discover:
        all_res = discover_stocks(args.discover, budget=args.budget,
                                   max_results=args.max, client=c)
        if all_res:
            for r in all_res:
                write_report(r)
            disc_path = write_discovery_report(args.discover, all_res)
            print(f"\nDone! Discovery report -> {disc_path}")
            print(f"   Individual reports -> {DR_DIR}/")
            if args.open:
                webbrowser.open(disc_path.as_uri())
        else:
            print("No stocks discovered for that theme.")
