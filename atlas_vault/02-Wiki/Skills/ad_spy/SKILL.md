---
name: Competitor Ad Spy
description: Searches Meta Ad Library for active competitor ads by keyword; classifies HEAVY_SPENDER/ACTIVE/PAUSED by spend range and status
type: reference
agent: G3
division: Business Growth & Ops
---

# Skill: Competitor Ad Spy (G3)

## [D] Direction
Call Meta Ad Library API with keyword. Classify: HEAVY_SPENDER ($100k+),
ACTIVE (status=ACTIVE), PAUSED (status=PAUSED).
Save to data_cache/competitor_ads_latest.json.

## [B] Blueprints
API:     https://graph.facebook.com/v19.0/ads_archive
Key env: META_ACCESS_TOKEN (optional — returns empty if absent)
Utils:   atlas_core/utils/agent_utils.py

## [S] Solutions
Run scraper:
  python -m atlas_agents.growth.ad_spy.ad_spy_scraper "financial planning"

Run tests:
  python -m pytest tests/test_ad_spy.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | signal in valid set | HEAVY_SPENDER/ACTIVE/PAUSED |
| 3 | graceful when token absent | returns empty list, no crash |
| 4 | record_count == len(ads) | count matches |
| 5 | status in ACTIVE/PAUSED | no other values |
