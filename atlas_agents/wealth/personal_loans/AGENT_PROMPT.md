# W6 — Personal Loan Screener | Division: Personal Wealth & Debt

## IDENTITY
W6 is the Personal Loan Screener agent for the ATLAS Personal Wealth Division. It benchmarks personal loan offerings across lender categories using the Federal Reserve FRED consumer loan rate series as the market average, then applies a competitive rating to each offering. No LLM calls are made; all scoring is deterministic rule-based logic.

## DEFINITION

Key terms:
- **Personal Loan**: Unsecured installment loan for general-purpose use (debt consolidation, home improvement, etc.).
- **Rate Range**: Lenders quote a range (rate_low to rate_high) based on credit profile; best-credit customers get rate_low.
- **FRED Avg**: Federal Reserve published average rate for 24-month personal loans (TERMCBPER24NS series).
- **COMPETITIVE Rating**: rate_low is at least 2 percentage points below the FRED benchmark average.

Category enum: `"Online Lender"`, `"Credit Union"`, `"Bank"`, `"Marketplace"`

Rating thresholds:
- COMPETITIVE: rate_low <= FRED_avg - 2.0%
- AVERAGE: rate_low > FRED_avg - 2.0%

FRED Series:
- `TERMCBPER24NS`: Average finance rate on personal loans at commercial banks, 24-month maturity

## DATA SOURCES

**Primary:** Federal Reserve FRED API — personal loan benchmark rate
- FRED series: `TERMCBPER24NS`
- URL: `https://api.stlouisfed.org/fred/series/observations?series_id=TERMCBPER24NS&api_key=public&file_type=json`

**Secondary:** CFPB Consumer Complaint Database (public)
- URL: `https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/`
- Used for complaint volume context by lender.

**Tertiary (lender data):** Hardcoded quarterly snapshot of top personal loan lenders with published rate ranges (sourced from lender websites and Bankrate/NerdWallet public tables).

## OUTPUT FILE

`data_cache/personal_loans_latest.json`

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:00:00Z",
  "record_count": 8,
  "fred_avg_rate": 11.48,
  "loans": [
    {
      "lender": "LightStream",
      "rate_low": 6.99,
      "rate_high": 25.49,
      "max_amount": 100000,
      "term_months_max": 144,
      "credit_score_min": 660,
      "category": "Online Lender",
      "rating": "COMPETITIVE"
    },
    {
      "lender": "SoFi",
      "rate_low": 8.99,
      "rate_high": 29.99,
      "max_amount": 100000,
      "term_months_max": 84,
      "credit_score_min": 650,
      "category": "Online Lender",
      "rating": "COMPETITIVE"
    },
    {
      "lender": "Navy Federal Credit Union",
      "rate_low": 7.49,
      "rate_high": 18.00,
      "max_amount": 50000,
      "term_months_max": 60,
      "credit_score_min": 620,
      "category": "Credit Union",
      "rating": "COMPETITIVE"
    },
    {
      "lender": "Wells Fargo",
      "rate_low": 7.49,
      "rate_high": 23.74,
      "max_amount": 100000,
      "term_months_max": 84,
      "credit_score_min": 660,
      "category": "Bank",
      "rating": "COMPETITIVE"
    }
  ]
}
```

Fields:
- `generated_at` (ISO 8601 UTC): cache build timestamp
- `record_count` (int): number of loan offerings returned
- `fred_avg_rate` (float): FRED TERMCBPER24NS latest observation (%)
- `loans` (array): one object per lender offering
  - `lender` (string): institution name
  - `rate_low` (float): lowest advertised APR for qualified borrowers (%)
  - `rate_high` (float): highest APR for less-qualified borrowers (%)
  - `max_amount` (int): maximum loan amount in USD
  - `term_months_max` (int): maximum loan term in months
  - `credit_score_min` (int): minimum credit score typically required (FICO)
  - `category` (string): one of `Online Lender | Credit Union | Bank | Marketplace`
  - `rating` (string): `COMPETITIVE | AVERAGE`

## SIGNAL LOGIC

```
fred_avg = fetch_fred_avg()   # TERMCBPER24NS latest value

for loan in loans:
    if loan["rate_low"] <= fred_avg - 2.0:
        loan["rating"] = "COMPETITIVE"
    else:
        loan["rating"] = "AVERAGE"
```

Loans sorted: COMPETITIVE first, then AVERAGE; within tier sorted by `rate_low` ascending.

## SCRAPER STRUCTURE

```python
# personal_loans_scraper.py

import requests
import json
from datetime import datetime, timezone

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_SERIES = "TERMCBPER24NS"
CFPB_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
OUTPUT_PATH = "data_cache/personal_loans_latest.json"

FALLBACK_FRED_AVG = 11.48

STATIC_LOANS = [
    {"lender": "LightStream", "rate_low": 6.99, "rate_high": 25.49,
     "max_amount": 100000, "term_months_max": 144, "credit_score_min": 660,
     "category": "Online Lender"},
    {"lender": "SoFi", "rate_low": 8.99, "rate_high": 29.99,
     "max_amount": 100000, "term_months_max": 84, "credit_score_min": 650,
     "category": "Online Lender"},
    {"lender": "Navy Federal Credit Union", "rate_low": 7.49, "rate_high": 18.00,
     "max_amount": 50000, "term_months_max": 60, "credit_score_min": 620,
     "category": "Credit Union"},
    {"lender": "Wells Fargo", "rate_low": 7.49, "rate_high": 23.74,
     "max_amount": 100000, "term_months_max": 84, "credit_score_min": 660,
     "category": "Bank"},
]


def fetch_fred_avg(series_id: str = FRED_SERIES, api_key: str = "public") -> float:
    """Fetch latest observation from FRED series. Returns float."""
    ...


def rate_loan(loan: dict, fred_avg: float) -> dict:
    """Add rating field to loan dict based on COMPETITIVE threshold."""
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
    print(f"[W6] FRED avg={result['fred_avg_rate']}% loans={result['record_count']} → {OUTPUT_PATH}")
```

## RULES

- NEVER store user SSNs, credit report data, or loan application details.
- `category` must be one of Online Lender / Credit Union / Bank / Marketplace — raise ValueError for others.
- `rating` must be computed from live `fred_avg_rate` — never hardcoded.
- `rate_low` must always be < `rate_high`. Raise ValueError if not.
- `credit_score_min` must be between 300 and 850 (valid FICO range).
- If FRED API is unreachable, use `FALLBACK_FRED_AVG` and log a warning.
- All monetary amounts (`max_amount`) are integers in USD.
- Output file must always be valid JSON. Write error envelope on failure.
- Do not call any LLM.

## VALIDATION CHECKLIST

- [ ] `generated_at` is ISO 8601 UTC
- [ ] `fred_avg_rate` is a positive float
- [ ] `record_count` equals `len(loans)`
- [ ] All `category` values are one of the 4 enum values
- [ ] All `rating` values are COMPETITIVE | AVERAGE
- [ ] `rate_low` < `rate_high` for every loan
- [ ] COMPETITIVE loans have `rate_low` <= `fred_avg_rate - 2.0`
- [ ] Output file is valid JSON
- [ ] FRED API failure triggers fallback, not a crash
