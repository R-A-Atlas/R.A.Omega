# W2 — Auto Loan Scanner | Division: Personal Wealth & Debt

## IDENTITY
W2 is the Auto Loan Scanner agent for the ATLAS Personal Wealth Division. It retrieves current auto loan rate benchmarks from the Federal Reserve's FRED database and computes week-over-week trend signals for 5 standard loan terms. No LLM calls are made; all trend logic is rule-based.

## DEFINITION

Key terms:
- **APR (Auto)**: Average new-car loan interest rate (annualized) across all lenders.
- **Credit Union Rate**: Typically 0.5–1.5% below dealer/bank rates due to member-owned structure.
- **Dealer Rate**: Rate offered by dealership-affiliated finance arms (GMAC, Ford Credit, etc.).
- **WoW Trend**: Week-over-week change in the 60-month rate, benchmarked against 0.1% threshold.

Thresholds:
- RISING: WoW change on 60-month rate >= +0.10%
- FALLING: WoW change on 60-month rate <= -0.10%
- STABLE: -0.10% < change < +0.10%

Term months enum: `24, 36, 48, 60, 72`

FRED Series:
- `TERMCBCCALLNS`: Commercial bank credit card interest rate (reference baseline)
- `DTCTHFNM`: Finance rate on consumer installment loans at commercial banks — new cars (primary auto loan series)

## DATA SOURCES

**Primary:** Federal Reserve FRED API (public, no auth for recent observations)
- Auto loan rate: `https://api.stlouisfed.org/fred/series/observations?series_id=TERMCBCCALLNS&api_key=public&file_type=json`
- DTCTHFNM (new car 48-month): `https://api.stlouisfed.org/fred/series/observations?series_id=DTCTHFNM&api_key=public&file_type=json`
- Note: FRED public access requires a free API key. Fallback to last known values if key missing.

**Secondary:** Hardcoded snapshot (updated quarterly from FRED release H.15)

## OUTPUT FILE

`data_cache/auto_loans_latest.json`

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:00:00Z",
  "record_count": 5,
  "period": "2026-Q1",
  "trend": "RISING",
  "wow_change_60mo": 0.15,
  "rates": [
    {
      "term_months": 24,
      "avg_rate": 6.45,
      "credit_union_rate": 5.75,
      "dealer_rate": 7.10
    },
    {
      "term_months": 36,
      "avg_rate": 6.85,
      "credit_union_rate": 6.10,
      "dealer_rate": 7.50
    },
    {
      "term_months": 48,
      "avg_rate": 7.10,
      "credit_union_rate": 6.40,
      "dealer_rate": 7.80
    },
    {
      "term_months": 60,
      "avg_rate": 7.45,
      "credit_union_rate": 6.75,
      "dealer_rate": 8.20
    },
    {
      "term_months": 72,
      "avg_rate": 7.90,
      "credit_union_rate": 7.20,
      "dealer_rate": 8.65
    }
  ]
}
```

Fields:
- `generated_at` (ISO 8601 UTC): cache build timestamp
- `record_count` (int): number of term rows (always 5)
- `period` (string): quarter label e.g. "2026-Q1"
- `trend` (string): `RISING | FALLING | STABLE` based on 60-month WoW
- `wow_change_60mo` (float): week-over-week change in 60-month rate (percentage points)
- `rates` (array of 5): one object per term
  - `term_months` (int): loan term in months
  - `avg_rate` (float): blended average rate (%)
  - `credit_union_rate` (float): estimated credit union rate (%)
  - `dealer_rate` (float): estimated dealer/bank rate (%)

## SIGNAL LOGIC

```
prev_60mo = rates[-2]["value"]   # from FRED observations, sorted by date
curr_60mo = rates[-1]["value"]
wow_change = curr_60mo - prev_60mo

if wow_change >= 0.10:
    trend = "RISING"
elif wow_change <= -0.10:
    trend = "FALLING"
else:
    trend = "STABLE"
```

Credit union rate is estimated as: `avg_rate - 0.70` (representative 70bps advantage).
Dealer rate is estimated as: `avg_rate + 0.75` (representative 75bps premium).

## SCRAPER STRUCTURE

```python
# auto_loans_scraper.py

import requests
import json
from datetime import datetime, timezone

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
SERIES_AUTO = "DTCTHFNM"
SERIES_CC = "TERMCBCCALLNS"
OUTPUT_PATH = "data_cache/auto_loans_latest.json"

TERM_MONTHS = [24, 36, 48, 60, 72]

STATIC_RATES = {
    24: 6.45, 36: 6.85, 48: 7.10, 60: 7.45, 72: 7.90
}


def fetch_fred_series(series_id: str, api_key: str = "public") -> list[dict]:
    """Fetch observations list from FRED. Returns list of {date, value} dicts."""
    ...


def compute_trend(observations: list[dict]) -> tuple[str, float]:
    """Return (trend_label, wow_change) from last two 60-month observations."""
    ...


def build_rate_rows(base_rate: float) -> list[dict]:
    """Build 5-row rate table for term_months [24, 36, 48, 60, 72]."""
    ...


def scrape() -> dict:
    """Main entry point. Returns full output schema dict."""
    ...


def save(data: dict) -> None:
    """Write data to OUTPUT_PATH as formatted JSON."""
    ...


if __name__ == "__main__":
    result = scrape()
    save(result)
    print(f"[W2] Period={result['period']} trend={result['trend']} → {OUTPUT_PATH}")
```

## RULES

- NEVER store user credit scores, VINs, or personal financial data.
- `term_months` must only be one of [24, 36, 48, 60, 72] — no custom terms.
- `trend` must be computed from actual WoW delta against 0.10% threshold — never hardcoded.
- If FRED API is unavailable, use STATIC_RATES with `trend = "STABLE"` and log a warning.
- All rates must be positive floats > 0. Raise ValueError if FRED returns a negative or null value.
- `period` must reflect the actual data quarter, not the current date.
- Output file must always be valid JSON. Wrap in try/except; write error envelope on failure.
- Do not call any LLM.

## VALIDATION CHECKLIST

- [ ] `generated_at` is ISO 8601 UTC
- [ ] `record_count` equals 5 (always 5 term rows)
- [ ] `term_months` values are exactly [24, 36, 48, 60, 72]
- [ ] `trend` is one of RISING / FALLING / STABLE
- [ ] `wow_change_60mo` is a float (can be negative)
- [ ] `credit_union_rate` < `avg_rate` < `dealer_rate` for all rows
- [ ] Output file is valid JSON
- [ ] FRED API failure triggers fallback, not a crash
