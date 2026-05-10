# R5 — Zoning & Permit Watcher | Division: Real Estate & Property

## IDENTITY
You track building permit activity across US cities as a leading indicator
of housing supply and construction momentum. Rising permits signal future
inventory growth; falling permits signal supply constraints ahead.
Primary source: US Census Bureau Building Permits Survey (free API).
No LLM calls. Pure data fetch + trend classification.

## DEFINITION
  permit_type: Residential (1-unit, 2-4 unit, 5+ unit), Commercial
  count: number of permits issued in the most recent month
  yoy_change: percentage change vs same month prior year
  trend_signal: direction of permit activity

  Trend classification:
    SURGING:    yoy_change >= +20%
    GROWING:    yoy_change >= +5%
    STABLE:     -5% <= yoy_change < +5%
    DECLINING:  yoy_change < -5%
    COLLAPSING: yoy_change <= -20%

## DATA SOURCES (free, no auth)

### Primary — US Census Bureau Building Permits Survey API:
  https://api.census.gov/data/timeseries/eits/bps
  Endpoint: Building Permits Survey (BPS) — monthly series
  No API key required for basic access (key optional for higher rate limits)
  Key parameters: get=cell_value,time_slot_id&for=us:1&time=2026-03

### Secondary — Census Building Permits endpoint (simpler):
  https://www.census.gov/construction/bps/txt/u2026a.txt
  Annual permit data by metro area — fixed-width text format

### Tertiary — HUD SOCDS Building Permits Database:
  https://socds.huduser.gov/permits/output.odb
  MSA-level monthly permits — POST request, returns HTML table
  Parse with BeautifulSoup

## OUTPUT FILE
  data_cache/zoning_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "census_bps",
  "period": "2026-03",
  "record_count": 12,
  "permits": [
    {
      "city": "National",
      "permit_type": "1-Unit Residential",
      "count": 82400,
      "yoy_change": -8.3,
      "trend_signal": "DECLINING"
    },
    {
      "city": "National",
      "permit_type": "5+ Unit Residential",
      "count": 41200,
      "yoy_change": 22.1,
      "trend_signal": "SURGING"
    }
  ]
}
```

## TREND SIGNAL LOGIC
  yoy_change >= 20.0   → "SURGING"
  yoy_change >= 5.0    → "GROWING"
  yoy_change >= -5.0   → "STABLE"
  yoy_change >= -20.0  → "DECLINING"
  yoy_change < -20.0   → "COLLAPSING"

## SCRAPER STRUCTURE
```python
import requests
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "zoning_latest.json"

CENSUS_BPS_URL = "https://api.census.gov/data/timeseries/eits/bps"

PERMIT_TYPES = [
    "1-Unit Residential",
    "2-4 Unit Residential",
    "5+ Unit Residential",
    "Total Residential",
]

def fetch_census_permits(period: str) -> list[dict]: ...   # Census BPS API
def fetch_prior_year(permit_type: str, period: str) -> int: ...
def compute_yoy(current: int, prior: int) -> float: ...
def classify_trend(yoy_change: float) -> str: ...
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — fetch + arithmetic only
- yoy_change expressed as float percentage (e.g., -8.3 = -8.3%)
- count expressed as integer (number of permits)
- trend_signal must be exactly: "SURGING", "GROWING", "STABLE", "DECLINING", or "COLLAPSING"
- period expressed as "YYYY-MM" string
- generated_at must be ISO UTC string
- If Census API unavailable: log warning, return empty permits list
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile zoning_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, permits list, record_count
  [ ] All permits have city, permit_type, count, yoy_change, trend_signal
  [ ] trend_signal in {"SURGING", "GROWING", "STABLE", "DECLINING", "COLLAPSING"}
  [ ] python -m pytest tests/test_zoning.py -v passes
