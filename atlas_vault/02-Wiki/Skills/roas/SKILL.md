---
name: ROAS Optimizer
description: Pulls Meta/Google Ads campaign data; computes ROAS = revenue/spend; classifies PROFITABLE/BREAK_EVEN/LOSING and recommends SCALE/OPTIMIZE/MONITOR/PAUSE
type: reference
agent: G10
division: Business Growth & Ops
---

# Skill: ROAS Optimizer (G10)

## [D] Direction
Fetch campaign performance from Meta Marketing API and Google Ads API.
Compute roas = revenue_usd / spend_usd. Classify signal and recommendation.
Save to data_cache/roas_latest.json. Graceful empty return if tokens absent.

## [B] Blueprints
APIs:    Meta Graph API v19.0, Google Ads API
Keys:    ATLAS_META_TOKEN, ATLAS_GOOGLE_ADS_TOKEN (both optional)
Utils:   atlas_core/utils/agent_utils.py

## [S] Solutions
Run scraper:
  python -m atlas_agents.growth.roas.roas_scraper

Run tests:
  python -m pytest tests/test_roas.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | roas >= 0 | non-negative |
| 3 | signal in valid set | PROFITABLE/BREAK_EVEN/LOSING |
| 4 | recommendation in valid set | SCALE/OPTIMIZE/MONITOR/PAUSE |
| 5 | graceful when tokens absent | returns empty list, no crash |
