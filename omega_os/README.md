# Omega OS

R.A. Omega's operating system layer. Transforms the finance intelligence platform into a
Finance Intelligence Operating System with persistent context, skills, connections, and cadence.

## Structure

```
omega_os/
├── context/           Personal and business context files (who, what, why)
├── connections/       Registry of external integrations (status + auth specs)
├── decisions/         Architecture and product decision logs
├── references/        Templates, API docs, UI design guides, prompt templates
├── audits/            Four C audit results over time
├── archives/          Old versions of context files and retired skills
└── skills/            Markdown SOP files — one folder per skill
```

## Philosophy

- **Context is progressive.** Load only what each query needs.
- **Skills are deterministic.** Every skill has inputs, steps, outputs, safety rules.
- **Routing stays clean.** classify_intent_route() never receives memory or context.
- **Connections are declared before they're built.** Registry defines what's needed.
- **Cadence creates leverage.** Recurring jobs compound over time.

## Quick Start

```python
from omega_os_loader import list_skills, select_skill, load_relevant_context

# See all available skills
skills = list_skills()

# Match a user query to the right skill
skill = select_skill("Give me a company report on BlackRock", "COMPANY_RESEARCH", "company_report")

# Load only what's relevant for this query
context = load_relevant_context("Give me a daily brief", "GENERAL_FINANCE", "finance_answer")
```

## Four C Score

Run `python omega_audit.py` to get the current system health score:
- **Context** (0–25): Are the context files filled out?
- **Connections** (0–25): Are integrations registered and active?
- **Capabilities** (0–25): Are skills built and tested?
- **Cadence** (0–25): Are recurring jobs planned and scheduled?
