# T10 — Bond Yield Curve | Division: Trading Desk

## IDENTITY
You track US Treasury yields across the full maturity spectrum and detect
yield curve shape signals — normal, flat, or inverted. Curve inversion is
the most reliable leading indicator of recession risk. No LLM calls.
Pure data fetch + arithmetic.

## DEFINITION
  Yield curve: 2y vs 10y spread is the canonical inversion signal.
  INVERTED: 10y rate < 2y rate  (spread < 0)
  FLAT:     |10y - 2y| <= 0.25% (within 25 bps)
  NORMAL:   10y rate > 2y rate + 0.25% (spread > 25 bps)

## DATA SOURCE (free, no auth)
  US Treasury FiscalData API:
    https://api.fiscaldata.treasury.gov/services/api/v1/accounting/od/avg_interest_rates
    Use endpoint: Daily Treasury Par Yield Curve Rates
    https://api.fiscaldata.treasury.gov/services/api/v1/accounting/od/avg_interest_rates?fields=record_date,security_desc,avg_interest_rate_amt&filter=security_desc:in:(1-Year,2-Year,5-Year,10-Year,30-Year)&sort=-record_date&page[size]=5

  Alternate endpoint (yield curve rates):
    https://api.fiscaldata.treasury.gov/services/api/v1/accounting/od/avg_interest_rates

  Maturities to fetch: 1M, 3M, 6M, 1Y, 2Y, 5Y, 10Y, 20Y, 30Y
  All rates expressed as annual percentage (e.g., 4.35 = 4.35%)

## OUTPUT FILE
  data_cache/bond_yields_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "fiscaldata_treasury_gov",
  "record_date": "2026-05-08",
  "record_count": 9,
  "curve_signal": "INVERTED",
  "spread_2y_10y": -0.42,
  "yields": [
    {
      "maturity": "1M",
      "rate": 5.28,
      "date": "2026-05-08"
    },
    {
      "maturity": "3M",
      "rate": 5.21,
      "date": "2026-05-08"
    },
    {
      "maturity": "6M",
      "rate": 5.05,
      "date": "2026-05-08"
    },
    {
      "maturity": "1Y",
      "rate": 4.87,
      "date": "2026-05-08"
    },
    {
      "maturity": "2Y",
      "rate": 4.62,
      "date": "2026-05-08"
    },
    {
      "maturity": "5Y",
      "rate": 4.38,
      "date": "2026-05-08"
    },
    {
      "maturity": "10Y",
      "rate": 4.20,
      "date": "2026-05-08"
    },
    {
      "maturity": "20Y",
      "rate": 4.45,
      "date": "2026-05-08"
    },
    {
      "maturity": "30Y",
      "rate": 4.51,
      "date": "2026-05-08"
    }
  ]
}
```

## CURVE SIGNAL LOGIC
  spread_2y_10y = rate_10y - rate_2y
  spread_2y_10y < 0              → curve_signal = "INVERTED"
  -0.25 <= spread_2y_10y <= 0.25 → curve_signal = "FLAT"
  spread_2y_10y > 0.25           → curve_signal = "NORMAL"

## SCRAPER STRUCTURE
```python
import requests
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "bond_yields_latest.json"

BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/v1/accounting/od/avg_interest_rates"

MATURITY_MAP = {
    "Treasury Bills": ["1-Month", "3-Month", "6-Month"],
    "Treasury Notes": ["1-Year", "2-Year", "5-Year", "10-Year"],
    "Treasury Bonds": ["20-Year", "30-Year"],
}

MATURITY_LABEL = {
    "1-Month": "1M", "3-Month": "3M", "6-Month": "6M",
    "1-Year": "1Y", "2-Year": "2Y", "5-Year": "5Y",
    "10-Year": "10Y", "20-Year": "20Y", "30-Year": "30Y",
}

def fetch_yields() -> list[dict]: ...   # GET fiscaldata API, parse JSON
def classify_curve(yields: list) -> tuple[str, float]: ...  # returns (signal, spread)
def scrape() -> dict: ...               # assembles full output payload
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — fetch + arithmetic only
- All rates must be float (percentage, e.g., 4.35 not 0.0435)
- spread_2y_10y = rate_10y - rate_2y (may be negative for INVERTED)
- curve_signal must be exactly: "NORMAL", "INVERTED", or "FLAT"
- generated_at must be ISO UTC string
- record_date is the Treasury data date (not generated_at)
- If API unavailable: log warning, return empty yields list with curve_signal = null
- Use write_cache_json_pair for output
- No auth required — FiscalData is fully public

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile bond_yields_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, yields list, curve_signal
  [ ] curve_signal is one of: NORMAL, INVERTED, FLAT
  [ ] spread_2y_10y = rate_10y - rate_2y (verify arithmetic)
  [ ] All yield rates are positive floats
  [ ] python -m pytest tests/test_bond_yields.py -v passes
