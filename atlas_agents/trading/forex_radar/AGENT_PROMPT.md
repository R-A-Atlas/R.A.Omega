# T6 — Forex Radar | Division: Trading Desk

## IDENTITY
You track major currency pair rates and flag volatility signals.
Forex moves precede equity market moves. DXY strength hits commodities and
emerging markets. EUR/USD drives European stock sentiment. No LLM calls.

## DATA SOURCES (free, no auth)
Primary — Frankfurter API (ECB data, always free, no key required):
  https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,JPY,CAD,CHF,AUD,CNY,MXN
  https://api.frankfurter.app/<YESTERDAY>?from=USD&to=EUR,GBP,JPY,CAD,CHF,AUD,CNY,MXN

Secondary — ExchangeRate-API free tier (1500 req/month, no key for basic):
  https://open.er-api.com/v6/latest/USD

## CURRENCY PAIRS TO TRACK
  USD/EUR, USD/GBP, USD/JPY, USD/CAD, USD/CHF, USD/AUD, USD/CNY, USD/MXN
  DXY proxy: weighted basket of above (EUR 57.6%, JPY 13.6%, GBP 11.9%, CAD 9.1%, CHF 3.6%, SEK 4.2%)

## OUTPUT FILE
  data_cache/forex_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "frankfurter_ecb",
  "base": "USD",
  "record_count": 8,
  "dxy_proxy": 104.2,
  "pairs": [
    {
      "pair": "USD/EUR",
      "rate": 0.9234,
      "prev_rate": 0.9201,
      "change_24h": 0.36,
      "change_24h_pct": 0.36,
      "volatility_signal": "STABLE"
    }
  ]
}
```

## VOLATILITY SIGNAL LOGIC
  abs(change_24h_pct) >= 1.0   → "HIGH_VOLATILITY"
  abs(change_24h_pct) >= 0.5   → "ELEVATED"
  abs(change_24h_pct) < 0.5    → "STABLE"

## SCRAPER STRUCTURE
```python
from atlas_core.utils.agent_utils import requests_get_json, write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "forex_latest.json"

PAIRS = ["EUR", "GBP", "JPY", "CAD", "CHF", "AUD", "CNY", "MXN"]

def fetch_current_rates() -> dict: ...     # frankfurter /latest
def fetch_previous_rates() -> dict: ...    # frankfurter /yesterday
def compute_change(curr, prev) -> float: ...
def classify_volatility(change_pct: float) -> str: ...
def compute_dxy_proxy(rates: dict) -> float: ...
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — pure rate math
- No auth required — Frankfurter is public ECB data
- Always fetch both current AND previous day rates to compute 24h change
- Use requests_get_json for all HTTP
- Use write_cache_json_pair for output
- generated_at must be ISO UTC string
- If previous day fetch fails: set change_24h = null, signal = "UNKNOWN"

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile forex_radar_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, pairs list, dxy_proxy
  [ ] All pairs have pair, rate, change_24h_pct, volatility_signal
  [ ] volatility_signal only: STABLE / ELEVATED / HIGH_VOLATILITY / UNKNOWN
  [ ] python -m pytest tests/test_forex_radar.py -v passes
