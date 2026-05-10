# T9 — Penny Stock Screener | Division: Trading Desk

## IDENTITY
You surface high-volume micro-cap stocks under $10 with unusual volume spikes.
Penny stocks with 5x+ average volume are often in play — early detection before
Reddit/StockTwits picks them up is the edge. No LLM calls. Pure screening.

## DEFINITION
  Penny stock: price < $10.00 AND market_cap < $300M
  In-play signal: volume >= 3x the 30-day average daily volume

## DATA SOURCES (free, no auth)

### Primary — Yahoo Finance screener via yfinance:
  Use yf.screen() with predefined screeners OR build a custom filter.
  Most-active screener filtered post-fetch to price < $10:
    yf.screen("most_actives")   → filter results where regularMarketPrice < 10

### Secondary — Finviz free screener (scrape public page, no auth):
  URL: https://finviz.com/screener.ashx?v=111&f=cap_micro,cap_small,sh_price_u10,sh_relvol_o3
  Parse HTML table with BeautifulSoup. Rate limit: 1 req/10s.

### Tertiary — yfinance direct ticker scan:
  Scan a universe of known micro-caps (OTC, Russell 2000 tail) via yf.Tickers()

## OUTPUT FILE
  data_cache/penny_stocks_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "yfinance_screener",
  "record_count": 25,
  "stocks": [
    {
      "ticker": "SOUN",
      "price": 8.45,
      "volume": 45200000,
      "avg_volume_30d": 8900000,
      "volume_ratio": 5.08,
      "market_cap": 2100000000,
      "change_pct": 18.4,
      "sector": "Technology",
      "signal": "HIGH_VOLUME_PENNY"
    }
  ]
}
```

## SIGNAL LOGIC
  volume_ratio = volume / avg_volume_30d
  volume_ratio >= 5.0 AND price < $10  → "HIGH_VOLUME_PENNY"
  volume_ratio >= 3.0 AND price < $10  → "ELEVATED_VOLUME_PENNY"
  volume_ratio < 3.0                   → exclude from output

## SCRAPER STRUCTURE
```python
import yfinance as yf
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "penny_stocks_latest.json"

MAX_PRICE = 10.0
MAX_MARKET_CAP = 300_000_000
MIN_VOLUME_RATIO = 3.0

def fetch_most_active_screener() -> list[dict]: ...   # yfinance most_actives
def filter_penny_criteria(stocks: list) -> list: ...  # price < 10, volume_ratio >= 3x
def compute_volume_ratio(stock: dict) -> float: ...
def classify_signal(ratio: float) -> str: ...
def scrape(*, top_n: int = 25) -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — screener + filter math only
- price < $10.00 is a hard filter (not a soft preference)
- Sort by volume_ratio descending, return top_n
- Add 0.1s sleep between any per-ticker lookups
- Use write_cache_json_pair for output
- generated_at must be ISO UTC string
- Exclude ETFs and funds (check quoteType != "ETF")
- If screener returns empty: log warning, return empty stocks list

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile penny_screener_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, stocks list, record_count
  [ ] All stocks have price < 10.0
  [ ] All stocks have volume_ratio >= 3.0
  [ ] signal only: HIGH_VOLUME_PENNY or ELEVATED_VOLUME_PENNY
  [ ] python -m pytest tests/test_penny_screener.py -v passes
