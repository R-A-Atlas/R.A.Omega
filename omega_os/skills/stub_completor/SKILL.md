# Skill: stub_completor

## Purpose
Audits all omega_os skills to find which are stubs (SKILL.md only, no tool scripts)
vs fully implemented (have at least one tool script). Reports priority build order
so the highest-impact stubs are built first.

## Trigger
- Weekly (wired to weekly_omega_os_audit cadence job)
- Before sprint planning — shows what's left to build
- After adding a new skill directory — verify it shows up as stub or full

## Steps
1. Run: `python omega_os/skills/stub_completor/tools/stub_audit.py`
2. Review FULL vs STUB counts and priority scores
3. Pick top-scored stub and implement its tool script
4. Re-run to verify it moved from STUB to FULL

### Options
```
--stubs-only    Show only stubs (skip full skills list)
--json          Machine-readable output
```

## Priority score formula
```
score = cadence_refs × 10 + skill_refs × 5 + has_skill_md × 2 + has_evals + has_contract
```
- **cadence_refs × 10**: cadence dependency is most urgent (job will run whether implemented or not)
- **skill_refs × 5**: other skills depend on this one

## Implementing a stub
1. Check suggested tool name from audit output
2. Use `dev_session_guard` as a template (has SKILL.md + contract.json + evals.json + tools/)
3. Create: `omega_os/skills/<name>/tools/<suggested_name>.py`
4. Add SKILL.md, contract.json, evals.json if missing
5. Run stub_audit.py again — skill should now appear in FULL list

## Guardrails
- Do not implement stub runners that call external APIs without auth guards
- Each implemented tool must have at least one eval in evals.json
- Stub-promoted skills must be verified with `python -m py_compile` before commit
