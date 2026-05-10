# W5 — IRA/401k Limit Bot | Division: Personal Wealth & Debt

## IDENTITY
W5 is the IRA/401k Limit Bot for the ATLAS Personal Wealth Division. It maintains authoritative annual IRS contribution limits for retirement and health savings accounts, and tracks Roth IRA income phase-out thresholds. Limits are hardcoded from IRS publication and updated each November when the IRS announces the following year's limits. No LLM calls are made.

## DEFINITION

Key terms:
- **IRA Limit**: Maximum annual contribution to a Traditional or Roth IRA.
- **Catch-Up (50+)**: Additional contribution allowed for participants age 50 and older.
- **401(k) Limit**: Maximum employee elective deferrals to a 401(k), 403(b), or most 457 plans.
- **HSA (Health Savings Account)**: Tax-advantaged account for medical expenses; requires HDHP enrollment.
- **Roth Phase-Out**: MAGI range over which Roth IRA contribution eligibility is phased out (reduces to $0 at high end).

2026 IRS Contribution Limits:
- IRA contribution limit: $7,000
- IRA catch-up (age 50+): $1,000 (additional)
- 401(k)/403(b)/457 elective deferral: $23,500
- 401(k) catch-up (age 50+): $7,500 (additional)
- HSA individual coverage: $4,300
- HSA family coverage: $8,550
- Roth IRA phase-out (single): $150,000 – $165,000 MAGI
- Roth IRA phase-out (married filing jointly): $236,000 – $246,000 MAGI

Source: IRS Rev. Proc. 2025-XX (announced November 2025)
Source URL: `https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-ira-contribution-limits`

## DATA SOURCES

**Primary:** IRS.gov public retirement plan pages
- IRA limits: `https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-ira-contribution-limits`
- 401(k) limits: `https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-401k-and-profit-sharing-plan-contribution-limits`
- HSA limits: `https://www.irs.gov/publications/p969`

**Implementation:** Hardcoded 2026 values (IRS updates annually in November). The agent scrapes IRS pages to detect if new-year limits have been published and flags for manual update.

## OUTPUT FILE

`data_cache/retirement_limits_latest.json`

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:00:00Z",
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
  "next_update_expected": "2026-11"
}
```

Fields:
- `generated_at` (ISO 8601 UTC): cache build timestamp
- `year` (int): tax year these limits apply to
- `ira_limit` (int): maximum IRA contribution in USD
- `ira_catch_up_50plus` (int): additional IRA catch-up contribution for age 50+
- `k401_limit` (int): maximum 401(k)/403(b)/457 employee deferral in USD
- `k401_catch_up_50plus` (int): additional 401(k) catch-up for age 50+
- `hsa_individual` (int): HSA contribution limit for individual HDHP coverage
- `hsa_family` (int): HSA contribution limit for family HDHP coverage
- `roth_income_phase_out_single_low` (int): Roth phase-out start (single filer MAGI)
- `roth_income_phase_out_single_high` (int): Roth phase-out end (single filer MAGI)
- `roth_income_phase_out_married_low` (int): Roth phase-out start (married filing jointly MAGI)
- `roth_income_phase_out_married_high` (int): Roth phase-out end (married filing jointly MAGI)
- `source_url` (string): canonical IRS page for verification
- `data_vintage` (string): month limits were published, format "YYYY-MM"
- `next_update_expected` (string): expected next IRS update, format "YYYY-MM"

## SIGNAL LOGIC

Roth eligibility helper (not stored in output, used by OmegaAgent on request):
```
def roth_eligibility(magi: float, filing_status: str) -> str:
    if filing_status == "single":
        low, high = roth_income_phase_out_single_low, roth_income_phase_out_single_high
    else:
        low, high = roth_income_phase_out_married_low, roth_income_phase_out_married_high

    if magi <= low:
        return "FULLY_ELIGIBLE"
    elif magi >= high:
        return "INELIGIBLE"
    else:
        reduced = ira_limit * (1 - (magi - low) / (high - low))
        return f"PARTIAL — max contribution: ${int(reduced):,}"
```

Update detection: If scraper detects IRS page year != hardcoded year, log `[W5 STALE] New limits detected — manual update required`.

## SCRAPER STRUCTURE

```python
# retirement_limits_scraper.py

import requests
import json
from datetime import datetime, timezone

IRS_IRA_URL = "https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-ira-contribution-limits"
OUTPUT_PATH = "data_cache/retirement_limits_latest.json"

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
    "source_url": IRS_IRA_URL,
    "data_vintage": "2025-11",
    "next_update_expected": "2026-11",
}


def detect_stale_limits(current_year: int) -> bool:
    """Scrape IRS page title to detect if new year limits are published."""
    ...


def roth_eligibility(magi: float, filing_status: str, limits: dict) -> str:
    """Return FULLY_ELIGIBLE | PARTIAL | INELIGIBLE for a given MAGI."""
    ...


def scrape() -> dict:
    """Return hardcoded 2026 limits with generated_at timestamp."""
    ...


def save(data: dict) -> None:
    """Write data to OUTPUT_PATH as formatted JSON."""
    ...


if __name__ == "__main__":
    result = scrape()
    save(result)
    print(f"[W5] Year={result['year']} IRA=${result['ira_limit']:,} 401k=${result['k401_limit']:,} → {OUTPUT_PATH}")
```

## RULES

- NEVER modify hardcoded limits without cross-referencing the official IRS source URL.
- All monetary limits are integers (IRS publishes whole-dollar amounts only).
- `year` must match the actual IRS publication year — not the current calendar year.
- `roth_income_phase_out_single_high` must always be > `roth_income_phase_out_single_low`.
- `roth_income_phase_out_married_high` must always be > `roth_income_phase_out_married_low`.
- `hsa_family` must always be > `hsa_individual`.
- `k401_limit` must always be > `ira_limit`.
- Output file must always be valid JSON. Wrap in try/except.
- Do not call any LLM.
- This is a READ-ONLY data agent — it never accepts user input to modify limits.

## VALIDATION CHECKLIST

- [ ] `generated_at` is ISO 8601 UTC
- [ ] `year` is an integer (e.g., 2026)
- [ ] `ira_limit` = 7000, `ira_catch_up_50plus` = 1000
- [ ] `k401_limit` = 23500, `k401_catch_up_50plus` = 7500
- [ ] `hsa_individual` = 4300, `hsa_family` = 8550
- [ ] Roth phase-out ranges are low < high for both filing statuses
- [ ] `source_url` contains "irs.gov"
- [ ] `data_vintage` format is "YYYY-MM"
- [ ] Output file is valid JSON
