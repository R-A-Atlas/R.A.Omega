# /morning - R.A. Omega Morning Intelligence Brief

Run this at the start of each day to get a full system status.

STEP 1: Read all summary files in `data_cache/summaries/`.
STEP 2: Check which cache files are stale, defined as older than 24 hours.
STEP 3: Run `python -m pytest tests/ -q --tb=no`.
STEP 4: Check `AGENT_REGISTRY.md` for any `PENDING` agents.
STEP 5: Read `CLAUDE.md` Section 9, Priority Build List.

OUTPUT FORMAT:

```text
----------------------------
R.A. OMEGA - MORNING BRIEF [date]
----------------------------
SYSTEM: X/117 agents active | X tests passing
MARKET: [crypto signal] | [equity signal] | [macro signal]
STALE DATA: [list any cache files older than 24h]
TOP PRIORITY: [from CLAUDE.md Section 9]
TODAY'S TASK: [what to build today]
----------------------------
```

Rules:
- Do not invent market signals. Use the summary files or say unavailable.
- If tests fail, make the failing test group the top priority.
- If any PENDING agent exists, include the first affected division.
- Keep the brief short enough to read in under one minute.
