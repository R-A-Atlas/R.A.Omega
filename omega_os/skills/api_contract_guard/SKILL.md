# Skill: api_contract_guard

## Purpose
Verifies that internal Python module interfaces (health_scorer, upgrade_scanner,
chain_mapper, ui_audit, session_briefing, route_audit) match the return types and
attribute shapes that callers depend on. Catches contract drift before it reaches
tests or production.

## Trigger
- Before any PR that touches a checked module
- After adding a new tool script to any omega_os skill
- Wired into dev_session_guard pre-commit flow

## Steps
1. Run `python omega_os/skills/api_contract_guard/tools/verify_contracts.py`
2. Read the output — each check prints [OK] or [FAIL] with a clear description
3. Fix any FAIL before continuing
4. Optionally run with `--json` for machine-readable output

## Contracts checked

| Module | Key assertion |
|---|---|
| health_scorer | `.overall` is numeric (float/int-castable) |
| upgrade_scanner | `scan()` returns ScanResult with `.opportunities` list |
| chain_mapper | DeadWire has `.category`, `.target`, `.detail` attrs (not dict) |
| ui_audit | `run_audit()` returns list of FileReport with `.filename`, `.overall`, `.exists` |
| session_briefing | `brief()` returns ≤40-line string containing "Branch" and "Health" |
| route_audit | Returns AuditReport with `.routes` list and `.auth_redirect_ok` bool |

## Guardrails
- Never modify checked modules to make contracts pass — the contracts document real caller assumptions
- If a module's interface changes intentionally, update this skill's tool AND the callers together
- Do not add side effects (file writes, network calls) to this checker

## Output shape
```
[OK]  health_scorer.overall is numeric: 87.5
[FAIL] upgrade_scanner.scan() missing .opportunities attribute
...
RESULT: 1 contract failure(s) — fix before commit
```
