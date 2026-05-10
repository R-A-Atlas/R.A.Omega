# W8 — Insurance Premium Tracker | Division: Personal Wealth & Debt

## IDENTITY
W8 is the Insurance Premium Tracker agent for the ATLAS Personal Wealth Division. It maintains a structured snapshot of average annual insurance premiums across five major personal insurance lines, with year-over-year change signals. Data is sourced from NAIC annual reports and updated annually — the NAIC PDF is not machine-parseable, so W8 uses a validated hardcoded snapshot. No LLM calls are made.

## DEFINITION

Key terms:
- **Average Annual Premium**: Mean premium paid per household/policy across all states for a given line.
- **YoY Change %**: Year-over-year percentage change in the average premium.
- **Trend**: Directional signal based on YoY change magnitude.
- **Highest/Lowest State**: State with the maximum/minimum average premium for the given line.

Insurance type enum: `"Auto"`, `"Home"`, `"Health"`, `"Life"`, `"Renters"`

Trend thresholds:
- RISING: yoy_change_pct >= 5.0%
- STABLE: -5.0% < yoy_change_pct < 5.0%
- FALLING: yoy_change_pct <= -5.0%

## DATA SOURCES

**Primary:** NAIC (National Association of Insurance Commissioners) annual report
- Homeowners: `https://content.naic.org/sites/default/files/publication-mkt-pb-homeowners-insurance-report.pdf`
- Note: PDF is not machine-parseable. Data is extracted manually and stored as a hardcoded annual snapshot.
- NAIC updates data each year; snapshot is refreshed when new annual report is published.

**Secondary:** State Farm, Allstate, Progressive public rate filings and press releases (used for sanity checks).

**Implementation:** Fully hardcoded 2025 snapshot validated against NAIC published figures. Agent generates a consistent output without making HTTP requests to the PDF.

## OUTPUT FILE

`data_cache/insurance_latest.json`

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:00:00Z",
  "record_count": 5,
  "data_year": 2025,
  "source_url": "https://content.naic.org/sites/default/files/publication-mkt-pb-homeowners-insurance-report.pdf",
  "premiums": [
    {
      "type": "Auto",
      "avg_annual_premium": 2150,
      "yoy_change_pct": 12.5,
      "trend": "RISING",
      "highest_state": "Michigan",
      "highest_state_premium": 4100,
      "lowest_state": "Maine",
      "lowest_state_premium": 980
    },
    {
      "type": "Home",
      "avg_annual_premium": 2285,
      "yoy_change_pct": 8.9,
      "trend": "RISING",
      "highest_state": "Oklahoma",
      "highest_state_premium": 5800,
      "lowest_state": "Hawaii",
      "lowest_state_premium": 510
    },
    {
      "type": "Health",
      "avg_annual_premium": 8435,
      "yoy_change_pct": 4.2,
      "trend": "STABLE",
      "highest_state": "West Virginia",
      "highest_state_premium": 12200,
      "lowest_state": "Massachusetts",
      "lowest_state_premium": 5400
    },
    {
      "type": "Life",
      "avg_annual_premium": 684,
      "yoy_change_pct": 1.3,
      "trend": "STABLE",
      "highest_state": "New York",
      "highest_state_premium": 1250,
      "lowest_state": "Wisconsin",
      "lowest_state_premium": 420
    },
    {
      "type": "Renters",
      "avg_annual_premium": 210,
      "yoy_change_pct": 6.8,
      "trend": "RISING",
      "highest_state": "Louisiana",
      "highest_state_premium": 450,
      "lowest_state": "North Dakota",
      "lowest_state_premium": 110
    }
  ]
}
```

Fields:
- `generated_at` (ISO 8601 UTC): cache build timestamp
- `record_count` (int): number of insurance lines (always 5)
- `data_year` (int): year of NAIC data snapshot
- `source_url` (string): NAIC report URL for reference
- `premiums` (array of 5): one object per insurance type
  - `type` (string): one of `Auto | Home | Health | Life | Renters`
  - `avg_annual_premium` (int): mean annual premium across all states (USD)
  - `yoy_change_pct` (float): year-over-year change percentage
  - `trend` (string): `RISING | STABLE | FALLING`
  - `highest_state` (string): state with highest average premium
  - `highest_state_premium` (int): highest state average premium (USD)
  - `lowest_state` (string): state with lowest average premium
  - `lowest_state_premium` (int): lowest state average premium (USD)

## SIGNAL LOGIC

```
if yoy_change_pct >= 5.0:
    trend = "RISING"
elif yoy_change_pct <= -5.0:
    trend = "FALLING"
else:
    trend = "STABLE"
```

Premiums are sorted by `yoy_change_pct` descending (most rapidly rising types first).

## SCRAPER STRUCTURE

```python
# insurance_scraper.py

import json
from datetime import datetime, timezone

NAIC_SOURCE_URL = "https://content.naic.org/sites/default/files/publication-mkt-pb-homeowners-insurance-report.pdf"
OUTPUT_PATH = "data_cache/insurance_latest.json"

SNAPSHOT_2025 = [
    {"type": "Auto", "avg_annual_premium": 2150, "yoy_change_pct": 12.5,
     "highest_state": "Michigan", "highest_state_premium": 4100,
     "lowest_state": "Maine", "lowest_state_premium": 980},
    {"type": "Home", "avg_annual_premium": 2285, "yoy_change_pct": 8.9,
     "highest_state": "Oklahoma", "highest_state_premium": 5800,
     "lowest_state": "Hawaii", "lowest_state_premium": 510},
    {"type": "Health", "avg_annual_premium": 8435, "yoy_change_pct": 4.2,
     "highest_state": "West Virginia", "highest_state_premium": 12200,
     "lowest_state": "Massachusetts", "lowest_state_premium": 5400},
    {"type": "Life", "avg_annual_premium": 684, "yoy_change_pct": 1.3,
     "highest_state": "New York", "highest_state_premium": 1250,
     "lowest_state": "Wisconsin", "lowest_state_premium": 420},
    {"type": "Renters", "avg_annual_premium": 210, "yoy_change_pct": 6.8,
     "highest_state": "Louisiana", "highest_state_premium": 450,
     "lowest_state": "North Dakota", "lowest_state_premium": 110},
]

VALID_TYPES = {"Auto", "Home", "Health", "Life", "Renters"}


def compute_trend(yoy_change_pct: float) -> str:
    """Return RISING | STABLE | FALLING based on threshold."""
    ...


def build_premiums(snapshot: list[dict]) -> list[dict]:
    """Apply trend signal to each entry and validate types."""
    ...


def scrape() -> dict:
    """Return hardcoded 2025 NAIC snapshot with generated_at and trends applied."""
    ...


def save(data: dict) -> None:
    """Write data to OUTPUT_PATH as formatted JSON."""
    ...


if __name__ == "__main__":
    result = scrape()
    save(result)
    print(f"[W8] Data year={result['data_year']} types={result['record_count']} → {OUTPUT_PATH}")
```

## RULES

- NEVER store user insurance policy numbers, claims data, or personal coverage details.
- `type` must be one of Auto / Home / Health / Life / Renters — raise ValueError for others.
- `trend` must be computed from `yoy_change_pct` using the threshold rules — never hardcoded directly.
- `record_count` must always equal 5 (all 5 insurance types required in output).
- `highest_state_premium` must always be > `avg_annual_premium` (sanity check).
- `lowest_state_premium` must always be < `avg_annual_premium` (sanity check).
- `data_year` must reflect the NAIC report year, not the current year.
- Output file must always be valid JSON. Wrap in try/except.
- Do not call any LLM.
- This agent does not make HTTP calls to NAIC (PDF not parseable). Source URL is for reference only.

## VALIDATION CHECKLIST

- [ ] `generated_at` is ISO 8601 UTC
- [ ] `record_count` equals 5
- [ ] All 5 `type` values present: Auto, Home, Health, Life, Renters
- [ ] All `trend` values are RISING | STABLE | FALLING
- [ ] RISING entries have `yoy_change_pct` >= 5.0
- [ ] FALLING entries have `yoy_change_pct` <= -5.0
- [ ] `highest_state_premium` > `avg_annual_premium` for each row
- [ ] `lowest_state_premium` < `avg_annual_premium` for each row
- [ ] `source_url` contains "naic.org"
- [ ] Output file is valid JSON
