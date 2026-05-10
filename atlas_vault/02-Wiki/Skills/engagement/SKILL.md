---
name: Engagement Rater
description: Computes social media engagement rate = (avg_likes + avg_comments) / followers * 100; classifies HIGH_ENGAGEMENT/AVERAGE/LOW and NANO/MICRO/MID/MACRO tier
type: reference
agent: G8
division: Business Growth & Ops
---

# Skill: Engagement Rater (G8)

## [D] Direction
Scrape public Instagram profiles for follower count and recent post metrics.
Compute engagement_rate = (avg_likes + avg_comments) / followers * 100.
Classify tier: NANO/MICRO/MID/MACRO. Classify signal: HIGH_ENGAGEMENT/AVERAGE/LOW.
Save to data_cache/engagement_latest.json.

## [B] Blueprints
Source:  Instagram public profile pages (5s sleep between requests)
Utils:   atlas_core/utils/agent_utils.py

## [S] Solutions
Run scraper:
  python -m atlas_agents.growth.engagement.engagement_scraper

Run tests:
  python -m pytest tests/test_engagement.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | engagement_rate formula correct | (likes+comments)/followers*100 |
| 3 | tier in NANO/MICRO/MID/MACRO | valid tiers |
| 4 | signal in HIGH_ENGAGEMENT/AVERAGE/LOW | valid signals |
| 5 | record_count == len(profiles) | count matches |
