"""
omega_level_up.py — Level-up engine for the Omega OS layer.

Analyzes the current system state and user workflows to identify the highest-leverage
automation opportunities, recommend the next skill to build, and suggest the next
connection to add.

Five Questions:
  1. What did the user do repeatedly this week?
  2. What felt manual, boring, or copy-paste?
  3. What could a smart intern do with clear instructions?
  4. What would break if 500 new users came tomorrow?
  5. What would create the most leverage if automated?

Run directly:
  python omega_level_up.py

Or import:
  from omega_level_up import analyze
  result = analyze(weekly_actions=["ran company report 5x", "manually updated watchlist"])
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from typing import Any

_ROOT = Path(__file__).parent
_OMEGA_OS_DIR = _ROOT / "omega_os"
_SKILLS_DIR   = _OMEGA_OS_DIR / "skills"
_CONNECTIONS_FILE = _OMEGA_OS_DIR / "connections" / "connections.md"

LEVERAGE_LEVELS = ("low", "medium", "high", "10x")

# ── Known automation patterns → skills that solve them ───────────────────────
_AUTOMATION_PATTERNS: list[dict[str, Any]] = [
    {
        "pattern": "ran company report",
        "opportunity": "Automate company reports via watchlist — run at market open for tracked tickers",
        "skill": "company_report",
        "connection": "Google Sheets (save reports to Drive automatically)",
        "priority": 8,
        "leverage": "high",
    },
    {
        "pattern": "updated watchlist",
        "opportunity": "Daily watchlist refresh with RYG status — runs automatically at 7 AM ET",
        "skill": "watchlist_update",
        "connection": "Telegram (push RED alerts to phone)",
        "priority": 9,
        "leverage": "high",
    },
    {
        "pattern": "morning brief",
        "opportunity": "Daily market brief — auto-generated at 7 AM ET, no manual input needed",
        "skill": "daily_brief",
        "connection": "Gmail or Telegram (send brief to inbox/phone)",
        "priority": 9,
        "leverage": "10x",
    },
    {
        "pattern": "portfolio review",
        "opportunity": "Weekly portfolio review — runs every Sunday, surfaces rebalancing needs",
        "skill": "portfolio_review",
        "connection": "Google Sheets (log performance history automatically)",
        "priority": 8,
        "leverage": "high",
    },
    {
        "pattern": "pdf report",
        "opportunity": "Auto-generate PDF reports for each company research query",
        "skill": "document_generator",
        "connection": "Google Drive (auto-save reports to Drive)",
        "priority": 7,
        "leverage": "medium",
    },
    {
        "pattern": "research",
        "opportunity": "Research queue — batch research during off-peak hours to reduce cost",
        "skill": "research_queue",
        "connection": None,
        "priority": 7,
        "leverage": "high",
    },
    {
        "pattern": "audit",
        "opportunity": "Weekly Four C audit — auto-runs every Monday, logs progress over time",
        "skill": "audit",
        "connection": None,
        "priority": 6,
        "leverage": "medium",
    },
    {
        "pattern": "voice",
        "opportunity": "Voice-to-query pipeline — speak queries on the go, auto-route to correct skill",
        "skill": "voice_capture_triage",
        "connection": "Telegram (send voice notes → auto-process)",
        "priority": 6,
        "leverage": "medium",
    },
]

# ── Scalability risk patterns ─────────────────────────────────────────────────
_SCALE_RISKS: list[dict[str, str]] = [
    {
        "risk": "Gemini API rate limits hit at scale",
        "mitigation": "gemini_limiter.py already handles rate limiting — verify backoff at 500 concurrent users",
        "priority": "high",
    },
    {
        "risk": "atlas_memory.db becomes a write bottleneck (SQLite single-writer)",
        "mitigation": "Migrate atlas_memory to Supabase Postgres for multi-user write concurrency",
        "priority": "high",
    },
    {
        "risk": "yfinance rate-limited at scale (no auth, best-effort)",
        "mitigation": "Add Polygon.io or Alpha Vantage as fallback — register API key in connections",
        "priority": "medium",
    },
    {
        "risk": "Session data stored in-memory (atlas_db.py test_user_local path)",
        "mitigation": "All sessions must go through Supabase for multi-user support",
        "priority": "high",
    },
    {
        "risk": "POST /query has no rate limiting per user",
        "mitigation": "Add per-user rate limiting middleware (subscription tier check exists — enforce hard limits)",
        "priority": "high",
    },
]

# ── Missing skills and connections (from omega_os) ────────────────────────────

def _get_missing_skills() -> list[str]:
    if not _SKILLS_DIR.exists():
        return ["omega_os/skills/ directory missing"]
    existing = {d.name for d in _SKILLS_DIR.iterdir() if d.is_dir()}
    required = {
        "onboard", "audit", "level_up", "company_report", "daily_brief",
        "document_generator", "dashboard_generator", "portfolio_review",
        "research_queue", "watchlist_update", "voice_capture_triage", "weekly_product_review",
    }
    return sorted(required - existing)


def _get_missing_connections() -> list[str]:
    if not _CONNECTIONS_FILE.exists():
        return ["connections.md not found"]
    text = _CONNECTIONS_FILE.read_text(encoding="utf-8")
    planned = [
        "Google Workspace", "Gmail", "Google Calendar", "Google Drive",
        "GitHub", "Telegram", "Notion", "Slack", "SEC EDGAR",
    ]
    return [c for c in planned if f"| active" not in text.lower().split(c.lower(), 1)[-1][:100]]


# ── Five Questions ────────────────────────────────────────────────────────────

def _q1_repeated_actions(weekly_actions: list[str]) -> list[str]:
    """What did the user do repeatedly this week?"""
    counts: dict[str, int] = {}
    for action in weekly_actions:
        a = action.lower()
        for pattern_entry in _AUTOMATION_PATTERNS:
            if pattern_entry["pattern"] in a:
                key = pattern_entry["pattern"]
                counts[key] = counts.get(key, 0) + 1
    return [f"{k} (repeated {v}x)" for k, v in sorted(counts.items(), key=lambda x: -x[1])]


def _q2_manual_boring(weekly_actions: list[str]) -> list[str]:
    """What felt manual, boring, or copy-paste?"""
    boring_signals = [
        "manual", "copy", "paste", "every day", "same thing",
        "again", "repeat", "boring", "tedious", "routine",
    ]
    found = []
    for action in weekly_actions:
        a = action.lower()
        if any(sig in a for sig in boring_signals):
            found.append(action)
    if not found:
        found = [
            "Updating watchlist manually (no auto-refresh)",
            "Running the same company report each morning",
            "Copy-pasting research results into a spreadsheet",
        ]
    return found[:5]


def _q3_intern_tasks() -> list[str]:
    """What could a smart intern do with clear instructions?"""
    return [
        "Run daily_brief every morning and send to Telegram or Gmail",
        "Monitor watchlist tickers and flag RED/YELLOW moves",
        "Generate company reports for new watchlist additions",
        "Queue and execute batch research during off-peak hours",
        "Write weekly portfolio review every Sunday at 6 PM",
    ]


def _q4_scale_risks() -> list[dict[str, str]]:
    """What would break if 500 new users came tomorrow?"""
    return _SCALE_RISKS


def _q5_highest_leverage() -> list[dict[str, Any]]:
    """What would create the most leverage if automated?"""
    return sorted(
        _AUTOMATION_PATTERNS,
        key=lambda x: (-x["priority"], x["leverage"]),
    )[:5]


# ── Scoring and recommendation ────────────────────────────────────────────────

def _rank_opportunities(weekly_actions: list[str]) -> list[dict[str, Any]]:
    """Rank automation opportunities by relevance to this week's actions."""
    q = " ".join(a.lower() for a in weekly_actions)
    scored = []
    for entry in _AUTOMATION_PATTERNS:
        base_priority = entry["priority"]
        if entry["pattern"] in q:
            base_priority = min(base_priority + 2, 10)  # boost if seen this week
        scored.append({**entry, "priority": base_priority})
    return sorted(scored, key=lambda x: (-x["priority"], x["leverage"]))


# ── Public API ────────────────────────────────────────────────────────────────

def analyze(weekly_actions: list[str] | None = None) -> dict[str, Any]:
    """
    Run the Five Questions analysis and return a structured level-up report.

    Args:
        weekly_actions: list of strings describing what the user did this week.
                        If None, uses default common patterns.
    """
    if weekly_actions is None:
        weekly_actions = []

    repeated    = _q1_repeated_actions(weekly_actions)
    manual      = _q2_manual_boring(weekly_actions)
    intern_jobs = _q3_intern_tasks()
    scale_risks = _q4_scale_risks()
    high_leverage = _q5_highest_leverage()

    opportunities = _rank_opportunities(weekly_actions)
    top_opp = opportunities[0] if opportunities else {}

    missing_skills = _get_missing_skills()
    missing_conns  = _get_missing_connections()

    recommended_skill = top_opp.get("skill", missing_skills[0] if missing_skills else "audit")
    recommended_conn  = top_opp.get("connection") or (missing_conns[0] if missing_conns else "Telegram")

    return {
        "q1_repeated_actions":   repeated or ["No repeated actions detected this week"],
        "q2_manual_boring":      manual,
        "q3_intern_tasks":       intern_jobs,
        "q4_scale_risks":        [r["risk"] for r in scale_risks],
        "q5_highest_leverage":   [o["opportunity"] for o in high_leverage],
        "opportunities":         opportunities[:5],
        "recommended_skill":     recommended_skill,
        "recommended_connection": recommended_conn,
        "priority_score":        top_opp.get("priority", 7),
        "estimated_leverage":    top_opp.get("leverage", "medium"),
        "missing_skills":        missing_skills,
        "missing_connections":   missing_conns[:5],
        "analyzed_at":           datetime.now(timezone.utc).isoformat(),
    }


def print_report(result: dict[str, Any]) -> None:
    """Print formatted level-up report to stdout."""
    sep = "=" * 60
    print("\n" + sep)
    print("  OMEGA OS -- LEVEL-UP ENGINE")
    print(sep)

    print("\n  Q1: What did you do repeatedly this week?")
    for item in result["q1_repeated_actions"]:
        print(f"    * {item}")

    print("\n  Q2: What felt manual or boring?")
    for item in result["q2_manual_boring"]:
        print(f"    * {item}")

    print("\n  Q3: What could a smart intern do?")
    for item in result["q3_intern_tasks"]:
        print(f"    * {item}")

    print("\n  Q4: What would break at 500 users?")
    for item in result["q4_scale_risks"]:
        print(f"    * {item}")

    print("\n  Q5: Highest leverage automations:")
    for item in result["q5_highest_leverage"]:
        print(f"    * {item}")

    print("\n  " + "-" * 40)
    print("  TOP RECOMMENDATION:")
    print(f"    Skill to build:    {result['recommended_skill']}")
    print(f"    Connection to add: {result['recommended_connection']}")
    print(f"    Priority score:    {result['priority_score']}/10")
    print(f"    Estimated leverage: {result['estimated_leverage'].upper()}")

    if result["missing_skills"]:
        print(f"\n  Missing skills: {', '.join(result['missing_skills'][:4])}")
    if result["missing_connections"]:
        print(f"  Missing connections: {', '.join(result['missing_connections'][:3])}")

    print(sep + "\n")


if __name__ == "__main__":
    import sys
    actions = sys.argv[1:] if len(sys.argv) > 1 else []
    result = analyze(weekly_actions=actions)
    print_report(result)
