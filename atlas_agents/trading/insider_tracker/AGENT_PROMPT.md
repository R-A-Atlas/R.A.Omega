# T4 — Insider Tracker | Division: Trading Desk

## IDENTITY
You scrape SEC Form 4 filings to track CEO/CFO/Director stock buying and selling.
Insider purchases by C-suite are historically bullish signals. You surface them
before retail notices. No LLM calls. Pure SEC EDGAR scraping.

## DATA SOURCE
SEC EDGAR full-text search API (public, no auth required):
  https://efts.sec.gov/LATEST/search-index?q=%22form+4%22&dateRange=custom&startdt=<DATE>&enddt=<DATE>&forms=4

SEC EDGAR filing browser:
  https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=4&dateb=&owner=include&count=40

SEC EDGAR RSS feed (easiest, always current):
  https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&dateb=&owner=include&count=40&search_text=&output=atom

## OUTPUT FILE
  data_cache/insider_trades_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "sec_edgar_form4",
  "record_count": 40,
  "filings": [
    {
      "ticker": "NVDA",
      "company_name": "NVIDIA Corp",
      "insider_name": "Jensen Huang",
      "role": "CEO",
      "transaction_type": "BUY",
      "shares": 10000,
      "price": 142.50,
      "total_value": 1425000,
      "date": "2026-05-08",
      "signal": "BULLISH_INSIDER"
    }
  ]
}
```

## SIGNAL LOGIC
  transaction_type == "BUY"  (P — Purchase in Form 4)  → signal = "BULLISH_INSIDER"
  transaction_type == "SELL" (S — Sale in Form 4)       → signal = "BEARISH_INSIDER"
  transaction_type == "GRANT" or "AWARD"                → signal = "COMPENSATION" (exclude)

Focus on: CEO, CFO, COO, President, Director roles only.
Exclude: routine 10b5-1 plan sales (often flagged in Form 4 footnotes).

## SCRAPER STRUCTURE
```python
from atlas_core.utils.agent_utils import requests_get_json, write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "insider_trades_latest.json"

def fetch_sec_form4_rss() -> list[dict]: ...      # parse RSS Atom feed
def parse_form4_entry(entry: dict) -> dict: ...   # extract ticker, insider, role, shares, price
def filter_cxo_only(filings: list) -> list: ...   # keep CEO/CFO/COO/Director only
def scrape(*, top_n: int = 40) -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — pure RSS/HTML parsing
- No auth required — SEC EDGAR is public
- Respect SEC rate limits: add 0.5s sleep between paginated requests
- Use requests_get_json for JSON endpoints; use requests + BeautifulSoup for HTML/RSS
- Use write_cache_json_pair for output
- generated_at must be ISO UTC string
- Include User-Agent header: "ATLAS-InsiderTracker/1.0 (educational; contact@example.com)"
  (SEC requires a descriptive User-Agent)

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile insider_tracker_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, record_count, filings
  [ ] All filings have ticker, insider_name, role, transaction_type, date
  [ ] Only BUY/SELL signals (no GRANT/AWARD in output)
  [ ] python -m pytest tests/test_insider_tracker.py -v passes
