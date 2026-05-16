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
