#!/usr/bin/env python3
"""
query_router.py — ATLAS Natural Language Query Router + 10-Loop Engine
======================================================================
Tier 1 (Foundation): Loops 1–5 — scrape, fact-check, context gather, (batch LLM),
                      personalize
Tier 2 (Amplifiers): Loops 6–8 — execution rules, scenario EV, regime memory
Tier 3 (Shapers):    Loops 9–10 — adversarial + narrative (inside single batch LLM)

Loop 1: Omnivore scrape (web_scraper.gather_all + market_scanner.full_awareness)
Loop 2: Fact-check / cross-reference tagging on context text
Loop 3: Python satellite context (volume profile, congress, memory, sector — no LLM)
Loop batch: ONE Gemini JSON call — synthesis + macro + scenarios + stress + narrative
Loop 4: Python trade_plan sanity audit (post-batch)
Loop 5: Personalization (positions from Supabase per user_id when set, else file cache; tracker, paper trades)
Loop 6: Execution rules + alerts.py hooks
Loop 7: Scenario expected value (Python)
Loop 8: Regime memory (SQLite) — runs before batch so the model sees history
Loops 9–10: API stubs — failure_modes & narrative come from the batch response

Public API:
    from query_router import QueryRouter
    QueryRouter().route("Analyze my SOUN $14 call expiring June 18")
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from dotenv import load_dotenv

from gemini_limiter import GEMINI_HTTP_TIMEOUT_MS, is_rate_limit_error, wait_for_slot

from atlas_options_parse import extract_options_values_from_text
from atlas_personalization import build_personalization_bundle

try:
    from atlas_omega import _thematic_symbols_for_query as _omega_thematic_symbols
except ImportError:
    def _omega_thematic_symbols(query: str) -> list[str]:
        return ["SPY", "QQQ", "IWM"]

load_dotenv()
log = logging.getLogger(__name__)

RATE_LIMIT_USER_MESSAGE = "API Rate Limit Exceeded - Please wait 60 seconds"


class GeminiQuotaExceededError(RuntimeError):
    """Raised when Gemini returns 429 / RESOURCE_EXHAUSTED (free tier quota)."""

    def __init__(self, message: str = RATE_LIMIT_USER_MESSAGE):
        super().__init__(message)
        self.user_message = message


class QueryCancelledError(RuntimeError):
    """Raised when a caller requests cancellation between pipeline stages."""


def _strip_json_fence(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-z]*\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s).strip()
    return s


def _json_loads_llm_output(resp_text: str) -> Any:
    """
    Parse Gemini JSON mode output. Models occasionally emit ASCII control characters
    inside string values that json.loads rejects ('Invalid control character').
    """
    raw = _strip_json_fence((resp_text or "").strip())
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
        if cleaned != raw:
            return json.loads(cleaned)
        raise


# One full /query pipeline at a time — shared FourLoopEngine + genai client are not safe
# for overlapping 10-loop runs; avoids cross-request corruption and flaky JSON.
_QUERY_PIPELINE_LOCK = threading.Lock()

QUERY_TYPES = {
    "TICKER_DEEP_DIVE": "Full research on one ticker",
    "OPTIONS_ANALYSIS": "Options contract analysis",
    "THEMATIC_DISCOVERY": "Thematic stock discovery",
    "MACRO_ANALYSIS": "Macro environment",
    "SECTOR_ROTATION": "Sector rotation",
    "EARNINGS_PREVIEW": "Pre-earnings",
    "EARNINGS_REVIEW": "Post-earnings",
    "CONCEPT_EXPLAINER": "Explain a concept",
    "POSITION_ADVISOR": "Hold / exit advice",
    "STRATEGY_RESEARCH": "Strategy deep dive",
}

INTENT_MARKET_DEEP_DIVE = "MARKET_DEEP_DIVE"
INTENT_GENERAL_FINANCE = "GENERAL_FINANCE"
INTENT_CRYPTO_MARKET_SCAN = "CRYPTO_MARKET_SCAN"
INTENT_EQUITIES_MARKET_SCAN = "EQUITIES_MARKET_SCAN"
INTENT_OPTIONS_FLOW_MARKET_SCAN = "OPTIONS_FLOW_MARKET_SCAN"
INTENT_INSIDER_TRADES_MARKET_SCAN = "INSIDER_TRADES_MARKET_SCAN"
INTENT_TREASURY_YIELD_MARKET_SCAN = "TREASURY_YIELD_MARKET_SCAN"
INTENT_CPI_INFLATION_MARKET_SCAN = "CPI_INFLATION_MARKET_SCAN"
INTENT_FED_WATCH_MARKET_SCAN = "FED_WATCH_MARKET_SCAN"
INTENT_WATCH_MARKET_SCAN = "WATCH_MARKET_SCAN"
INTENT_EARNINGS_MARKET_SCAN = "EARNINGS_MARKET_SCAN"
INTENT_FOREX_MARKET_SCAN = "FOREX_MARKET_SCAN"
INTENT_COMMODITIES_MARKET_SCAN = "COMMODITIES_MARKET_SCAN"
INTENT_SUPPLY_CHAIN_MARKET_SCAN = "SUPPLY_CHAIN_MARKET_SCAN"
INTENT_ENERGY_MARKET_SCAN = "ENERGY_MARKET_SCAN"
INTENT_CLIMATE_RISK_MARKET_SCAN = "CLIMATE_RISK_MARKET_SCAN"
INTENT_TARIFFS_MARKET_SCAN = "TARIFFS_MARKET_SCAN"
INTENT_JOBS_MARKET_SCAN = "JOBS_MARKET_SCAN"
INTENT_CONGRESS_TRADES_MARKET_SCAN = "CONGRESS_TRADES_MARKET_SCAN"

# Phase-2 extended intents (Tasks 4-12)
INTENT_DARK_POOL_SCAN = "DARK_POOL_SCAN"
INTENT_PENNY_STOCK_SCAN = "PENNY_STOCK_SCAN"
INTENT_REAL_ESTATE_SCAN = "REAL_ESTATE_SCAN"
INTENT_PERSONAL_WEALTH_SCAN = "PERSONAL_WEALTH_SCAN"
INTENT_TAX_LEGAL_SCAN = "TAX_LEGAL_SCAN"
INTENT_BUSINESS_SCAN = "BUSINESS_SCAN"
INTENT_ALTERNATIVE_ASSET_SCAN = "ALTERNATIVE_ASSET_SCAN"
INTENT_GLOBAL_LIQUIDITY_SCAN = "GLOBAL_LIQUIDITY_SCAN"
INTENT_GROWTH_MARKETING_SCAN = "GROWTH_MARKETING_SCAN"
INTENT_INTELLIGENCE_SYNTHESIS = "INTELLIGENCE_SYNTHESIS"
INTENT_SECTOR_ROTATION_SCAN = "SECTOR_ROTATION_SCAN"
INTENT_SENTIMENT_DIVERGENCE_SCAN = "SENTIMENT_DIVERGENCE_SCAN"
INTENT_MACRO_RISK_SCAN = "MACRO_RISK_SCAN"
INTENT_CASUAL = "CASUAL"
INTENT_GENERAL_CHAT = "GENERAL_CHAT"
INTENT_COMPANY_RESEARCH = "COMPANY_RESEARCH"
INTENT_DOCUMENT_GENERATION = "DOCUMENT_GENERATION"
INTENT_HTML_ARTIFACT = "HTML_ARTIFACT"
INTENT_MARKET_DATA = "MARKET_DATA"
INTENT_TRADING_ANALYSIS = "TRADING_ANALYSIS"

KNOWN_LARGE_COMPANIES: frozenset[str] = frozenset({
    "blackrock", "apple", "microsoft", "google", "amazon",
    "tesla", "jpmorgan", "goldman sachs", "morgan stanley",
    "berkshire", "warren buffett", "vanguard", "fidelity",
    "citadel", "bridgewater", "sequoia", "softbank",
})

# Alias-based company detection (canonical → list of aliases)
KNOWN_COMPANIES: dict[str, list[str]] = {
    "blackrock":      ["blackrock", "blk"],
    "apple":          ["apple", "apple inc", "aapl"],
    "microsoft":      ["microsoft", "msft"],
    "google":         ["google", "alphabet", "goog", "googl"],
    "amazon":         ["amazon", "amzn"],
    "tesla":          ["tesla", "tsla"],
    "jpmorgan":       ["jpmorgan", "jp morgan", "jpm"],
    "goldman sachs":  ["goldman sachs", "gs"],
    "morgan stanley": ["morgan stanley", "ms"],
    "berkshire":      ["berkshire", "berkshire hathaway", "brk"],
    "warren buffett": ["warren buffett", "buffett"],
    "vanguard":       ["vanguard"],
    "fidelity":       ["fidelity"],
    "citadel":        ["citadel"],
    "bridgewater":    ["bridgewater"],
    "sequoia":        ["sequoia capital", "sequoia"],
    "softbank":       ["softbank"],
    "blackstone":     ["blackstone", "bx"],
}

# Context words that indicate the word is NOT referring to the company
NON_COMPANY_CONTEXT: dict[str, list[str]] = {
    "apple":  ["pie", "fruit", "cider", "juice", "recipe", "orchard", "sauce", "tree"],
    "amazon": ["rainforest", "river", "jungle", "forest", "basin", "ecology"],
    "tesla":  ["coil", "inventor", "nikola", "alternating current"],
}


def _company_phrase_match(text: str, phrase: str) -> bool:
    """True if phrase appears as a whole token/word sequence in text."""
    escaped = re.escape(phrase.lower())
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text.lower()) is not None


def detect_company_name(raw_query: str) -> Optional[str]:
    """Return the canonical company name if the query is about a known company, else None."""
    q = (raw_query or "").lower()
    for canonical, aliases in KNOWN_COMPANIES.items():
        for alias in aliases:
            if _company_phrase_match(q, alias):
                blocked = NON_COMPANY_CONTEXT.get(canonical, [])
                if any(_company_phrase_match(q, term) for term in blocked):
                    continue
                return canonical
    return None

CASUAL_PATTERNS: tuple[str, ...] = (
    r"\bhow are you\b",
    r"\bhey\b",
    r"\bhello\b",
    r"\bhi\b",
    r"\bjoke\b",
    r"\bweather\b",
    r"\brecipe\b",
    r"\btell me something\b",
    r"\bwhat is your name\b",
)

CASUAL_SIGNALS: tuple[str, ...] = (
    r"\bhey\b",
    r"\bhello\b",
    r"\bhi\b",
    r"\bhow are you\b",
    r"\bwho won\b",
    r"\blast night\b",
    r"\bwrite me\b",
    r"\bmake me\b",
    r"\bjoke\b",
    r"\bweather\b",
)

# SCAN intents always use RESEARCH output format (no trading template)
_SCAN_INTENTS: frozenset[str] = frozenset({
    "DARK_POOL_SCAN", "PENNY_STOCK_SCAN", "REAL_ESTATE_SCAN",
    "PERSONAL_WEALTH_SCAN", "TAX_LEGAL_SCAN", "BUSINESS_SCAN",
    "ALTERNATIVE_ASSET_SCAN", "GLOBAL_LIQUIDITY_SCAN", "GROWTH_MARKETING_SCAN",
    "INTELLIGENCE_SYNTHESIS", "SECTOR_ROTATION_SCAN", "SENTIMENT_DIVERGENCE_SCAN",
    "MACRO_RISK_SCAN",
    "CRYPTO_MARKET_SCAN", "EQUITIES_MARKET_SCAN", "OPTIONS_FLOW_MARKET_SCAN",
    "INSIDER_TRADES_MARKET_SCAN", "TREASURY_YIELD_MARKET_SCAN",
    "CPI_INFLATION_MARKET_SCAN", "FED_WATCH_MARKET_SCAN", "WATCH_MARKET_SCAN",
    "EARNINGS_MARKET_SCAN", "FOREX_MARKET_SCAN", "COMMODITIES_MARKET_SCAN",
    "SUPPLY_CHAIN_MARKET_SCAN", "ENERGY_MARKET_SCAN", "CLIMATE_RISK_MARKET_SCAN",
    "TARIFFS_MARKET_SCAN", "JOBS_MARKET_SCAN", "CONGRESS_TRADES_MARKET_SCAN",
})

DOMAIN_FRAMING: dict[str, str] = {
    "REAL_ESTATE_SCAN": "You are a senior real estate analyst with expertise in residential, commercial, rental, and REIT markets.",
    "PERSONAL_WEALTH_SCAN": "You are a certified financial planner (CFP) helping users optimize savings, debt, and personal finances. Always append: 'Consult a CFP for personalized advice.'",
    "TAX_LEGAL_SCAN": "You are a senior tax and legal analyst. This is informational only — always append: 'Consult a licensed tax professional or attorney for your specific situation.'",
    "BUSINESS_SCAN": "You are a venture analyst and business strategist with deep expertise in SMBs, SaaS metrics, franchise, and startup funding.",
    "ALTERNATIVE_ASSET_SCAN": "You are an alternative asset specialist covering luxury watches, fine art, collectibles, precious metals, and P2P lending.",
    "GROWTH_MARKETING_SCAN": "You are a growth and marketing analyst specializing in digital ads, SEO, brand sentiment, and ROI optimization.",
    "INTELLIGENCE_SYNTHESIS": "You are a senior quant analyst and portfolio strategist. You synthesize signals across multiple data sources to find the highest-conviction insights across regimes, rotations, and catalysts.",
    "DARK_POOL_SCAN": "You are a market microstructure analyst specializing in dark pool activity, off-exchange block trades, and institutional flow detection.",
    "PENNY_STOCK_SCAN": "You are a small-cap specialist focused on penny stocks, micro-cap movers, and high-volume low-float opportunities. Always note the high-risk nature of this asset class.",
    "GLOBAL_LIQUIDITY_SCAN": "You are a global macro and liquidity specialist tracking M2 money supply, central bank policy, and liquidity cycles.",
    "SECTOR_ROTATION_SCAN": "You are a sector rotation specialist who tracks institutional money flows across market sectors to identify rotation opportunities.",
    "SENTIMENT_DIVERGENCE_SCAN": "You are a contrarian analyst who identifies divergences between retail and institutional sentiment to find early-mover signals.",
    "MACRO_RISK_SCAN": "You are a macro risk analyst synthesizing Fed policy, inflation, jobs, and yield curve signals into a unified risk picture for investors.",
}

_ROUTER_TICKER_DD_EXCLUDE_RE = re.compile(
    r"\banalyze\s+[A-Z]{2,5}\b|\b(?:deep\s+dive|dd)\s+on\s+[A-Z]{2,5}\b",
    re.I,
)
_CRYPTO_CACHE_TOPIC_RE = re.compile(
    r"\b(?:crypto|currencies|cryptocurrenc|bitcoin|btc\b|ethereum|eth\b|altcoin|defi|"
    r"digital\s+asset|token\b|coins?\b(?!\s+base))\b",
    re.I,
)
_CRYPTO_CACHE_SCAN_RE = re.compile(
    r"\b(?:top\s+\d*|biggest|largest)\b[\s\S]{0,120}\b(?:mover|gainer|loser)"
    r"|\b(?:movers|trending|heatmap|universe|market\s+(?:scan|overview|snapshot|wide)|"
    r"what(?:'s|s| is)\s+moving|right\s+now|snapshot|scan\b|leader(?:board)?|laggard|"
    r"which\s+\w+\s+(?:coin|crypto)s?)\b"
    r"|\bmoving\s+(?:today|rn|now)\b",
    re.I | re.S,
)
_EQU_CACHE_TOPIC_RE = re.compile(
    r"\b(?:equit(?:y|ies)|stock\s+market|\bspy\b|\bstocks\b|share\s+market|"
    r"s\&p|sp\s*-?\s*500|snp\s*500|russell|\bnasdaq\b(?!\s+crypto)|\bNYSE\b)\b",
    re.I,
)
_EQU_CACHE_SCAN_RE = re.compile(
    r"\b(?:top\s+\d*|biggest)\b[\s\S]{0,160}\b(?:gainer|loser|active)"
    r"|\b(?:day\s+)?gainers\b|\b(?:day\s+)?losers\b|\bmost\s+actives?\b|\bmovers\b|"
    r"\bheatmap\b|\buniverse\b|\bmarket\s+(?:scan|snapshot|overview)\b|\bsnapshot\b|"
    r"\bwhat(?:'s|s| is)\s+moving\b|\bscan\b|\bleader(?:board)?\b|\blaggards?\b",
    re.I | re.S,
)
_WATCH_CACHE_TOPIC_RE = re.compile(
    r"\b(?:luxury\s+watch|collectible\s+watch|wristwatch|timepieces?\b|chrono24|"
    r"rolex|patek(?:\s+philippe)?|audemars|royal\s+oak|speedmaster|submariner|"
    r"daytona|nautilus|watch\s+market|secondary\s+market\s+(?:for\s+)?watches)\b",
    re.I,
)
_WATCH_CACHE_SCAN_RE = re.compile(
    r"\b(?:market\s+(?:scan|snapshot|overview)|snapshot|scan\b|"
    r"premiums?|secondary\s+market|retail\s+vs|price\s+trends?|trends?\b|"
    r"valuation|leaderboard|heatmap)\b",
    re.I | re.S,
)

_DC_CONTEXT_SCAN_RE = re.compile(
    r"\b(?:overview|snapshot|scan|heatmap|today|recent|latest|right\s+now|"
    r"what\s+is\s+going\s+on|what(?:'|'|’)?s\s+going\s+on|what\s+happened|"
    r"quick\s+take|anything\s+standing\s+out|rundown|briefing|"
    r"what\s+does\s+this\s+mean|how\s+does\s+this\s+(?:read|look))\b",
    re.I | re.S,
)

_OPTIONS_FLOW_TOPIC_RE = re.compile(
    r"\b(?:options\s+flow|unusual\s+options\s+activity|"
    r"volume\s*(?:/\s*|to\s+)(?:open\s+)?interest|vol\s*/\s*oi\b|"
    r"call\s+walls?|put\s+walls?|gamma\s+hunt(?:ing)?|options\s+tape)\b",
    re.I | re.S,
)
_INSIDER_TOPIC_RE = re.compile(
    r"\b(?:insider\s+trading|insider\s+buys?|insider\s+sells?|form\s*4|"
    r"beneficial\s+ownership|ceo\s+buy|ceo\s+sell|cfo\s+buy|cfo\s+sell)\b",
    re.I | re.S,
)
_INSIDER_SEC_RE = re.compile(
    r"\b(?:sec\.gov|sec\s+edgar|edgar)\b.*(?:insider|form\s*4)|"
    r"(?:insider|form\s*4).*?(?:sec|edgar)",
    re.I | re.S,
)

_TREASURY_YIELD_TOPIC_RE = re.compile(
    r"\b(?:yield\s+curve|2s10s|curve\s+(?:invert|flatten|steep))"
    r"|\b(?:ust\b|u\.?s\.?\s+treasur(?:y|ies)|treasury\s+yields?)\b"
    r"|\b(?:term\s+premium|rates\s+backdrop|rates\s+environment)\b",
    re.I | re.S,
)
_CPI_INFLATION_TOPIC_RE = re.compile(
    r"\b(?:consumer\s+price\s+index|\bcpi\b|headline\s+inflation|"
    r"latest\s+PCE|PCE\b|core\s+PCE|categor(?:y|ies).*?inflation|"
    r"bls.*?cpi|inflation\s+(?:report|numbers?))\b",
    re.I | re.S,
)
_FED_TOPIC_RE = re.compile(
    r"\b(?:fomc|fedwatch|cme.*?fed\b|effective\s+federal\s+funds|dot\s+plot|"
    r"hawkish|dovish|rate\s+(?:probability|probabilities))"
    r"|\bprobability\b.*?(?:fed|fomc|rates?\s+(?:cuts?|hike)|basis\s+points)"
    r"|\bfed\b.*?(?:basis\s+points|bps\b|rates?\s+markets?|meeting)\b",
    re.I | re.S,
)
_EARNINGS_TOPIC_RE = re.compile(r"\b(?:earnings\s+calendar|upcoming\s+earnings|earnings\s+preview|reports?\s+earnings)\b", re.I | re.S)
_FOREX_TOPIC_RE = re.compile(r"\b(?:forex|fx\b|currency|currencies|dxy|usd/(?:eur|jpy|gbp|cad|chf|aud|cny|mxn)|euro|yen|pound)\b", re.I | re.S)
_COMMODITIES_TOPIC_RE = re.compile(r"\b(?:commodit(?:y|ies)|gold|silver|copper|oil|crude|natural\s+gas|wheat|corn)\b", re.I | re.S)
_SUPPLY_CHAIN_TOPIC_RE = re.compile(r"\b(?:supply\s+chain|freight|shipping\s+rates?|container|drewry|freightos|logistics)\b", re.I | re.S)
_ENERGY_TOPIC_RE = re.compile(r"\b(?:energy\s+grid|electricity|gasoline|gas\s+prices?|renewables|coal|nuclear|grid\s+mix)\b", re.I | re.S)
_CLIMATE_TOPIC_RE = re.compile(r"\b(?:climate\s+risk|fema|flood|nfip|insurance\s+premium|flood\s+zone)\b", re.I | re.S)
_TARIFF_TOPIC_RE = re.compile(r"\b(?:tariff|ustr|section\s+301|section\s+232|trade\s+war|import\s+duty)\b", re.I | re.S)
_JOBS_TOPIC_RE = re.compile(r"\b(?:jobs\s+report|job\s+market|payrolls?|unemployment|bls|labor\s+market)\b", re.I | re.S)
_CONGRESS_TRADES_TOPIC_RE = re.compile(r"\b(?:congress(?:ional)?\s+trades?|stock\s+act|house\s+stock|politician\s+trades?)\b", re.I | re.S)

# Phase-2 extended topic regexes
_DARK_POOL_TOPIC_RE = re.compile(
    r"\b(?:dark\s+pool|off[\s-]exchange|block\s+trade|dark\s+pool\s+volume|"
    r"institutional\s+buying|hidden\s+orders?|dark\s+pool\s+activity|dark\s+pool\s+prints?)\b",
    re.I | re.S,
)
_PENNY_STOCK_TOPIC_RE = re.compile(
    r"\b(?:penny\s+stock|micro[\s-]cap|small[\s-]cap\s+movers?|under\s+\$5|"
    r"high\s+volume\s+cheap|low\s+float|sub[\s-]\$5\s+stock|otc\s+stock)\b",
    re.I | re.S,
)
_REAL_ESTATE_TOPIC_RE = re.compile(
    r"\b(?:housing\s+market|home\s+prices?|real\s+estate|mortgage\s+rates?|"
    r"rental\s+yield|airbnb|short[\s-]term\s+rental|reit|commercial\s+property|"
    r"zoning|permit|residential|apartment\s+rent|home\s+values?|property\s+market|"
    r"housing\s+prices?|buying\s+a\s+home|sell(?:ing)?\s+(?:a\s+)?house)\b",
    re.I | re.S,
)
_PERSONAL_WEALTH_TOPIC_RE = re.compile(
    r"\b(?:credit\s+card|best\s+credit\s+card|auto\s+loan|car\s+loan|"
    r"student\s+(?:debt|loan)|loan\s+forgiveness|hysa|high[\s-]yield\s+savings?|"
    r"ira\s+limit|401k|retirement\s+(?:savings?|account|limit)|personal\s+loan|"
    r"cost\s+of\s+living|insurance\s+premium|debt\s+consolidation|savings\s+rate|"
    r"emergency\s+fund|pay\s+off\s+debt)\b",
    re.I | re.S,
)
_TAX_LEGAL_TOPIC_RE = re.compile(
    r"\b(?:federal\s+tax|tax\s+bracket|irs|state\s+tax|act\s+60|"
    r"bankruptcy|chapter\s+7|chapter\s+11|sec\s+filing|10[\s-]k|"
    r"consumer\s+protection|labor\s+law|minimum\s+wage|w[\s-]?2|"
    r"independent\s+contractor|tax\s+deduction|capital\s+gains\s+tax|"
    r"tax\s+(?:return|filing|planning|strategy))\b",
    re.I | re.S,
)
_BUSINESS_TOPIC_RE = re.compile(
    r"\b(?:sba\s+loan|sba\s+grant|small\s+business|saas\s+metrics?|"
    r"\bcac\b|\bltv\b|\bchurn\b|ecommerce\s+trends?|trending\s+niche|"
    r"freelance\s+rates?|franchise\s+cost|vc\s+funding|startup\s+funding|"
    r"venture\s+capital|b2b\s+metrics?|solopreneur|agency\s+pricing)\b",
    re.I | re.S,
)
_ALTERNATIVE_ASSET_TOPIC_RE = re.compile(
    r"\b(?:art\s+auction|sotheby|christie|collectibles?|trading\s+cards?|"
    r"\bpsa\b|ebay\s+sold|p2p\s+lending|prosper|lending\s+club|"
    r"physical\s+gold|silver\s+coin|bullion|premium\s+over\s+spot|"
    r"luxury\s+watches?|alternative\s+investment|"
    r"(?:rolex|patek|audemars)\s+(?:market|price|value|invest|appreciat|depreciat|premium|resale|sell|buy|worth|portfolio|return))\b",
    re.I | re.S,
)
_GLOBAL_LIQUIDITY_TOPIC_RE = re.compile(
    r"\b(?:global\s+liquidity|m2\s+money\s+supply|central\s+bank|"
    r"liquidity\s+cycle|monetary\s+policy|quantitative\s+easing|"
    r"qt\s+tightening|global\s+money|m2\s+growth|liquidity\s+signal)\b",
    re.I | re.S,
)
_MACRO_RISK_TOPIC_RE = re.compile(
    r"\b(?:macro\s+risk|systemic\s+risk|recession\s+risk|yield\s+curve\s+inversion|"
    r"credit\s+spread|sovereign\s+risk|macro\s+outlook|risk[\s-]off|risk[\s-]on|"
    r"macro\s+environment|economic\s+risk|macro\s+signal|macro\s+dashboard|"
    r"cpi\s+and\s+fed|fed\s+and\s+inflation|jobs\s+and\s+rates|"
    r"macro\s+picture|overall\s+macro)\b",
    re.I | re.S,
)
_GROWTH_MARKETING_TOPIC_RE = re.compile(
    r"\b(?:competitor\s+ads?|meta\s+ad\s+library|seo\s+keywords?|google\s+trends?|"
    r"trending\s+keywords?|social\s+sentiment|brand\s+mentions?|content\s+repurpose|"
    r"email\s+deliverability|dkim|spf|engagement\s+rate|"
    r"influencer|google\s+reviews?|roas|return\s+on\s+ad\s+spend|"
    r"lead\s+generation|local\s+business\s+marketing|\bcrm\b)\b",
    re.I | re.S,
)
_INTELLIGENCE_SYNTHESIS_TOPIC_RE = re.compile(
    r"\b(?:market\s+correlation|cross[\s-]asset|regime\s+change|"
    r"earnings\s+season|news\s+catalyst|"
    r"sentiment\s+divergence|risk\s+budget|portfolio\s+risk|"
    r"neural\s+web|combined\s+analysis|market\s+regime\s+signal|"
    r"market\s+regime\b)\b",
    re.I | re.S,
)
_SECTOR_ROTATION_TOPIC_RE = re.compile(
    r"\b(?:sector\s+rotation|money\s+flowing\s+into|institutional\s+rotation|"
    r"which\s+sectors?|energy\s+vs\s+tech|defensive\s+vs\s+growth|"
    r"rotating\s+(?:out\s+of|into)|sectors?\s+are\s+rotating|"
    r"sector\s+rotati\w+)\b",
    re.I | re.S,
)
_SENTIMENT_DIVERGENCE_TOPIC_RE = re.compile(
    r"\b(?:sentiment\s+divergence|retail\s+vs\s+institutional|smart\s+money|"
    r"contrarian\s+signal|sentiment\s+gap|retail\s+sentiment|"
    r"institutional\s+sentiment)\b",
    re.I | re.S,
)

_MARKET_HINT_RE = re.compile(
    r"\$[A-Za-z]{1,5}\b|"
    r"\b(?:buy|sell|short|long)\s+(?:the\s+)?(?:stock|shares)\b|"
    r"\b(?:call|put)\b.{0,40}\b(?:strike|expir)|"
    r"\b(?:strike|expir).{0,40}\b(?:call|put)\b|"
    r"\b(?:earnings|eps|guidance|10-?k|10-?q|8-?k)\b|"
    r"\b(?:price target|volume profile|vwap|macd|rsi)\b|"
    r"\b(?:iv crush|theta|gamma|option chain)\b",
    re.I | re.S,
)
_GENERAL_KW_SCORES: list[tuple[str, float]] = [
    ("relocat", 3.0),
    ("financial roadmap", 3.5),
    ("roadmap", 2.5),
    ("financial plan", 3.0),
    ("budget", 2.5),
    ("debt payoff", 3.0),
    ("credit card", 2.5),
    ("student loan", 2.5),
    ("mortgage", 2.5),
    ("refinance", 2.5),
    ("legal advice", 3.0),
    ("tax advice", 2.5),
    ("tax return", 2.0),
    ("estate plan", 3.0),
    ("my will", 2.0),
    ("divorce", 2.5),
    ("bankruptcy", 2.0),
    ("retirement plan", 2.5),
    ("401k", 1.5),
    ("roth ira", 2.0),
    ("emergency fund", 2.0),
    ("cost of living", 2.0),
    ("personal finance", 3.0),
    ("help me plan", 3.0),
    ("i'm worried", 3.0),
    ("i am worried", 3.0),
    ("my situation", 2.5),
    ("should i rent", 2.0),
    ("buy a house", 2.0),
    ("buying a home", 2.0),
    ("cpa", 1.5),
    ("attorney", 2.0),
    ("owe the irs", 2.0),
    ("relocation package", 2.5),
    ("moving for work", 3.0),
    ("life insurance", 2.0),
    ("how much should i save", 2.5),
]


def classify_intent_route(raw: str) -> str:
    """
    Coarse routing: MARKET_DEEP_DIVE (10-loop + ticker path) vs GENERAL_FINANCE / COMPANY_RESEARCH (Omega).
    Receives ONLY the user's raw plain-text query — no metadata, memory JSON, or request controls.
    """
    q = (raw or "").strip()
    if not q:
        return INTENT_GENERAL_CHAT

    lc = q.lower()

    # ── Explicit trade requests — checked FIRST before company detection ────────
    # This prevents "give me a trade setup for TSLA" from routing to COMPANY_RESEARCH.
    if _EXPLICIT_TRADE_RE.search(q):
        return INTENT_MARKET_DEEP_DIVE

    # ── HTML artifact detection ───────────────────────────────────────────────
    if re.search(r"\b(html|dashboard|landing\s+page|website|ui\s+component)\b", lc):
        return INTENT_HTML_ARTIFACT

    # ── Document generation detection ─────────────────────────────────────────
    if re.search(
        r"\b(?:make|create|generate|write)(?:\s+me)?\s+(?:a\s+)?(?:pdf|report|document|deck|brief|memo|presentation)\b",
        lc,
    ):
        return INTENT_DOCUMENT_GENERATION
    try:
        from output_modes import user_asked_finance_opinion, user_explicitly_requested_document
        if user_explicitly_requested_document(q):
            return INTENT_DOCUMENT_GENERATION
        if user_asked_finance_opinion(q):
            return INTENT_GENERAL_FINANCE
    except Exception:
        pass

    # ── Alias-based company detection with NON_COMPANY_CONTEXT disambiguation ─
    company = detect_company_name(q)
    if company:
        return INTENT_COMPANY_RESEARCH

    gen = 0.0
    mkt = 0.0
    if _MARKET_HINT_RE.search(q):
        mkt += 4.0
    for kw, w in _GENERAL_KW_SCORES:
        if kw in lc:
            gen += w
    if re.search(r"\bi\s*['']?m\b|\bi am\b", lc):
        gen += 2.5
    if re.search(r"\banalyze\s+[A-Z]{2,5}\b", q, re.IGNORECASE):
        mkt += 2.5
    if re.search(r"\b(?:deep dive|dd)\s+on\s+[A-Z]{2,5}\b", lc):
        mkt += 3.0
    log.debug("[intent] scores general=%.1f market=%.1f — %s", gen, mkt, q[:80])

    # Casual greeting / off-topic: scores will be zero and query matches casual pattern
    if gen == 0.0 and mkt == 0.0 and any(re.search(p, lc) for p in CASUAL_PATTERNS):
        return INTENT_CASUAL
    # Broader casual signals (write me, who won, last night, etc.) with no market signal
    if mkt == 0.0 and any(re.search(p, lc) for p in CASUAL_SIGNALS):
        return INTENT_GENERAL_CHAT
    # If BOTH scores are zero — no finance/market signal → casual
    if gen == 0.0 and mkt == 0.0:
        return INTENT_GENERAL_CHAT
    # General finance wins if it scores higher (with small buffer)
    if gen >= mkt + 0.75:
        return INTENT_GENERAL_FINANCE
    # Market deep dive needs a clear signal to justify the heavy 10-loop engine
    if mkt >= 2.0:
        return INTENT_MARKET_DEEP_DIVE
    # Tie or unclear — default to GENERAL_FINANCE (safer, less expensive)
    return INTENT_GENERAL_FINANCE


_OUTPUT_MODE_TRADE_RE = re.compile(
    r"\b(trade|entry|setup|options|scalp|swing|stop[\s-]loss|take[\s-]profit|call|put|strike|expir|position size|risk[\s/]reward)\b",
    re.I,
)
_OUTPUT_MODE_DOC_RE = re.compile(
    r"\b(report|pdf|html|document|generate|presentation|deck|spreadsheet|workbook|export)\b",
    re.I,
)

# Explicit trade-request patterns — matched before GENERAL_CHAT fallback
_EXPLICIT_TRADE_RE = re.compile(
    r"\b(trade\s+setup|trade\s+plan|entry\s+price|stop\s+loss|take\s+profit|scalp|swing\s+trade|day\s+trade|buy\s+calls|buy\s+puts|options\s+play|give\s+me\s+a\s+trade|show\s+me\s+a\s+trade)\b",
    re.I,
)

# Auto-promote to deep research when the user says so explicitly in the query
_DEEP_RESEARCH_RE = re.compile(
    r"\bdeep\s+research\b|\bfull\s+research\b|\bcomprehensive\s+research\b|\bexhaustive\s+research\b",
    re.I,
)


def resolve_output_mode(raw_query: str, intent: str) -> str:
    """Resolve the output mode — delegates to output_modes.py when available."""
    try:
        from output_modes import resolve_output_mode as _new_resolver
        return _new_resolver(raw_query, intent)
    except ImportError:
        pass
    # Legacy fallback (used only if output_modes.py is missing)
    if intent in (INTENT_CASUAL, INTENT_GENERAL_CHAT):
        return "chat"
    if intent == INTENT_DOCUMENT_GENERATION:
        return "document"
    if intent == INTENT_MARKET_DEEP_DIVE:
        return "trade_plan"
    lc = (raw_query or "").lower()
    if _OUTPUT_MODE_TRADE_RE.search(lc):
        return "trade_plan"
    if _OUTPUT_MODE_DOC_RE.search(lc):
        return "document"
    if intent in (INTENT_GENERAL_FINANCE, INTENT_COMPANY_RESEARCH):
        return "company_report"
    return "finance_answer"


def classify_sector_cache_intent(raw: str) -> Optional[str]:
    """
    Detect market-wide scan questions that should be answered from data_cache snapshots
    (Omega + internal JSON), not the 10-loop ticker engine.

    Returns an INTENT_*_MARKET_SCAN string for internal knowledge routing, or None.
    """
    q = (raw or "").strip()
    if not q:
        return None
    if _ROUTER_TICKER_DD_EXCLUDE_RE.search(q):
        return None
    crypto_scan = (
        bool(_CRYPTO_CACHE_TOPIC_RE.search(q)) and bool(_CRYPTO_CACHE_SCAN_RE.search(q))
    )
    equ_scan = (
        bool(_EQU_CACHE_TOPIC_RE.search(q)) or re.search(r"\bmy\s+stocks\b", q, re.I)
    ) and bool(_EQU_CACHE_SCAN_RE.search(q))
    # Tie-break: crypto-specific wording wins both
    has_crypto_kw = bool(_CRYPTO_CACHE_TOPIC_RE.search(q))
    if crypto_scan:
        return INTENT_CRYPTO_MARKET_SCAN
    if equ_scan:
        # Avoid equities cache on pure-crypto wording without stock-market topic
        if has_crypto_kw and not _EQU_CACHE_TOPIC_RE.search(q):
            return None
        return INTENT_EQUITIES_MARKET_SCAN

    watch_scan = bool(_WATCH_CACHE_TOPIC_RE.search(q)) and bool(
        _WATCH_CACHE_SCAN_RE.search(q)
    )
    if watch_scan:
        return INTENT_WATCH_MARKET_SCAN

    dc_ctx = bool(_DC_CONTEXT_SCAN_RE.search(q))
    dc_ok = dc_ctx or bool(
        re.search(
            r"\b(?:latest|recent|today|current|right\s+now|reading|surprise|"
            r"probability|probabilities|\bodds\b|implied|print|beat\b|miss\b|versus\b|vs\.|vs\b|"
            r"means\s+for|signal|backdrop|heatmap|breakdown)\b",
            q,
            re.I,
        )
    )
    flow_forced = bool(
        re.search(
            r"\b(?:options\s+flow|unusual\s+options\s+activity|vol\s*/\s*oi)\b",
            q,
            re.I,
        )
    )

    if _OPTIONS_FLOW_TOPIC_RE.search(q) and (dc_ok or flow_forced):
        return INTENT_OPTIONS_FLOW_MARKET_SCAN
    if (_INSIDER_TOPIC_RE.search(q) or _INSIDER_SEC_RE.search(q)) and dc_ok:
        return INTENT_INSIDER_TRADES_MARKET_SCAN
    if _TREASURY_YIELD_TOPIC_RE.search(q) and dc_ok:
        return INTENT_TREASURY_YIELD_MARKET_SCAN
    if _CPI_INFLATION_TOPIC_RE.search(q) and dc_ok:
        return INTENT_CPI_INFLATION_MARKET_SCAN
    if _FED_TOPIC_RE.search(q) and dc_ok:
        return INTENT_FED_WATCH_MARKET_SCAN
    if _EARNINGS_TOPIC_RE.search(q) and dc_ok:
        return INTENT_EARNINGS_MARKET_SCAN
    if _FOREX_TOPIC_RE.search(q) and dc_ok:
        return INTENT_FOREX_MARKET_SCAN
    if _COMMODITIES_TOPIC_RE.search(q) and dc_ok:
        return INTENT_COMMODITIES_MARKET_SCAN
    if _SUPPLY_CHAIN_TOPIC_RE.search(q) and dc_ok:
        return INTENT_SUPPLY_CHAIN_MARKET_SCAN
    if _ENERGY_TOPIC_RE.search(q) and dc_ok:
        return INTENT_ENERGY_MARKET_SCAN
    if _CLIMATE_TOPIC_RE.search(q) and dc_ok:
        return INTENT_CLIMATE_RISK_MARKET_SCAN
    if _TARIFF_TOPIC_RE.search(q) and dc_ok:
        return INTENT_TARIFFS_MARKET_SCAN
    if _JOBS_TOPIC_RE.search(q) and dc_ok:
        return INTENT_JOBS_MARKET_SCAN
    if _CONGRESS_TRADES_TOPIC_RE.search(q) and dc_ok:
        return INTENT_CONGRESS_TRADES_MARKET_SCAN

    # Phase-2 extended routing (Tasks 4-12)
    if _DARK_POOL_TOPIC_RE.search(q):
        return INTENT_DARK_POOL_SCAN
    if _PENNY_STOCK_TOPIC_RE.search(q):
        return INTENT_PENNY_STOCK_SCAN
    if _REAL_ESTATE_TOPIC_RE.search(q):
        return INTENT_REAL_ESTATE_SCAN
    if _PERSONAL_WEALTH_TOPIC_RE.search(q):
        return INTENT_PERSONAL_WEALTH_SCAN
    if _TAX_LEGAL_TOPIC_RE.search(q):
        return INTENT_TAX_LEGAL_SCAN
    if _BUSINESS_TOPIC_RE.search(q):
        return INTENT_BUSINESS_SCAN
    if _ALTERNATIVE_ASSET_TOPIC_RE.search(q):
        return INTENT_ALTERNATIVE_ASSET_SCAN
    if _GLOBAL_LIQUIDITY_TOPIC_RE.search(q):
        return INTENT_GLOBAL_LIQUIDITY_SCAN
    if _MACRO_RISK_TOPIC_RE.search(q):
        return INTENT_MACRO_RISK_SCAN
    if _SECTOR_ROTATION_TOPIC_RE.search(q):
        return INTENT_SECTOR_ROTATION_SCAN
    if _SENTIMENT_DIVERGENCE_TOPIC_RE.search(q):
        return INTENT_SENTIMENT_DIVERGENCE_SCAN
    if _INTELLIGENCE_SYNTHESIS_TOPIC_RE.search(q):
        return INTENT_INTELLIGENCE_SYNTHESIS
    if _GROWTH_MARKETING_TOPIC_RE.search(q):
        return INTENT_GROWTH_MARKETING_SCAN

    return None


def _omega_price_from_text(text: str) -> Optional[float]:
    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)\b", text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _omega_normalize_rating(raw: Any) -> str:
    s = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if s in ("buy", "sell", "hold", "strong_buy"):
        return s
    if s in ("strongbuy",):
        return "strong_buy"
    return "hold"


def _normalize_omega_ui_contract(
    *,
    action_plan: list[Any],
    scenarios_in: list[Any],
    failure_modes_in: list[dict[str, Any]],
    headline: str,
    primary: str,
    overall_rating_raw: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], str]:
    """
    Ensure Omega-mapped responses match the same structural contract as the 10-loop
    for dashboard + evals: 5 execution_rules, 3 scenarios (probs sum to 1), 3 failure_modes.
    """
    headline = (headline or "Analysis complete").strip()
    primary = (primary or "").strip()

    # --- execution_rules (exactly 5) ---
    rules: list[dict[str, Any]] = []
    ap = action_plan if isinstance(action_plan, list) else []
    prio_cycle = ("critical", "high", "medium", "medium", "low")
    for step in ap:
        if len(rules) >= 5:
            break
        if not isinstance(step, dict):
            continue
        action = str(step.get("action", "")).strip()
        how = str(step.get("how", "")).strip()
        tf = str(step.get("timeframe", "")).strip()
        st = str(step.get("step", "")).strip()
        body = " — ".join(x for x in (action, how) if x)
        if not body:
            body = st or "Execute plan step"
        if tf:
            body = f"[{tf}] {body}"
        trig = _omega_price_from_text(f"{action} {how} {st}")
        rules.append({
            "type": "ACTION_STEP",
            "ticker": None,
            "trigger_price": trig,
            "direction": "n/a",
            "action": body[:500],
            "priority": prio_cycle[min(len(rules) - 1, 4)],
        })

    pad_templates: list[tuple[str, str]] = [
        (
            "REASSESS",
            f"Revisit thesis if key assumptions change — context: {headline[:100]}",
        ),
        (
            "CHECKPOINT",
            f"Schedule a decision checkpoint per primary recommendation: "
            f"{primary[:120] or headline[:120]}",
        ),
        (
            "DATA_REFRESH",
            "Re-run ATLAS if prices, rates, or tax rules move materially vs this snapshot.",
        ),
        (
            "RISK_REVIEW",
            "If volatility spikes or liquidity tightens, shrink size and widen margins of safety.",
        ),
        (
            "DOCUMENT",
            "Capture assumptions and numbers you relied on so the next review is apples-to-apples.",
        ),
    ]
    pi = 0
    while len(rules) < 5 and pi < len(pad_templates):
        typ, msg = pad_templates[pi]
        pi += 1
        rules.append({
            "type": typ,
            "ticker": None,
            "trigger_price": None,
            "direction": "n/a",
            "action": msg,
            "priority": "medium",
        })
    while len(rules) < 5:
        rules.append({
            "type": "FALLBACK",
            "ticker": None,
            "trigger_price": None,
            "direction": "n/a",
            "action": "Reassess plan against updated figures before sizing risk.",
            "priority": "low",
        })
    rules = rules[:5]

    # --- scenarios (exactly 3, probabilities sum to 1) ---
    labels = ("bull", "base", "bear")
    raw_scn: list[dict[str, Any]] = []
    for x in scenarios_in:
        if isinstance(x, dict):
            raw_scn.append(dict(x))
        if len(raw_scn) >= 3:
            break
    si = len(raw_scn)
    while len(raw_scn) < 3:
        raw_scn.append({
            "label": labels[si],
            "trigger": "Conditions evolve vs this analysis.",
            "outcome": headline[:220],
            "your_action": (primary or "Follow the action plan and reassess on new data.")[:220],
            "timeline": "",
        })
        si += 1
    raw_scn = raw_scn[:3]

    probs: list[float] = []
    for s in raw_scn:
        p = s.get("probability")
        ok = False
        try:
            if p is not None and p != "":
                fv = float(p)
                if fv >= 0.0:
                    probs.append(fv)
                    ok = True
        except (TypeError, ValueError):
            pass
        if not ok:
            probs.append(-1.0)

    if any(p < 0 for p in probs):
        probs = [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]
    else:
        ssum = sum(probs)
        if ssum <= 1e-9:
            probs = [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0]
        else:
            probs = [p / ssum for p in probs]

    scenarios_out: list[dict[str, Any]] = []
    for i, s in enumerate(raw_scn):
        row = dict(s)
        row["label"] = str(row.get("label") or labels[i])
        row["probability"] = round(probs[i], 4)
        row.setdefault("trigger", "")
        row.setdefault("outcome", "")
        row.setdefault("your_action", "")
        row.setdefault("timeline", "")
        scenarios_out.append(row)

    # --- failure_modes (exactly 3) ---
    fm = [dict(x) for x in failure_modes_in if isinstance(x, dict)][:3]
    while len(fm) < 3:
        fm.append({
            "mode": "Staleness / execution gap",
            "how_it_unfolds": "Personal situation or markets move faster than a static write-up.",
            "severity": "medium",
            "probability": 0.2,
            "tripwire": "Major change in rates, income, liquidity, or headline tape",
            "response": (
                primary or "Re-run ATLAS with updated numbers before allocating capital."
            )[:400],
            "timeline": "",
        })

    rating = _omega_normalize_rating(overall_rating_raw)
    return rules, scenarios_out, fm, rating


def _omega_report_to_query_envelope(
    omega_report: dict[str, Any],
    query_text: str,
    *,
    intent_route: str = INTENT_GENERAL_FINANCE,
    intent_summary_prefix: Optional[str] = None,
) -> dict[str, Any]:
    """Map Omega JSON into the same top-level shape as FourLoopEngine.run for the dashboard."""
    r = dict(omega_report)
    meta = r.get("_meta") if isinstance(r.get("_meta"), dict) else {}
    if r.get("error") and not r.get("headline"):
        return {}
    domain = r.get("domain") or meta.get("domain") or "general_finance"
    dom_tag = str(domain).upper().replace(" ", "_")
    brief = (r.get("executive_brief") or r.get("executive_summary") or "").strip()
    headline = (r.get("headline") or brief[:120] or "Analysis complete").strip()
    risks_raw = r.get("risks_and_tripwires") or []
    if not isinstance(risks_raw, list):
        risks_raw = []
    failure_modes: list[dict[str, Any]] = []
    for x in risks_raw[:6]:
        if not isinstance(x, dict):
            continue
        failure_modes.append({
            "mode": str(x.get("risk", "risk")),
            "how_it_unfolds": str(x.get("tripwire", "")),
            "severity": str(x.get("severity", "medium")).lower(),
            "probability": 0.25,
            "tripwire": str(x.get("tripwire", "")),
            "response": str(x.get("response", "")),
            "timeline": "",
        })
    scenarios = r.get("scenarios") if isinstance(r.get("scenarios"), list) else []
    action_plan = r.get("action_plan") if isinstance(r.get("action_plan"), list) else []
    primary_txt = str(r.get("primary_recommendation") or "").strip()
    exec_rules, scenarios_norm, failure_norm, rating = _normalize_omega_ui_contract(
        action_plan=action_plan,
        scenarios_in=scenarios,
        failure_modes_in=failure_modes,
        headline=headline,
        primary=primary_txt,
        overall_rating_raw=r.get("overall_rating") or r.get("rating"),
    )
    fuq = r.get("follow_up_questions")
    if not isinstance(fuq, list):
        fuq = []
    clar = r.get("clarification_questions")
    if isinstance(clar, list):
        cqs = [str(x).strip() for x in clar if str(x).strip()]
    else:
        cqs = [str(x).strip() for x in fuq if str(x).strip()]
    fr: dict[str, Any] = {
        "domain_tag": dom_tag,
        "query_type": "OMEGA_GENERAL",
        "headline": headline,
        "executive_summary": brief,
        "executive_brief": brief,
        "situation_analysis": r.get("situation_analysis"),
        "key_insight": r.get("key_insight"),
        "primary_recommendation": r.get("primary_recommendation"),
        "scenarios": scenarios_norm,
        "execution_rules": exec_rules,
        "numbers_that_matter": r.get("numbers_that_matter") if isinstance(r.get("numbers_that_matter"), dict) else {},
        "action_plan": r.get("action_plan") if isinstance(r.get("action_plan"), list) else [],
        "named_resources": r.get("named_resources") if isinstance(r.get("named_resources"), list) else [],
        "hidden_angles": r.get("hidden_angles") if isinstance(r.get("hidden_angles"), list) else [],
        "risks_and_tripwires": risks_raw,
        "failure_modes": failure_norm,
        "trade_plan": {
            "action": "avoid",
            "entry_price": None,
            "stop_loss": None,
            "target_1": None,
            "target_2": None,
            "hold_period": "n/a",
            "position_size_suggestion": "See primary_recommendation",
        },
        "options_play": {
            "recommended": False,
            "existing_position_analysis": "",
            "hold_roll_exit": "hold",
            "hold_roll_exit_reasoning": "",
            "iv_crush_estimate": "",
            "theta_per_day": None,
            "breakeven_price": None,
            "probability_of_profit": "",
            "best_contract": {},
            "alternative_contract": {},
        },
        "overall_rating": rating,
        "confidence": 5,
        "ticker": None,
        "company_name": None,
        "sector": None,
        "price_now": None,
        "bull_thesis": "",
        "bear_thesis": "",
        "catalysts_timeline": [],
        "key_risks": [],
        "price_levels": {},
        "earnings_analysis": {},
        "macro_connections": {},
        "analyst_consensus": {},
        "100x_potential": {"score": 1, "why": "", "realistic_upside": ""},
        "clarification_questions": cqs,
        "last_researched": datetime.now(timezone.utc).isoformat(),
    }
    total_t = float(meta.get("total_time_s", 0) or 0)
    intent_label = intent_summary_prefix if intent_summary_prefix else intent_route
    return {
        "query": query_text,
        "parsed_query": {
            "query_type": "OMEGA_GENERAL",
            "domain_tag": dom_tag,
            "tickers": [],
            "intent_summary": f"{intent_label}: {query_text[:140]}",
            "options_context": {},
            "confidence": 0.0,
            "urgency": r.get("urgency") or "normal",
            "intent_route": intent_route,
        },
        "final_report": fr,
        "tldr": headline[:220],
        "trader_memo": brief[:3500],
        "hedge_fund_brief": brief[:2500],
        "execution_rules": exec_rules,
        "failure_modes": failure_norm,
        "scenarios": scenarios_norm,
        "clarification_questions": cqs,
        "audit_notes": [],
        "loop_outputs": {
            "intent_route": intent_route,
            "omega": {"meta": meta, "domain": domain},
        },
        "timing": {
            "total": total_t,
            "intent_route": intent_route,
            "omega_fetch_s": meta.get("fetch_time_s"),
        },
    }

@dataclass
class ParsedQuery:
    raw: str
    query_type: str
    tickers: list[str]
    theme: str
    budget: float
    options_context: dict
    intent_summary: str
    entities: list[str]
    urgency: str
    confidence: float
    raw_metadata: dict = field(default_factory=dict)


class QueryParser:
    _TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")
    _STRIKE_RE = re.compile(
        r"\$?(\d{1,4}(?:\.\d{1,2})?)\s*(?:strike|call|put|c|p)\b", re.I
    )
    _EXPIRY_RE = re.compile(
        r"(?:expir(?:ing|y|es?)\s+)?"
        r"(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+\d{1,2}(?:,?\s*\d{4})?"
        r"|\d{1,2}/\d{1,2}(?:/\d{2,4})?"
        r"|\d{4}-\d{2}-\d{2})",
        re.I,
    )
    _BUDGET_RE = re.compile(r"\$(\d+(?:,\d{3})*(?:\.\d{2})?)\b")
    _STOPWORDS = {
        "A", "I", "MY", "ME", "IN", "ON", "AT", "TO", "UP", "OR", "AND", "FOR",
        "THE", "THIS", "THAT", "WITH", "FROM", "INTO", "WILL", "HAVE", "HAS",
        "ARE", "WAS", "IS", "IT", "DO", "HOW", "WHO", "WHY", "WHAT", "WHEN",
        "WHERE", "ANY", "ALL", "BY", "AN", "BE", "AS", "IF", "NO", "SO", "US",
        "CAN", "GET", "BUY", "SELL", "PUT", "NOW", "OWN", "HIT", "LOW", "HIGH",
        "CEO", "CFO", "IPO", "ETF", "SP", "IV", "DTE", "ATM", "OTM", "ITM",
        "RSI", "EPS", "PE", "AI", "ML", "YOY", "QOQ", "GDP", "CPI", "FED",
        "SEC", "FDA", "ESG", "SMA", "EMA", "VWAP", "ATH", "Q1", "Q2", "Q3", "Q4",
        "IM", "ONN", "TV", "AH", "USA", "API", "PDF", "HTML",
    }
    _INTENT_KEYWORDS: dict[str, list[tuple[str, float]]] = {
        "OPTIONS_ANALYSIS": [
            ("call", 2.0), ("put", 2.0), ("option", 2.0), ("strike", 2.5),
            ("expir", 2.0), ("iv crush", 3.0), ("theta", 2.0), ("roll", 2.0),
        ],
        "POSITION_ADVISOR": [
            ("should i", 2.5), ("hold or", 2.0), ("game plan", 2.5),
            ("what do i do", 3.0), ("my trade", 2.0),
        ],
        "EARNINGS_REVIEW": [
            ("earnings call", 3.0), ("after hours", 2.5), ("guidance", 2.0),
            ("beat", 2.0), ("miss", 2.0), ("tanked", 2.0),
        ],
        "EARNINGS_PREVIEW": [
            ("preview", 2.5), ("before earnings", 2.0), ("upcoming earnings", 2.5),
        ],
        "MACRO_ANALYSIS": [
            ("macro", 3.0), ("inflation", 2.0), ("fed", 1.5), ("recession", 2.0),
        ],
        "SECTOR_ROTATION": [
            ("sector rotation", 3.0), ("money flow", 2.5), ("inflow", 2.5),
        ],
        "THEMATIC_DISCOVERY": [
            ("best", 1.0), ("find", 1.5), ("stocks", 1.0), ("penny", 2.0),
            ("screen", 2.0),
        ],
        "CONCEPT_EXPLAINER": [
            ("what is", 2.5), ("explain", 3.0), ("how does", 2.5), ("define", 3.0),
        ],
        "STRATEGY_RESEARCH": [
            ("strategy", 2.0), ("futures", 2.0), ("liquidity", 2.0),
            ("deep dive on", 2.5),
        ],
        "TICKER_DEEP_DIVE": [
            ("deep dive", 3.0), ("analyze", 2.0), ("research", 2.0),
            ("fundamental", 2.0),
        ],
    }

    def parse(self, raw_query: str, client=None) -> ParsedQuery:
        q = raw_query.strip()
        q_lower = q.lower()
        candidates = self._TICKER_RE.findall(q)
        tickers = [t for t in candidates if t not in self._STOPWORDS and len(t) >= 2]
        seen: set[str] = set()
        tickers = [t for t in tickers if not (t in seen or seen.add(t))]  # type: ignore

        options_ctx: dict[str, Any] = {}
        strike_m = self._STRIKE_RE.search(q)
        if strike_m:
            options_ctx["strike"] = float(strike_m.group(1))
        expiry_m = self._EXPIRY_RE.search(q)
        if expiry_m:
            options_ctx["expiry_raw"] = expiry_m.group(0)
        if re.search(r"\bcall\b", q_lower):
            options_ctx["option_type"] = "call"
        elif re.search(r"\bput\b", q_lower):
            options_ctx["option_type"] = "put"
        opt_extras = extract_options_values_from_text(q)
        if opt_extras.get("avg_premium") is not None:
            options_ctx["avg_premium"] = opt_extras["avg_premium"]
        if opt_extras.get("current_mark") is not None:
            options_ctx["current_mark"] = opt_extras["current_mark"]
        if opt_extras.get("iv_pct") is not None:
            options_ctx["iv_pct"] = opt_extras["iv_pct"]

        budget = 100.0
        for bm in self._BUDGET_RE.findall(q):
            val = float(bm.replace(",", ""))
            if val > 50 or not options_ctx.get("strike"):
                budget = val
                break

        scores: dict[str, float] = {qt: 0.0 for qt in QUERY_TYPES}
        for qt, kws in self._INTENT_KEYWORDS.items():
            for kw, weight in kws:
                if kw in q_lower:
                    scores[qt] += weight
        if options_ctx.get("strike") and options_ctx.get("expiry_raw"):
            scores["OPTIONS_ANALYSIS"] += 3.0
            scores["POSITION_ADVISOR"] += 2.0
        if any(w in q_lower for w in ("today", "tonight", "after hours")):
            scores["EARNINGS_REVIEW"] += 2.0
        if len(tickers) == 1 and max(scores.values()) < 3.0:
            scores["TICKER_DEEP_DIVE"] += 2.5
        if not tickers:
            scores["THEMATIC_DISCOVERY"] += 1.5

        best_type = max(scores, key=lambda k: scores[k])
        confidence = min(1.0, scores[best_type] / 6.0)

        entities = list(tickers)
        for sw in (
            "semiconductor", "biotech", "energy", "tech", "ai", "crypto", "retail",
        ):
            if sw in q_lower:
                entities.append(sw)

        intent_summary = f"{best_type}: {q[:90]}"
        urgency = "standard"
        if any(w in q_lower for w in ("right now", "today", "tonight", "tomorrow")):
            urgency = "immediate"
        theme = q if not tickers else " ".join(
            w for w in q.split() if w.upper() not in self._STOPWORDS
        )

        return ParsedQuery(
            raw=q,
            query_type=best_type,
            tickers=tickers,
            theme=theme,
            budget=budget,
            options_context=options_ctx,
            intent_summary=intent_summary,
            entities=entities,
            urgency=urgency,
            confidence=round(confidence, 2),
        )


class FourLoopEngine:
    def __init__(self, client=None):
        self.client = client or self._init_client()
        self.parser = QueryParser()
        self._load_optional_modules()

    def _init_client(self):
        try:
            import google.genai as genai
            from google.genai.types import HttpOptions

            key = os.environ.get("GOOGLE_API_KEY", "")
            if not key:
                return None
            return genai.Client(
                api_key=key,
                http_options=HttpOptions(timeout=GEMINI_HTTP_TIMEOUT_MS),
            )
        except Exception:
            return None

    def _load_optional_modules(self):
        for name, attr in (
            ("memory", "_memory"),
            ("tracker", "_tracker"),
            ("volume_profile", "_vp"),
            ("sector_tracker", "_sector"),
            ("congress_tracker", "_congress"),
            ("market_scanner", "_market_scanner"),
            ("rag_engine", "_rag"),
            ("auto_tuner", "_auto_tuner"),
        ):
            try:
                setattr(self, attr, importlib.import_module(name))
                setattr(self, f"{attr}_ok", True)
            except ImportError:
                setattr(self, attr, None)
                setattr(self, f"{attr}_ok", False)
        try:
            self._scraper = importlib.import_module("web_scraper")
            self._scraper_ok = True
        except ImportError:
            self._scraper = None
            self._scraper_ok = False

    def loop1_scrape(self, parsed: ParsedQuery) -> dict:
        result = {
            "loop": 1,
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query_type": parsed.query_type,
            "tickers": parsed.tickers,
            "scrape_data": {},
            "raw_context_text": "",
        }
        if parsed.tickers and self._scraper_ok:
            for ticker in parsed.tickers[:3]:
                try:
                    log.info("[Loop1] gather_all %s", ticker)
                    out = self._scraper.gather_all(ticker)
                    result["scrape_data"][ticker] = out
                    result["raw_context_text"] += (
                        f"\n\n=== {ticker} ===\n{out.get('context_text','')}"
                    )
                except Exception as e:
                    log.warning("[Loop1] scrape failed %s: %s", ticker, e)

        if parsed.query_type in ("MACRO_ANALYSIS", "SECTOR_ROTATION"):
            theme_l = parsed.theme.lower()
            etfs = ["SPY", "QQQ", "IWM"]
            if "semi" in theme_l or "chip" in theme_l:
                etfs = ["SOXX", "SMH", "XLK"]
            elif "energy" in theme_l:
                etfs = ["XLE", "VDE", "OIH"]
            for etf in etfs[:3]:
                if self._scraper_ok:
                    try:
                        out = self._scraper.gather_all(etf)
                        result["scrape_data"][etf] = out
                        result["raw_context_text"] += (
                            f"\n\n=== ETF {etf} ===\n{out.get('context_text','')[:4000]}"
                        )
                    except Exception:
                        pass

        if parsed.tickers and self._market_scanner_ok:
            t = parsed.tickers[0]
            try:
                aw = self._market_scanner.full_awareness(
                    t, scrape_data=result["scrape_data"].get(t), news_items=None
                )
                result["awareness_data"] = aw
                result["raw_context_text"] += (
                    "\n\n=== AWARENESS ===\n" + aw.get("context_text", "")
                )
            except Exception as e:
                log.debug("[Loop1] awareness: %s", e)

        if (not parsed.tickers) and self._market_scanner_ok:
            try:
                proxy = "SPY"
                if proxy not in result["scrape_data"] and self._scraper_ok:
                    try:
                        out = self._scraper.gather_all(proxy)
                        result["scrape_data"][proxy] = out
                        result["raw_context_text"] += (
                            f"\n\n=== {proxy} (macro regime proxy) ===\n"
                            + out.get("context_text", "")[:4000]
                        )
                    except Exception as e:
                        log.debug("[Loop1] SPY proxy scrape: %s", e)
                sd = result["scrape_data"].get(proxy)
                aw = self._market_scanner.full_awareness(
                    proxy, scrape_data=sd, news_items=None
                )
                result["awareness_data"] = aw
                result["raw_context_text"] += (
                    "\n\n=== AWARENESS ===\n" + aw.get("context_text", "")
                )
            except Exception as e:
                log.debug("[Loop1] awareness SPY fallback: %s", e)

        if parsed.query_type == "THEMATIC_DISCOVERY" and self._scraper_ok:
            seeds = list(parsed.tickers) if parsed.tickers else _omega_thematic_symbols(parsed.raw)
            for ticker in seeds[:6]:
                if ticker in result["scrape_data"]:
                    continue
                try:
                    log.info("[Loop1] thematic gather_all %s", ticker)
                    out = self._scraper.gather_all(ticker)
                    result["scrape_data"][ticker] = out
                    result["raw_context_text"] += (
                        f"\n\n=== {ticker} ===\n{out.get('context_text', '')[:5000]}"
                    )
                except Exception as e:
                    log.warning("[Loop1] thematic scrape failed %s: %s", ticker, e)
            if self._market_scanner_ok:
                try:
                    import market_scanner as ms

                    result["market_regime"] = ms.get_market_regime()
                    result["raw_context_text"] += (
                        "\n\n=== MARKET_REGIME ===\n"
                        + json.dumps(result["market_regime"], default=str)[:2500]
                    )
                except Exception as e:
                    log.debug("[Loop1] regime: %s", e)

        return result

    def loop2_factcheck(self, loop1_out: dict, parsed: ParsedQuery) -> dict:
        text = loop1_out.get("raw_context_text", "")
        lines = []
        for line in text.split("\n"):
            tag = ""
            if re.search(
                r"(?i)\b(rumor|reportedly|unconfirmed|could be|might be)\b", line
            ):
                tag = " [UNVERIFIED]"
            lines.append(line + tag)
        verified = "\n".join(lines)
        if loop1_out.get("awareness_data"):
            verified += "\n\n=== LIVE METRICS (scanner) ===\n"
            verified += loop1_out["awareness_data"].get("context_text", "")[:6000]
        return {
            "loop": 2,
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "verified_context": verified,
        }

    def loop3_synthesize(self, loop2_out: dict, loop1_out: dict, parsed: ParsedQuery) -> dict:
        if not self.client:
            return {"loop": 3, "status": "error", "error": "No GOOGLE_API_KEY / client"}
        ticker = parsed.tickers[0] if parsed.tickers else None
        today = datetime.now(timezone.utc).strftime("%B %d, %Y")
        satellite: dict[str, Any] = {}

        if ticker and self._memory_ok:
            try:
                satellite["memory"] = self._memory.build_ai_context(ticker=ticker)
            except Exception:
                pass
        if ticker and self._tracker_ok:
            try:
                scrape = loop1_out["scrape_data"].get(ticker)
                satellite["patterns"] = self._tracker.pattern_context_for_research(
                    {"ticker": ticker, "budget": parsed.budget, "synthesis": {}},
                    scrape,
                )
            except Exception:
                pass
        if ticker and self._vp_ok:
            try:
                vp = self._vp.calculate_volume_profile(ticker, lookback_days=30)
                if vp and not vp.get("error"):
                    vp_payload = {
                        k: vp.get(k)
                        for k in (
                            "ticker",
                            "lookback_days",
                            "poc",
                            "vah",
                            "val",
                            "vwap",
                            "hvn",
                            "lvn",
                            "current_price",
                            "interpretation",
                        )
                        if vp.get(k) is not None
                    }
                    satellite["volume_profile"] = vp_payload
            except Exception:
                pass
        if ticker and self._congress_ok:
            try:
                c = self._congress.get_trades_for_ticker(ticker, days_back=180)
                satellite["congress"] = c.get("context_text", "")
                if c.get("trades"):
                    satellite["congress_trades_json"] = json.dumps(
                        c.get("trades", [])[:10], default=str
                    )[:6000]
            except Exception:
                pass
        if ticker and self._sector_ok:
            try:
                satellite["sector"] = self._sector.sector_wind(ticker)
            except Exception:
                pass
        if ticker and self._rag_ok:
            try:
                satellite["rag"] = self._rag.get_rag_context(ticker, auto_ingest=True)
            except Exception:
                pass
        if self._auto_tuner_ok:
            try:
                cfg = self._auto_tuner.get_current_config()
                if not cfg.get("defaults_active"):
                    satellite["tuner"] = str(cfg.get("weights", {}))[:500]
            except Exception:
                pass

        def _fmt_sat_val(v: Any) -> str:
            if isinstance(v, (dict, list)):
                return json.dumps(v, indent=2, default=str)[:12000]
            return str(v)

        sat_text = "\n\n".join(
            f"=== {k.upper()} ===\n{_fmt_sat_val(v)}"
            for k, v in satellite.items()
            if v is not None and str(v).strip()
        )
        opts = parsed.options_context
        options_hint = ""
        if opts:
            options_hint = f"""
=== USER OPTIONS POSITION ===
Ticker: {ticker} | Type: {opts.get('option_type')} | Strike: {opts.get('strike')}
Expiry: {opts.get('expiry_raw')} | Avg cost / premium per share: {opts.get('avg_premium')}
Current mark (if stated): {opts.get('current_mark')} | IV % (if stated): {opts.get('iv_pct')}
"""
        verified = loop2_out.get("verified_context", "")[:12000]
        squeeze = 0
        regime = "unknown"
        if loop1_out.get("awareness_data"):
            squeeze = loop1_out["awareness_data"].get("squeeze", {}).get("score", 0)
            regime = loop1_out["awareness_data"].get("regime", {}).get("regime", "?")

        return {
            "loop": 3,
            "status": "context_only",
            "synthesis": {},
            "satellite_context": satellite,
            "_satellite_text_for_batch": sat_text,
            "_batch_aux": {
                "verified_excerpt": verified,
                "options_hint": options_hint,
                "squeeze": squeeze,
                "regime": regime,
                "today": today,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def loop_batch_synthesize(
        self,
        parsed: ParsedQuery,
        loop1_out: dict,
        loop2_out: dict,
        loop3_out: dict,
        loop5_out: dict,
        loop8_out: dict,
        finance_kb_block: str = "",
    ) -> dict:
        """
        ONE Gemini call — formerly Loops 3 (synthesis), 4 (macro enrich), 7 (scenarios),
        9 (adversarial), and 10 (narrative). Keeps free-tier quota usage minimal.
        """
        ts = datetime.now(timezone.utc).isoformat()
        if not self.client:
            return {
                "loop": "batch_3_10",
                "status": "error",
                "error": "no_client",
                "final_report": {
                    "error": "No GOOGLE_API_KEY / client",
                    "executive_summary": "Configure GOOGLE_API_KEY to run batched analysis.",
                },
                "timestamp": ts,
            }

        ticker = parsed.tickers[0] if parsed.tickers else None
        aux = loop3_out.get("_batch_aux") or {}
        today = aux.get("today") or datetime.now(timezone.utc).strftime("%B %d, %Y")
        sat_text = loop3_out.get("_satellite_text_for_batch") or ""
        verified = (aux.get("verified_excerpt") or loop2_out.get("verified_context", ""))[:12000]
        options_hint = aux.get("options_hint") or ""
        squeeze = aux.get("squeeze", 0)
        regime = aux.get("regime", "?")

        pers_ctx = loop5_out.get("context") or {}
        portfolio_risk = (loop5_out.get("portfolio_risk_prompt") or "").strip()
        rep8 = dict(loop8_out.get("final_report") or {})
        regime_memory = {
            k: rep8[k]
            for k in rep8
            if k.startswith("_regime") or k.startswith("_historical")
        }

        pers_blob = json.dumps(pers_ctx, indent=2, default=str)[:8000]
        regime_blob = json.dumps(regime_memory, indent=2, default=str)[:6000]
        portfolio_blob = (portfolio_risk or "")[:14000]

        kb_raw = (finance_kb_block or "").strip()
        if kb_raw:
            finance_kb_section = f"""
=== INTERNAL KNOWLEDGE BASE (indexed from rag_ingest/ — whitepapers and notes; NOT SEC EDGAR) ===
{kb_raw}

When you use facts from INTERNAL KNOWLEDGE BASE, cite the source_path shown for each passage using an inline tag [KB: <source_path>] in executive_summary, trader_memo, key_risks, and/or bull_thesis / bear_thesis as appropriate. Do not confuse this material with SEC filing RAG or live market data. If this block is irrelevant, ignore it entirely.
"""
        else:
            finance_kb_section = ""

        query_type = parsed.query_type
        concept_mode = query_type == "CONCEPT_EXPLAINER"
        macro_instruction = (
            "Fill macro_connections with supply_chain_links, competitor_movements, "
            "sector_rotation_impact, plus optional macro_triggers and hidden_catalyst strings."
            if not concept_mode
            else "Provide brief macro_connections anyway (may be general market context)."
        )

        # Detect output format based on what was actually asked
        _q_lower = parsed.raw.lower()
        _is_trade_query = any(w in _q_lower for w in [
            "trade", "setup", "entry", "options", "calls", "puts",
            "buy signal", "sell signal", "short", "position size",
            "stop loss", "target price", "entry price"
        ])
        _is_personal = any(w in _q_lower for w in [
            " i ", " my ", " me ", " i'm ", " should i ", " can i ",
            " how do i ", " what should i ", " am i ", " will i "
        ])
        _has_ticker = bool(parsed.tickers)
        # Format rules:
        # - Ticker + trade keywords → TRADING format (default)
        # - Personal question → ADVICE format
        # - General research (deep mode or company/topic) → RESEARCH format
        if _is_personal:
            _output_format = "ADVICE"
        elif _has_ticker and _is_trade_query:
            _output_format = "TRADING"
        elif not _has_ticker or (not _is_trade_query):
            _output_format = "RESEARCH"
        else:
            _output_format = "TRADING"

        _format_instruction = {
            "TRADING": """OUTPUT FORMAT: TRADING ANALYSIS
You are a senior trader. Provide a full trading analysis with specific entry/exit levels,
trade plan, execution rules, failure modes, and scenarios.
All fields in the JSON schema are required including trade_plan, options_play, price_levels.""",
            "RESEARCH": """OUTPUT FORMAT: DEEP RESEARCH REPORT
You are a senior analyst. The user wants comprehensive research, NOT a trading report.
Focus on: thorough overview, business model, financials, recent developments, opportunities, risks.
For trade_plan use: action="N/A - research query", entry_price=null, stop_loss=null, targets=null.
For tldr: summarize the most important finding in plain English (not "buy/sell").
For trader_memo: write a research brief, not a trading memo.
For scenarios: describe outcome scenarios for the topic/company, not price targets.""",
            "ADVICE": """OUTPUT FORMAT: PERSONAL FINANCE ADVICE
You are a personal finance advisor. The user is asking for advice about their situation.
Focus on: their specific situation, options available, recommended action, risks, next steps.
For trade_plan: use action="N/A - personal finance" with null prices.
For scenarios: describe financial outcome scenarios based on their choices.
For trader_memo: write clear plain-English advice they can act on.""",
        }[_output_format]

        prompt = f"""You are ATLAS — senior financial analyst. Today is {today}.
Return ONE valid JSON object only (no markdown fences). Python has already gathered data; you interpret and structure it.

{_format_instruction}

QUALITY AND DEPTH (non-negotiable):
Do not sacrifice quality or detail for brevity. You are an institutional analyst. Provide exhaustive, hedge-fund-level deep dives for every section, particularly the "scenarios", "trader_memo", and "failure_modes". Take as many tokens as necessary to produce a flawless, comprehensive analysis. Use long, specific JSON string values wherever substance demands it.

QUERY_TYPE: {query_type}
INTENT: {parsed.intent_summary}
URGENCY: {parsed.urgency}

=== SATELLITE CONTEXT (volume profile, congress, memory, sector — use in levels & risks) ===
{sat_text}

{options_hint}

=== VERIFIED SCRAPE / SCANNER TEXT ===
{verified}

=== LIVE METRICS ===
Squeeze score: {squeeze}/100 | Regime: {regime}

=== USER PORTFOLIO & RISK CONTEXT (Loop 5 — authoritative; personalize outputs) ===
{portfolio_blob}

=== PERSONALIZATION JSON (same Loop 5 data; structured — use with narrative block above) ===
{pers_blob}

=== REGIME MEMORY (past ATLAS calls / DB — reference in thesis if relevant) ===
{regime_blob}
{finance_kb_section}
You MUST explicitly use VOLUME_PROFILE (POC/VAH/VAL/VWAP/HVN/LVN) and CONGRESSIONAL / insider context when present in SATELLITE CONTEXT above.

PORTFOLIO-AWARE OUTPUTS (mandatory when USER PORTFOLIO section has positions or tracker stats):
- You have the user's current book (stocks/options), paper/simulated trades, and historical ATLAS tracker performance (win rates, best/worst, risk flags).
- trader_memo MUST explicitly reference other open tickers or concentration when relevant (e.g. user asks about TSLA but holds SOUN — acknowledge SOUN exposure and how the new thesis fits total risk).
- execution_rules SHOULD reflect this profile: e.g. if sector concentration or tech-heavy book is flagged, add/adjust rules about trimming correlated risk or staggering exits; if options win rate in tracker is weak, tighten stops or favor partial profits.
- trade_plan.position_size_suggestion and key_risk bullets should mention portfolio-level implications when data supports it.

{macro_instruction}

Include exactly 3 scenarios (bull, base, bear) with probabilities summing to 1.0 triggers, outcomes, your_action, timeline.

Include exactly 3 failure_modes (mechanistic, observable tripwire, response, severity, probability).

Include thesis_resilience_score (1-10) and resilience_note.

Include trader_memo (plain English; as detailed as a desk memo requires — not limited to a short sentence count), hedge_fund_brief (pipe format as before), tldr (max 15 words).

CRITICAL — NEVER ABORT; ASSUME AND PROCEED:
- If premium per share, strike, expiration, IV, or other details are missing or ambiguous, DO NOT refuse, stop, or output only questions/warnings.
- Make reasonable assumptions from the user query + VERIFIED DATA + options hints; state them in executive_summary under a brief "Assumptions:" lead-in.
- Populate clarification_questions with 1-2 specific follow-ups the user could answer next time (or use an empty array if none).
- You MUST still output the FULL JSON object with every required field below (including tldr, scenarios, trader_memo, failure_modes, options_play, trade_plan).

JSON schema (all top-level keys required; use null where unknown):
{{
  "query_type": "{query_type}",
  "ticker": {json.dumps(ticker)},
  "company_name": "<string>",
  "sector": "<string>",
  "overall_rating": "strong_buy | buy | hold | sell | strong_sell",
  "confidence": <1-10>,
  "price_now": <number or null>,
  "executive_summary": "<string>",
  "bull_thesis": "<string>",
  "bear_thesis": "<string>",
  "trade_plan": {{"action": "hold | buy_stock | sell | exit | roll | avoid", "entry_price": null, "stop_loss": null, "target_1": null, "target_2": null, "hold_period": "<string>", "position_size_suggestion": "<string>"}},
  "options_play": {{"recommended": false, "existing_position_analysis": "<string>", "hold_roll_exit": "hold | roll | exit", "hold_roll_exit_reasoning": "<string>", "iv_crush_estimate": "<string>", "theta_per_day": null, "breakeven_price": null, "probability_of_profit": "<string>", "best_contract": {{}}, "alternative_contract": {{}} }},
  "catalysts_timeline": [{{"date": "<string>", "event": "<string>", "impact": "high|medium|low", "direction": "bullish|bearish|neutral"}}],
  "key_risks": [{{"risk": "<string>", "severity": "high|medium|low", "mitigation": "<string>"}}],
  "price_levels": {{"immediate_support": null, "strong_support": null, "immediate_resistance": null, "strong_resistance": null, "volume_poc": null}},
  "earnings_analysis": {{"what_happened": "<string>", "revenue_actual": null, "guidance_raised": null, "market_reaction": "<string>", "next_date": "<string>"}},
  "macro_connections": {{"supply_chain_links": "<string>", "competitor_movements": "<string>", "sector_rotation_impact": "<string>", "macro_triggers": "<string>", "hidden_catalyst": "<string>"}},
  "analyst_consensus": {{"rating": "<string>", "avg_target": null, "count": null}},
  "100x_potential": {{"score": 1, "why": "<string>", "realistic_upside": "<string>"}},
  "scenarios": [
    {{"label": "bull", "probability": 0.0, "trigger": "<string>", "outcome": "<string>", "your_action": "<string>", "timeline": "<string>"}},
    {{"label": "base", "probability": 0.0, "trigger": "<string>", "outcome": "<string>", "your_action": "<string>", "timeline": "<string>"}},
    {{"label": "bear", "probability": 0.0, "trigger": "<string>", "outcome": "<string>", "your_action": "<string>", "timeline": "<string>"}}
  ],
  "failure_modes": [
    {{"mode": "<string>", "how_it_unfolds": "<string>", "severity": "critical", "probability": 0.0, "tripwire": "<string>", "response": "<string>", "timeline": "<string>"}},
    {{"mode": "<string>", "how_it_unfolds": "<string>", "severity": "high", "probability": 0.0, "tripwire": "<string>", "response": "<string>", "timeline": "<string>"}},
    {{"mode": "<string>", "how_it_unfolds": "<string>", "severity": "medium", "probability": 0.0, "tripwire": "<string>", "response": "<string>", "timeline": "<string>"}}
  ],
  "thesis_resilience_score": 5,
  "resilience_note": "<string>",
  "trader_memo": "<string>",
  "hedge_fund_brief": "<string>",
  "tldr": "<string>",
  "clarification_questions": [],
  "last_researched": "{ts}"
}}
Use only numbers from context; otherwise say unknown or null."""

        try:
            import google.genai.types as gtypes

            model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
            wait_for_slot("query_router_batch_3_10")
            resp = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=gtypes.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                    max_output_tokens=16384,
                ),
            )
            data = _json_loads_llm_output(resp.text or "")
        except Exception as e:
            if is_rate_limit_error(e):
                log.warning("[Batch LLM] Rate limit: %s", e)
                raise GeminiQuotaExceededError(RATE_LIMIT_USER_MESSAGE) from e
            log.warning("[Batch LLM] Failed: %s", e)
            return {
                "loop": "batch_3_10",
                "status": "error",
                "error": str(e),
                "final_report": {
                    "error": str(e),
                    "executive_summary": str(e)[:400],
                },
                "timestamp": ts,
            }

        report = dict(data)
        cq_raw = report.get("clarification_questions")
        if cq_raw is None:
            report["clarification_questions"] = []
        elif isinstance(cq_raw, list):
            report["clarification_questions"] = [
                str(x).strip() for x in cq_raw if str(x).strip()
            ]
        else:
            s = str(cq_raw).strip()
            report["clarification_questions"] = [s] if s else []
        tr_score = report.pop("thesis_resilience_score", None)
        tr_note = report.pop("resilience_note", None)
        if tr_score is not None or tr_note is not None:
            report["_thesis_resilience"] = {"score": tr_score, "note": tr_note}
        report["_batch_llm_timestamp"] = ts
        log.info("[Batch LLM] Complete — rating=%s", report.get("overall_rating", "?"))
        return {
            "loop": "batch_3_10",
            "status": "ok",
            "final_report": report,
            "timestamp": ts,
        }

    def loop4_python_trade_plan_audit(self, report: dict) -> dict:
        """Loop 4 — Python-only trade_plan sanity checks on batched model output."""
        syn = dict(report)
        if not syn or syn.get("error"):
            return {
                "loop": 4,
                "status": "passthrough",
                "final_report": syn,
                "audit_notes": ["No structured report to audit"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        notes: list[str] = []
        tp = syn.get("trade_plan") or {}
        entry, stop, t1 = tp.get("entry_price"), tp.get("stop_loss"), tp.get("target_1")
        try:
            if entry and stop and t1 and float(stop) > float(entry):
                tp["stop_loss"] = round(float(entry) * 0.9, 2)
                notes.append("Adjusted stop_loss below entry")
            if entry and t1 and float(t1) < float(entry):
                tp["target_1"] = round(float(entry) * 1.15, 2)
                notes.append("Adjusted target above entry")
        except (TypeError, ValueError):
            pass
        syn["trade_plan"] = tp
        syn["_audit_notes"] = notes
        return {
            "loop": 4,
            "status": "ok",
            "final_report": syn,
            "audit_notes": notes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def loop5_personalize(
        self, loop4_out: dict, parsed: ParsedQuery, user_id: Optional[str] = None
    ) -> dict:
        """
        Loop 5 — Personalization Engine
        Loads open positions (Supabase when user_id is set, file cache when user_id is None,
        empty portfolio when user_id is test_user_local), paper_trades.json, atlas_tracker.db via
        atlas_personalization.build_personalization_bundle. Injects a narrative
        portfolio + risk block into the batched LLM (see portfolio_risk_prompt).
        """
        report = dict(loop4_out.get("final_report", {}))
        base = Path(__file__).parent
        bundle = build_personalization_bundle(base, user_id=user_id)
        ctx = bundle["context"]
        report["_personalization"] = bundle["report_personalization_meta"]
        portfolio_risk_prompt = bundle["portfolio_risk_prompt"]

        if parsed.tickers and ctx.get("positions"):
            ticker = parsed.tickers[0].upper()
            matching = [
                p for p in ctx["positions"]
                if p.get("ticker", "").upper() == ticker
            ]
            if matching:
                pos = matching[0]
                tp = report.get("trade_plan") or {}
                if pos.get("_type") == "option":
                    note = (
                        f"YOUR OPEN POSITION: "
                        f"{pos.get('option_type', 'call').upper()} "
                        f"${pos.get('strike', '?')} exp {pos.get('expiry', '?')} | "
                        f"{pos.get('contracts', 1)} contract(s) @ "
                        f"${pos.get('avg_premium', '?')}/share avg cost"
                    )
                else:
                    note = (
                        f"YOUR OPEN POSITION: {pos.get('shares', '?')} shares @ "
                        f"${pos.get('avg_buy_price', '?')} avg cost"
                    )
                tp["personalization_note"] = note
                report["trade_plan"] = tp

        report["_loop5_timestamp"] = datetime.now(timezone.utc).isoformat()
        log.info(
            "[Loop5] Personalization — %d positions, %d paper, tracker rows=%s",
            len(ctx.get("positions") or []),
            len(ctx.get("paper_trades") or []),
            bundle.get("tracker_summary", {}).get("row_count", 0),
        )
        return {
            "loop": 5,
            "status": "ok",
            "final_report": report,
            "context": ctx,
            "portfolio_risk_prompt": portfolio_risk_prompt,
            "tracker_summary": bundle.get("tracker_summary") or {},
        }

    def loop6_execution_timing(self, loop5_out: dict, parsed: ParsedQuery) -> dict:
        """
        Loop 6 — Execution Timing Engine
        Converts analysis into specific conditional entry/exit rules with price
        triggers. Auto-registers rules with alerts.py so the system monitors
        them automatically. Zero AI cost — pure Python rule generation.
        """
        report = dict(loop5_out.get("final_report", {}))
        rules: list[dict] = []
        ticker = parsed.tickers[0].upper() if parsed.tickers else None

        if ticker:
            price_levels = report.get("price_levels") or {}
            tp            = report.get("trade_plan")   or {}
            op            = report.get("options_play") or {}

            support    = price_levels.get("immediate_support")
            resistance = price_levels.get("immediate_resistance")
            target1    = tp.get("target_1")
            target2    = tp.get("target_2")
            stop       = tp.get("stop_loss")
            entry      = tp.get("entry_price")
            action     = tp.get("action", "hold")

            if stop:
                rules.append({
                    "type": "STOP_LOSS", "ticker": ticker,
                    "trigger_price": stop, "direction": "below",
                    "action": f"Exit position — stop loss triggered at ${stop}",
                    "priority": "critical",
                })
            if entry and action in ("buy_stock", "buy_calls", "buy_puts"):
                rules.append({
                    "type": "ENTRY", "ticker": ticker,
                    "trigger_price": entry, "direction": "at_or_below",
                    "action": f"Consider entry — {action} at ${entry}",
                    "priority": "high",
                })
            if target1:
                rules.append({
                    "type": "TARGET_1", "ticker": ticker,
                    "trigger_price": target1, "direction": "above",
                    "action": f"Target 1 reached ${target1} — take partial or full profit",
                    "priority": "high",
                })
            if target2:
                rules.append({
                    "type": "TARGET_2", "ticker": ticker,
                    "trigger_price": target2, "direction": "above",
                    "action": f"Target 2 reached ${target2} — reassess and trail stop",
                    "priority": "medium",
                })
            if support:
                rules.append({
                    "type": "SUPPORT_BREAK", "ticker": ticker,
                    "trigger_price": support, "direction": "below",
                    "action": f"Support at ${support} broken — reassess thesis immediately",
                    "priority": "high",
                })

            hold_roll = op.get("hold_roll_exit")
            if hold_roll and parsed.options_context.get("expiry_raw"):
                rules.append({
                    "type": "OPTIONS_DEADLINE", "ticker": ticker,
                    "trigger_price": None, "direction": "time",
                    "action": f"Options expiry approaching — ATLAS says: {hold_roll.upper()}",
                    "expiry": parsed.options_context.get("expiry_raw"),
                    "priority": "critical",
                })

            try:
                import alerts as _alerts
                registered = 0
                for rule in rules:
                    if rule.get("trigger_price") and hasattr(_alerts, "add_price_alert"):
                        _alerts.add_price_alert(
                            ticker=rule["ticker"],
                            price=rule["trigger_price"],
                            direction=rule["direction"],
                            message=rule["action"],
                        )
                        registered += 1
                if registered:
                    log.info("[Loop6] Registered %d price alerts with alerts.py", registered)
            except Exception as e:
                log.debug("[Loop6] Alert registration skipped: %s", e)

        report["execution_rules"] = rules
        report["_loop6_timestamp"] = datetime.now(timezone.utc).isoformat()
        log.info("[Loop6] %d conditional execution rules generated", len(rules))
        return {"loop": 6, "status": "ok", "final_report": report, "rules": rules}

    def loop7_probabilistic_scenarios(self, loop6_out: dict,
                                       parsed: ParsedQuery) -> dict:
        """
        Loop 7 — Scenario EV (Python only).
        Scenarios are produced by loop_batch_synthesize. This step computes
        expected value (EV%) from weighted scenarios when entry_price exists.
        """
        report = dict(loop6_out.get("final_report", {}))
        existing = report.get("scenarios") or []

        probs_present = (
            len(existing) >= 3 and
            all(
                isinstance(s.get("probability"), (int, float)) and
                s.get("probability", 0) > 0
                for s in existing
            )
        )

        if probs_present:
            log.info("[Loop7] Scenarios already complete — calculating EV only")

        try:
            entry = float((report.get("trade_plan") or {}).get("entry_price") or 0)
            if entry and existing:
                ev = 0.0
                for s in existing:
                    prob        = float(s.get("probability", 0))
                    outcome_str = str(s.get("outcome", ""))
                    pct_m = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%', outcome_str)
                    px_m  = re.search(r'\$(\d+(?:\.\d+)?)', outcome_str)
                    if pct_m:
                        ev += prob * float(pct_m.group(1))
                    elif px_m:
                        ev += prob * ((float(px_m.group(1)) - entry) / entry * 100)
                report["_ev_pct"] = round(ev, 2)
                log.info("[Loop7] Expected value: %+.1f%%", ev)
        except Exception:
            pass

        report["_loop7_timestamp"] = datetime.now(timezone.utc).isoformat()
        return {"loop": 7, "status": "ok", "final_report": report}

    def loop8_regime_memory(self, loop5_out: dict, parsed: ParsedQuery) -> dict:
        """
        Loop 8 — Regime Memory & Historical Analogue Engine
        Searches atlas_tracker.db for past calls on this ticker and for all
        past calls with this same rating type. Reports win rates and analogues.
        Searches atlas_memory.db for permanent memories about this ticker.
        Zero AI cost — pure SQLite queries. Builds the ATLAS data moat.
        """
        import sqlite3
        report     = dict(loop5_out.get("final_report", {}))
        base       = Path(__file__).parent
        analogues: list[dict] = []
        regime_note = ""
        ticker = parsed.tickers[0].upper() if parsed.tickers else None
        rating = report.get("overall_rating", "")
        similar: list[Any] = []

        try:
            db = base / "atlas_tracker.db"
            if db.exists():
                conn = sqlite3.connect(str(db))
                try:
                    rows = conn.execute(
                        "SELECT ticker, rating, confidence, pnl_pct, created_at, setup_tags "
                        "FROM recommendations "
                        "WHERE ticker = ? AND pnl_pct IS NOT NULL "
                        "ORDER BY created_at DESC LIMIT 10",
                        (ticker,)
                    ).fetchall() if ticker else []

                    if rows:
                        wins   = [r for r in rows if (r[3] or 0) > 0]
                        losses = [r for r in rows if (r[3] or 0) < 0]
                        avg_pnl = sum(r[3] for r in rows if r[3]) / len(rows)
                        regime_note = (
                            f"ATLAS history on {ticker}: {len(rows)} past calls — "
                            f"{len(wins)}W / {len(losses)}L / avg P&L {avg_pnl:+.1f}%"
                        )
                        analogues = [
                            {
                                "ticker": r[0], "rating": r[1],
                                "confidence": r[2], "pnl_pct": r[3],
                                "date": r[4], "setup_tags": r[5],
                            }
                            for r in rows[:5]
                        ]

                    similar = conn.execute(
                        "SELECT ticker, rating, pnl_pct, setup_tags "
                        "FROM recommendations "
                        "WHERE rating = ? AND pnl_pct IS NOT NULL LIMIT 20",
                        (rating,)
                    ).fetchall() if rating else []

                finally:
                    conn.close()

                if similar:
                    wins_s = [r for r in similar if (r[2] or 0) > 0]
                    wr = round(len(wins_s) / len(similar) * 100, 1)
                    report["_regime_win_rate_same_rating"] = {
                        "rating": rating,
                        "sample_size": len(similar),
                        "win_rate_pct": wr,
                        "note": (
                            f"ATLAS has rated {rating} {len(similar)} times — "
                            f"won {wr}% of the time historically"
                        ),
                    }
        except Exception as e:
            log.debug("[Loop8] Tracker query failed: %s", e)

        try:
            mem_db = base / "atlas_memory.db"
            if mem_db.exists() and ticker:
                conn = sqlite3.connect(str(mem_db))
                try:
                    mem_rows = conn.execute(
                        "SELECT memory_type, content, confidence, created_at "
                        "FROM memories "
                        "WHERE ticker = ? AND tier = 'permanent' "
                        "ORDER BY created_at DESC LIMIT 5",
                        (ticker,)
                    ).fetchall()
                finally:
                    conn.close()
                if mem_rows:
                    report["_historical_memory"] = [
                        {
                            "type": r[0],
                            "content": r[1][:200],
                            "confidence": r[2],
                            "date": r[3],
                        }
                        for r in mem_rows
                    ]
        except Exception as e:
            log.debug("[Loop8] Memory db query failed: %s", e)

        if regime_note:
            report["_regime_analogue_note"] = regime_note
        if analogues:
            report["_historical_analogues"] = analogues

        report["_loop8_timestamp"] = datetime.now(timezone.utc).isoformat()
        log.info(
            "[Loop8] %d analogues found | %s",
            len(analogues),
            regime_note[:60] if regime_note else "no history yet"
        )
        return {"loop": 8, "status": "ok", "final_report": report}

    def loop9_adversarial_stress_test(self, loop8_out: dict,
                                       parsed: ParsedQuery) -> dict:
        """
        Loop 9 — Adversarial Stress Test (batched).
        failure_modes and resilience are produced in loop_batch_synthesize.
        This method remains for API compatibility; it performs no LLM I/O.
        """
        report = dict(loop8_out.get("final_report", {}))
        report["_loop9_timestamp"] = datetime.now(timezone.utc).isoformat()
        return {
            "loop": 9,
            "status": "batched",
            "note": "failure_modes merged in single batch LLM call",
            "final_report": report,
        }

    def loop10_narrative_compiler(self, loop9_out: dict,
                                   parsed: ParsedQuery) -> dict:
        """
        Loop 10 — Narrative compiler (batched).
        trader_memo / hedge_fund_brief / tldr come from loop_batch_synthesize.
        """
        report = dict(loop9_out.get("final_report", {}))
        report["_loop10_timestamp"] = datetime.now(timezone.utc).isoformat()
        return {
            "loop": 10,
            "status": "batched",
            "note": "narrative fields merged in single batch LLM call",
            "final_report": report,
        }

    def run(
        self,
        query: str,
        client=None,
        user_id: Optional[str] = None,
        progress_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> dict:
        """
        Execute the full 10-loop ATLAS research pipeline.

        Python does scrape → fact-check → satellite context → personalize → regime
        memory, then ONE batched Gemini call (synthesis + macro + scenarios +
        stress + narrative), then Python trade-plan audit → execution rules → EV.

        user_id: Supabase auth user UUID string for POST /query; None = CLI/file fallback for Loop 5 positions.
        """
        t_start = time.time()
        if client:
            self.client = client
        timing: dict[str, float] = {}

        def progress(stage: str, pct: int, message: str, loop: str | int | None = None) -> None:
            if progress_callback:
                progress_callback(
                    {
                        "stage": stage,
                        "progress_pct": pct,
                        "message": message,
                        "loop": loop,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                )

        def check_cancel(stage: str) -> None:
            if cancel_check and cancel_check():
                progress("Cancelled", 100, f"Cancelled before {stage}.")
                raise QueryCancelledError(f"Research cancelled before {stage}")

        progress("Parsing request", 8, "Classifying intent, tickers, options context, and urgency.", "parse")
        parsed = self.parser.parse(query, client=self.client)
        timing["parse"] = round(time.time() - t_start, 2)
        log.info(
            "[ATLAS 10-LOOP] Starting — type=%s tickers=%s urgency=%s",
            parsed.query_type, parsed.tickers, parsed.urgency
        )

        check_cancel("Loop 1")
        progress("Loop 1: market scrape", 15, "Gathering market, quote, filings, and awareness context.", 1)
        t0 = time.time()
        l1 = self.loop1_scrape(parsed)
        timing["loop1_scrape"] = round(time.time() - t0, 2)

        check_cancel("Loop 2")
        progress("Loop 2: fact check", 25, "Cross-checking gathered context and tagging evidence quality.", 2)
        t0 = time.time()
        l2 = self.loop2_factcheck(l1, parsed)
        timing["loop2_factcheck"] = round(time.time() - t0, 2)

        check_cancel("Loop 3")
        progress("Loop 3: satellite context", 35, "Adding volume, congress, memory, sector, and pattern context.", 3)
        t0 = time.time()
        l3 = self.loop3_synthesize(l2, l1, parsed)
        timing["loop3_context_gather"] = round(time.time() - t0, 2)

        l4_pre = {
            "loop": 4,
            "status": "pending_batch",
            "final_report": {},
            "audit_notes": [],
        }
        check_cancel("Loop 5")
        progress("Loop 5: personalization", 45, "Loading portfolio, tracker, paper-trade, and risk context.", 5)
        t0 = time.time()
        l5 = self.loop5_personalize(l4_pre, parsed, user_id=user_id)
        timing["loop5_personalize"] = round(time.time() - t0, 2)

        check_cancel("Loop 8")
        progress("Loop 8: regime memory", 55, "Checking historical analogues and regime memory.", 8)
        t0 = time.time()
        l8 = self.loop8_regime_memory(l5, parsed)
        timing["loop8_regime"] = round(time.time() - t0, 2)

        finance_kb_block = ""
        check_cancel("RAG retrieval")
        progress("Knowledge retrieval", 62, "Retrieving finance knowledge and local RAG context.", "rag")
        t0 = time.time()
        if self._rag_ok and self._rag is not None:
            try:
                finance_kb_block = self._rag.get_finance_knowledge_context(
                    parsed.intent_summary or "",
                    parsed.raw,
                )
            except Exception as e:
                log.debug("[rag] finance_knowledge context: %s", e)
        timing["finance_kb_retrieval"] = round(time.time() - t0, 2)

        check_cancel("batch synthesis")
        progress("Loops 3-10: synthesis batch", 72, "Running the single low-cost synthesis, scenario, stress, and narrative batch.", "batch_3_10")
        t0 = time.time()
        l_batch = self.loop_batch_synthesize(
            parsed, l1, l2, l3, l5, l8, finance_kb_block=finance_kb_block
        )
        timing["loop_batch_llm"] = round(time.time() - t0, 2)

        report = dict(l_batch.get("final_report") or {})
        check_cancel("Loop 4 audit")
        progress("Loop 4: trade-plan audit", 82, "Auditing trade plan consistency and risk controls.", 4)
        t0 = time.time()
        l4 = self.loop4_python_trade_plan_audit(report)
        timing["loop4_python_audit"] = round(time.time() - t0, 2)
        report = dict(l4.get("final_report") or {})

        check_cancel("Loop 6")
        progress("Loop 6: execution timing", 88, "Generating execution rules and alert hooks.", 6)
        t0 = time.time()
        l6 = self.loop6_execution_timing({"final_report": report}, parsed)
        timing["loop6_execution"] = round(time.time() - t0, 2)

        check_cancel("Loop 7")
        progress("Loop 7: scenario EV", 92, "Calculating scenario expected value where possible.", 7)
        t0 = time.time()
        l7 = self.loop7_probabilistic_scenarios(l6, parsed)
        timing["loop7_scenarios_ev"] = round(time.time() - t0, 2)

        check_cancel("Loop 9")
        progress("Loop 9: adversarial check", 96, "Stress-testing assumptions and failure modes.", 9)
        t0 = time.time()
        l9 = self.loop9_adversarial_stress_test(l7, parsed)
        timing["loop9_adversarial"] = round(time.time() - t0, 2)

        check_cancel("Loop 10")
        progress("Loop 10: final narrative", 98, "Compiling the final answer for the selected output style.", 10)
        t0 = time.time()
        l10 = self.loop10_narrative_compiler(l9, parsed)
        timing["loop10_narrative"] = round(time.time() - t0, 2)

        timing["total"] = round(time.time() - t_start, 2)

        l_batch_meta = {k: v for k, v in l_batch.items() if k != "final_report"}
        log.info(
            "[ATLAS 10-LOOP] Complete in %.1fs | batch_llm=%.1fs",
            timing["total"],
            timing.get("loop_batch_llm", 0),
        )
        progress("Completed", 100, "10-loop research pipeline completed.", "done")

        final = l10.get("final_report", {})
        if isinstance(final, dict) and parsed.query_type:
            final["domain_tag"] = parsed.query_type
        cq = final.get("clarification_questions")
        if not isinstance(cq, list):
            cq = []
        return {
            "query": query,
            "parsed_query": {
                "query_type":      parsed.query_type,
                "domain_tag":      parsed.query_type,
                "tickers":         parsed.tickers,
                "intent_summary":  parsed.intent_summary,
                "options_context": parsed.options_context,
                "confidence":      parsed.confidence,
                "urgency":         parsed.urgency,
                "intent_route":    INTENT_MARKET_DEEP_DIVE,
            },
            "final_report":     final,
            "tldr":             final.get("tldr", ""),
            "trader_memo":      final.get("trader_memo", ""),
            "hedge_fund_brief": final.get("hedge_fund_brief", ""),
            "execution_rules":  final.get("execution_rules", []),
            "failure_modes":    final.get("failure_modes", []),
            "scenarios":        final.get("scenarios", []),
            "clarification_questions": cq,
            "audit_notes":      l4.get("audit_notes", []),
            "loop_outputs": {
                "loop1": l1,
                "loop2": l2,
                "loop3": l3,
                "loop_batch": l_batch_meta,
                "loop4": l4,
                "loop5": l5,
                "loop8": l8,
                "loop6": l6,
                "loop7": l7,
                "loop9": l9,
                "loop10": l10,
            },
            "timing": timing,
        }


class QueryRouter:
    def __init__(self):
        self._engine = FourLoopEngine()
        self._omega_agent: Any = None

    def _get_omega(self) -> Any:
        if self._omega_agent is False:
            return None
        if self._omega_agent is None:
            try:
                from atlas_omega import OmegaAgent

                self._omega_agent = OmegaAgent()
            except Exception as e:
                log.warning("[QueryRouter] OmegaAgent unavailable: %s", e)
                self._omega_agent = False
                return None
        return self._omega_agent

    def route(
        self,
        query: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        *,
        crypto_snapshot: bool = False,
        research_mode: Optional[str] = None,
        progress_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> dict[str, Any]:
        with _QUERY_PIPELINE_LOCK:
            raw_q = (query or "").strip()
            cache_intent = classify_sector_cache_intent(raw_q)
            if crypto_snapshot:
                cache_intent = INTENT_CRYPTO_MARKET_SCAN
            if cache_intent:
                om = self._get_omega()
                if om:
                    try:
                        report = om.query(raw_q, session_id=session_id, data_cache_intent=cache_intent)
                        if isinstance(report, dict):
                            env = _omega_report_to_query_envelope(
                                report, raw_q, intent_route=cache_intent
                            )
                            if env:
                                log.info("[QueryRouter] %s → Omega (data_cache)", cache_intent)
                                return env
                    except Exception as e:
                        log.warning("[QueryRouter] Omega data_cache route failed, continuing: %s", e)

            # Auto-promote: if query text says "deep research" treat as deep mode
            if research_mode != "deep" and _DEEP_RESEARCH_RE.search(raw_q):
                research_mode = "deep"

            # Force 10-loop engine when user explicitly chose Deep mode
            if research_mode == "deep":
                route_kind = INTENT_MARKET_DEEP_DIVE
            else:
                route_kind = classify_intent_route(raw_q)
                # In normal/web mode, only explicit trade requests use the 10-loop engine.
                # Score-based MARKET_DEEP_DIVE falls back to Omega (fast path).
                if route_kind == INTENT_MARKET_DEEP_DIVE and not _EXPLICIT_TRADE_RE.search(raw_q):
                    route_kind = INTENT_GENERAL_FINANCE
            if route_kind in (
                INTENT_GENERAL_FINANCE, INTENT_CASUAL, INTENT_GENERAL_CHAT,
                INTENT_COMPANY_RESEARCH, INTENT_HTML_ARTIFACT, INTENT_DOCUMENT_GENERATION,
            ):
                om = self._get_omega()
                if om:
                    try:
                        report = om.query(raw_q, session_id=session_id, intent_route=route_kind)
                        if isinstance(report, dict):
                            env = _omega_report_to_query_envelope(report, raw_q)
                            if env:
                                log.info("[QueryRouter] %s → Omega", route_kind)
                                return env
                    except Exception as e:
                        log.warning("[QueryRouter] Omega route failed, using 10-loop: %s", e)
                else:
                    log.warning("[QueryRouter] %s but Omega missing — falling back to 10-loop", route_kind)
            return self._engine.run(
                raw_q,
                user_id=user_id,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )

    def parse_only(self, query: str) -> ParsedQuery:
        return self._engine.parser.parse(query, client=self._engine.client)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import sys

    q = " ".join(sys.argv[1:]) or "Analyze SOUN stock"
    r = QueryRouter().route(q)
    print(json.dumps(r.get("final_report", r), indent=2)[:8000])
