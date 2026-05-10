# G4 — SEO Keyword Tracker | Division: Business Growth & Ops

## IDENTITY
You track Google Trends interest scores for finance-related keywords via pytrends.
Identifies rising search demand for content opportunities. No LLM calls.
pytrends fetch + classify.

## DEFINITION
  trend_score: 0–100 Google Trends relative interest (past 3 months)
  trend_direction:
    BREAKOUT:  score == 100 or marked as breakout by Google
    RISING:    score >= 70
    STABLE:    40–69
    DECLINING: < 40
  competition_level: hardcoded by keyword category

## DATA SOURCES
  pytrends Google Trends (no auth, no API key):
    from pytrends.request import TrendReq
    pt = TrendReq(hl="en-US", tz=360)
    pt.build_payload(kw_list=[keyword], timeframe="today 3-m")
    df = pt.interest_over_time()

## OUTPUT FILE
  data_cache/seo_keywords_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "google_trends_pytrends",
  "record_count": 8,
  "keywords": [
    {
      "term": "financial planning",
      "trend_score": 72,
      "trend_direction": "RISING",
      "volume_estimate": "HIGH",
      "competition_level": "HIGH",
      "rising_queries": ["financial planning app", "financial planning for beginners"]
    }
  ]
}
```

## DEFAULT KEYWORDS
  ["financial planning", "stock analysis", "real estate investing",
   "crypto portfolio", "mortgage rates", "ETF investing",
   "options trading", "REIT dividend"]

## TREND DIRECTION LOGIC
  score == 100 or breakout → "BREAKOUT"
  score >= 70              → "RISING"
  score >= 40              → "STABLE"
  score < 40               → "DECLINING"

## COMPETITION LEVEL (hardcoded by category)
  HIGH:   finance, insurance, legal, real estate keywords
  MEDIUM: general business, investing terms
  LOW:    niche/long-tail terms

## SCRAPER STRUCTURE
```python
from pytrends.request import TrendReq
import time
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "seo_keywords_latest.json"

DEFAULT_KEYWORDS = [
    "financial planning", "stock analysis", "real estate investing",
    "crypto portfolio", "mortgage rates", "ETF investing",
    "options trading", "REIT dividend",
]

def fetch_trend_score(keyword: str, pt: TrendReq) -> dict: ...
def classify_direction(score: int) -> str: ...
def classify_competition(keyword: str) -> str: ...
def scrape(keywords: list[str] = None) -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — pytrends fetch + classify only
- trend_score expressed as integer 0–100
- Sleep 1s between pytrends requests (rate limit)
- generated_at must be ISO UTC string
- Use write_cache_json_pair for output
- If pytrends fails: log warning, return empty keywords list

## VALIDATION CHECKLIST
  [ ] python -m py_compile seo_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, keywords list, record_count
  [ ] 0 <= trend_score <= 100
  [ ] trend_direction in {"BREAKOUT", "RISING", "STABLE", "DECLINING"}
  [ ] python -m pytest tests/test_seo.py -v passes
