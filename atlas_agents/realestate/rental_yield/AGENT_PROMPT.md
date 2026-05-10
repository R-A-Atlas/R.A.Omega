# R2 — Rental Yield Calculator | Division: Real Estate & Property

## IDENTITY
You estimate gross rental yield for residential properties across US metros
by combining HUD Fair Market Rents with median home prices. Yield is the
primary signal for identifying cash-flow-positive markets. No LLM calls.
Pure fetch + arithmetic.

## DEFINITION
  Gross rental yield = (annual_rent / median_home_price) * 100
  annual_rent = avg_rent_2br * 12  (2-bedroom as standard unit)
  yield_estimate expressed as percentage float (e.g., 6.4 = 6.4%)

  Good yield: >= 6.0% (positive cash flow likely)
  Average:    4.0% – 5.9%
  Low yield:  < 4.0% (appreciation play, not cash flow)

## DATA SOURCES (free, no auth)

### Primary — HUD Fair Market Rents (FMR) API:
  https://www.huduser.gov/hudapi/public/fmr/listMetroAreas
  https://www.huduser.gov/hudapi/public/fmr/data/{entityid}?year=2026
  Fields: area_name, Efficiency, One-Bedroom, Two-Bedroom, Three-Bedroom
  Note: HUD API is free but requires token from https://www.huduser.gov/portal/dataset/fmr-api.html
  Token stored in env as HUD_API_TOKEN

### Secondary — Zillow Observed Rent Index (ZORI) public CSV:
  https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv
  Fields: RegionName, State, monthly columns (use latest)
  No auth required — direct S3 download

### Tertiary — Combine with R1 median_price from:
  data_cache/residential_latest.json  (if available, avoids double-fetch)

## OUTPUT FILE
  data_cache/rental_yield_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "hud_fmr_zillow_zori",
  "record_count": 20,
  "markets": [
    {
      "city": "Cleveland",
      "state": "OH",
      "avg_rent_1br": 820,
      "avg_rent_2br": 1050,
      "median_home_price": 185000,
      "mortgage_rate": 7.1,
      "yield_estimate": 6.81,
      "yield_signal": "GOOD"
    }
  ]
}
```

## YIELD SIGNAL LOGIC
  yield_estimate >= 6.0  → "GOOD"
  yield_estimate >= 4.0  → "AVERAGE"
  yield_estimate < 4.0   → "LOW"

## SCRAPER STRUCTURE
```python
import requests
import csv
import io
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "rental_yield_latest.json"

ZORI_URL = "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv"

def fetch_zori_rents() -> list[dict]: ...     # download ZORI CSV, extract latest month
def load_residential_cache() -> dict: ...     # read data_cache/residential_latest.json
def compute_yield(annual_rent: float, median_price: float) -> float: ...
def classify_yield_signal(yield_pct: float) -> str: ...
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — fetch + arithmetic only
- yield_estimate = (avg_rent_2br * 12 / median_home_price) * 100
- yield_estimate expressed as float rounded to 2 decimal places
- avg_rent_1br, avg_rent_2br expressed as integer USD/month
- median_home_price expressed as integer USD
- mortgage_rate expressed as float percentage (e.g., 7.1)
- generated_at must be ISO UTC string
- If ZORI unavailable: log warning, return empty markets list
- Use write_cache_json_pair for output
- yield_signal must be exactly: "GOOD", "AVERAGE", or "LOW"

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile rental_yield_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, markets list, record_count
  [ ] All markets have yield_estimate > 0
  [ ] yield_signal in {"GOOD", "AVERAGE", "LOW"}
  [ ] python -m pytest tests/test_rental_yield.py -v passes
