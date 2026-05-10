---
name: Fed Rate Probability
description: Fetches CME FedWatch implied probabilities for next FOMC meeting; classifies dominant action as DOVISH/NEUTRAL/HAWKISH; probabilities must sum to 100
type: reference
agent: M1
division: Macro Risk & Geopolitics
---

# Skill: Fed Rate Probability (M1)

## [D] Direction
Scrape CME FedWatch tool for FOMC meeting rate probabilities across 5 actions:
CUT_50BPS, CUT_25BPS, HOLD, HIKE_25BPS, HIKE_50BPS.
Dominant action = highest probability. Classify macro_signal: DOVISH/NEUTRAL/HAWKISH.
Sum of probabilities must equal 100 (±0.5). Save to data_cache/fed_watch_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/trading/bond_yields/bond_yields_scraper.py (REST fetch)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://www.cmegroup.com/CmeWS/mvc/ProductCalendar/V2/FedWatch/Probabilities
Fallback:   yfinance ZQ=F Fed Funds futures
Output:     data_cache/fed_watch_latest.json

Signal logic:
  dominant in [CUT_50BPS, CUT_25BPS] → DOVISH
  dominant == HOLD                    → NEUTRAL
  dominant in [HIKE_25BPS, HIKE_50BPS] → HAWKISH

## [S] Solutions
Run scraper:
  python -m atlas_agents.macro.fed_watch.fed_watch_scraper

Run tests:
  python -m pytest tests/test_fed_watch.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | probabilities sum to 100 | abs(sum - 100) <= 0.5 |
| 3 | dominant_action matches max probability | argmax check |
| 4 | macro_signal in valid set | DOVISH, NEUTRAL, or HAWKISH |
| 5 | record_count == len(probabilities) | count matches |
