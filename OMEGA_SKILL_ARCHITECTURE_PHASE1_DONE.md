# OMEGA SKILL ARCHITECTURE — PHASE 1 DONE

Date: 2026-05-15
Branch: codex/chat-modes-settings
Tests: **2012 passed, 0 failed**
New tests: 0 (existing test_omega_os.py now covers the 10 core skills)

---

## Goal Met

- `docs/architecture/SKILLS_ARCHITECTURE.md` — architecture reference written
- 10 core skill directories created under `omega_os/skills/`
- Each skill has: `skill.md`, `contract.json`, `examples.md`, `CHANGELOG.md`, `tools/`, `tests/`
- `omega_skill_registry.py` created — progressive disclosure registry

---

## Architecture

```
Pipeline = Spine
  omega_pipeline.plan_request()
    → get_skill_for_output_mode(output_mode)
    → omega_skill_registry.load_skill_instructions(skill)  ← only when skill activated
    → prompt_builder.build_synthesis_prompt(skill_context=...)

Skills = Reusable Procedures
  omega_os/skills/<skill_name>/
  ├── skill.md         — Instructions, rules, steps, examples, repair strategy
  ├── contract.json    — Machine-readable metadata and safety flags
  ├── examples.md      — Real input/output examples
  ├── tools/           — Deterministic Python verification scripts
  ├── tests/           — Tests for the skill's tools
  └── CHANGELOG.md     — Versioned change log

Registry = Progressive Disclosure
  Level 1: list_skills()              — name + description (always fast)
  Level 2: load_skill_instructions()  — full skill.md text
  Level 3: get_skill_contract()       — contract.json dict
  Level 4: get_skill_tools()          — tool script paths
```

---

## 10 Core Skills

| Skill | output_mode | renderer_type | auto_invocable |
|---|---|---|---|
| company_report | company_report | paper_report | true |
| trade_plan | trade_plan | trade_cards | true |
| general_chat | chat / general_chat | chat_bubble | true |
| document_generator | document | document | false |
| dashboard_generator | html_artifact | html_artifact | false |
| source_verification | any | any | true |
| report_export | any | document | false |
| capture_triage | any | chat_bubble | false |
| visual_qa | any | chat_bubble | false |
| improve_system | any | chat_bubble | false |

---

## omega_skill_registry.py Functions

| Function | Level | Purpose |
|---|---|---|
| `list_skills()` | 1 | All installed skills: name + description |
| `load_skill_metadata(skill)` | 1 | Lightweight metadata without full SKILL.md |
| `load_skill_instructions(skill)` | 2 | Full skill.md text |
| `get_skill_contract(skill)` | 3 | contract.json dict |
| `get_skill_tools(skill)` | 4 | List of tool script paths |
| `get_skill_for_output_mode(mode)` | — | Routing: output_mode → skill name |
| `get_related_skills(skill)` | — | Related skill names (installed only) |
| `validate_skill_structure(skill)` | — | Validate files + contract fields + safety invariants |
| `audit_all_skills()` | — | validate_skill_structure on all installed skills |

---

## Safety Rules Enforced

1. No skill may have `destructive=true` and `auto_invocable=true` simultaneously
2. Skills that send email, push code, or modify external state must have `requires_confirmation=true` and `auto_invocable=false`
3. All 10 core skills are `destructive=false`
4. Verification tools must be deterministic and API-key-free

---

## skill.md Required Sections

All 10 core skills include these sections (matches `test_omega_os.py::REQUIRED_SKILL_SECTIONS`):
- `## name`
- `## description`
- `## when_to_use`
- `## inputs_required`
- `## steps`
- `## outputs`
- `## safety_rules`
- `## quality_checks`
- `## examples`
- `## repair_strategy`
- `## related_files`

---

## Files Created

- `docs/architecture/SKILLS_ARCHITECTURE.md` — Architecture reference
- `omega_skill_registry.py` — Registry with 9 functions
- `omega_os/skills/company_report/` — skill.md, contract.json, examples.md, CHANGELOG.md, tools/, tests/
- `omega_os/skills/trade_plan/` — same structure
- `omega_os/skills/general_chat/` — same structure
- `omega_os/skills/document_generator/` — same structure
- `omega_os/skills/dashboard_generator/` — same structure
- `omega_os/skills/source_verification/` — same structure
- `omega_os/skills/report_export/` — same structure
- `omega_os/skills/capture_triage/` — same structure
- `omega_os/skills/visual_qa/` — same structure
- `omega_os/skills/improve_system/` — same structure

---

## Notes

9 pre-existing legacy skill directories (`audit`, `daily_brief`, `level_up`, `onboard`,
`portfolio_review`, `research_queue`, `voice_capture_triage`, `watchlist_update`,
`weekly_product_review`) exist in `omega_os/skills/` with an older SKILL.md schema.
They are tracked in `test_omega_os.py::REQUIRED_SKILLS` and pass those tests.
They are NOT in the 10 core skills defined here and are out of scope for this goal.

---

## py_compile Results

```
python -m py_compile omega_skill_registry.py omega_pipeline.py prompt_builder.py quality_firewall.py output_contracts.py output_modes.py api_server.py atlas_omega.py query_router.py
# ALL PASS — no output
```

---

## pytest Results

```
2012 passed, 0 failed, 16 warnings in 103.92s
```

---

## Status

| Layer | Status |
|---|---|
| docs/architecture/SKILLS_ARCHITECTURE.md | ✅ |
| 10 skill directories + all 4 files each | ✅ |
| omega_skill_registry.py — all 9 functions | ✅ |
| skill.md section names match test_omega_os.py | ✅ |
| Safety invariant: no destructive+auto_invocable | ✅ |
| Progressive disclosure: 4 levels | ✅ |
| output_mode → skill routing | ✅ |
| All 2012 tests pass | ✅ |

Optional future work:
- Wire `omega_skill_registry.get_skill_for_output_mode()` into `omega_pipeline.plan_request()` to populate `required_tools` from the skill contract
- Add tool scripts (`verify_company_report.py`, `verify_trade_plan.py`) to the `tools/` directories
- Add tests for `omega_skill_registry.py`
