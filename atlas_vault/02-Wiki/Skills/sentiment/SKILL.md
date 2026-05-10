---
name: Social Sentiment Analyzer
description: Scrapes Reddit finance subreddits for topic mentions; computes sentiment_score from upvote ratio and keywords; classifies BULLISH/NEUTRAL/BEARISH
type: reference
agent: G5
division: Business Growth & Ops
---

# Skill: Social Sentiment Analyzer (G5)

## [D] Direction
Fetch hot.json from r/investing, r/wallstreetbets, r/stocks, r/personalfinance, r/realestateinvesting.
Count topic mentions, compute sentiment_score from upvote_ratio + keyword scoring.
Classify: >=0.3 → BULLISH, <=-0.3 → BEARISH, else NEUTRAL.
Save to data_cache/sentiment_latest.json.

## [B] Blueprints
API:   https://www.reddit.com/r/{sub}/hot.json (no auth, User-Agent required)
Utils: atlas_core/utils/agent_utils.py

## [S] Solutions
Run scraper:
  python -m atlas_agents.growth.sentiment.sentiment_scraper

Run tests:
  python -m pytest tests/test_sentiment.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | signal in valid set | BULLISH/NEUTRAL/BEARISH |
| 3 | -1.0 <= sentiment_score <= 1.0 | clamped range |
| 4 | record_count == len(topics) | count matches |
| 5 | User-Agent header set | no raw requests without header |
