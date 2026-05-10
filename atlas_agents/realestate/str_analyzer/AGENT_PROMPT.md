# R3 — Airbnb/STR Analyzer | Division: Real Estate & Property

## IDENTITY
You analyze short-term rental (STR) market performance across US cities —
average daily rates, occupancy, annual revenue estimates, and regulatory risk.
STR yield often outpaces long-term rental yield by 2-3x but carries
regulation risk. No LLM calls. Public data fetch + arithmetic.

## DEFINITION
  STR: Short-term rental listed on Airbnb, VRBO, etc. (< 30-day stays)
  Annual revenue estimate = avg_daily_rate * occupancy_rate * 365
  Occupancy rate expressed as decimal (e.g., 0.72 = 72%)
  avg_daily_rate expressed as integer USD

  Regulation risk categories:
    HIGH:   City has banned or severely restricted STR (permit required + cap)
    MEDIUM: City requires permit but no hard cap
    LOW:    Minimal regulation, no permit required

## DATA SOURCES (free, no auth)

### Primary — Inside Airbnb (public datasets, CC license):
  http://insideairbnb.com/get-the-data/
  Per-city CSV files: listings.csv.gz, calendar.csv.gz
  Key fields: price, availability_365, neighbourhood_cleansed, room_type
  Rate limit: 1 req/5s (be polite — public hosting)

### Secondary — AirDNA free market summary pages (scrape):
  https://www.airdna.co/vacation-rental-data/app/us/  (public overview pages)
  Parse ADR and occupancy from public market summary (no auth needed for top-line)

### Tertiary — STR regulation tracker (static reference table):
  Maintain a hardcoded dict of known regulation status for top 20 markets
  Updated manually when regulations change — source: local ordinance records

## OUTPUT FILE
  data_cache/str_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "inside_airbnb",
  "record_count": 15,
  "markets": [
    {
      "city": "Nashville",
      "state": "TN",
      "avg_daily_rate": 185,
      "occupancy_rate": 0.68,
      "annual_revenue_est": 45878,
      "active_listings": 8420,
      "regulation_risk": "MEDIUM"
    }
  ]
}
```

## REVENUE ESTIMATE FORMULA
  annual_revenue_est = round(avg_daily_rate * occupancy_rate * 365)

## REGULATION RISK REFERENCE TABLE (hardcoded baseline)
  HIGH:   New York City, San Francisco, Santa Monica, Honolulu, New Orleans
  MEDIUM: Nashville, Austin, Denver, Miami, Los Angeles, Seattle
  LOW:    Phoenix, Tampa, Charlotte, Atlanta, Dallas, Houston

## SCRAPER STRUCTURE
```python
import requests
import gzip
import csv
import io
import time
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "str_latest.json"

INSIDE_AIRBNB_BASE = "http://insideairbnb.com/get-the-data/"

REGULATION_RISK = {
    "New York City": "HIGH", "San Francisco": "HIGH",
    "Santa Monica": "HIGH", "Honolulu": "HIGH", "New Orleans": "HIGH",
    "Nashville": "MEDIUM", "Austin": "MEDIUM", "Denver": "MEDIUM",
    "Miami": "MEDIUM", "Los Angeles": "MEDIUM", "Seattle": "MEDIUM",
    "Phoenix": "LOW", "Tampa": "LOW", "Charlotte": "LOW",
    "Atlanta": "LOW", "Dallas": "LOW", "Houston": "LOW",
}

def fetch_city_listings(city: str, url: str) -> list[dict]: ...  # download + gunzip CSV
def compute_market_stats(listings: list) -> dict: ...            # ADR, occupancy, revenue
def classify_regulation_risk(city: str) -> str: ...
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — CSV parsing + arithmetic only
- annual_revenue_est = round(avg_daily_rate * occupancy_rate * 365)
- occupancy_rate expressed as decimal 0.0–1.0 (not percentage)
- avg_daily_rate expressed as integer USD
- annual_revenue_est expressed as integer USD
- regulation_risk must be exactly: "HIGH", "MEDIUM", or "LOW"
- Sleep 5s between Inside Airbnb city requests (rate limit)
- generated_at must be ISO UTC string
- If city fetch fails: skip that city, log warning, continue
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile str_analyzer_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, markets list, record_count
  [ ] All markets have avg_daily_rate > 0 and 0 < occupancy_rate <= 1.0
  [ ] annual_revenue_est = round(avg_daily_rate * occupancy_rate * 365)
  [ ] regulation_risk in {"HIGH", "MEDIUM", "LOW"}
  [ ] python -m pytest tests/test_str_analyzer.py -v passes
