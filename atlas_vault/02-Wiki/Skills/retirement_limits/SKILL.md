---
name: IRA/401k Limit Bot
description: Maintains authoritative IRS annual contribution limits for IRAs, 401(k)s, and HSAs, with Roth income phase-out thresholds. Hardcoded from IRS publication, updated each November.
type: reference
agent: W5
division: Personal Wealth & Debt
---

# Skill: IRA/401k Limit Bot (W5)

## [D] Direction

**Goal:** Produce `data_cache/retirement_limits_latest.json` with the current-year IRS contribution limits for all major tax-advantaged retirement and health savings accounts.

**Steps:**
1. Return hardcoded 2026 IRS limits (see LIMITS_2026 constant).
2. Optionally scrape IRS page title to detect if new-year limits have been published (run annually in November check).
3. If new-year limits detected and current `year` < page year → log `[W5 STALE]` warning.
4. Stamp `generated_at` with current UTC time.
5. Write output JSON to `data_cache/retirement_limits_latest.json`.

**Stop conditions:**
- IRS page unreachable → use hardcoded values (never crash — limits don't change mid-year).
- `year` field mismatch detected → log warning only, do not raise exception.

**Guardrails:**
- Never accept external input to modify limits.
- All limits are integers (IRS publishes whole-dollar amounts).
- `hsa_family` must always be > `hsa_individual`.
- `k401_limit` must always be > `ira_limit`.
- Phase-out ranges: high must always be > low.
- Never call any LLM.

## [B] Blueprints

**2026 IRS Limits (canonical reference):**
```python
LIMITS_2026 = {
    "year": 2026,
    "ira_limit": 7000,
    "ira_catch_up_50plus": 1000,
    "k401_limit": 23500,
    "k401_catch_up_50plus": 7500,
    "hsa_individual": 4300,
    "hsa_family": 8550,
    "roth_income_phase_out_single_low": 150000,
    "roth_income_phase_out_single_high": 165000,
    "roth_income_phase_out_married_low": 236000,
    "roth_income_phase_out_married_high": 246000,
    "source_url": "https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-ira-contribution-limits",
    "data_vintage": "2025-11",
    "next_update_expected": "2026-11",
}
```

**IRS Source URLs:**
- IRA limits: `https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-ira-contribution-limits`
- 401(k) limits: `https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-401k-and-profit-sharing-plan-contribution-limits`
- HSA limits: `https://www.irs.gov/publications/p969`

**Roth eligibility helper:**
```python
def roth_eligibility(magi, filing_status, limits):
    if filing_status == "single":
        low = limits["roth_income_phase_out_single_low"]
        high = limits["roth_income_phase_out_single_high"]
    else:
        low = limits["roth_income_phase_out_married_low"]
        high = limits["roth_income_phase_out_married_high"]
    if magi <= low:
        return "FULLY_ELIGIBLE"
    elif magi >= high:
        return "INELIGIBLE"
    else:
        reduced = limits["ira_limit"] * (1 - (magi - low) / (high - low))
        return f"PARTIAL — max contribution: ${int(reduced):,}"
```

## [S] Solutions

**Stale-check (run annually):**
```python
import requests, re
def detect_stale(current_year):
    try:
        resp = requests.get(
            "https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-ira-contribution-limits",
            timeout=10, headers={"User-Agent": "ATLAS/1.0"}
        )
        match = re.search(r"20\d\d", resp.text[:2000])
        page_year = int(match.group()) if match else current_year
        return page_year > current_year
    except Exception:
        return False
```

**Syntax check:**
```bash
python -m py_compile atlas_agents/wealth/retirement_limits/retirement_limits_scraper.py
```

## Evals

| # | Assertion | Pass Condition |
|---|-----------|---------------|
| 1 | Package importable | `importlib.import_module("atlas_agents.wealth.retirement_limits")` returns without error |
| 2 | AGENT_PROMPT.md exists and non-empty | `pathlib.Path(...AGENT_PROMPT.md).stat().st_size > 0` |
| 3 | SKILL.md exists and non-empty | `pathlib.Path(...retirement_limits/SKILL.md).stat().st_size > 0` |
| 4 | All schema fields documented | `ira_limit,ira_catch_up_50plus,k401_limit,k401_catch_up_50plus,hsa_individual,hsa_family,roth_income_phase_out_single_low,roth_income_phase_out_single_high,roth_income_phase_out_married_low,roth_income_phase_out_married_high` all in AGENT_PROMPT.md |
| 5 | 2026 values + IRS URL documented | `7000,23500,4300,8550,150000,irs.gov` all in AGENT_PROMPT.md |
