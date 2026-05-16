# Skill: audit_runner

## Purpose
Orchestrates both the competitive benchmark (ai_benchmarker) and product readiness
audit (product_readiness_audit) to produce a single master report with an overall
score, letter grade, and prioritized fix list. Saves a dated Markdown report to
atlas_vault/03-Outputs/.

## Trigger
- Weekly cadence (Monday 9:00 AM ET — wired to weekly_omega_os_audit job)
- On demand before any product decision or feature launch
- Run by founder at the start of any planning session

## Steps

### Standard full audit (recommended)
```
python omega_os/skills/audit_runner/tools/run_audit.py
```

### Quick audit (product readiness only, skips benchmark)
```
python omega_os/skills/audit_runner/tools/run_audit.py --quick
```

### JSON output (for automation)
```
python omega_os/skills/audit_runner/tools/run_audit.py --json --no-save
```

### Skip saving to vault
```
python omega_os/skills/audit_runner/tools/run_audit.py --no-save
```

## Overall score formula
```
overall = readiness_pct × 0.60 + benchmark_score × 0.40
```
- **60% readiness**: how production-ready is the product (100-point rubric)
- **40% benchmark**: how we compare to ChatGPT / Claude / Gemini / Perplexity

## Output
Prints full report to terminal AND saves to:
```
atlas_vault/03-Outputs/omega_audit_YYYY-MM-DD.md
```

## Verdict thresholds

| Overall Score | Verdict |
|---|---|
| 90–100 | PRODUCTION READY — ship it |
| 75–89 | BETA READY — invite beta users |
| 60–74 | ALPHA — internal testing only |
| < 60 | BUILDING — keep shipping |

## Cadence wiring
- Slug: `weekly_omega_os_audit` (already in omega_cadence.py)
- REAL runner in cadence_wirer/tools/start_cadence.py
- Activates when `OMEGA_CADENCE_ENABLED=true`

## Guardrails
- Read-only — never modifies source code or databases
- No external API calls — all data from local codebase inspection
- Does not modify audit scores manually — they are auto-detected
- NEVER inflate scores to look better — the audit must reflect true state
