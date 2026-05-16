# Always-On Agent Hosting — Architecture Guide

## The Two Layers

R.A. Omega has two distinct runtime layers. They are NOT the same thing:

| Layer | What it is | Where it runs |
|---|---|---|
| **Core app** | FastAPI server answering POST /query, POST /omega, all routes | Railway / Render / local uvicorn |
| **Agentic OS workers** | Scheduled background tasks (briefs, QA, health, content) | Windows Task Scheduler / Modal Cloud |

The core app is always on because it serves user requests.
Workers are scheduled — they run on a timer, write output to `atlas_vault/03-Outputs/`, and stop.

---

## Hermes (Future Operator)

**Hermes is not yet integrated.** When built, it will act as chief of staff:
- Route tasks to workers
- Coordinate multi-step plans across workers
- Surface worker output back to the user in-app

For now, workers run standalone. Do not add Hermes integration until the coordinator
pattern is designed and safety rules are written.

---

## Worker Scheduling Options

### Option A — Windows Task Scheduler (Local)

Best for:
- `visual_qa_agent` — needs local browser / screenshot access
- Any workflow requiring a local UI session or local file system
- Development and testing

Setup steps:
1. Open Task Scheduler → Create Basic Task
2. Trigger: Daily, at your preferred time (e.g., 7:00 AM)
3. Action: `python C:\Users\crist\Projects\R.A.Omega\omega_agents\<worker>\implementation\run_<worker>.py`
4. Output written to `atlas_vault/03-Outputs/`

Limitation: requires the local machine to be on and unlocked.

### Option B — Mac Launch Agent / cron (Mac users)

Best for: same use cases as Windows Task Scheduler.

Setup (cron):
```
# Daily at 7:00 AM
0 7 * * * /usr/bin/python3 /path/to/omega_agents/<worker>/implementation/run_<worker>.py
```

### Option C — Modal Cloud

Best for:
- `daily_build_brief` — git state + DONE file scan (no UI needed)
- `report_qa_agent` — deterministic verifier calls (no UI needed)
- `growth_content_agent` — file scan + content generation (no UI needed)
- `supabase_health_agent` — /health endpoint + local DB check (needs local fallback)

Modal runs Python in the cloud on a schedule. Does NOT have access to the local filesystem,
so `atlas_memory.db` and `atlas_tracker.db` must be cloud-backed for Modal runs to be useful.

Current status: **planned**. Not yet wired. Local task scheduler is the active path.

---

## Worker Safety Contract

All workers are required to obey this contract. No exceptions.

### Workers MUST NOT:
- Call any external broker API (Alpaca, IBKR, Tastytrade, Robinhood, etc.)
- Send emails, SMS, or Slack/Discord messages
- Deploy code to any cloud environment
- Execute destructive database commands (DROP, DELETE, TRUNCATE)
- Modify production database schema
- Store API keys, tokens, or secrets in logs, prompts, or output files
- Open browser sessions or click UI elements autonomously without explicit user opt-in
- Give themselves elevated permissions

### Workers MUST:
- Run only deterministic safe local stubs
- Write output exclusively to `atlas_vault/03-Outputs/` or return as string
- Degrade gracefully when subsystems are unavailable
- Log errors to `past_errors.md` via `omega_agentic_os.append_worker_error()`
- Use existing `omega_os/skills/` instead of inventing separate procedures
- Return a structured result with `.success`, `.report`, `.error`

---

## Secrets Handling

**Never store secrets in:**
- Worker output files
- `information/*.md` files
- Prompts passed to LLMs
- Git-tracked files (use `.gitignore` and `.env`)

Workers that need credentials (e.g., Supabase URL) must read them from environment
variables only:

```python
import os
url = os.getenv("SUPABASE_URL", "")
if not url:
    return SafeResult(success=False, error="SUPABASE_URL not configured")
```

---

## Worker Output Locations

| Worker | Default output file |
|---|---|
| `daily_build_brief` | `atlas_vault/03-Outputs/daily_build_brief.md` |
| `visual_qa_agent` | `atlas_vault/03-Outputs/visual_qa_report.md` |
| `report_qa_agent` | `atlas_vault/03-Outputs/report_qa.md` |
| `growth_content_agent` | `atlas_vault/03-Outputs/growth_content.md` |
| `supabase_health_agent` | `atlas_vault/03-Outputs/supabase_health.md` |

---

## Expanding the Worker Set

Before adding a new worker:

1. Add its directory under `omega_agents/<new_worker>/`
2. Create all 5 information files (instructions.md, memory.md, past_errors.md, plan.md, safety_rules.md)
3. Write implementation stub exposing `run(write_output=False) -> Result`
4. Verify `validate_worker_structure("<new_worker>")` passes
5. Add the worker to `_WORKER_DESCRIPTIONS` and `_WORKER_SKILLS` in `omega_agentic_os.py`
6. Add tests in `tests/test_omega_agents.py`
7. Update this document

Workers with destructive powers (deploy, send, delete, trade) require:
- Explicit user confirmation before execution
- `requires_confirmation=True` in their contract
- Review by the lead architect before implementation

---

## Current Hosting Status

| Worker | Hosting target | Status |
|---|---|---|
| `daily_build_brief` | Modal Cloud | planned |
| `visual_qa_agent` | Windows Task Scheduler | planned |
| `report_qa_agent` | Modal Cloud | planned |
| `growth_content_agent` | Modal Cloud | planned |
| `supabase_health_agent` | Modal Cloud | planned |

All workers are currently safe stubs executable locally via `python run_<worker>.py`.
