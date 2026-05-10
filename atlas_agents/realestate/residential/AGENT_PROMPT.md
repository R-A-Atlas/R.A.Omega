# R1 — Residential Scout | Division: Real Estate & Property

## IDENTITY
You track residential real estate market conditions across US metros —
median prices, price trends, days on market, and inventory levels.
Early signals of cooling or heating markets. No LLM calls. Pure data fetch.

## DEFINITION
  Residential market data: median sale price, YoY price change,
  days on market (DOM), active inventory count.
  Coverage: top 20 US metros by population.

## DATA SOURCES (free, no auth)

### Primary — Redfin Data Center (public CSV):
  https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/redfin_metro_market_tracker.tsv000.gz
  Fields: period_end, region, median_sale_price, median_ppsf,
          homes_sold, inventory, days_on_market, avg_sale_to_list

### Secondary — Zillow Research Data (public CSV):
  Metro-level ZHVI (Zillow Home Value Index):
  https://files.zillowstatic.com/research/public_csvs/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv
  Fields: RegionName, State, plus monthly value columns

### Tertiary — FRED API (no auth required for free endpoints):
  Case-Shiller Home Price Index: CSUSHPISA series
  https://api.stlouisfed.org/fred/series/observations?series_id=CSUSHPISA&api_key=&file_type=json
  Note: FRED requires free API key — use only if key is in env

## OUTPUT FILE
  data_cache/residential_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "redfin_public_data",
  "record_count": 20,
  "markets": [
    {
      "city": "Austin",
      "state": "TX",
      "median_price": 485000,
      "yoy_change": -3.2,
      "days_on_market": 42,
      "inventory": 3850,
      "period_end": "2026-04-30"
    }
  ]
}
```

## SCRAPER STRUCTURE
```python
import requests
import gzip
import csv
import io
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "residential_latest.json"

REDFIN_URL = "https://redfin-public-data.s3.us-west-2.amazonaws.com/redfin_market_tracker/redfin_metro_market_tracker.tsv000.gz"

TOP_METROS = [
    "Austin, TX", "Phoenix, AZ", "Miami, FL", "Nashville, TN",
    "Dallas, TX", "Denver, CO", "Seattle, WA", "Charlotte, NC",
    "Tampa, FL", "Atlanta, GA", "New York, NY", "Los Angeles, CA",
    "Chicago, IL", "Houston, TX", "San Francisco, CA",
]

def fetch_redfin_data() -> list[dict]: ...   # download + gunzip + parse TSV
def filter_top_metros(rows: list) -> list: ...  # keep only TOP_METROS, latest period
def build_market_record(row: dict) -> dict: ...  # extract required fields
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — CSV parsing + field extraction only
- yoy_change expressed as percentage float (e.g., -3.2 = -3.2%)
- median_price expressed as integer USD (no cents)
- days_on_market expressed as integer
- inventory expressed as integer count
- generated_at must be ISO UTC string
- If Redfin URL unavailable: log warning, return empty markets list
- Use write_cache_json_pair for output
- 0.5s sleep between any paginated requests

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile residential_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, markets list, record_count
  [ ] All markets have city, state, median_price, yoy_change, days_on_market, inventory
  [ ] median_price > 0 for all records
  [ ] python -m pytest tests/test_residential.py -v passes
