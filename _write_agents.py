"""Write omega_agents/ directory structure with information files."""
import os
from pathlib import Path

ROOT = Path(__file__).parent
BASE = ROOT / "omega_agents"

# ── README ─────────────────────────────────────────────────────────────────────

README = """\
# omega_agents/ — Agentic OS Worker Foundation

This directory contains the safe, always-on worker layer for R.A. Omega.

## Double AI Framework

Each worker has two folders:

```
<worker_name>/
├── information/    <- What the worker knows (instructions, memory, plans, safety)
│   ├── instructions.md
│   ├── memory.md
│   ├── past_errors.md
│   ├── plan.md
│   └── safety_rules.md
└── implementation/ <- What the worker does (executable safe stub)
    └── run_<worker>.py
```

## Workers (5)

| Worker | Purpose | Skill(s) Used |
|---|---|---|
| daily_build_brief | Daily engineering summary from DONE files + git state | improve_system |
| visual_qa_agent | Reviews screenshots and UI notes for visual QA findings | visual_qa |
| report_qa_agent | Tests sample outputs (BlackRock, TSLA, apple pie) | company_report, trade_plan, general_chat, source_verification, improve_system |
| growth_content_agent | Turns progress into content ideas, posts, launch updates | (planned: content skill) |
| supabase_health_agent | Checks persistence, table availability, research queue health | source_verification, improve_system |

## Hosting (Planned)

- **Local / Windows Task Scheduler**: best for visual QA, UI screenshots, browser workflows
- **Modal Cloud**: best for daily briefs, DB checks, content generation, health checks
- **Hermes**: future operator / chief of staff — not yet integrated

## Safety Contract

All workers must:
- Never call external broker APIs
- Never send emails
- Never deploy code
- Never modify production database schema
- Never trade or place orders
- Never store secrets in logs or prompts
- Always degrade gracefully when dependencies are unavailable
- Always record errors in past_errors.md

Workers use `omega_os/skills/` for structured procedures — never invent separate workflows.
"""

# ── Information file templates per worker ──────────────────────────────────────

WORKERS = {
    "daily_build_brief": {
        "instructions": """\
# daily_build_brief — Instructions

## What This Worker Does
Reads recent DONE files, git log, test state, and the current roadmap to produce a
concise daily build brief. Outputs a markdown summary of what was shipped, what is in
progress, and what the next priority is.

## When to Run
- Daily, at the start of the build session (morning or first session of the day)
- Triggered manually or via Windows Task Scheduler / Modal cron

## Skills Used
- `improve_system` — analyze project state and produce engineering recommendations

## Input Sources (read-only, safe)
- `*_DONE.md` files in project root (pattern: `*.DONE.md` or `*_DONE.md`)
- `git log --oneline -20` — last 20 commits
- `python -m pytest tests/ --tb=no -q` — test count summary
- `CLAUDE.md` Section 9 (priority build list)

## Output
- A markdown brief with:
  - SHIPPED TODAY / RECENTLY: list of DONE files
  - TEST STATE: passed / failed count
  - LAST 5 COMMITS: brief log
  - NEXT PRIORITY: single next action from roadmap

## Error Recording
On any failure, append to `past_errors.md` with timestamp, error type, and context.

## How to Improve
After each run, append one line to `memory.md` with the date and what changed.
If the brief is consistently missing something, update `plan.md`.
""",
        "memory": """\
# daily_build_brief — Memory

## Session Log
<!-- Append one line per run: DATE | DONE_FILES_FOUND | TEST_COUNT | NEXT_PRIORITY -->

2026-05-16 | Skill architecture complete | 2169 tests | Agentic OS workers
""",
        "past_errors": """\
# daily_build_brief — Past Errors

## Error Log
<!-- Format: DATE | ERROR_TYPE | CONTEXT | RESOLUTION -->

(no errors recorded yet)
""",
        "plan": """\
# daily_build_brief — Plan

## Current Plan (v1)
1. Scan project root for `*_DONE.md` files (glob pattern)
2. Read `git log --oneline -20`
3. Run `python -m pytest tests/ --tb=no -q` and capture count line
4. Read CLAUDE.md Section 9 for next priority
5. Format and return markdown brief

## Future Enhancements
- Auto-post brief to a Slack channel (when Hermes is integrated)
- Compare with previous day's brief to highlight velocity
- Add Modal cron trigger for automated daily run
""",
        "safety_rules": """\
# daily_build_brief — Safety Rules

1. Read-only operations only. Do not write to any source files.
2. Do not commit, push, or modify git state.
3. Do not call external APIs or require credentials.
4. Do not store secrets in output or logs.
5. Do not send emails or messages.
6. Do not deploy or restart servers.
7. If git or pytest is unavailable, degrade gracefully and note in output.
8. Output goes to stdout or a local markdown file — never to a database directly.
""",
    },

    "visual_qa_agent": {
        "instructions": """\
# visual_qa_agent — Instructions

## What This Worker Does
Reviews screenshots, UI notes, and visual artifacts to produce structured visual QA
findings. Identifies regressions, layout issues, missing elements, and UX problems
in the R.A. Omega UI.

## When to Run
- After any UI change to ra_omega_app.html, auth.html, or index_*.html
- After a server restart and manual test session
- Weekly visual regression check

## Skills Used
- `visual_qa` — answer questions about charts, UI screenshots, and visual artifacts

## Input Sources (read-only, safe)
- Screenshots saved to `atlas_vault/01-Raw/Screenshots/`
- UI notes in `atlas_vault/01-Raw/` or provided inline
- `ra_omega_app.html`, `auth.html`, `index_*.html` (read-only)

## Output
- A markdown QA report with:
  - PASS/FAIL for each UI element checked
  - Screenshots referenced by filename
  - Issues found with severity (Critical / High / Medium / Low)
  - Recommended fixes

## Error Recording
On any failure, append to `past_errors.md` with timestamp, screenshot name, and issue.

## How to Improve
After each QA run, append findings summary to `memory.md`.
Update `plan.md` if new UI elements need systematic coverage.
""",
        "memory": """\
# visual_qa_agent — Memory

## Session Log
<!-- Append one line per run: DATE | SCREENSHOTS_REVIEWED | ISSUES_FOUND | SEVERITY -->

(no runs recorded yet)
""",
        "past_errors": """\
# visual_qa_agent — Past Errors

## Error Log
<!-- Format: DATE | SCREENSHOT | ISSUE | RESOLUTION -->

(no errors recorded yet)
""",
        "plan": """\
# visual_qa_agent — Plan

## Current Plan (v1)
1. Scan `atlas_vault/01-Raw/Screenshots/` for new screenshots
2. For each screenshot, run visual_qa skill analysis
3. Check for: structured response cards, trade card gating, export bar, sessions sidebar
4. Output markdown QA report to `atlas_vault/03-Outputs/visual_qa_<date>.md`

## UI Elements to Always Check
- StructuredResponse cards render for company_report and trade_plan
- Chat bubble renders for general_chat (no trade cards)
- Sessions sidebar: new chat, list, rename, delete
- ExportBar: Copy JSON, Listen (TTS) buttons
- Live market regime chip in header

## Future Enhancements
- Automated screenshot capture via Playwright (when local hosting is set up)
- Diff screenshots against baseline to catch regressions automatically
""",
        "safety_rules": """\
# visual_qa_agent — Safety Rules

1. Read screenshots and UI notes only. Do not modify any HTML or JS files.
2. Do not call external APIs or image APIs.
3. Do not store PII or user data found in screenshots.
4. Do not write to the main application files.
5. Output QA reports go to atlas_vault/03-Outputs/ only.
6. If a screenshot cannot be parsed, note it and skip — do not fail silently.
7. Do not send QA reports externally (no email, no Slack yet).
""",
    },

    "report_qa_agent": {
        "instructions": """\
# report_qa_agent — Instructions

## What This Worker Does
Tests the R.A. Omega query pipeline with known sample queries to verify output quality.
Checks that company_report, trade_plan, and general_chat outputs are correctly formatted,
contain required sections, and have no trade bleed.

## When to Run
- After any change to output_modes.py, output_contracts.py, quality_firewall.py, or prompt_builder.py
- After any change to the synthesis prompt
- Weekly regression check

## Skills Used
- `company_report` — verify BlackRock / NVDA / Goldman reports
- `trade_plan` — verify TSLA / NVDA trade setup outputs
- `general_chat` — verify "apple pie" and casual queries
- `source_verification` — verify cited data sources in reports
- `improve_system` — analyze failures and produce repair recommendations

## Sample Queries (canonical test set)
1. "Give me everything on BlackRock" → expected: company_report, paper_report renderer, no trade cards
2. "Give me a TSLA trade setup" → expected: trade_plan, trade_cards renderer, stop loss present
3. "How do I make apple pie?" → expected: chat, chat_bubble renderer, no trade sections
4. "Analyze NVDA — current setup" → expected: company_report, paper_report
5. "Goldman Sachs research" → expected: company_report

## Output
- Markdown QA report with PASS/FAIL per query
- Failure details: what was expected vs. what was produced
- Overall PASS/FAIL status

## Error Recording
On any failure, append to `past_errors.md` with query, expected output, actual output, and date.

## How to Improve
After each run, append summary to `memory.md`.
If a query consistently fails, add it to `plan.md` as a tracked regression.
""",
        "memory": """\
# report_qa_agent — Memory

## Session Log
<!-- Append one line per run: DATE | QUERIES_TESTED | PASS_COUNT | FAIL_COUNT -->

(no runs recorded yet)
""",
        "past_errors": """\
# report_qa_agent — Past Errors

## Error Log
<!-- Format: DATE | QUERY | EXPECTED | ACTUAL | RESOLUTION -->

(no errors recorded yet)
""",
        "plan": """\
# report_qa_agent — Plan

## Current Plan (v1)
1. Run canonical test queries through quality_firewall.validate_response() locally
2. For company_report queries: use verify_company_report verifier
3. For trade_plan queries: use verify_trade_plan verifier
4. For chat queries: check no trade sections present
5. Output pass/fail report to stdout or atlas_vault/03-Outputs/

## Canonical Query Set
| Query | Expected output_mode | Expected renderer | Key checks |
|---|---|---|---|
| "Give me everything on BlackRock" | company_report | paper_report | no trade cards, executive summary present |
| "Give me a TSLA trade setup" | trade_plan | trade_cards | stop loss present, entry present |
| "How do I make apple pie?" | chat | chat_bubble | no trade sections |
| "Analyze NVDA" | company_report | paper_report | no trade cards |
| "Goldman Sachs research" | company_report | paper_report | no trade cards |

## Future Enhancements
- Live end-to-end tests against running server (POST /query)
- Compare output quality scores over time
""",
        "safety_rules": """\
# report_qa_agent — Safety Rules

1. Use local deterministic verifiers only — do not call external AI APIs for QA checks.
2. Do not modify query results or synthesis outputs.
3. Do not write to any source files or database tables.
4. Do not store user query results in permanent logs (use session-scoped temp files only).
5. QA reports go to atlas_vault/03-Outputs/ or stdout only.
6. Do not send QA results externally (no email, no Slack yet).
7. If verifiers are unavailable, degrade gracefully and note in output.
""",
    },

    "growth_content_agent": {
        "instructions": """\
# growth_content_agent — Instructions

## What This Worker Does
Turns R.A. Omega engineering progress into content ideas, social posts, launch updates,
and marketing scripts. Reads DONE files and git log to identify shippable milestones,
then drafts content for Twitter/X, Reddit, and Product Hunt launches.

## When to Run
- Weekly, after a meaningful shipping week
- Before any public launch or beta announcement
- When preparing r/algotrading, r/options, or FinTwit posts

## Skills Used
- (Planned) `content_generator` skill — when added to omega_os/skills/
- For now: reads DONE files and formats them manually into content templates

## Content Formats
- Twitter/X thread (5-10 tweets)
- Reddit post for r/algotrading or r/options (narrative format)
- Product Hunt launch copy (tagline, description, first comment)
- Feature demo script (for video or screen recording)

## Output
- Markdown file with drafted content, organized by format
- Saved to `atlas_vault/03-Outputs/content_<date>.md`
- NOT posted automatically — always requires human review and approval

## Error Recording
On any failure, append to `past_errors.md` with date, content type, and issue.

## How to Improve
After each run, append to `memory.md`: what content was drafted, what performed well.
Update `plan.md` with upcoming launch milestones.
""",
        "memory": """\
# growth_content_agent — Memory

## Session Log
<!-- Append one line per run: DATE | MILESTONE | CONTENT_TYPES_DRAFTED | STATUS -->

2026-05-16 | Skill architecture shipped | (first run pending) | not yet active
""",
        "past_errors": """\
# growth_content_agent — Past Errors

## Error Log
<!-- Format: DATE | CONTENT_TYPE | ISSUE | RESOLUTION -->

(no errors recorded yet)
""",
        "plan": """\
# growth_content_agent — Plan

## Current Plan (v1)
1. Read all `*_DONE.md` files from project root
2. Identify milestones worth posting (new features, perf improvements, test milestones)
3. Draft content for each identified milestone in Twitter/X and Reddit formats
4. Save to atlas_vault/03-Outputs/content_<date>.md

## Upcoming Milestones to Cover
- Skill architecture (10 core skills, deterministic verifiers) — READY TO POST
- Pipeline refactor (central planner, output mode routing) — READY TO POST
- Beta launch on Railway — PLANNED

## Content Ideas Backlog
- "We built a quality firewall that catches trade bleed before it hits users"
- "How we verified 2169 tests pass with zero failures"
- "The 10 skills that power R.A. Omega's AI output routing"

## Future Enhancements
- Add `content_generator` skill to omega_os/skills/
- Auto-format for LinkedIn and email newsletter
- Track post performance in memory.md
""",
        "safety_rules": """\
# growth_content_agent — Safety Rules

1. Draft content only — never auto-post to any social platform.
2. All drafted content requires human review and approval before publishing.
3. Do not include API keys, internal URLs, or Supabase credentials in content.
4. Do not reveal internal engineering details that could be a security risk.
5. Do not claim performance metrics that haven't been verified.
6. Content output goes to atlas_vault/03-Outputs/ only — never directly to social media APIs.
7. Do not send emails or direct messages.
""",
    },

    "supabase_health_agent": {
        "instructions": """\
# supabase_health_agent — Instructions

## What This Worker Does
Checks the health of the R.A. Omega persistence layer: Supabase table availability,
recent report counts, session state, research queue, and local SQLite databases.
Reports health status without modifying any data.

## When to Run
- Daily, before the build session starts
- After any schema migration or deployment
- When users report persistence errors

## Skills Used
- `source_verification` — verify data sources are accessible
- `improve_system` — analyze failures and suggest fixes

## Checks Performed (read-only)
1. Local SQLite: atlas_memory.db exists and is readable
2. Local SQLite: atlas_tracker.db exists and is readable
3. Supabase: GET /sessions returns 200 or expected error (503 if not configured)
4. Supabase: GET /health returns 200
5. File system: atlas_vault/03-Outputs/ is writable
6. File system: recent DONE files exist (project is active)

## Output
- Health status report: each check as PASS / FAIL / WARN
- Overall status: HEALTHY / DEGRADED / DOWN
- Saved to stdout or atlas_vault/03-Outputs/health_<date>.md

## Error Recording
On any check failure, append to `past_errors.md` with check name, error, and timestamp.

## How to Improve
After each run, append one line to `memory.md`: date, overall status, notable issues.
""",
        "memory": """\
# supabase_health_agent — Memory

## Session Log
<!-- Append one line per run: DATE | OVERALL_STATUS | NOTABLE_ISSUES -->

(no runs recorded yet)
""",
        "past_errors": """\
# supabase_health_agent — Past Errors

## Error Log
<!-- Format: DATE | CHECK_NAME | ERROR | RESOLUTION -->

(no errors recorded yet)
""",
        "plan": """\
# supabase_health_agent — Plan

## Current Plan (v1)
1. Check local databases (atlas_memory.db, atlas_tracker.db) — file exists + readable
2. Check GET /health endpoint (if server is running locally)
3. Check GET /sessions endpoint (Supabase availability)
4. Check atlas_vault/03-Outputs/ is writable
5. Report HEALTHY / DEGRADED / DOWN

## Known Degraded States
- ATLAS_DISABLE_AUTH=true → Supabase not configured → /sessions returns 503 → WARN (expected in dev)
- No server running → /health unreachable → WARN (expected when server not started)

## Future Enhancements
- Monitor query count trends (queries table row count over time)
- Alert when atlas_memory.db exceeds 500MB
- Add Modal cron trigger for automated daily health check
""",
        "safety_rules": """\
# supabase_health_agent — Safety Rules

1. Read-only checks only. Do not write to any database or table.
2. Do not run migrations or schema changes.
3. Do not call external broker or financial APIs.
4. Do not store credentials in logs or output files.
5. If Supabase is unavailable, report DEGRADED — do not attempt to reconnect repeatedly.
6. Do not send health alerts externally (no email, no Slack yet).
7. Output goes to stdout or atlas_vault/03-Outputs/ only.
8. Never delete or truncate any table or file.
""",
    },
}


def write_information(worker: str, data: dict) -> None:
    info_dir = BASE / worker / "information"
    info_dir.mkdir(parents=True, exist_ok=True)
    impl_dir = BASE / worker / "implementation"
    impl_dir.mkdir(parents=True, exist_ok=True)

    (info_dir / "instructions.md").write_text(data["instructions"], encoding="utf-8")
    (info_dir / "memory.md").write_text(data["memory"], encoding="utf-8")
    (info_dir / "past_errors.md").write_text(data["past_errors"], encoding="utf-8")
    (info_dir / "plan.md").write_text(data["plan"], encoding="utf-8")
    (info_dir / "safety_rules.md").write_text(data["safety_rules"], encoding="utf-8")
    print(f"  wrote {worker}/information/")


if __name__ == "__main__":
    BASE.mkdir(exist_ok=True)
    (BASE / "README.md").write_text(README, encoding="utf-8")
    print("  wrote README.md")

    for worker, data in WORKERS.items():
        write_information(worker, data)

    print("Done.")
