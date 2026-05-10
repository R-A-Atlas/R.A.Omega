# T8 — Dark Pool Monitor | Division: Trading Desk

## IDENTITY
You track off-exchange (dark pool) block trade volume. When institutions
quietly accumulate in dark pools before announcing, the ratio of dark pool
volume to total volume spikes. You surface those spikes. No LLM calls.

## DATA SOURCES (free, public)

### Primary — FINRA ATS (Alternative Trading System) public data:
  FINRA publishes weekly ATS (dark pool) volume by security:
  https://www.finra.org/finra-data/browse-catalog/short-sale-volume-statistics
  Download URL pattern (CSV, updated weekly):
  https://cdn.finra.org/equity/regsho/weekly/CNMSshvol<YYYYMMDD>.txt

### Secondary — FINRA OTC Transparency (daily consolidated):
  https://www.finra.org/sites/default/files/OTC_Transparency_Data/

### Tertiary — Unusual Whales dark pool endpoint (check free tier availability):
  https://unusualwhales.com/api/darkpool/recent  (may require API key)

## OUTPUT FILE
  data_cache/dark_pool_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "finra_ats",
  "week_of": "2026-05-05",
  "record_count": 50,
  "signals": [
    {
      "ticker": "NVDA",
      "dark_pool_volume": 12500000,
      "total_volume": 45000000,
      "dark_pool_ratio": 0.278,
      "date": "2026-05-08",
      "signal": "ELEVATED_DARK_POOL"
    }
  ]
}
```

## SIGNAL LOGIC
  dark_pool_ratio = dark_pool_volume / total_volume
  ratio >= 0.45   → "HIGH_DARK_POOL"       (institutions heavily active)
  ratio >= 0.30   → "ELEVATED_DARK_POOL"   (above average activity)
  ratio < 0.30    → "NORMAL" (exclude from output — only flag elevated/high)

Focus on S&P 500 universe only. Sort by dark_pool_ratio descending. Top 50.

## SCRAPER STRUCTURE
```python
import io
import csv
import requests
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "dark_pool_latest.json"

FINRA_BASE = "https://cdn.finra.org/equity/regsho/weekly/"

def get_latest_finra_url() -> str: ...         # compute most recent Monday's date
def fetch_finra_csv(url: str) -> list[dict]: ... # download + parse pipe-delimited CSV
def load_sp500_tickers() -> set[str]: ...       # filter to S&P 500 universe only
def compute_ratio(row: dict) -> float: ...
def classify_signal(ratio: float) -> str: ...
def scrape(*, top_n: int = 50) -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## FINRA CSV FORMAT
  FINRA weekly short/dark pool file is pipe-delimited:
  Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
  Use ShortVolume as dark pool proxy (FINRA off-exchange short sale volume)
  Filter Market == "FINRA" rows only

## RULES
- No LLM calls — CSV parsing + ratio math only
- No auth required — FINRA data is public
- Only include ELEVATED_DARK_POOL and HIGH_DARK_POOL signals in output
- Filter to S&P 500 universe (load from same CSV as equities_scraper)
- Use write_cache_json_pair for output
- generated_at must be ISO UTC string
- If FINRA file unavailable: return empty signals list with warning key

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile dark_pool_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, signals list, record_count
  [ ] All signals have dark_pool_ratio >= 0.30
  [ ] signal only: ELEVATED_DARK_POOL or HIGH_DARK_POOL
  [ ] python -m pytest tests/test_dark_pool.py -v passes
