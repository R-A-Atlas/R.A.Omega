# G5 — Social Sentiment Analyzer | Division: Business Growth & Ops

## IDENTITY
You monitor Reddit finance subreddits for topic mentions and sentiment.
Computes sentiment_score from upvote ratio and keyword matching.
Identifies trending topics before mainstream media. No LLM calls.
Reddit JSON API + keyword scoring.

## DEFINITION
  sentiment_score: -1.0 to 1.0 (positive=bullish, negative=bearish)
  computed from: upvote_ratio, bullish/bearish keyword presence
  trending: True if topic mentioned in >= 3 top posts
  Signal:
    BULLISH:  sentiment_score >= 0.3
    NEUTRAL: -0.3 to 0.3
    BEARISH:  sentiment_score <= -0.3

## DATA SOURCES
  Reddit public JSON API (no auth for public posts):
    https://www.reddit.com/r/{subreddit}/hot.json?limit=25
  Subreddits: r/investing, r/wallstreetbets, r/stocks, r/personalfinance, r/realestateinvesting
  User-Agent header required: "ATLAS/1.0 (financial research bot)"

## OUTPUT FILE
  data_cache/sentiment_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "reddit_public_api",
  "record_count": 10,
  "topics": [
    {
      "topic": "NVDA",
      "subreddit": "wallstreetbets",
      "mentions": 14,
      "sentiment_score": 0.62,
      "trending": true,
      "signal": "BULLISH",
      "top_post_title": "NVDA calls printing again",
      "top_post_upvotes": 4820
    }
  ]
}
```

## SENTIMENT SCORE FORMULA
  upvote_ratio: Reddit field (0.0–1.0)
  bullish_keywords: ["bull", "buy", "calls", "moon", "rocket", "long", "breakout"]
  bearish_keywords: ["bear", "sell", "puts", "crash", "short", "dump", "red"]
  keyword_score = (bullish_matches - bearish_matches) / max(total_keywords, 1)
  sentiment_score = round((upvote_ratio - 0.5) * 2 * 0.5 + keyword_score * 0.5, 2)
  Clamp to [-1.0, 1.0]

## SCRAPER STRUCTURE
```python
import requests
import time
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "sentiment_latest.json"

SUBREDDITS = ["investing", "wallstreetbets", "stocks", "personalfinance", "realestateinvesting"]
REDDIT_HEADERS = {"User-Agent": "ATLAS/1.0 (financial research bot)"}

def fetch_subreddit_posts(subreddit: str) -> list[dict]: ...
def compute_sentiment(posts: list) -> float: ...
def extract_topics(posts: list, min_mentions: int = 3) -> list[dict]: ...
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — keyword matching + arithmetic only
- sentiment_score clamped to [-1.0, 1.0]
- Sleep 2s between subreddit requests (Reddit rate limit)
- User-Agent header required
- generated_at must be ISO UTC string
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
  [ ] python -m py_compile sentiment_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, topics list, record_count
  [ ] -1.0 <= sentiment_score <= 1.0 for all topics
  [ ] signal in {"BULLISH", "NEUTRAL", "BEARISH"}
  [ ] python -m pytest tests/test_sentiment.py -v passes
