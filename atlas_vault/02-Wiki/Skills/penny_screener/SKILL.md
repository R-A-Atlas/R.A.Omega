---
name: Penny Stock Screener
description: Screens yfinance most-actives for stocks under $10 with 3x+ average volume; flags HIGH_VOLUME_PENNY (5x+) or ELEVATED_VOLUME_PENNY (3x+)
type: reference
agent: T9
division: Trading Desk
---

# Skill: Penny Stock Screener (T9)

## [D] Direction
Fetch Yahoo Finance most-active screener via yfinance. Filter to price < $10
and volume_ratio >= 3x average. Sort by volume_ratio descending. Label 5x+ as
HIGH_VOLUME_PENNY, 3x+ as ELEVATED_VOLUME_PENNY. Exclude ETFs.
Save to data_cache/penny_stocks_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/equities/equities_scraper.py (screener pattern)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Library:    yfinance (already in requirements.txt)
Output:     data_cache/penny_stocks_latest.json

Hard filters:
  price < $10.00
  volume_ratio = volume / avg_volume_30d >= 3.0
  quoteType != "ETF"

Signal thresholds:
  volume_ratio >= 5.0  → HIGH_VOLUME_PENNY
  volume_ratio >= 3.0  → ELEVATED_VOLUME_PENNY

## [S] Solutions
Run scraper:
  python -m atlas_agents.trading.penny_screener.penny_screener_scraper

Test screener call:
  python -c "import yfinance as yf; r = yf.screen('most_actives'); print(len(r.get('quotes', [])))"

Run tests:
  python -m pytest tests/test_penny_screener.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | all stocks price < 10.0 | max(price) < 10.0 |
| 3 | all stocks volume_ratio >= 3.0 | min(volume_ratio) >= 3.0 |
| 4 | signal only valid values | HIGH_VOLUME_PENNY or ELEVATED_VOLUME_PENNY |
| 5 | no ETFs in output | no quoteType == "ETF" |
