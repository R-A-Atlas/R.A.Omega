# Skill: test_contract_guard

## Purpose
Scans the test suite for fragile assertions that break during correct refactoring.
Catches tests that assert implementation details (hex colors, line counts, redirect
aliases) rather than semantic behavior.

## Trigger
- Before any PR that touches HTML, CSS, or auth redirect logic
- After a refactoring session that moved strings or redesigned UI components
- Weekly as part of weekly_omega_os_audit

## Steps
1. Run: `python omega_os/skills/test_contract_guard/tools/test_fragility_scan.py`
2. Review HIGH severity findings first — these cause false test failures on refactor
3. Run with `--fix-hints` to see suggested replacements for each pattern
4. Fix fragile assertions in the test files; re-run to confirm clean

### Options
```
--fix-hints    Print semantic alternatives for each fragile pattern
--high-only    Report only HIGH severity issues
--json         Machine-readable output
```

## Fragile patterns detected

| Pattern | Severity | Example | Fix |
|---|---|---|---|
| hex_color_assertion | HIGH | `assert "#18C6C8" in html` | Use CSS variable name token |
| implementation_detail_string | HIGH | `assert "/option1" in response` | Assert semantic destination `/command-center` |
| hardcoded_line_count | MEDIUM | `assert len(output.splitlines()) == 42` | Assert semantic content instead |
| magic_number_test_count | MEDIUM | `assert count >= 1397` | Use relative check or BASELINE constant |
| raw_css_property_assertion | MEDIUM | `assert "color: #18C6C8;" in html` | Assert CSS variable |
| exact_version_string | LOW | `assert "1.2.3" == version` | Assert key present or use >= |

## Guardrails
- This scanner reports patterns — it never modifies test files automatically
- HIGH severity issues must be fixed before the next release
- MEDIUM/LOW: fix before refactoring the area they cover
- Do not add patterns that flag legitimate semantic assertions (e.g., asserting a UI label text is fine)
