---
name: Options Flow Monitor
description: Scrapes CBOE/Barchart for unusual options activity; flags contracts with volume/OI ratio > 3x as BULLISH_UNUSUAL or BEARISH_UNUSUAL
type: reference
agent: T3
division: Trading Desk
---

# Skill: Options Flow Monitor (T3)

## [D] Direction
Fetch public options data from CBOE or Barchart. Compute volume/OI ratio for
each contract. Keep only those with ratio > 3.0 and label them BULLISH_UNUSUAL
(calls) or BEARISH_UNUSUAL (puts). Save to data_cache/options_flow_latest.json.
No LLM calls. No auth required. Follow crypto_scraper.py pattern.

## [B] Blueprints
Pattern:    atlas_agents/crypto/crypto_scraper.py
Utils:      atlas_core/utils/agent_utils.py
Output:     data_cache/options_flow_latest.json
Schema:     { generated_at, source, record_count, unusual_activity: [{ticker, expiry,
              strike, type, volume, open_interest, volume_oi_ratio, signal}] }

Signal logic:
  ratio = volume / open_interest
  ratio > 3 + CALL  → BULLISH_UNUSUAL
  ratio > 3 + PUT   → BEARISH_UNUSUAL

Data sources (free, no auth):
  CBOE: https://www.cboe.com/us/options/market_statistics/
  Barchart: barchart.com unusual options screener (public)

## [S] Solutions
Run scraper:
  python -m atlas_agents.trading.options_flow.options_flow_scraper

Validate output:
  python -m atlas_core.validation.data_validator  (add options_flow validator)

Run tests:
  python -m pytest tests/test_options_flow.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | generated_at present | non-empty ISO string |
| 3 | all items have ratio > 3.0 | min(volume_oi_ratio) > 3.0 |
| 4 | signal values valid | only BULLISH_UNUSUAL / BEARISH_UNUSUAL |
| 5 | stable file written | data_cache/options_flow_latest.json exists |
