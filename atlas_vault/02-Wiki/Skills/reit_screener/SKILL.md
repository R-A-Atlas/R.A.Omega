---
name: REIT Screener
description: Screens top 30 US REITs via yfinance for dividend yield, price, sector; rates STRONG_BUY/BUY/HOLD/UNDERPERFORM vs current Treasury yield
type: reference
agent: R6
division: Real Estate & Property
---

# Skill: REIT Screener (R6)

## [D] Direction
Fetch yfinance .info for 30 REIT tickers. Extract dividendYield, currentPrice,
longName, sector, marketCap. Convert yield to percentage. Classify rating:
>= 7% → STRONG_BUY, >= 5.5% → BUY, >= 4% → HOLD, < 4% → UNDERPERFORM.
Include treasury_10y_rate as benchmark context.
Save to data_cache/reits_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/equities/equities_scraper.py (yfinance batch fetch)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Library:    yfinance (already in requirements.txt)
Output:     data_cache/reits_latest.json

Rating thresholds (vs 10y Treasury ~4.2%):
  dividend_yield >= 7.0%  → STRONG_BUY
  dividend_yield >= 5.5%  → BUY
  dividend_yield >= 4.0%  → HOLD
  dividend_yield < 4.0%   → UNDERPERFORM

## [S] Solutions
Run scraper:
  python -m atlas_agents.realestate.reit_screener.reit_screener_scraper

Test yfinance REIT fetch:
  python -c "import yfinance as yf; t = yf.Ticker('O'); print(t.info.get('dividendYield'), t.info.get('currentPrice'))"

Run tests:
  python -m pytest tests/test_reit_screener.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | dividend_yield > 0 | all included REITs have positive yield |
| 3 | rating in valid set | STRONG_BUY, BUY, HOLD, or UNDERPERFORM |
| 4 | treasury_10y_rate present | top-level field in output |
| 5 | record_count == len(reits) | count matches list length |
