"""
division_sandbox.py — R.A. Omega Division Sandboxes

Each division is a department-level workspace with its own playbook (SOPs),
memory (learned insights from past queries), and agent team. Divisions inject
their playbook rules into the synthesis prompt for relevant queries.

Divisions persist to: atlas_vault/04-Projects/Divisions/<id>/
  playbook.md    — static SOPs and rules for this domain
  memory.jsonl   — learned insights appended after each relevant query
  context.json   — live snapshot of division state

Usage:
    from division_sandbox import get_division, learn, list_divisions, get_playbook_context
    ctx = get_division("market_intelligence")
    learn("market_intelligence", query="Analyze NVDA", insight="NVDA broke 900 with volume", category="technical")
    rules = get_playbook_context("MARKET_DEEP_DIVE")
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE_DIR  = Path(__file__).resolve().parent
DIV_ROOT  = BASE_DIR / "atlas_vault" / "04-Projects" / "Divisions"
DIV_ROOT.mkdir(parents=True, exist_ok=True)

_MAX_MEMORY = 200          # max entries per division before pruning oldest


# ── Division registry ─────────────────────────────────────────────────────────

DIVISIONS: dict[str, dict] = {
    "market_intelligence": {
        "name": "Market Intelligence",
        "icon": "📈",
        "color": "#10b981",
        "description": "Equities, options, dark pool, earnings, regime detection",
        "intents": ["MARKET_DEEP_DIVE", "TRADING_ANALYSIS"],
        "agents": [
            "EquityScraper", "OptionsScraper", "DarkPoolScanner",
            "NewsScanner", "SentimentAgent", "RegimeDetector", "BacktestEngine",
        ],
        "playbook": [
            "Always check market regime before making directional calls — regime overrides individual signals.",
            "Dark pool prints and options flow confirm or deny price action. Never rely on price alone.",
            "Options IV crush after earnings is a known trap — size positions accordingly before events.",
            "Volume is the lie detector — breakouts on low volume are traps until proven otherwise.",
            "Analyst consensus is a contrarian signal when >80% agree — check for crowding.",
            "RSI divergence on weekly timeframe carries more weight than daily divergence.",
            "Earnings beats mean nothing if guidance is cut — always read the full transcript signal.",
            "When dark pool prints exceed 30% of daily volume, institutional accumulation/distribution is underway.",
        ],
    },
    "macro_global": {
        "name": "Macro & Global",
        "icon": "🌐",
        "color": "#6366f1",
        "description": "Fed policy, inflation, yield curve, global liquidity, tariffs",
        "intents": ["MACRO_RISK_SCAN", "GENERAL_FINANCE"],
        "agents": [
            "MacroScanner", "RegimeDetector", "NewsScanner",
        ],
        "playbook": [
            "The yield curve (2s10s) leads the economy by 12–18 months — inversion is the warning, un-inversion is the alarm.",
            "Fed dot plots are aspirational. Watch actual balance sheet changes and overnight repo activity.",
            "CPI headline vs core divergence signals energy or food shocks — base effects matter for trend reads.",
            "Global M2 expansion leads risk asset rallies by 6–9 months — track it before the crowd.",
            "Tariff announcements are negotiating tactics first, policy second. Wait for implementation details.",
            "Dollar strength is a liquidity drain on EM and commodities — DXY above 105 is a risk-off signal.",
            "Labor market strength buys the Fed cover to hold rates higher for longer than markets expect.",
            "Geopolitical supply shocks are sticky — oil above $90 for 3+ months historically tips inflation back up.",
        ],
    },
    "real_estate": {
        "name": "Real Estate",
        "icon": "🏠",
        "color": "#f59e0b",
        "description": "Residential, commercial, REITs, mortgage rates, rental yield",
        "intents": ["REAL_ESTATE_SCAN"],
        "agents": [
            "RealEstateAgent", "MortgageAgent",
        ],
        "playbook": [
            "Mortgage rates above 7% historically kill transaction volume by 30–40% — affordability is the primary driver.",
            "Inventory levels under 3 months = seller's market. Over 6 months = buyer's market. 3–6 = balanced.",
            "Rent vs buy breaks even at roughly 5% price-to-rent ratio — above that, renting is cheaper per month.",
            "Cap rates below 5% in major metros signal speculative pricing, not income investing.",
            "STR (Airbnb) yields collapse when city occupancy drops below 65% — watch local regulation as the trigger.",
            "Commercial office vacancy is a lagging indicator — lease expirations matter more than current vacancy.",
            "REIT dividend yields above 7% often signal balance sheet stress, not value — check debt maturity schedules.",
            "Local job growth and net migration are the two strongest long-term RE price predictors.",
        ],
    },
    "personal_finance": {
        "name": "Personal Finance",
        "icon": "💰",
        "color": "#3b82f6",
        "description": "Debt payoff, savings, tax optimization, retirement, insurance",
        "intents": ["PERSONAL_WEALTH_SCAN"],
        "agents": [
            "WealthScanAgent", "DebtOptimizer", "TaxAgent", "MortgageAgent",
        ],
        "playbook": [
            "High-interest debt (>8% APR) beats almost any investment — clear it before investing.",
            "Emergency fund: 3 months if dual income, 6 months if single income, 12 months if self-employed.",
            "401k match is a 50–100% instant return — always capture it before any other savings goal.",
            "Roth conversion makes sense when current bracket < expected retirement bracket.",
            "Avalanche method (highest APR first) saves most money. Snowball (smallest balance first) builds momentum.",
            "I-bonds and HYSA rates matter when inflation > 3% — cash drag is a real cost.",
            "Tax-loss harvesting window: realize losses before Dec 31. Wash-sale rule: 30 days before/after.",
            "Insurance is not an investment — buy term life, not whole life, for pure death benefit.",
        ],
    },
    "business_intelligence": {
        "name": "Business Intelligence",
        "icon": "🏢",
        "color": "#8b5cf6",
        "description": "SaaS metrics, ecommerce, franchise, VC deals, growth",
        "intents": ["GENERAL_FINANCE"],
        "agents": [
            "DataCache", "RAGEngine",
        ],
        "playbook": [
            "SaaS health check: NRR > 110%, CAC payback < 18 months, churn < 2% monthly.",
            "Rule of 40: growth rate + profit margin >= 40% is the SaaS quality threshold.",
            "eCommerce CVR benchmark: 1–3% is standard, >3% is strong, <1% is a funnel problem.",
            "Franchise ROI: expect 2–5 year payback on a quality franchise; <2 years is exceptional.",
            "VC term sheets: valuation matters less than pro-rata rights and liquidation preferences.",
            "CAC that exceeds 1/3 of LTV is unsustainable — the business is buying customers, not earning them.",
            "Gross margin below 50% in SaaS means the product has infrastructure cost problems.",
            "VC deal flow concentrates in 3 themes per cycle — being early to the next cycle beats chasing the current one.",
        ],
    },
    "alternative_assets": {
        "name": "Alternative Assets",
        "icon": "💎",
        "color": "#ec4899",
        "description": "Metals, crypto, art, watches, collectibles, P2P lending",
        "intents": ["GENERAL_FINANCE"],
        "agents": [
            "CryptoAgent", "DataCache",
        ],
        "playbook": [
            "Gold is a dollar hedge, not an inflation hedge — watch DXY more than CPI for gold direction.",
            "Bitcoin halving cycles historically produce the bull peak 12–18 months post-halving.",
            "Crypto funding rates > 0.1% per 8h on perpetuals signal overleveraged longs — fade the move.",
            "Art and watch markets are illiquid — assume 15–20% transaction cost when calculating returns.",
            "Collectibles appreciation is mean-reverting over 20+ years; speculative premiums always compress.",
            "P2P lending credit risk spikes during rate hiking cycles — defaults lag rate rises by 12–18 months.",
            "Crypto on-chain metrics (exchange inflows, whale movements) lead price by 24–72 hours.",
            "Metals silver has 2x the industrial demand of gold — silver outperforms in growth phases.",
        ],
    },
    "regulatory_intelligence": {
        "name": "Regulatory Intelligence",
        "icon": "⚖️",
        "color": "#ef4444",
        "description": "SEC filings, insider trades, congressional activity, legal alerts",
        "intents": ["COMPANY_RESEARCH", "DEEP_RESEARCH"],
        "agents": [
            "SECFilingAgent", "DataCache", "RAGEngine",
        ],
        "playbook": [
            "Form 4 insider buying clusters (3+ insiders buying within 30 days) have an 80%+ hit rate on price appreciation.",
            "10-K risk factor changes year-over-year reveal what management is newly worried about.",
            "Congressional trade disclosures lag 30–45 days — the signal is the direction, not the timing.",
            "SEC comment letters on 10-Ks often precede earnings restatements — flag them immediately.",
            "Goodwill impairments in 10-Ks signal acquisitions that didn't work — watch for write-downs.",
            "Revenue recognition changes (ASC 606) can mask deteriorating fundamentals — check cash flow.",
            "Related-party transactions in footnotes are the most frequently abused accounting area.",
            "Short-seller reports with specific EDGAR citations carry more weight than thematic critiques.",
        ],
    },
    "marketing_intelligence": {
        "name": "Marketing Intelligence",
        "icon": "📣",
        "color": "#06b6d4",
        "description": "Competitor ads, SEO, ROAS, engagement, lead generation",
        "intents": ["GENERAL_FINANCE"],
        "agents": [
            "DataCache",
        ],
        "playbook": [
            "ROAS below 2x for e-commerce is burning cash — minimum viable ROAS is 3–4x for most categories.",
            "SEO compounding: content that ranks in top 3 positions generates 3–5x the clicks of position 5–10.",
            "Email deliverability: list hygiene matters more than send frequency — clean quarterly.",
            "Competitor ad spend spikes before product launches — use ad intelligence as a leading indicator.",
            "CAC from paid vs organic divergence > 5x signals paid channel dependency — a vulnerability.",
            "Review velocity matters more than average rating for local businesses (Google, Yelp).",
            "Content engagement rate < 1% on LinkedIn, < 3% on Instagram signals audience-content mismatch.",
            "CRM lead scoring without behavioural signals (not just demographic) misses 40–60% of intent.",
        ],
    },
}

# Map intent → division id for context injection
_INTENT_TO_DIVISION: dict[str, str] = {
    "MARKET_DEEP_DIVE":    "market_intelligence",
    "TRADING_ANALYSIS":    "market_intelligence",
    "COMPANY_RESEARCH":    "regulatory_intelligence",
    "DEEP_RESEARCH":       "regulatory_intelligence",
    "MACRO_RISK_SCAN":     "macro_global",
    "REAL_ESTATE_SCAN":    "real_estate",
    "PERSONAL_WEALTH_SCAN":"personal_finance",
    "GENERAL_FINANCE":     "business_intelligence",
}


# ── Disk helpers ──────────────────────────────────────────────────────────────

def _div_dir(division_id: str) -> Path:
    return DIV_ROOT / division_id


def _memory_path(division_id: str) -> Path:
    return _div_dir(division_id) / "memory.jsonl"


def _context_path(division_id: str) -> Path:
    return _div_dir(division_id) / "context.json"


def _playbook_path(division_id: str) -> Path:
    return _div_dir(division_id) / "playbook.md"


def _ensure_div(division_id: str) -> None:
    """Initialise division folder and playbook on first access."""
    meta = DIVISIONS.get(division_id)
    if not meta:
        return
    d = _div_dir(division_id)
    d.mkdir(parents=True, exist_ok=True)

    pb = _playbook_path(division_id)
    if not pb.exists():
        rules = "\n".join(f"{i+1}. {r}" for i, r in enumerate(meta["playbook"]))
        pb.write_text(
            f"# {meta['name']} Division Playbook\n\n"
            f"**Domain:** {meta['description']}\n\n"
            f"## Operative Rules\n\n{rules}\n",
            encoding="utf-8",
        )

    ctx = _context_path(division_id)
    if not ctx.exists():
        ctx.write_text(json.dumps({
            "division_id": division_id,
            "name": meta["name"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "memory_count": 0,
            "last_active": None,
        }, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Core API ──────────────────────────────────────────────────────────────────

def learn(
    division_id: str,
    query: str,
    insight: str,
    category: str = "general",
    confidence: float = 0.85,
    source_intent: str = "",
) -> dict:
    """
    Append a learned insight to division memory.

    Args:
        division_id:    e.g. "market_intelligence"
        query:          The raw user query that produced this insight.
        insight:        The key takeaway to remember (≤300 chars).
        category:       Sub-category label (e.g. "technical", "options", "macro").
        confidence:     0–1 confidence score.
        source_intent:  The intent that triggered this query.

    Returns:
        The memory entry dict.
    """
    if division_id not in DIVISIONS:
        return {}
    _ensure_div(division_id)

    entry = {
        "entry_id": str(uuid.uuid4())[:8],
        "division_id": division_id,
        "query": query[:200],
        "insight": insight[:300],
        "category": category,
        "confidence": confidence,
        "source_intent": source_intent,
        "ts": _now(),
    }

    mp = _memory_path(division_id)
    with mp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    # Prune if over limit
    _prune_memory(division_id)

    # Update context count
    _update_context(division_id)
    return entry


def get_division(division_id: str) -> dict:
    """Return full division context including recent memories."""
    if division_id not in DIVISIONS:
        return {}
    _ensure_div(division_id)
    meta = DIVISIONS[division_id]
    memories = _load_memories(division_id, limit=10)
    ctx = _load_context(division_id)
    return {
        "division_id": division_id,
        "name": meta["name"],
        "icon": meta["icon"],
        "color": meta["color"],
        "description": meta["description"],
        "intents": meta["intents"],
        "agents": meta["agents"],
        "playbook_rules": meta["playbook"],
        "memory_count": ctx.get("memory_count", 0),
        "last_active": ctx.get("last_active"),
        "recent_memories": memories,
    }


def list_divisions() -> list[dict]:
    """Return summary of all divisions."""
    result = []
    for div_id, meta in DIVISIONS.items():
        _ensure_div(div_id)
        ctx = _load_context(div_id)
        result.append({
            "division_id": div_id,
            "name": meta["name"],
            "icon": meta["icon"],
            "color": meta["color"],
            "description": meta["description"],
            "memory_count": ctx.get("memory_count", 0),
            "last_active": ctx.get("last_active"),
            "agent_count": len(meta["agents"]),
            "intents": meta["intents"],
        })
    return result


def get_playbook_context(intent: str, max_rules: int = 5) -> str:
    """
    Return playbook rules for the division matching the given intent.
    Used to inject domain SOPs into the synthesis prompt.
    """
    division_id = _INTENT_TO_DIVISION.get(intent)
    if not division_id:
        return ""
    meta = DIVISIONS.get(division_id, {})
    rules = meta.get("playbook", [])[:max_rules]
    if not rules:
        return ""
    name = meta.get("name", division_id)
    lines = [f"DIVISION PLAYBOOK — {name.upper()}:"] + [f"  • {r}" for r in rules]
    return "\n".join(lines)


def get_division_memories(intent: str, limit: int = 3) -> str:
    """
    Return recent memories from the division matching the given intent.
    Used to inject learned context into the synthesis prompt.
    """
    division_id = _INTENT_TO_DIVISION.get(intent)
    if not division_id:
        return ""
    _ensure_div(division_id)
    memories = _load_memories(division_id, limit=limit)
    if not memories:
        return ""
    lines = ["DIVISION MEMORY (recent learnings):"]
    for m in memories:
        lines.append(f"  [{m.get('category','general')}] {m.get('insight','')}")
    return "\n".join(lines)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_memories(division_id: str, limit: int = 10) -> list[dict]:
    mp = _memory_path(division_id)
    if not mp.exists():
        return []
    try:
        lines = mp.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return entries[-limit:]
    except Exception:
        return []


def _load_context(division_id: str) -> dict:
    cp = _context_path(division_id)
    if not cp.exists():
        return {}
    try:
        return json.loads(cp.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _update_context(division_id: str) -> None:
    memories = _load_memories(division_id, limit=10000)
    cp = _context_path(division_id)
    try:
        ctx = json.loads(cp.read_text(encoding="utf-8")) if cp.exists() else {}
    except Exception:
        ctx = {}
    ctx.update({
        "division_id": division_id,
        "memory_count": len(memories),
        "last_active": _now(),
    })
    cp.write_text(json.dumps(ctx, indent=2), encoding="utf-8")


def _prune_memory(division_id: str) -> None:
    mp = _memory_path(division_id)
    if not mp.exists():
        return
    try:
        lines = [l for l in mp.read_text(encoding="utf-8").strip().splitlines() if l.strip()]
        if len(lines) > _MAX_MEMORY:
            mp.write_text("\n".join(lines[-_MAX_MEMORY:]) + "\n", encoding="utf-8")
    except Exception:
        pass
