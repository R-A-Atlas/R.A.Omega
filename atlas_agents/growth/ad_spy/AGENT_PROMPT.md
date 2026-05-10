# G3 — Competitor Ad Spy | Division: Business Growth & Ops

## IDENTITY
You search the Meta Ad Library for active competitor ads by keyword.
Surfaces spend ranges, impression ranges, and ad copy previews.
Identifies heavy spenders in any niche. No LLM calls. Scrape + classify.

## DEFINITION
  Meta Ad Library: public database of all active Facebook/Instagram ads
  spend_range: estimated monthly spend bucket
  Signal:
    HEAVY_SPENDER: spend_range includes "$100,000+"
    ACTIVE: status == "ACTIVE"
    PAUSED: status == "PAUSED"

## DATA SOURCES
  Meta Ad Library public search (no auth required for basic access):
    https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&q={keyword}
  Meta Ad Library API (optional, requires META_ACCESS_TOKEN in .env):
    https://graph.facebook.com/v19.0/ads_archive?search_terms={keyword}&ad_reached_countries=US&access_token={token}

## OUTPUT FILE
  data_cache/competitor_ads_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "search_keyword": "financial planning",
  "source": "meta_ad_library",
  "record_count": 15,
  "ads": [
    {
      "page_name": "WealthFront",
      "ad_text_preview": "Start investing with just $500...",
      "spend_range": "$10,000 - $99,999",
      "impressions_range": "100K - 499K",
      "platforms": ["Facebook", "Instagram"],
      "started_date": "2026-04-01",
      "status": "ACTIVE",
      "signal": "ACTIVE"
    }
  ]
}
```

## SIGNAL LOGIC
  "$100,000+" in spend_range → signal = "HEAVY_SPENDER"
  status == "ACTIVE"         → signal = "ACTIVE"
  status == "PAUSED"         → signal = "PAUSED"

## SCRAPER STRUCTURE
```python
import requests
import os
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "competitor_ads_latest.json"

META_AD_LIBRARY_URL = "https://graph.facebook.com/v19.0/ads_archive"

def fetch_ads(keyword: str, token: str) -> list[dict]: ...
def classify_signal(ad: dict) -> str: ...
def scrape(keyword: str = "financial planning") -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — API fetch + classify only
- If META_ACCESS_TOKEN missing: return empty ads list, source="no_token"
- spend_range must be one of the Meta standard buckets
- status expressed as string: "ACTIVE" or "PAUSED"
- generated_at must be ISO UTC string
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
  [ ] python -m py_compile ad_spy_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, ads list, record_count
  [ ] signal in {"HEAVY_SPENDER", "ACTIVE", "PAUSED"}
  [ ] python -m pytest tests/test_ad_spy.py -v passes
