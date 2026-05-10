# G10 — ROAS Optimizer | Division: Business Growth & Ops

## IDENTITY
You pull campaign performance from Meta and Google Ads APIs, computes ROAS
(Return on Ad Spend), and recommends scale/optimize/pause per campaign.
No LLM calls. API fetch + arithmetic.

## DEFINITION
  ROAS = revenue_usd / spend_usd
  CPA  = spend_usd / conversions
  Signal:
    PROFITABLE:  roas >= 2.0
    BREAK_EVEN:  0.8 <= roas < 2.0
    LOSING:      roas < 0.8
  Recommendation:
    SCALE:    roas >= 3.0
    OPTIMIZE: roas >= 1.5
    MONITOR:  roas >= 0.8
    PAUSE:    roas < 0.8

## DATA SOURCES
  Meta Marketing API (requires ATLAS_META_TOKEN in .env):
    https://graph.facebook.com/v19.0/act_{account_id}/campaigns?fields=name,status,insights{spend,revenue,impressions}&access_token={token}
  Google Ads API (requires ATLAS_GOOGLE_ADS_TOKEN in .env):
    google-ads Python library — campaign performance report
  Note: if tokens absent, return empty campaigns list with source="no_credentials"

## OUTPUT FILE
  data_cache/roas_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "meta_google_ads",
  "record_count": 4,
  "campaigns": [
    {
      "name": "Finance App - Prospecting",
      "platform": "Meta",
      "spend_usd": 4820.00,
      "revenue_usd": 18640.00,
      "roas": 3.87,
      "cpa_usd": 24.10,
      "status": "ACTIVE",
      "signal": "PROFITABLE",
      "recommendation": "SCALE"
    }
  ]
}
```

## ROAS LOGIC
  roas = round(revenue_usd / spend_usd, 2) if spend_usd > 0 else 0
  signal:
    roas >= 2.0 → "PROFITABLE"
    roas >= 0.8 → "BREAK_EVEN"
    roas < 0.8  → "LOSING"
  recommendation:
    roas >= 3.0 → "SCALE"
    roas >= 1.5 → "OPTIMIZE"
    roas >= 0.8 → "MONITOR"
    roas < 0.8  → "PAUSE"

## SCRAPER STRUCTURE
```python
import requests
import os
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "roas_latest.json"

def fetch_meta_campaigns(token: str, account_id: str) -> list[dict]: ...
def fetch_google_campaigns(token: str) -> list[dict]: ...
def compute_roas(spend: float, revenue: float) -> float: ...
def classify_signal(roas: float) -> str: ...
def classify_recommendation(roas: float) -> str: ...
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — API fetch + arithmetic only
- roas = round(revenue / spend, 2) if spend > 0 else 0.0
- spend_usd, revenue_usd expressed as float USD
- status: "ACTIVE", "PAUSED", or "LEARNING"
- signal: "PROFITABLE", "BREAK_EVEN", or "LOSING"
- recommendation: "SCALE", "OPTIMIZE", "MONITOR", or "PAUSE"
- If credentials absent: return empty campaigns list
- generated_at must be ISO UTC string
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
  [ ] python -m py_compile roas_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, campaigns list, record_count
  [ ] roas >= 0 for all campaigns
  [ ] signal in {"PROFITABLE", "BREAK_EVEN", "LOSING"}
  [ ] recommendation in {"SCALE", "OPTIMIZE", "MONITOR", "PAUSE"}
  [ ] python -m pytest tests/test_roas.py -v passes
