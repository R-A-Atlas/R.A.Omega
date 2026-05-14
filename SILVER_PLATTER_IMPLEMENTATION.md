# R.A. OMEGA — SILVER PLATTER IMPLEMENTATION
# Give this entire file to Codex as a task.
# Say: "Read this file completely and implement everything in it
#       in the order listed. Commit after each section. Do not stop
#       between sections unless tests fail."

---

## CONTEXT — WHAT WE ARE DOING

R.A. Omega has 192 data cache JSON files and 117 agents.
The problem: when agents run, they spend 80% of their context
window parsing raw JSON and only 20% doing actual analysis.
This degrades output quality and wastes API tokens.

The solution (from agentic OS best practices):
1. Create summary tables — distill each raw cache into compact signals
2. Add hooks — inject context automatically at session start
3. Build critical paths — give agents step-by-step SOPs
4. Clean up CLAUDE.md to reflect true current state

---

## SECTION 1 — CREATE SUMMARY TABLES

For each major data cache file, create a companion summary file.
The summary file contains ONLY the 5-10 most important signals.
Agents read the summary by default, raw file only if they need depth.

Create: atlas_core/summaries/summary_generator.py

This script reads each *_latest.json and outputs a *_summary.json.

### Summary schemas to implement:

crypto_top50_summary.json:
{
  "generated_at": "ISO timestamp",
  "top_gainer": {"symbol": "", "change_pct": 0},
  "top_loser": {"symbol": "", "change_pct": 0},
  "highest_volume": {"symbol": "", "volume_usd": 0},
  "meme_count": 0,
  "utility_count": 0,
  "market_regime": "RISK_ON|RISK_OFF|NEUTRAL",
  "signal": "BULLISH|BEARISH|MIXED"
}

equities_summary.json:
{
  "generated_at": "ISO timestamp",
  "top_gainer": {"ticker": "", "change_pct": 0, "sector": ""},
  "top_loser": {"ticker": "", "change_pct": 0, "sector": ""},
  "most_active": {"ticker": "", "volume": 0},
  "hot_sector": "",
  "cold_sector": "",
  "breadth_signal": "EXPANDING|CONTRACTING|NEUTRAL"
}

options_flow_summary.json:
{
  "generated_at": "ISO timestamp",
  "unusual_calls": [{"ticker": "", "signal_strength": ""}],
  "unusual_puts": [{"ticker": "", "signal_strength": ""}],
  "put_call_ratio_signal": "BULLISH|BEARISH|NEUTRAL",
  "top_conviction_ticker": ""
}

bond_yields_summary.json:
{
  "generated_at": "ISO timestamp",
  "curve_signal": "NORMAL|INVERTED|FLAT",
  "recession_signal": "LOW|MEDIUM|HIGH",
  "2y_rate": 0,
  "10y_rate": 0,
  "spread_2y_10y": 0
}

cpi_summary.json:
{
  "generated_at": "ISO timestamp",
  "yoy_change_pct": 0,
  "trend": "ACCELERATING|DECELERATING|STABLE",
  "hot_categories": [],
  "fed_implication": "HAWKISH|DOVISH|NEUTRAL"
}

congress_trades_summary.json:
{
  "generated_at": "ISO timestamp",
  "most_bought_tickers": [],
  "most_sold_tickers": [],
  "net_sentiment": "BULLISH|BEARISH|MIXED",
  "notable_trade": {"member": "", "ticker": "", "action": ""}
}

Create summaries for ALL 64+ cache files following same pattern.
Store in: data_cache/summaries/

Run summary_generator.py as part of each agent's scraper output.
When a scraper writes *_latest.json it also writes *_summary.json.

After implementing:
  python -m py_compile atlas_core/summaries/summary_generator.py
  python atlas_core/summaries/summary_generator.py
  Confirm summary files appear in data_cache/summaries/
  Commit: "Add silver platter summary layer for all data caches"

---

## SECTION 2 — UPDATE OMEGA TO READ SUMMARIES FIRST

Update atlas_omega.py data cache loading:
  _load_internal_knowledge_payload() should:
  1. Try to read *_summary.json first (fast, compact)
  2. Fall back to full *_latest.json only if summary missing
  3. Log which path was taken for debugging

This reduces context tokens consumed by ~80% for standard queries.
Only deep research queries should load the full raw cache.

After implementing:
  python -m py_compile atlas_omega.py
  python -m pytest tests/ -q
  Commit: "Omega reads summary layer first for compact context"

---

## SECTION 3 — ADD CLAUDE CODE HOOKS

Create: .claude/hooks/

### Hook 1: Session start context injection
File: .claude/hooks/session_start.md

Content:
"""
# R.A. Omega Session Start Hook
# Auto-injected at the start of every Claude Code session

## Project Identity
Name: R.A. Omega — AI Finance Model
Location: C:\Users\crist\Projects\R.A.Omega
Server: uvicorn api_server:app --host 127.0.0.1 --port 8000

## Current State (auto-updated)
- 117 agents: all BUILT+VERIFIED
- 962 tests passing
- Main UI: ra_omega_app.html at /app
- Brand: R.A. Omega (#0B1020, #18C6C8, Space Grotesk)

## Iron Rules (never break these)
- Never modify: deep_research.py, gemini_limiter.py
- Never delete: atlas_memory.db, atlas_tracker.db
- Always run pytest after changes
- Always update CLAUDE.md after completing a task

## First action every session
Read CLAUDE.md completely before touching any file.
"""

### Hook 2: Post-compaction memory injection
File: .claude/hooks/post_compact.md

Content:
"""
# R.A. Omega — Post-Compaction Memory Restore

The conversation was just compacted. Here is what you need to know:

## What R.A. Omega is
A 117-agent AI financial intelligence platform.
POST /query runs the 10-loop engine (~$0.017, ~154-176s).
POST /omega runs OmegaAgent (fast, cross-domain queries).
Main UI at /app served by FastAPI at port 8000.

## What we were working on
[Claude Code fills this in from the last 5 messages before compact]

## Do not re-explain or re-introduce yourself.
Continue from where we were.
"""

### Hook 3: Pre-commit validation
File: .claude/hooks/pre_commit.md

Content:
"""
# Pre-Commit Validation Hook
# Runs before every git commit

Before committing, verify:
1. python -m py_compile api_server.py (must pass)
2. python -m pytest tests/ -q (must stay at 962+ passing)
3. CLAUDE.md Section 8 updated if something new was built
4. AGENT_REGISTRY.md updated if any agent status changed

If any check fails: fix before committing.
"""

After creating hooks:
  Commit: "Add Claude Code session hooks for context continuity"

---

## SECTION 4 — BUILD CRITICAL PATHS FOR TOP 5 AGENTS

A critical path is a step-by-step SOP that tells an agent exactly
what to do — no guessing, no open-ended exploration.
Agents with critical paths are deterministic and fast.

### Critical Path 1: OmegaAgent crypto query
File: atlas_agents/cognitive/critical_paths/crypto_query_path.md

"""
# Critical Path: Crypto Market Query

TRIGGER: classify_intent_route() returns CRYPTO_MARKET_SCAN

STEP 1: Read data_cache/summaries/crypto_top50_summary.json
        (NOT the full raw file — summary only)
STEP 2: Check market_regime field
        If RISK_OFF: lead with caution signal
        If RISK_ON: lead with opportunity signal
STEP 3: Pull top_gainer and top_loser with their change_pct
STEP 4: Check if any ticker matches user's watchlist
        (GET /watchlist — only if user is authenticated)
STEP 5: Generate response using this template:
        - Market regime: [signal]
        - Top mover: [ticker] [change]%
        - Key signal: [from summary]
        - Recommendation: [based on regime + movers]
STEP 6: Append standard disclaimer

DO NOT: Read the full 50-coin raw JSON
DO NOT: Make up tickers not in the summary
DO NOT: Give specific buy/sell recommendations without data
"""

### Critical Path 2: Equity query
### Critical Path 3: Macro query
### Critical Path 4: Options flow query
### Critical Path 5: Portfolio analysis query

Create all 5 critical paths following the same structure.
Store in: atlas_agents/cognitive/critical_paths/

After implementing:
  Commit: "Add critical paths for top 5 query types"

---

## SECTION 5 — CREATE THE DATA MAP

Create: atlas_core/data_map.py

This script generates a visual HTML data map showing:
- All data sources (which agents produce what)
- Summary layer (what summaries exist)
- Critical paths (which paths are defined)
- Gap analysis (what's missing)

Output: atlas_vault/03-Outputs/data_map.html

The HTML shows three sections:
1. PANTRY — all data sources and cache files with freshness timestamps
2. PREP TABLE — summary files, what's been distilled
3. PLATE — critical paths, what the agents can actually do with data

Run:
  python atlas_core/data_map.py
  Open atlas_vault/03-Outputs/data_map.html in browser
  Confirm it shows all 64 cache files + summaries + critical paths

Commit: "Add data map generator and output"

---

## SECTION 6 — SYNC CLAUDE.MD TO REALITY

This is the most important step. CLAUDE.md must reflect the TRUE
current state of the project, not what was planned or hoped for.

Read every file that has been modified or created.
Then rewrite CLAUDE.md Section 8 (Confirmed Working) to show:

For each confirmed working item:
  ✅ [Feature] — [exact file/line where it lives] — [how to test]

For each item that is partially working:
  ⚠️ [Feature] — [what works] — [what's missing]

For each item that is NOT working or not built:
  ❌ [Feature] — [reason]

Also update:
  Section 4 (How to Start Server) — confirm current paths
  Section 5 (File Map) — add all new files
  Section 9 (Priority Build List) — cross off completed items
  Section 10 (Business Roadmap) — update current phase

After rewriting:
  Commit: "Sync CLAUDE.md to true current project state"

---

## SECTION 7 — THE MORNING BRIEF SKILL

Create a slash command that generates a daily morning brief.
File: .claude/commands/morning.md

Content:
"""
# /morning — R.A. Omega Morning Intelligence Brief

Run this at the start of each day to get a full system status.

STEP 1: Read all summary files in data_cache/summaries/
STEP 2: Check which cache files are stale (>24 hours old)
STEP 3: Run python -m pytest tests/ -q --tb=no
STEP 4: Check AGENT_REGISTRY.md for any PENDING agents
STEP 5: Read CLAUDE.md Section 9 (Priority Build List)

OUTPUT FORMAT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
R.A. OMEGA — MORNING BRIEF [date]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM: X/117 agents active | X tests passing
MARKET: [crypto signal] | [equity signal] | [macro signal]
STALE DATA: [list any cache files older than 24h]
TOP PRIORITY: [from CLAUDE.md Section 9]
TODAY'S TASK: [what to build today]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

After creating:
  Test with: /morning in Claude Code
  Confirm output matches format above
  Commit: "Add /morning daily brief slash command"

---

## FINAL STEP — FULL AUDIT

After completing all sections above, run:

  python -m pytest tests/ -q
  python atlas_core/data_map.py
  python atlas_core/summaries/summary_generator.py

Then write CODEX_DONE.md with:
  - Every file created
  - Every file modified
  - Test count before and after
  - Summary layer coverage (X/64 cache files have summaries)
  - Critical paths created (X/5)
  - Hooks created (X/3)
  - Any sections that could not be completed and why

Commit everything with: "Silver platter + hooks + critical paths complete"
