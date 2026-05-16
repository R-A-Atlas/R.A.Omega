# R.A. Omega Skill Architecture

## Core Concepts

### Pipeline = Spine
`omega_pipeline.py` is the spine of every request. It decides route, output_mode,
workflow, renderer_type, and deep_research flag. Skills plug into the pipeline;
they do not replace it.

```
Input → API → Intent Router → omega_pipeline.plan_request()
              ↓
              skill = get_skill_for_output_mode(output_mode)
              ↓
        Workflow Executor (company_report_fast, trade_analysis, etc.)
        ↓
        omega_os_loader.load_skill_instructions(skill)  ← only if skill matched
        ↓
        prompt_builder.build_synthesis_prompt(skill_context=...)
        ↓
        Model / Synthesis
        ↓
        quality_firewall.validate_response()
        ↓  (optionally calls skill verification tool)
        verify_company_report.py / verify_trade_plan.py
        ↓
        Renderer → Output → Persistence/Export
```

### Skills = Reusable Procedures
A skill is a versioned, documented procedure for a specific repeated task.
It defines: what it does, when to use it, required inputs, output contract,
safety rules, examples, repair strategy, and related skills.

Skills are NOT random prompt snippets. They are structured documents with
deterministic verification tools.

### Agents = Specialists / Reviewers / Coordinators
Agents are roles. They decide what to do, review quality, or coordinate
between skills. The pipeline planner is an agent. The quality firewall is
an agent. Skills are what those agents use.

### Tools/Scripts = Deterministic Operations
Each skill's `tools/` directory contains Python scripts that:
- Never call external APIs or LLMs
- Never require API keys
- Are fully deterministic
- Can be run standalone for testing

Examples: verify_company_report.py, verify_trade_plan.py, audit_skills.py

### Memory/Context = Supporting Knowledge
Context files in `omega_os/context/` are loaded per intent, not globally.
Skill instructions are loaded only when the skill is activated.
Nothing is dumped into every prompt.

---

## Skill Registry

`omega_skill_registry.py` provides progressive disclosure:

| Level | Function | Content | When |
|---|---|---|---|
| 1 | `list_skills()` | name + description | Always fast |
| 2 | `load_skill_instructions(skill)` | Full SKILL.md | When skill is activated |
| 3 | `get_skill_contract(skill)` | contract.json | Quality check / planning |
| 4 | `get_skill_tools(skill)` | Tool script paths | When verification runs |

**Never** load all skills at once into a prompt. The registry exists to keep
context lean.

---

## Standard Skill Structure

```
omega_os/skills/<skill_name>/
├── SKILL.md         — Instructions, rules, examples, repair strategy
├── examples.md      — Real input/output examples for testing + few-shot
├── contract.json    — Machine-readable metadata and safety flags
├── tools/           — Deterministic Python verification/export scripts
├── tests/           — Tests for the skill's tools
└── CHANGELOG.md     — Versioned change log for the skill
```

### SKILL.md Required Sections
- `name` — skill identifier
- `description` — one-line summary
- `when_to_use` — conditions that activate this skill
- `when_not_to_use` — explicit exclusions
- `required_inputs` — what the skill needs
- `output_contract` — what a valid output looks like
- `safety_rules` — hard rules that cannot be violated
- `examples` — concrete input/output pairs
- `repair_strategy` — what to do when output fails validation
- `related_skills` — other skills to consider

### contract.json Required Fields
- `name`, `description`
- `output_mode` — maps to pipeline output_mode
- `renderer_type` — chat_bubble, paper_report, trade_cards, document, html_artifact
- `auto_invocable` — pipeline can activate without user asking
- `user_invocable` — user can ask for it directly
- `requires_confirmation` — must ask user before running
- `destructive` — modifies external state (file, DB, API)
- `required_sections` — sections that must be in the output
- `forbidden_sections` — sections that must NOT appear
- `related_tools` — deterministic tool scripts for this skill

---

## Safety Rules

1. **No skill may have `destructive=true` and `auto_invocable=true` simultaneously.**
2. Skills that send email, push code, modify schema, or call broker APIs must have
   `requires_confirmation=true` and `auto_invocable=false`.
3. All current 10 core skills are `destructive=false`.
4. Verification tools must be deterministic and API-key-free.

---

## Avoiding Skill Debt

- Keep the active skill count small (target: ≤ 15 core skills).
- Retire skills that are never activated.
- Update CHANGELOG.md after any failure or edge case repair.
- Prefer updating one skill over creating two specialized variants.

---

## Active Core Skills (10)

| Skill | output_mode | renderer_type | auto_invocable |
|---|---|---|---|
| company_report | company_report | paper_report | true |
| trade_plan | trade_plan | trade_cards | true |
| general_chat | chat / general_chat | chat_bubble | true |
| document_generator | document | document | false |
| dashboard_generator | html_artifact | html_artifact | false |
| source_verification | (any) | (any) | true |
| report_export | (any) | document | false |
| capture_triage | (any) | chat_bubble | false |
| visual_qa | (any) | chat_bubble | false |
| improve_system | (any) | chat_bubble | false |
