# G1 — Lead Generation Scraper | Division: Business Growth & Ops

## IDENTITY
You find local business leads via Google Maps Places API for a given search
query and city. Flags businesses without a modern website as high-value
outreach targets. No LLM calls. Pure API fetch + classify.

## DEFINITION
  lead: a local business matching the search query
  has_modern_site: True if website is https:// and not a generic builder
  Signal:
    HOT_LEAD:  rating >= 4.5 AND review_count >= 50 AND has_modern_site=False
    WARM_LEAD: rating >= 4.0
    COLD_LEAD: else

## DATA SOURCES
  Google Maps Places Text Search API (requires GOOGLE_MAPS_KEY in .env):
    https://maps.googleapis.com/maps/api/place/textsearch/json?query={query}&key={key}
  Note: if GOOGLE_MAPS_KEY absent, return empty leads list (no error)

## OUTPUT FILE
  data_cache/leads_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "search_query": "plumbers near Austin TX",
  "record_count": 20,
  "leads": [
    {
      "business_name": "Austin Plumbing Co",
      "address": "123 Main St, Austin, TX",
      "phone": "+15125550100",
      "website": "",
      "category": "Plumber",
      "rating": 4.7,
      "review_count": 312,
      "has_modern_site": false,
      "signal": "HOT_LEAD"
    }
  ]
}
```

## SIGNAL LOGIC
  has_modern_site = website.startswith("https://") AND not generic_builder(website)
  generic_builders: ["wix.com", "wordpress.com", "squarespace.com", "weebly.com", "godaddy.com"]
  HOT_LEAD:  rating >= 4.5 AND review_count >= 50 AND has_modern_site=False
  WARM_LEAD: rating >= 4.0
  COLD_LEAD: else

## SCRAPER STRUCTURE
```python
import requests
import os
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "leads_latest.json"

PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
GENERIC_BUILDERS = ["wix.com", "wordpress.com", "squarespace.com", "weebly.com", "godaddy.com"]

def fetch_leads(query: str, api_key: str) -> list[dict]: ...
def classify_signal(lead: dict) -> str: ...
def has_modern_site(url: str) -> bool: ...
def scrape(query: str = "local businesses", city: str = "Austin TX") -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — API fetch + classify only
- If GOOGLE_MAPS_KEY not in env: return empty leads list, source="no_api_key"
- rating expressed as float (0.0–5.0)
- review_count expressed as integer
- has_modern_site expressed as bool
- generated_at must be ISO UTC string
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
  [ ] python -m py_compile lead_gen_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, leads list, record_count
  [ ] signal in {"HOT_LEAD", "WARM_LEAD", "COLD_LEAD"}
  [ ] python -m pytest tests/test_lead_gen.py -v passes
