# T3 — Options Flow Monitor | Division: Trading Desk

## IDENTITY
You track unusual options activity from public data sources.
You flag contracts where volume/open-interest ratio exceeds 3x —
a signal of institutional positioning. No LLM calls. Pure scraping.

## DATA SOURCES (priority order)
1. CBOE market statistics: https://www.cboe.com/us/options/market_statistics/
2. Barchart unusual options activity (public screener, no auth required)
3. Unusual Whales free-tier endpoints (check current availability)

## OUTPUT FILE
  data_cache/options_flow_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "cboe_public",
  "record_count": 25,
  "unusual_activity": [
    {
      "ticker": "NVDA",
      "expiry": "2026-06-20",
      "strike": 150,
      "type": "CALL",
      "volume": 50000,
      "open_interest": 10000,
      "volume_oi_ratio": 5.0,
      "signal": "BULLISH_UNUSUAL"
    }
  ]
}
```

## SIGNAL LOGIC
  volume_oi_ratio = volume / open_interest
  ratio > 3.0 AND type == "CALL"  → signal = "BULLISH_UNUSUAL"
  ratio > 3.0 AND type == "PUT"   → signal = "BEARISH_UNUSUAL"
  ratio <= 3.0                    → signal = "NORMAL" (exclude from output)

## SCRAPER STRUCTURE (follow crypto_scraper.py pattern)
```python
from atlas_core.utils.agent_utils import requests_get_json, write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "options_flow_latest.json"

def fetch_cboe_unusual() -> list[dict]: ...
def score_unusual_activity(raw: list[dict]) -> list[dict]: ...
def scrape(*, top_n: int = 25) -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — pure scraping + ratio math
- No hardcoded API keys (CBOE public data requires no auth)
- Use requests_get_json for all HTTP (handles 429, retry, timeout)
- Use write_cache_json_pair for output (stable + timestamped)
- Exit 0 on success, non-zero on failure
- generated_at must be ISO UTC string

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile options_flow_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, record_count, unusual_activity
  [ ] All items in unusual_activity have volume_oi_ratio > 3.0
  [ ] write_outputs() creates data_cache/options_flow_latest.json
  [ ] python -m pytest tests/test_options_flow.py -v passes
