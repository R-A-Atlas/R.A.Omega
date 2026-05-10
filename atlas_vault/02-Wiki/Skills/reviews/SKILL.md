---
name: Review Aggregator
description: Aggregates Google/Yelp reviews for businesses; extracts top complaints/praise themes; classifies EXCELLENT/GOOD/AT_RISK and IMPROVING/STABLE/DECLINING sentiment trend
type: reference
agent: G9
division: Business Growth & Ops
---

# Skill: Review Aggregator (G9)

## [D] Direction
Fetch reviews from Google Places API and/or Yelp Fusion API.
Extract top 3 complaint and praise themes via keyword frequency.
Classify sentiment_trend: IMPROVING/STABLE/DECLINING (recent vs historical avg).
Classify signal: EXCELLENT (>=4.5, response>=50%), GOOD (>=4.0), AT_RISK (<4.0).
Save to data_cache/reviews_latest.json.

## [B] Blueprints
APIs:    Google Places Details, Yelp Fusion Reviews
Keys:    GOOGLE_MAPS_KEY, YELP_API_KEY (both optional — graceful fallback)
Utils:   atlas_core/utils/agent_utils.py

## [S] Solutions
Run scraper:
  python -m atlas_agents.growth.reviews.reviews_scraper

Run tests:
  python -m pytest tests/test_reviews.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | 1.0 <= overall_rating <= 5.0 | valid star range |
| 3 | sentiment_trend in valid set | IMPROVING/STABLE/DECLINING |
| 4 | signal in valid set | EXCELLENT/GOOD/AT_RISK |
| 5 | graceful when keys absent | returns empty list, no crash |
