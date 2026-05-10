# R7 — Mortgage Rate Tracker | Division: Real Estate & Property

## IDENTITY
You track weekly US mortgage rates from Freddie Mac's Primary Mortgage Market
Survey (PMMS) — the gold standard for 30y and 15y fixed rates. Mortgage rates
are the single biggest lever on housing affordability and market activity.
No LLM calls. Pure data fetch + trend classification.

## DEFINITION
  PMMS: Primary Mortgage Market Survey — published every Thursday by Freddie Mac
  term: loan duration (30-Year Fixed, 15-Year Fixed, 5/1 ARM)
  rate: annual interest rate as float percentage (e.g., 7.12)
  points: origination points charged (float, e.g., 0.7)
  week_of: ISO date of the Thursday survey (YYYY-MM-DD)

  Trend classification (WoW change on 30y fixed):
    RISING:  rate_now > rate_last_week + 0.05
    FALLING: rate_now < rate_last_week - 0.05
    STABLE:  |rate_now - rate_last_week| <= 0.05

## DATA SOURCES (free, no auth)

### Primary — Freddie Mac PMMS via FRED API (no auth required):
  30-Year Fixed: https://api.stlouisfed.org/fred/series/observations?series_id=MORTGAGE30US&file_type=json&sort_order=desc&limit=4
  15-Year Fixed: https://api.stlouisfed.org/fred/series/observations?series_id=MORTGAGE15US&file_type=json&sort_order=desc&limit=4
  5/1 ARM:       https://api.stlouisfed.org/fred/series/observations?series_id=MORTGAGE5US&file_type=json&sort_order=desc&limit=4
  Note: FRED returns PMMS data with 1-week lag. No API key needed for these series.

### Secondary — Freddie Mac direct data download (CSV):
  https://www.freddiemac.com/pmms/docs/historicalweeklydata.xls
  Contains full history back to 1971. Parse with openpyxl or xlrd.

### Tertiary — Bankrate public mortgage rate table (scrape):
  https://www.bankrate.com/mortgages/mortgage-rates/
  Parse HTML table for current rates. Rate limit: 1 req/10s.

## OUTPUT FILE
  data_cache/mortgage_rates_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "freddie_mac_pmms_fred",
  "trend": "RISING",
  "wow_change_30y": 0.12,
  "record_count": 3,
  "rates": [
    {
      "term": "30-Year Fixed",
      "rate": 7.12,
      "points": 0.7,
      "week_of": "2026-05-08"
    },
    {
      "term": "15-Year Fixed",
      "rate": 6.58,
      "points": 0.6,
      "week_of": "2026-05-08"
    },
    {
      "term": "5/1 ARM",
      "rate": 6.34,
      "points": 0.5,
      "week_of": "2026-05-08"
    }
  ]
}
```

## TREND LOGIC
  wow_change_30y = rate_30y_this_week - rate_30y_last_week
  wow_change_30y > 0.05   → trend = "RISING"
  wow_change_30y < -0.05  → trend = "FALLING"
  else                    → trend = "STABLE"

## SCRAPER STRUCTURE
```python
import requests
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "mortgage_rates_latest.json"

FRED_SERIES = {
    "30-Year Fixed": "MORTGAGE30US",
    "15-Year Fixed": "MORTGAGE15US",
    "5/1 ARM":       "MORTGAGE5US",
}
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

def fetch_fred_series(series_id: str, limit: int = 4) -> list[dict]: ...
def classify_trend(wow_change: float) -> str: ...
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — fetch + arithmetic only
- rate expressed as float percentage (e.g., 7.12 not 0.0712)
- points expressed as float (e.g., 0.7)
- wow_change_30y = rate_this_week - rate_last_week (may be negative)
- trend must be exactly: "RISING", "FALLING", or "STABLE"
- week_of expressed as ISO date string YYYY-MM-DD
- generated_at must be ISO UTC string
- If FRED unavailable: log warning, return empty rates list, trend = null
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile mortgage_rates_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, rates list, trend, wow_change_30y
  [ ] All rates have term, rate, points, week_of
  [ ] rate > 0 for all terms
  [ ] trend in {"RISING", "FALLING", "STABLE"}
  [ ] python -m pytest tests/test_mortgage_rates.py -v passes
