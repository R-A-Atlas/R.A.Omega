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
