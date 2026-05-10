# T5 — Earnings Parser | Division: Trading Desk

## IDENTITY
You pull upcoming earnings dates and analyst estimates for S&P 500 companies.
Earnings catalysts drive the biggest single-day moves. You surface them 2 weeks
in advance so ATLAS can front-run the setup. No LLM calls. Pure data parsing.

## DATA SOURCES (priority order)
1. yfinance earnings calendar (primary — already in requirements.txt):
   yf.Ticker("AAPL").calendar  →  {Earnings Date, EPS Estimate, Revenue Estimate}
   yf.get_earnings_dates("AAPL", limit=4)

2. Yahoo Finance earnings calendar endpoint (secondary — public, no auth):
   https://finance.yahoo.com/calendar/earnings?day=<YYYY-MM-DD>

3. EarningsWhispers public calendar (tertiary — scrape public page):
   https://www.earningswhispers.com/stocks/<ticker>

## OUTPUT FILE
  data_cache/earnings_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "yfinance_calendar",
  "window_days": 14,
  "record_count": 30,
  "upcoming": [
    {
      "ticker": "AAPL",
      "company_name": "Apple Inc.",
      "date": "2026-05-15",
      "time": "AMC",
      "est_eps": 1.58,
      "est_revenue": 89500000000,
      "sector": "Technology",
      "days_until": 6,
      "signal": "CATALYST_UPCOMING"
    }
  ]
}
```

## FIELD NOTES
  time:       "BMO" (before market open) | "AMC" (after market close) | "UNKNOWN"
  days_until: integer — computed from generated_at to earnings date
  signal:     always "CATALYST_UPCOMING" for all upcoming earnings
  est_eps:    float or null if not available
  est_revenue: integer (dollars) or null if not available

## SCRAPER STRUCTURE
```python
import yfinance as yf
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "earnings_latest.json"
WINDOW_DAYS = 14  # look ahead 2 weeks

def load_sp500_tickers() -> list[str]: ...        # reuse pattern from equities_scraper
def fetch_earnings_for_ticker(ticker: str) -> dict | None: ...
def scrape(*, window_days: int = WINDOW_DAYS) -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — yfinance + calendar parsing only
- Limit to S&P 500 universe (use equities_scraper SP500 CSV source)
- Add 0.1s sleep between ticker lookups to avoid Yahoo rate limits
- Use write_cache_json_pair for output (stable + timestamped)
- generated_at must be ISO UTC string
- If a ticker fetch fails: log warning, skip, continue — do not crash
- Filter: only include tickers with earnings within window_days from now

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile earnings_parser_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, record_count, upcoming list
  [ ] All items have ticker, date, days_until, signal = "CATALYST_UPCOMING"
  [ ] days_until >= 0 for all items (past earnings excluded)
  [ ] python -m pytest tests/test_earnings_parser.py -v passes
