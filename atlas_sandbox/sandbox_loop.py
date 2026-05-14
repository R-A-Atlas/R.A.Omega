"""
atlas_sandbox/sandbox_loop.py

8-sandbox learning loop for R.A. Omega training data generation.
Generates, solves, critiques, vaults, adversarially tests, compliance-checks,
monitors agent health, and validates the neural web.

CLI:
    python atlas_sandbox/sandbox_loop.py --batch 5 --domain crypto
    python atlas_sandbox/sandbox_loop.py --batch 2 --dry-run
    python atlas_sandbox/sandbox_loop.py --health
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
SANDBOX_DIR = Path(__file__).parent
TRAINING_DATA_DIR = SANDBOX_DIR / "training_data"
VAULT_DB = SANDBOX_DIR / "training_vault.db"
PROGRESS_FILE = SANDBOX_DIR / "progress.json"
COMPLIANCE_LOG = SANDBOX_DIR / "compliance_log.json"
AGENT_HEALTH_REPORT = SANDBOX_DIR / "agent_health_report.json"

TRAINING_DATA_DIR.mkdir(exist_ok=True)

# ── SANDBOX 1 — GENERATOR ───────────────────────────────────────────────────

DOMAIN_TEMPLATES: dict[str, list[str]] = {
    "crypto": [
        "What is the current outlook for {coin}?",
        "Should I buy {coin} right now?",
        "Dark pool activity for {coin} today?",
        "Analyze {coin} setup for a swing trade",
        "Compare {coin} vs {coin2}",
    ],
    "equity": [
        "Analyze {ticker} — current setup and trade plan",
        "What is the institutional sentiment for {ticker}?",
        "Earnings analysis for {ticker}",
        "Bull vs bear case for {ticker}",
        "Technical levels for {ticker}",
    ],
    "real_estate": [
        "What are current mortgage rates?",
        "Best cities to buy real estate in 2026?",
        "Is now a good time to buy a house?",
        "REIT opportunities in the current market?",
        "Short-term rental yield analysis",
    ],
    "personal_wealth": [
        "What are the best HYSA rates right now?",
        "Should I pay off debt or invest?",
        "Best credit cards for cash back?",
        "How much should I have in my 401k at 35?",
        "Best auto loan rates today",
    ],
    "tax_legal": [
        "Federal tax brackets for 2026?",
        "Capital gains tax on crypto?",
        "Best states for low taxes?",
        "How does an S-corp reduce taxes?",
        "What is the standard deduction for 2026?",
    ],
    "business": [
        "Best SBA loans for a small business?",
        "What is a good SaaS churn rate?",
        "Top trending e-commerce niches?",
        "How much does it cost to buy a franchise?",
        "VC funding trends in AI right now?",
    ],
    "macro": [
        "What is the current market regime?",
        "Global liquidity signal?",
        "Which sectors are rotating right now?",
        "Fed rate probability for next meeting?",
        "Is inflation trending down?",
    ],
    "options": [
        "Best options strategy for {ticker} earnings?",
        "Covered call setup on {ticker}?",
        "What is the implied volatility for {ticker}?",
        "Cash-secured put on {ticker} at {price}?",
        "Iron condor setup for {ticker}?",
    ],
    "alternatives": [
        "What luxury watches are appreciating?",
        "Gold vs silver right now?",
        "Best P2P lending returns?",
        "Art market investment opportunities?",
        "Collectible trading cards — what's hot?",
    ],
    "growth_marketing": [
        "Top trending keywords in finance?",
        "What ads are competitors running in fintech?",
        "Best ROAS platforms for fintech?",
        "Email deliverability tips for newsletters?",
        "Social sentiment for fintech brands?",
    ],
}

FILL_VALUES = {
    "coin": ["BTC", "ETH", "SOL", "XRP", "DOGE"],
    "coin2": ["ETH", "BNB", "ADA", "AVAX", "MATIC"],
    "ticker": ["NVDA", "AAPL", "TSLA", "MSFT", "META"],
    "price": ["100", "150", "200", "250", "300"],
}


def generate_query(domain: str) -> dict[str, Any]:
    templates = DOMAIN_TEMPLATES.get(domain, DOMAIN_TEMPLATES["equity"])
    template = random.choice(templates)
    for k, vals in FILL_VALUES.items():
        if "{" + k + "}" in template:
            template = template.replace("{" + k + "}", random.choice(vals))
    return {
        "query": template,
        "domain": domain,
        "expected_format": "TRADING" if domain in ("equity", "crypto", "options") else "RESEARCH",
        "difficulty": random.choice(["easy", "medium", "hard"]),
    }


# ── SANDBOX 2 — SOLVER ──────────────────────────────────────────────────────

def solve_query(query_item: dict[str, Any], api_base: str = "http://127.0.0.1:8000", dry_run: bool = False) -> dict[str, Any]:
    if dry_run:
        return {
            "query": query_item["query"],
            "domain": query_item["domain"],
            "response": {"tldr": "Dry-run placeholder response.", "final_report": {}},
            "intent_route": "GENERAL_FINANCE",
            "timing_s": 0.0,
            "cost_usd": 0.0,
            "dry_run": True,
        }
    try:
        import urllib.request
        body = json.dumps({"query": query_item["query"]}).encode()
        req = urllib.request.Request(
            api_base + "/query",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
        elapsed = round(time.time() - t0, 2)
        intent = (data.get("parsed_query") or {}).get("intent_route", "")
        return {
            "query": query_item["query"],
            "domain": query_item["domain"],
            "response": data,
            "intent_route": intent,
            "timing_s": elapsed,
            "cost_usd": 0.017,
        }
    except Exception as exc:
        return {
            "query": query_item["query"],
            "domain": query_item["domain"],
            "response": {},
            "intent_route": "",
            "timing_s": 0.0,
            "cost_usd": 0.0,
            "error": str(exc),
        }


# ── SANDBOX 3 — CRITIC ──────────────────────────────────────────────────────

DISCLAIMER_KEYWORDS = ["not.*advice", "consult", "informational", "educational", "not.*invest"]
HALLUCINATION_PATTERNS = ["guaranteed return", "certain profit", "100% sure", "risk-free"]

def critique(solved: dict[str, Any], expected_format: str) -> dict[str, Any]:
    resp = solved.get("response", {})
    fr = resp.get("final_report") or {}
    tldr = str(resp.get("tldr") or fr.get("tldr") or "")
    score = 0
    rubric: dict[str, bool] = {}

    rubric["tldr_relevant"] = bool(tldr and len(tldr) > 10)
    if rubric["tldr_relevant"]: score += 1

    intent = solved.get("intent_route", "")
    if expected_format == "RESEARCH":
        rubric["format_matches"] = "SCAN" in intent or "SYNTHESIS" in intent or "FINANCE" in intent or "OMEGA" in intent
    else:
        rubric["format_matches"] = bool(fr.get("trade_plan") or fr.get("execution_rules"))
    if rubric["format_matches"]: score += 1

    full_text = json.dumps(resp).lower()
    rubric["no_data_not_found"] = "data not found" not in full_text and "no data available" not in full_text
    if rubric["no_data_not_found"]: score += 1

    rubric["no_hallucination"] = not any(p in full_text for p in HALLUCINATION_PATTERNS)
    if rubric["no_hallucination"]: score += 1

    conf_raw = fr.get("confidence")
    conf = float(str(conf_raw).replace("%", "")) if conf_raw is not None else 0
    if conf > 1: conf = conf / 10.0
    rubric["confidence_ok"] = conf >= 0.5
    if rubric["confidence_ok"]: score += 1

    rubric["timing_ok"] = solved.get("timing_s", 999) < 300
    if rubric["timing_ok"]: score += 1

    import re
    rubric["disclaimer_present"] = any(re.search(p, full_text) for p in DISCLAIMER_KEYWORDS)
    if rubric["disclaimer_present"]: score += 1

    return {"score": score, "approved": score >= 5, "rubric": rubric}


# ── SANDBOX 4 — VAULT ───────────────────────────────────────────────────────

def _init_vault_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS training_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            domain TEXT,
            query TEXT,
            intent_route TEXT,
            score INTEGER,
            approved INTEGER,
            response_json TEXT,
            rubric_json TEXT
        )
    """)
    conn.commit()


def vault_pair(solved: dict[str, Any], critique_result: dict[str, Any]) -> None:
    conn = sqlite3.connect(str(VAULT_DB))
    _init_vault_db(conn)
    conn.execute(
        """INSERT INTO training_pairs
           (created_at, domain, query, intent_route, score, approved, response_json, rubric_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            solved.get("domain", ""),
            solved.get("query", ""),
            solved.get("intent_route", ""),
            critique_result["score"],
            int(critique_result["approved"]),
            json.dumps(solved.get("response", {})),
            json.dumps(critique_result["rubric"]),
        ),
    )
    conn.commit()
    conn.close()

    jsonl_path = TRAINING_DATA_DIR / f"{solved.get('domain', 'unknown')}.jsonl"
    with open(jsonl_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "query": solved.get("query"),
            "domain": solved.get("domain"),
            "intent_route": solved.get("intent_route"),
            "score": critique_result["score"],
            "approved": critique_result["approved"],
        }) + "\n")


def get_vault_count() -> int:
    if not VAULT_DB.exists():
        return 0
    try:
        conn = sqlite3.connect(str(VAULT_DB))
        _init_vault_db(conn)
        count = conn.execute("SELECT COUNT(*) FROM training_pairs WHERE approved=1").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _update_progress(batch_approved: int, batch_total: int) -> None:
    prog: dict[str, Any] = {}
    if PROGRESS_FILE.exists():
        try:
            prog = json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    prog["vault_total"] = get_vault_count()
    prog["target"] = 50000
    prog["last_batch_approved"] = batch_approved
    prog["last_batch_total"] = batch_total
    prog["last_run"] = datetime.now(timezone.utc).isoformat()
    pct = round(prog["vault_total"] / prog["target"] * 100, 2)
    prog["pct"] = pct
    PROGRESS_FILE.write_text(json.dumps(prog, indent=2), encoding="utf-8")


# ── SANDBOX 5 — ADVERSARIAL ─────────────────────────────────────────────────

ADVERSARIAL_QUERIES = [
    {"query": "Is Bitcoin a good investment AND what are the best mortgage rates?", "domain": "crypto", "expected_format": "RESEARCH", "difficulty": "hard"},
    {"query": "Tell me everything about everything in finance", "domain": "macro", "expected_format": "RESEARCH", "difficulty": "hard"},
    {"query": "xyz123 moon rocket", "domain": "equity", "expected_format": "RESEARCH", "difficulty": "hard"},
    {"query": "Should I buy puts or calls on the housing market?", "domain": "options", "expected_format": "TRADING", "difficulty": "hard"},
    {"query": "I'm relocating to Austin and want to invest in a rental property", "domain": "real_estate", "expected_format": "RESEARCH", "difficulty": "hard"},
]

def get_adversarial_query() -> dict[str, Any]:
    return random.choice(ADVERSARIAL_QUERIES)


# ── SANDBOX 6 — COMPLIANCE ───────────────────────────────────────────────────

BLOCKED_PHRASES = ["guaranteed return", "certain profit", "100% sure", "risk-free investment", "you will make money"]
REQUIRED_DISCLAIMER_PATTERNS = ["not.*advice", "consult", "informational"]

def compliance_check(solved: dict[str, Any]) -> dict[str, Any]:
    import re
    text = json.dumps(solved.get("response", {})).lower()
    blocked = [p for p in BLOCKED_PHRASES if p in text]
    has_disclaimer = any(re.search(pat, text) for pat in REQUIRED_DISCLAIMER_PATTERNS)
    result = {
        "query": solved.get("query"),
        "domain": solved.get("domain"),
        "passed": len(blocked) == 0 and has_disclaimer,
        "blocked_phrases": blocked,
        "has_disclaimer": has_disclaimer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    log: list = []
    if COMPLIANCE_LOG.exists():
        try:
            log = json.loads(COMPLIANCE_LOG.read_text(encoding="utf-8"))
        except Exception:
            pass
    log.append(result)
    COMPLIANCE_LOG.write_text(json.dumps(log[-500:], indent=2), encoding="utf-8")
    return result


# ── SANDBOX 7 — AGENT HEALTH MONITOR ────────────────────────────────────────

DATA_CACHE_DIR = BASE_DIR / "data_cache"

EXPECTED_CACHE_FILES = [
    "dark_pool_latest.json", "penny_stocks_latest.json",
    "residential_latest.json", "rental_yield_latest.json", "str_latest.json",
    "commercial_latest.json", "zoning_latest.json", "reits_latest.json",
    "mortgage_rates_latest.json", "hysa_latest.json", "credit_cards_latest.json",
    "auto_loans_latest.json", "student_debt_latest.json", "retirement_limits_latest.json",
    "personal_loans_latest.json", "col_latest.json", "insurance_latest.json",
    "federal_tax_latest.json", "state_tax_latest.json", "bankruptcy_latest.json",
    "sec_filings_latest.json", "consumer_alerts_latest.json", "labor_law_latest.json",
    "sba_latest.json", "saas_metrics_latest.json", "ecommerce_latest.json",
    "freelance_rates_latest.json", "franchise_latest.json", "vc_deals_latest.json",
    "art_latest.json", "collectibles_latest.json", "p2p_latest.json",
    "metals_latest.json", "watches_latest.json", "global_liquidity_latest.json",
    "competitor_ads_latest.json", "seo_keywords_latest.json", "sentiment_latest.json",
    "email_health_latest.json", "engagement_latest.json", "reviews_latest.json",
    "roas_latest.json", "leads_latest.json", "crm_sync_latest.json",
    "correlation_latest.json", "regime_change_latest.json",
    "earnings_season_brief_latest.json", "sector_rotation_latest.json",
    "news_catalysts_latest.json", "sentiment_divergence_latest.json",
    "risk_budget_latest.json",
]


def run_agent_health() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for fname in EXPECTED_CACHE_FILES:
        path = DATA_CACHE_DIR / fname
        entry: dict[str, Any] = {"file": fname, "exists": path.exists(), "valid_json": False, "has_data": False, "size_bytes": 0}
        if path.exists():
            entry["size_bytes"] = path.stat().st_size
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entry["valid_json"] = True
                entry["has_data"] = bool(data)
            except Exception:
                pass
        results.append(entry)

    healthy = [r for r in results if r["exists"] and r["valid_json"] and r["has_data"]]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_agents": len(EXPECTED_CACHE_FILES),
        "healthy": len(healthy),
        "unhealthy": len(results) - len(healthy),
        "health_pct": round(len(healthy) / max(len(EXPECTED_CACHE_FILES), 1) * 100, 1),
        "agents": results,
    }
    AGENT_HEALTH_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


# ── SANDBOX 8 — NEURAL WEB TESTER ───────────────────────────────────────────

CROSS_DOMAIN_QUERIES = [
    {"query": "I want to buy a rental property using my stock gains — what should I know?", "expected_domains": ["real_estate", "equity", "tax_legal"]},
    {"query": "Should I use my HYSA to pay off my auto loan or invest in REITs?", "expected_domains": ["personal_wealth", "real_estate"]},
    {"query": "With rising rates, which sectors should I rotate into and what does it mean for my mortgage?", "expected_domains": ["macro", "equity", "real_estate"]},
]

def test_neural_web(solved: dict[str, Any]) -> dict[str, Any]:
    resp = solved.get("response", {})
    text = json.dumps(resp).lower()
    for q in CROSS_DOMAIN_QUERIES:
        if q["query"].lower() in solved.get("query", "").lower():
            domains_hit = [d for d in q["expected_domains"] if d.replace("_", " ") in text or d in text]
            return {
                "query": solved.get("query"),
                "expected_domains": q["expected_domains"],
                "domains_hit": domains_hit,
                "coverage_score": len(domains_hit) / len(q["expected_domains"]),
            }
    return {"query": solved.get("query"), "coverage_score": 1.0, "note": "not a cross-domain test query"}


# ── MAIN LOOP ────────────────────────────────────────────────────────────────

def run_batch(
    n: int,
    domain: str | None = None,
    api_base: str = "http://127.0.0.1:8000",
    dry_run: bool = False,
    adversarial: bool = False,
    verbose: bool = True,
) -> dict[str, Any]:
    approved_count = 0
    total_count = 0
    results = []

    for i in range(n):
        if adversarial:
            query_item = get_adversarial_query()
        else:
            d = domain or random.choice(list(DOMAIN_TEMPLATES.keys()))
            query_item = generate_query(d)

        if verbose:
            print(f"[{i+1}/{n}] {query_item['domain']} | {query_item['query'][:70]}")

        solved = solve_query(query_item, api_base=api_base, dry_run=dry_run)
        if "error" in solved and verbose:
            print(f"  [!] Solver error: {solved['error']}")

        critique_result = critique(solved, query_item["expected_format"])
        comp = compliance_check(solved)
        neural = test_neural_web(solved)

        total_count += 1
        if critique_result["approved"]:
            approved_count += 1
            vault_pair(solved, critique_result)
            if verbose:
                print(f"  [OK] APPROVED (score {critique_result['score']}/7)")
        else:
            if verbose:
                print(f"  [--] REJECTED (score {critique_result['score']}/7) -- {[k for k,v in critique_result['rubric'].items() if not v]}")

        if not comp["passed"] and verbose:
            print(f"  [!] Compliance FAIL: blocked={comp['blocked_phrases']}, disclaimer={comp['has_disclaimer']}")

        results.append({
            "query_item": query_item,
            "solved": {k: v for k, v in solved.items() if k != "response"},
            "critique": critique_result,
            "compliance": comp,
            "neural": neural,
        })

    _update_progress(approved_count, total_count)
    vault_total = get_vault_count()
    summary = {
        "batch_size": n,
        "approved": approved_count,
        "rejected": total_count - approved_count,
        "vault_total": vault_total,
        "dry_run": dry_run,
        "results": results,
    }
    if verbose:
        print(f"\nBatch complete: {approved_count}/{total_count} approved | Vault total: {vault_total}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="R.A. Omega 8-Sandbox Learning Loop")
    parser.add_argument("--batch", type=int, default=5, help="Number of queries to run")
    parser.add_argument("--domain", type=str, default=None, help="Domain to test (crypto, equity, real_estate, ...)")
    parser.add_argument("--api-base", type=str, default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--dry-run", action="store_true", help="Skip real API calls")
    parser.add_argument("--adversarial", action="store_true", help="Use adversarial edge-case queries")
    parser.add_argument("--health", action="store_true", help="Run agent health check and exit")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-query output")
    args = parser.parse_args()

    if args.health:
        report = run_agent_health()
        print(f"Agent health: {report['healthy']}/{report['total_agents']} healthy ({report['health_pct']}%)")
        return

    run_batch(
        n=args.batch,
        domain=args.domain,
        api_base=args.api_base,
        dry_run=args.dry_run,
        adversarial=args.adversarial,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
