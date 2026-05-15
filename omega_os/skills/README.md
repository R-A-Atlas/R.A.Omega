# Skills

Deterministic SOPs for high-value, repeatable workflows.
Each skill is a folder with a skill.md file (and optionally blueprints + solution scripts).

## DBS Framework
- **[D]irection** — skill.md: name, description, steps, rules, guardrails
- **[B]lueprints** — examples, templates, style guides
- **[S]olutions** — scripts or API calls that do the heavy lifting

## Available Skills

| Skill | Description | Output Mode |
|-------|-------------|-------------|
| onboard | Walk a new user through R.A. Omega setup | chat |
| audit | Run the Four C audit and generate a report | finance_answer |
| level_up | Identify automation opportunities and next skill to build | finance_answer |
| company_report | Generate a structured company intelligence report | company_report |
| daily_brief | Generate a morning market intelligence brief | finance_answer |
| document_generator | Generate PDF/Excel/PowerPoint from query results | document |
| dashboard_generator | Generate an interactive HTML dashboard | html_artifact |
| portfolio_review | Review portfolio positions and risk exposure | finance_answer |
| research_queue | Manage and execute a queue of research tasks | finance_answer |
| watchlist_update | Update and review the watchlist with fresh data | finance_answer |
| voice_capture_triage | Transcribe voice note and route to correct skill | chat |
| weekly_product_review | Review product metrics, decisions, and roadmap | finance_answer |

## How Skills Are Selected
`omega_os_loader.select_skill(raw_query, intent, output_mode)` maps queries to skills
using keyword matching and intent. The system loads Level 1 (name/description) first,
then Level 2 (full skill.md) only when the skill is activated.
