# G8 — Engagement Rater | Division: Business Growth & Ops

## IDENTITY
You measure social media engagement rates for public influencer profiles.
Engagement rate is the primary metric for identifying authentic audiences
vs inflated follower counts. No LLM calls. Public profile scrape + arithmetic.

## DEFINITION
  engagement_rate = (avg_likes + avg_comments) / followers * 100
  tier:
    NANO:  followers < 10,000
    MICRO: 10,000 – 100,000
    MID:   100,000 – 1,000,000
    MACRO: > 1,000,000
  Signal:
    HIGH_ENGAGEMENT: engagement_rate >= 3%
    AVERAGE:         1% – 3%
    LOW:             < 1%

## DATA SOURCES
  Instagram public data (no auth for public profiles):
    Scrape https://www.instagram.com/{handle}/ public HTML
    Parse follower count, recent post likes from JSON-LD or meta tags
  Note: Instagram heavily rate-limits scraping — 5s sleep between requests

## OUTPUT FILE
  data_cache/engagement_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "instagram_public",
  "record_count": 5,
  "profiles": [
    {
      "handle": "financialpanther",
      "platform": "Instagram",
      "followers": 48200,
      "avg_likes": 1840,
      "avg_comments": 62,
      "engagement_rate": 3.94,
      "tier": "MICRO",
      "niche": "Personal Finance",
      "signal": "HIGH_ENGAGEMENT"
    }
  ]
}
```

## ENGAGEMENT FORMULA
  engagement_rate = round((avg_likes + avg_comments) / followers * 100, 2)

## TIER LOGIC
  followers < 10000           → "NANO"
  followers < 100000          → "MICRO"
  followers < 1000000         → "MID"
  followers >= 1000000        → "MACRO"

## SCRAPER STRUCTURE
```python
import requests
import time
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "engagement_latest.json"

def fetch_profile(handle: str, platform: str = "Instagram") -> dict: ...
def compute_engagement_rate(followers: int, avg_likes: float, avg_comments: float) -> float: ...
def classify_tier(followers: int) -> str: ...
def classify_signal(rate: float) -> str: ...
def scrape(handles: list[str] = None) -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — scrape + arithmetic only
- engagement_rate expressed as float percentage (e.g., 3.94 not 0.0394)
- Sleep 5s between profile requests (Instagram rate limit)
- tier must be exactly: "NANO", "MICRO", "MID", or "MACRO"
- signal must be exactly: "HIGH_ENGAGEMENT", "AVERAGE", or "LOW"
- generated_at must be ISO UTC string
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
  [ ] python -m py_compile engagement_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, profiles list, record_count
  [ ] engagement_rate = round((avg_likes + avg_comments) / followers * 100, 2)
  [ ] tier in {"NANO", "MICRO", "MID", "MACRO"}
  [ ] signal in {"HIGH_ENGAGEMENT", "AVERAGE", "LOW"}
  [ ] python -m pytest tests/test_engagement.py -v passes
