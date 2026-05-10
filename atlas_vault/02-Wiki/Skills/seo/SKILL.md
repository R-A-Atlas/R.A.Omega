---
name: SEO Keyword Tracker
description: Uses pytrends to fetch Google Trends scores for finance keywords; classifies BREAKOUT/RISING/STABLE/DECLINING by trend score
type: reference
agent: G4
division: Business Growth & Ops
---

# Skill: SEO Keyword Tracker (G4)

## [D] Direction
Use pytrends TrendReq to fetch interest_over_time for 8 default finance keywords.
Classify: score==100 → BREAKOUT, >=70 → RISING, >=40 → STABLE, <40 → DECLINING.
Save to data_cache/seo_keywords_latest.json.

## [B] Blueprints
Library: pytrends (pip install pytrends)
Utils:   atlas_core/utils/agent_utils.py

## [S] Solutions
Run scraper:
  python -m atlas_agents.growth.seo.seo_scraper

Run tests:
  python -m pytest tests/test_seo.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | trend_direction in valid set | BREAKOUT/RISING/STABLE/DECLINING |
| 3 | 0 <= trend_score <= 100 | valid range |
| 4 | record_count == len(keywords) | count matches |
| 5 | graceful on pytrends fail | returns empty list, no crash |
