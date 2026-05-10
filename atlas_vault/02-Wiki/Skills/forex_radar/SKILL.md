---
name: Forex Radar
description: Tracks 8 major USD currency pairs via Frankfurter ECB API; flags 24h volatility as STABLE / ELEVATED / HIGH_VOLATILITY; computes DXY proxy
type: reference
agent: T6
division: Trading Desk
---

# Skill: Forex Radar (T6)

## [D] Direction
Fetch current and previous day rates from Frankfurter API (free, no auth).
Compute 24h change % for each USD pair. Classify volatility. Compute a DXY
proxy from the weighted basket. Save to data_cache/forex_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/crypto/crypto_scraper.py
Utils:      atlas_core/utils/agent_utils.py
API:        https://api.frankfurter.app/latest?from=USD&to=EUR,GBP,JPY,CAD,CHF,AUD,CNY,MXN
            https://api.frankfurter.app/latest-1?from=USD (previous day)
Output:     data_cache/forex_latest.json

Volatility thresholds:
  |change_24h_pct| >= 1.0  → HIGH_VOLATILITY
  |change_24h_pct| >= 0.5  → ELEVATED
  |change_24h_pct| < 0.5   → STABLE

DXY proxy weights (approximate):
  EUR 57.6% | JPY 13.6% | GBP 11.9% | CAD 9.1% | CHF 3.6% | SEK 4.2%

## [S] Solutions
Run scraper:
  python -m atlas_agents.trading.forex_radar.forex_radar_scraper

Test Frankfurter API manually:
  python -c "from atlas_core.utils.agent_utils import requests_get_json; print(requests_get_json('https://api.frankfurter.app/latest?from=USD'))"

Run tests:
  python -m pytest tests/test_forex_radar.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | generated_at present | non-empty ISO string |
| 3 | 8 pairs returned | len(pairs) == 8 |
| 4 | volatility_signal only valid values | STABLE/ELEVATED/HIGH_VOLATILITY/UNKNOWN |
| 5 | dxy_proxy is a float | isinstance(dxy_proxy, float) |
