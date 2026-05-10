# A4 — P2P Lending Bot | Division: Alternative Assets & Niche

## IDENTITY
You track peer-to-peer lending platform statistics — net annualized returns, default
rates, and loan volumes. You fetch public summary data from LendingClub and Prosper,
supplemented by hardcoded quarterly snapshots where login walls block full data access.
No LLM calls. Pure data fetch + signal classification.

## DEFINITION
  Coverage: major US P2P lending platforms (LendingClub, Prosper, plus hardcoded others).
  Signal: ATTRACTIVE / MODERATE / AVOID based on return and default rate.
  Output: data_cache/p2p_latest.json

## DATA SOURCES (with URLs)

### Primary — LendingClub Public Statistics:
  https://www.lendingclub.com/info/statistics.action
  Public page with aggregate loan performance statistics.
  Note: Full investor data requires login. Parse public summary section only.

### Secondary — Prosper Public Performance:
  https://www.prosper.com/invest/performance/
  Public performance data page. Parse seasoned return rates from public sections.
  Note: Full account data requires login. Use publicly visible aggregate metrics only.

### Hardcoded Quarterly Snapshot:
  Platforms that have closed to retail investors (e.g., Funding Circle US) are
  included as hardcoded CLOSED_TO_RETAIL records. Update quarterly.
  Status field indicates ACTIVE vs CLOSED_TO_RETAIL.

## OUTPUT FILE
  data_cache/p2p_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "lendingclub_prosper_public",
  "record_count": 4,
  "platforms": [
    {
      "name": "LendingClub",
      "avg_return_pct": 5.8,
      "default_rate_12m_pct": 4.2,
      "active_loans_count": 180000,
      "min_investment": 1000,
      "accredited_only": false,
      "status": "ACTIVE",
      "signal": "MODERATE"
    }
  ]
}
```

## SIGNAL LOGIC
  signal classification (applied in order — first match wins):
    "ATTRACTIVE" — avg_return_pct >= 8.0 AND default_rate_12m_pct <= 5.0
    "MODERATE"   — avg_return_pct >= 5.0
    "AVOID"      — default_rate_12m_pct > 10.0  (check before MODERATE)

  Full order check:
    1. If default_rate_12m_pct > 10.0  → "AVOID"
    2. Elif avg_return_pct >= 8.0 AND default_rate_12m_pct <= 5.0 → "ATTRACTIVE"
    3. Elif avg_return_pct >= 5.0 → "MODERATE"
    4. Else → "AVOID"

  avg_return_pct = net annualized return after defaults and fees
  default_rate_12m_pct = trailing 12-month default rate as percentage

## PLATFORM UNIVERSE (hardcoded baseline — update from public pages when available)
  [
    {"name": "LendingClub",     "min_investment": 1000,  "accredited_only": False, "status": "ACTIVE"},
    {"name": "Prosper",         "min_investment": 25,    "accredited_only": False, "status": "ACTIVE"},
    {"name": "Funding Circle",  "min_investment": 50000, "accredited_only": True,  "status": "CLOSED_TO_RETAIL"},
    {"name": "Upstart",         "min_investment": 100,   "accredited_only": True,  "status": "ACTIVE"},
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
OUTPUT_STABLE_NAME = "p2p_latest.json"

LENDINGCLUB_URL = "https://www.lendingclub.com/info/statistics.action"
PROSPER_URL = "https://www.prosper.com/invest/performance/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

PLATFORM_UNIVERSE = [
    {"name": "LendingClub",    "min_investment": 1000,  "accredited_only": False, "status": "ACTIVE"},
    {"name": "Prosper",        "min_investment": 25,    "accredited_only": False, "status": "ACTIVE"},
    {"name": "Funding Circle", "min_investment": 50000, "accredited_only": True,  "status": "CLOSED_TO_RETAIL"},
    {"name": "Upstart",        "min_investment": 100,   "accredited_only": True,  "status": "ACTIVE"},
]

# Hardcoded quarterly snapshot — used as fallback when live page parsing fails
QUARTERLY_SNAPSHOT = {
    "LendingClub": {"avg_return_pct": 5.8, "default_rate_12m_pct": 4.2, "active_loans_count": 180000},
    "Prosper":     {"avg_return_pct": 5.3, "default_rate_12m_pct": 5.1, "active_loans_count": 90000},
    "Funding Circle": {"avg_return_pct": 0.0, "default_rate_12m_pct": 0.0, "active_loans_count": 0},
    "Upstart":     {"avg_return_pct": 8.2, "default_rate_12m_pct": 6.8, "active_loans_count": 45000},
}

def fetch_lendingclub_stats() -> dict: ...
    # GET LENDINGCLUB_URL, parse public summary section
    # Return dict with avg_return_pct, default_rate_12m_pct, active_loans_count
    # On failure: return QUARTERLY_SNAPSHOT["LendingClub"]

def fetch_prosper_stats() -> dict: ...
    # GET PROSPER_URL, parse public performance section
    # Return dict with avg_return_pct, default_rate_12m_pct, active_loans_count
    # On failure: return QUARTERLY_SNAPSHOT["Prosper"]

def classify_signal(avg_return: float, default_rate: float) -> str: ...
    # Apply SIGNAL LOGIC in correct priority order

def build_platform_record(platform: dict, stats: dict) -> dict: ...
    # Merge platform definition with fetched stats + signal

def scrape() -> dict: ...
    # Build records for all platforms, return payload

def write_outputs(payload: dict) -> tuple[Path, Path]: ...
    # Call write_cache_json_pair(DATA_CACHE_DIR, OUTPUT_STABLE_NAME, payload)

def main(argv=None) -> int: ...
    # payload = scrape(); write_outputs(payload); return 0
```

## RULES
- No LLM calls — HTML parsing and arithmetic only
- avg_return_pct expressed as float rounded to 1 decimal place
- default_rate_12m_pct expressed as float rounded to 1 decimal place
- active_loans_count expressed as integer
- min_investment expressed as integer USD
- accredited_only expressed as boolean
- status must be one of: ACTIVE, CLOSED_TO_RETAIL
- signal must be one of: ATTRACTIVE, MODERATE, AVOID
- generated_at must be ISO UTC string (datetime.utcnow().isoformat() + "Z")
- If live fetch fails: use QUARTERLY_SNAPSHOT values and log warning
- 1.0s sleep between platform requests
- Use write_cache_json_pair for output
- record_count must equal len(platforms)

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile p2p_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, record_count, platforms list
  [ ] All platforms have name, avg_return_pct, default_rate_12m_pct, active_loans_count, min_investment, accredited_only, status, signal
  [ ] signal is one of: ATTRACTIVE, MODERATE, AVOID
  [ ] status is one of: ACTIVE, CLOSED_TO_RETAIL
  [ ] record_count == 4
  [ ] python -m pytest tests/test_p2p_lending.py -v passes
