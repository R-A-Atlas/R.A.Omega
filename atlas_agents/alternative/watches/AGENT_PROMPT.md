# A1 — Watch Market Bot | Division: Alternative Assets & Niche

## IDENTITY
You track the secondary market for luxury collectible watches — Rolex, Patek Philippe,
Audemars Piguet, and Omega. You scrape Chrono24 public listing pages, compute average
secondary-market prices, and compare against known retail prices to derive a
premium_over_retail_pct signal. No LLM calls. Pure data scrape + calculation.

## DEFINITION
  Coverage: 8 top collectible references across 4 brands.
  Signal: premium percentage over manufacturer retail price.
  Output: data_cache/watches_latest.json

## DATA SOURCES (with URLs)

### Primary — Chrono24 Public Listing Search:
  https://www.chrono24.com/search/index.htm?query={model}&resultview=block
  Public HTML pages — scrape listing prices from search results.
  Parse price elements from listing cards (class: .article-item or similar).
  Rate limit: 1.0s sleep between each model query (8 requests total).

### Hardcoded Retail Price Reference:
  Embedded in WATCH_UNIVERSE dict below. Manufacturer retail MSRPs (USD).
  Updated manually when brands adjust pricing (typically annual).

## OUTPUT FILE
  data_cache/watches_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "chrono24_public",
  "record_count": 8,
  "models": [
    {
      "brand": "Rolex",
      "model": "Submariner",
      "reference": "116610LN",
      "avg_price": 14200,
      "retail_price": 9100,
      "premium_over_retail_pct": 56.04,
      "trend": "APPRECIATING",
      "listings_count": 42
    }
  ]
}
```

## SIGNAL LOGIC
  premium_over_retail_pct = ((avg_price - retail_price) / retail_price) * 100

  trend classification:
    "APPRECIATING"  — avg_price > retail_price * 1.5  (premium >= 50%)
    "PREMIUM"       — avg_price > retail_price  (premium > 0% but < 50%)
    "AT_RETAIL"     — avg_price within 10% of retail_price  (-10% to +10% range)
    "BELOW_RETAIL"  — avg_price < retail_price * 0.90

  Note: AT_RETAIL takes priority over PREMIUM when overlap occurs (check AT_RETAIL first).

## SCRAPER STRUCTURE
```python
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "watches_latest.json"

BASE_URL = "https://www.chrono24.com/search/index.htm"

# brand, model, reference, retail_price (USD MSRP)
WATCH_UNIVERSE = [
    {"brand": "Rolex",           "model": "Submariner",    "reference": "116610LN",             "retail_price": 9100},
    {"brand": "Rolex",           "model": "GMT-Master II", "reference": "126710BLNR",            "retail_price": 10800},
    {"brand": "Rolex",           "model": "Daytona",       "reference": "116500LN",              "retail_price": 14550},
    {"brand": "Patek Philippe",  "model": "Nautilus",      "reference": "5711/1A",               "retail_price": 35000},
    {"brand": "Patek Philippe",  "model": "Aquanaut",      "reference": "5167A",                 "retail_price": 28000},
    {"brand": "AP",              "model": "Royal Oak",     "reference": "15400ST",               "retail_price": 24100},
    {"brand": "AP",              "model": "Royal Oak",     "reference": "15202ST",               "retail_price": 29000},
    {"brand": "Omega",           "model": "Speedmaster",   "reference": "311.30.42.30.01.005",   "retail_price": 6100},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def fetch_listings(watch: dict) -> list[float]: ...
    # GET BASE_URL?query={reference}&resultview=block
    # Parse BeautifulSoup for price elements
    # Return list of float prices found on page

def compute_avg_price(prices: list[float]) -> float: ...
    # Return mean, or 0.0 if list is empty

def classify_trend(avg_price: float, retail_price: float) -> str: ...
    # Apply SIGNAL LOGIC thresholds, return one of the four trend strings

def build_model_record(watch: dict, prices: list[float]) -> dict: ...
    # Build and return full model record dict

def scrape() -> dict: ...
    # Iterate WATCH_UNIVERSE with 1.0s sleep, build records list, return payload

def write_outputs(payload: dict) -> tuple[Path, Path]: ...
    # Call write_cache_json_pair(DATA_CACHE_DIR, OUTPUT_STABLE_NAME, payload)

def main(argv=None) -> int: ...
    # payload = scrape(); write_outputs(payload); return 0
```

## RULES
- No LLM calls — HTML parsing and arithmetic only
- avg_price expressed as integer USD (round float to int)
- retail_price expressed as integer USD (hardcoded)
- premium_over_retail_pct expressed as float rounded to 2 decimal places
- listings_count is the count of valid price elements found on the page
- generated_at must be ISO UTC string (datetime.utcnow().isoformat() + "Z")
- If Chrono24 returns non-200 or parse fails: set avg_price=0, listings_count=0, trend="AT_RETAIL"
- 1.0s sleep between each watch query (8 requests total)
- Use write_cache_json_pair for output
- Respect robots.txt; do not hammer the server

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile watches_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, record_count, models list
  [ ] All models have brand, model, reference, avg_price, retail_price, premium_over_retail_pct, trend, listings_count
  [ ] record_count == len(models) == 8
  [ ] premium_over_retail_pct computed correctly: ((avg - retail) / retail) * 100
  [ ] python -m pytest tests/test_watches.py -v passes
