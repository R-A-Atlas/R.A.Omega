# A2 — Art Auction Tracker | Division: Alternative Assets & Niche

## IDENTITY
You track fine art auction results from public MutualArt pages and compare realized
prices against pre-sale estimates. You also maintain the Artprice100 index as a
benchmark for the broader art market. No LLM calls. Pure HTML scrape + calculation.

## DEFINITION
  Coverage: public auction results from major houses (Christie's, Sotheby's, Phillips, Bonhams).
  Signal: premium_over_estimate_pct — how much realized price exceeded high estimate.
  Benchmark: Artprice100 index (hardcoded quarterly update from public reports).
  Output: data_cache/art_latest.json

## DATA SOURCES (with URLs)

### Primary — MutualArt Public Auction Results:
  https://www.mutualart.com/Auction-Results
  Public HTML pages showing recent auction results across all major houses.
  Parse: artist name, artwork title, medium, auction house, realized price,
         pre-sale estimate (low and high), sale date.
  Rate limit: 1.5s sleep between paginated requests.

### Benchmark — Artprice100 Index:
  Source: https://www.artprice.com/artprice-reports/the-artprice100-index
  Hardcoded quarterly value in ARTPRICE100_INDEX constant (update manually each quarter).
  Current value: 1842 (Q1 2026 — represents cumulative performance vs 2000 baseline).

## OUTPUT FILE
  data_cache/art_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "mutualart_public",
  "record_count": 20,
  "artprice100_index": 1842,
  "sales": [
    {
      "artist": "Jean-Michel Basquiat",
      "title": "Untitled (Head)",
      "medium": "Oil on canvas",
      "house": "Christie's",
      "realized_price_usd": 4200000,
      "estimate_low_usd": 3000000,
      "estimate_high_usd": 4000000,
      "sold_date": "2026-05-01",
      "premium_over_estimate_pct": 5.0,
      "signal": "ABOVE_ESTIMATE"
    }
  ]
}
```

## SIGNAL LOGIC
  premium_over_estimate_pct = ((realized_price_usd - estimate_high_usd) / estimate_high_usd) * 100

  signal classification:
    "ABOVE_ESTIMATE"  — realized_price_usd > estimate_high_usd
    "IN_RANGE"        — realized_price_usd >= estimate_low_usd AND <= estimate_high_usd
    "BELOW_ESTIMATE"  — realized_price_usd < estimate_low_usd

  Note: premium_over_estimate_pct is negative when IN_RANGE or BELOW_ESTIMATE.

## SCRAPER STRUCTURE
```python
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "art_latest.json"

MUTUALART_URL = "https://www.mutualart.com/Auction-Results"
ARTPRICE100_INDEX = 1842  # Q1 2026 — update quarterly

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

MAX_PAGES = 3        # scrape first 3 pages of results
RESULTS_PER_PAGE = 10

def fetch_results_page(page: int = 1) -> str: ...
    # GET MUTUALART_URL with pagination params
    # Return raw HTML string

def parse_sales(html: str) -> list[dict]: ...
    # Parse BeautifulSoup for auction result rows
    # Extract: artist, title, medium, house, realized_price_usd,
    #          estimate_low_usd, estimate_high_usd, sold_date

def classify_signal(realized: float, est_low: float, est_high: float) -> str: ...
    # Apply SIGNAL LOGIC, return one of three signal strings

def compute_premium(realized: float, est_high: float) -> float: ...
    # Return ((realized - est_high) / est_high) * 100 rounded to 2 decimal places

def build_sale_record(raw: dict) -> dict: ...
    # Enrich raw record with signal and premium_over_estimate_pct

def scrape() -> dict: ...
    # Iterate pages with 1.5s sleep, collect up to 20 records, return payload

def write_outputs(payload: dict) -> tuple[Path, Path]: ...
    # Call write_cache_json_pair(DATA_CACHE_DIR, OUTPUT_STABLE_NAME, payload)

def main(argv=None) -> int: ...
    # payload = scrape(); write_outputs(payload); return 0
```

## RULES
- No LLM calls — HTML parsing and arithmetic only
- realized_price_usd, estimate_low_usd, estimate_high_usd expressed as integer USD
- premium_over_estimate_pct expressed as float rounded to 2 decimal places
- sold_date expressed as ISO date string (YYYY-MM-DD)
- generated_at must be ISO UTC string (datetime.utcnow().isoformat() + "Z")
- artprice100_index is hardcoded integer — update manually each quarter
- If MutualArt page unavailable: log warning, return empty sales list
- 1.5s sleep between paginated requests
- Use write_cache_json_pair for output
- record_count must equal len(sales)

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile art_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, record_count, artprice100_index, sales list
  [ ] All sales have artist, title, medium, house, realized_price_usd, estimate_low_usd, estimate_high_usd, sold_date, premium_over_estimate_pct, signal
  [ ] signal is one of: ABOVE_ESTIMATE, IN_RANGE, BELOW_ESTIMATE
  [ ] premium_over_estimate_pct computed correctly
  [ ] python -m pytest tests/test_art.py -v passes
