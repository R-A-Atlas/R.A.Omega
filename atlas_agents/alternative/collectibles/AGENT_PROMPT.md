# A3 — Collectibles/Cards Scraper | Division: Alternative Assets & Niche

## IDENTITY
You track prices and trading volume for graded collectibles across five categories:
Sports Cards, Pokemon, Magic: The Gathering, Comic Books, and Coins. You query the
eBay Browse API for recently sold listings and the PSA registry for population data.
No LLM calls. Pure API fetch + calculation.

## DEFINITION
  Coverage: 5 tracked items across 5 collectible categories.
  Signal: HOT / RISING / STABLE / COOLING based on volume and MoM price change.
  Output: data_cache/collectibles_latest.json

## DATA SOURCES (with URLs)

### Primary — eBay Browse API (public, no auth for basic search):
  https://api.ebay.com/buy/browse/v1/item_summary/search?q={query}&filter=buyingOptions:{FIXED_PRICE},conditions:{3000}&limit=10
  filter conditions:{3000} = Used (graded items appear here)
  Use itemFilter: soldItems=true equivalent via the Marketplace Insights endpoint.
  Public searches do not require OAuth for read-only Browse API calls.
  Rate limit: 1.0s sleep between each item query (5 requests total).

### Secondary — PSA Population Registry (public):
  https://www.psacard.com/pop
  Public HTML — scrape PSA population count for each graded card.
  Low pop count = scarcer = higher collectible value signal.

### eBay Sold Listings Fallback (public HTML):
  https://www.ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1
  Use if Browse API is unavailable without auth token.
  Parse sold item prices from public HTML search results.

## OUTPUT FILE
  data_cache/collectibles_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "ebay_browse_api",
  "record_count": 5,
  "items": [
    {
      "category": "Pokemon",
      "item": "PSA 10 Charizard Base Set",
      "grade": "PSA 10",
      "avg_sold_price": 8500.00,
      "volume_30d": 12,
      "trend": "HOT"
    }
  ]
}
```

## SIGNAL LOGIC
  trend classification (applied in order — first match wins):
    "HOT"     — volume_30d >= 100 AND price_change_mom_pct >= 10.0
    "RISING"  — price_change_mom_pct >= 5.0
    "STABLE"  — price_change_mom_pct >= -5.0 AND < 5.0
    "COOLING" — price_change_mom_pct < -5.0

  price_change_mom_pct requires two data points: current month avg vs prior month avg.
  If only one period of data available, default to "STABLE".
  volume_30d: count of sold listings in last 30 days returned by eBay API.

## TRACKED ITEMS UNIVERSE
  [
    {"category": "Pokemon",                  "item": "PSA 10 Charizard Base Set",        "grade": "PSA 10",  "ebay_query": "PSA 10 Charizard Base Set Holo"},
    {"category": "Sports Cards",             "item": "PSA 10 LeBron James RC",            "grade": "PSA 10",  "ebay_query": "PSA 10 LeBron James Rookie Card"},
    {"category": "Sports Cards",             "item": "PSA 10 Tom Brady RC",               "grade": "PSA 10",  "ebay_query": "PSA 10 Tom Brady Rookie Card"},
    {"category": "Comic Books",              "item": "CGC 9.8 Amazing Fantasy 15 reprint","grade": "CGC 9.8", "ebay_query": "CGC 9.8 Amazing Fantasy 15 reprint"},
    {"category": "Coins",                    "item": "MS-65 Morgan Silver Dollar",         "grade": "MS-65",   "ebay_query": "MS-65 Morgan Silver Dollar PCGS NGC"},
  ]

## SCRAPER STRUCTURE
```python
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "collectibles_latest.json"

EBAY_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SOLD_FALLBACK = "https://www.ebay.com/sch/i.html"

TRACKED_ITEMS = [
    {"category": "Pokemon",       "item": "PSA 10 Charizard Base Set",         "grade": "PSA 10",  "ebay_query": "PSA 10 Charizard Base Set Holo"},
    {"category": "Sports Cards",  "item": "PSA 10 LeBron James RC",             "grade": "PSA 10",  "ebay_query": "PSA 10 LeBron James Rookie Card"},
    {"category": "Sports Cards",  "item": "PSA 10 Tom Brady RC",                "grade": "PSA 10",  "ebay_query": "PSA 10 Tom Brady Rookie Card"},
    {"category": "Comic Books",   "item": "CGC 9.8 Amazing Fantasy 15 reprint", "grade": "CGC 9.8", "ebay_query": "CGC 9.8 Amazing Fantasy 15 reprint"},
    {"category": "Coins",         "item": "MS-65 Morgan Silver Dollar",          "grade": "MS-65",   "ebay_query": "MS-65 Morgan Silver Dollar PCGS NGC"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def fetch_ebay_sold(query: str) -> list[float]: ...
    # Try Browse API first; fall back to public HTML sold search
    # Return list of sold prices (float USD)

def fetch_sold_html_fallback(query: str) -> list[float]: ...
    # GET EBAY_SOLD_FALLBACK with _nkw, LH_Sold=1, LH_Complete=1
    # Parse price spans from search results HTML
    # Return list of float prices

def compute_avg_price(prices: list[float]) -> float: ...
    # Return mean of prices list, or 0.0 if empty

def classify_trend(volume_30d: int, price_change_mom_pct: float) -> str: ...
    # Apply SIGNAL LOGIC thresholds in order (HOT first)

def build_item_record(item_def: dict, prices: list[float]) -> dict: ...
    # Build full item record dict; volume_30d = len(prices)

def scrape() -> dict: ...
    # Iterate TRACKED_ITEMS with 1.0s sleep, build records, return payload

def write_outputs(payload: dict) -> tuple[Path, Path]: ...
    # Call write_cache_json_pair(DATA_CACHE_DIR, OUTPUT_STABLE_NAME, payload)

def main(argv=None) -> int: ...
    # payload = scrape(); write_outputs(payload); return 0
```

## RULES
- No LLM calls — API/HTML parsing and arithmetic only
- avg_sold_price expressed as float rounded to 2 decimal places
- volume_30d expressed as integer count of sold listings found
- trend must be one of: HOT, RISING, STABLE, COOLING
- category must be one of: Sports Cards, Pokemon, Magic: The Gathering, Comic Books, Coins
- generated_at must be ISO UTC string (datetime.utcnow().isoformat() + "Z")
- If eBay returns no results: set avg_sold_price=0.0, volume_30d=0, trend="STABLE"
- 1.0s sleep between each item query
- Use write_cache_json_pair for output
- record_count must equal len(items)

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile collectibles_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, record_count, items list
  [ ] All items have category, item, grade, avg_sold_price, volume_30d, trend
  [ ] trend is one of: HOT, RISING, STABLE, COOLING
  [ ] category is one of the 5 defined categories
  [ ] record_count == 5
  [ ] python -m pytest tests/test_collectibles.py -v passes
