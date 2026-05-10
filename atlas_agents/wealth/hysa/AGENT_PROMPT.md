# W4 — HYSA Tracker | Division: Personal Wealth & Debt

## IDENTITY
W4 is the HYSA (High-Yield Savings Account) Tracker agent for the ATLAS Personal Wealth Division. It collects current deposit account APYs from top FDIC-insured institutions and benchmarks them against the Federal Reserve fed funds rate. All scoring is deterministic rule-based logic — no LLM calls.

## DEFINITION

Key terms:
- **APY (Annual Percentage Yield)**: Effective annual return including compounding; always >= stated APR.
- **Fed Funds Rate**: The overnight lending rate set by the FOMC — the primary benchmark for HYSA rates.
- **FDIC Insured**: Deposits guaranteed up to $250,000 per depositor per institution.
- **Spread**: APY minus Fed Funds Rate. Positive spread = account outperforms benchmark.

Account type enum: `"HYSA"`, `"Money Market"`, `"CD"`

Rating thresholds:
- TOP_PICK: APY >= fed_funds_rate - 0.50%
- COMPETITIVE: APY >= fed_funds_rate - 1.50%
- AVERAGE: APY < fed_funds_rate - 1.50%

## DATA SOURCES

**Primary:** FDIC BankFind Suite API (public, no auth)
- URL: `https://banks.data.fdic.gov/api/institutions?filters=ACTIVE%3A1&fields=NAME,REPDTE,ASSET,STALP&limit=10&offset=0&sort_by=ASSET&sort_order=DESC&output=json`
- Returns top institutions by asset size for FDIC validation; APY data supplemented by static snapshot.

**Secondary:** Federal Reserve FRED API — Fed Funds Rate
- FRED series: `FEDFUNDS`
- URL: `https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&api_key=public&file_type=json`

**Tertiary (APY data):** Hardcoded monthly snapshot from publicly published rate tables (Bankrate, NerdWallet, institution websites). Updated monthly.

## OUTPUT FILE

`data_cache/hysa_latest.json`

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:00:00Z",
  "fed_funds_rate": 4.33,
  "record_count": 8,
  "accounts": [
    {
      "bank": "Marcus by Goldman Sachs",
      "apy": 4.50,
      "min_balance": 0,
      "fdic_insured": true,
      "account_type": "HYSA",
      "rating": "TOP_PICK",
      "spread_vs_fed": 0.17
    },
    {
      "bank": "Ally Bank",
      "apy": 4.35,
      "min_balance": 0,
      "fdic_insured": true,
      "account_type": "HYSA",
      "rating": "TOP_PICK",
      "spread_vs_fed": 0.02
    },
    {
      "bank": "Synchrony Bank",
      "apy": 4.75,
      "min_balance": 0,
      "fdic_insured": true,
      "account_type": "Money Market",
      "rating": "TOP_PICK",
      "spread_vs_fed": 0.42
    },
    {
      "bank": "Discover Bank 12-Mo CD",
      "apy": 4.80,
      "min_balance": 2500,
      "fdic_insured": true,
      "account_type": "CD",
      "rating": "TOP_PICK",
      "spread_vs_fed": 0.47
    }
  ]
}
```

Fields:
- `generated_at` (ISO 8601 UTC): cache build timestamp
- `fed_funds_rate` (float): current FOMC fed funds target rate (%)
- `record_count` (int): number of accounts returned
- `accounts` (array): one object per account
  - `bank` (string): institution name
  - `apy` (float): annual percentage yield (%)
  - `min_balance` (float): minimum balance to earn stated APY (0 = no minimum)
  - `fdic_insured` (bool): always true for included accounts
  - `account_type` (string): one of `HYSA | Money Market | CD`
  - `rating` (string): `TOP_PICK | COMPETITIVE | AVERAGE`
  - `spread_vs_fed` (float): apy - fed_funds_rate (percentage points)

## SIGNAL LOGIC

```
spread = apy - fed_funds_rate

if spread >= -0.50:
    rating = "TOP_PICK"
elif spread >= -1.50:
    rating = "COMPETITIVE"
else:
    rating = "AVERAGE"
```

Accounts are sorted by `apy` descending within each `account_type`.
Fed funds rate is fetched from FRED FEDFUNDS series (latest observation).

## SCRAPER STRUCTURE

```python
# hysa_scraper.py

import requests
import json
from datetime import datetime, timezone

FDIC_URL = "https://banks.data.fdic.gov/api/institutions"
FRED_FEDFUNDS_URL = "https://api.stlouisfed.org/fred/series/observations"
OUTPUT_PATH = "data_cache/hysa_latest.json"

STATIC_ACCOUNTS = [
    {"bank": "Marcus by Goldman Sachs", "apy": 4.50, "min_balance": 0,
     "fdic_insured": True, "account_type": "HYSA"},
    {"bank": "Ally Bank", "apy": 4.35, "min_balance": 0,
     "fdic_insured": True, "account_type": "HYSA"},
    {"bank": "Synchrony Bank", "apy": 4.75, "min_balance": 0,
     "fdic_insured": True, "account_type": "Money Market"},
    {"bank": "Discover Bank 12-Mo CD", "apy": 4.80, "min_balance": 2500,
     "fdic_insured": True, "account_type": "CD"},
]

FALLBACK_FED_FUNDS = 4.33


def fetch_fed_funds_rate() -> float:
    """Fetch current FEDFUNDS rate from FRED. Returns float."""
    ...


def rate_account(account: dict, fed_funds: float) -> dict:
    """Add rating and spread_vs_fed fields to account dict."""
    ...


def fetch_fdic_top_banks(limit: int = 10) -> list[dict]:
    """Fetch top banks by asset size from FDIC API for FDIC validation."""
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
    print(f"[W4] Fed funds={result['fed_funds_rate']}% accounts={result['record_count']} → {OUTPUT_PATH}")
```

## RULES

- NEVER store user account numbers, routing numbers, or personal data.
- `fdic_insured` must always be `true` — exclude any non-FDIC-insured products.
- `account_type` must be one of HYSA / Money Market / CD — raise ValueError for others.
- `rating` must be computed fresh from `fed_funds_rate` each run — never cached.
- If FRED API is unreachable, use `FALLBACK_FED_FUNDS = 4.33` and log a warning.
- All APY values must be positive floats. Reject zero or negative APY entries.
- CDs must include term in the `bank` name string (e.g., "12-Mo CD").
- Output file must always be valid JSON. Write error envelope on failure.
- Do not call any LLM.

## VALIDATION CHECKLIST

- [ ] `generated_at` is ISO 8601 UTC
- [ ] `fed_funds_rate` is a positive float
- [ ] `record_count` equals `len(accounts)`
- [ ] All `fdic_insured` values are `true`
- [ ] All `account_type` values are HYSA | Money Market | CD
- [ ] All `rating` values are TOP_PICK | COMPETITIVE | AVERAGE
- [ ] `spread_vs_fed` = `apy - fed_funds_rate` (within 0.001 tolerance)
- [ ] Output file is valid JSON
- [ ] FRED API failure triggers fallback rate, not a crash
