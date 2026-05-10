# G9 — Review Aggregator | Division: Business Growth & Ops

## IDENTITY
You aggregate Google and Yelp reviews for local businesses, surface top
complaints and praise themes, and compute a sentiment trend signal.
No LLM calls. API fetch + keyword theme extraction.

## DEFINITION
  overall_rating: average star rating (1.0–5.0)
  response_rate_pct: % of reviews the business has responded to
  sentiment_trend: direction of recent (last 30 days) vs historical ratings
  Signal:
    EXCELLENT: rating >= 4.5 AND response_rate_pct >= 50
    GOOD:      rating >= 4.0
    AT_RISK:   rating < 4.0

## DATA SOURCES
  Google Places API (requires GOOGLE_MAPS_KEY in .env):
    https://maps.googleapis.com/maps/api/place/details/json?place_id={id}&fields=rating,user_ratings_total,reviews&key={key}
  Yelp Fusion API (requires YELP_API_KEY in .env):
    https://api.yelp.com/v3/businesses/{id}/reviews
  Note: if keys absent, return empty businesses list

## OUTPUT FILE
  data_cache/reviews_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "google_places_yelp",
  "record_count": 3,
  "businesses": [
    {
      "name": "Austin Plumbing Co",
      "platform": "Google",
      "overall_rating": 4.6,
      "review_count": 312,
      "top_complaints": ["slow response time", "pricing unclear", "parking difficult"],
      "top_praise": ["great work quality", "professional staff", "fast service"],
      "sentiment_trend": "IMPROVING",
      "response_rate_pct": 72,
      "signal": "EXCELLENT"
    }
  ]
}
```

## SENTIMENT TREND LOGIC
  recent_avg = avg rating of reviews from last 30 days
  historical_avg = overall_rating
  recent_avg > historical_avg + 0.2  → "IMPROVING"
  recent_avg < historical_avg - 0.2  → "DECLINING"
  else                               → "STABLE"

## SCRAPER STRUCTURE
```python
import requests
import os
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "reviews_latest.json"

def fetch_google_reviews(place_id: str, api_key: str) -> dict: ...
def fetch_yelp_reviews(business_id: str, api_key: str) -> dict: ...
def extract_themes(reviews: list, sentiment: str) -> list[str]: ...  # top 3 themes
def classify_sentiment_trend(recent: float, historical: float) -> str: ...
def classify_signal(rating: float, response_rate: float) -> str: ...
def scrape(business_ids: list[dict] = None) -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — keyword extraction + arithmetic only
- overall_rating expressed as float 1.0–5.0
- response_rate_pct expressed as integer 0–100
- top_complaints and top_praise: exactly 3 strings each
- sentiment_trend: exactly "IMPROVING", "STABLE", or "DECLINING"
- signal: exactly "EXCELLENT", "GOOD", or "AT_RISK"
- generated_at must be ISO UTC string
- If API keys absent: return empty businesses list
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
  [ ] python -m py_compile reviews_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, businesses list, record_count
  [ ] 1.0 <= overall_rating <= 5.0
  [ ] sentiment_trend in {"IMPROVING", "STABLE", "DECLINING"}
  [ ] signal in {"EXCELLENT", "GOOD", "AT_RISK"}
  [ ] python -m pytest tests/test_reviews.py -v passes
