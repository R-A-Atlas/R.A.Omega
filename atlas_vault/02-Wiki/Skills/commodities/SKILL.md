---
name: Commodities Watch
description: Tracks Gold, Silver, Copper, WTI Oil, Nat Gas, Wheat, Corn via yfinance futures tickers; classifies 24h trend as RISING / FALLING / FLAT
type: reference
agent: T7
division: Trading Desk
---

# Skill: Commodities Watch (T7)

## [D] Direction
Fetch 7 commodity futures via yfinance (GC=F, SI=F, HG=F, CL=F, NG=F, ZW=F, ZC=F).
Compute 24h price change from prev_close. Classify trend. Skip failures silently.
Save to data_cache/commodities_latest.json. Add 0.1s sleep between fetches.

## [B] Blueprints
Pattern:    atlas_agents/crypto/crypto_scraper.py
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Library:    yfinance (already in requirements.txt)
Output:     data_cache/commodities_latest.json

Tickers:
  Gold GC=F | Silver SI=F | Copper HG=F | WTI Oil CL=F
  Nat Gas NG=F | Wheat ZW=F | Corn ZC=F

Trend thresholds:
  change_24h_pct >= 0.5   → RISING
  change_24h_pct <= -0.5  → FALLING
  otherwise               → FLAT

## [S] Solutions
Run scraper:
  python -m atlas_agents.trading.commodities.commodities_scraper

Test single ticker:
  python -c "import yfinance as yf; t = yf.Ticker('GC=F'); print(t.fast_info)"

Run tests:
  python -m pytest tests/test_commodities.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | generated_at present | non-empty ISO string |
| 3 | up to 7 commodities returned | len(commodities) <= 7 |
| 4 | trend only valid values | RISING/FALLING/FLAT |
| 5 | price is float or null | not a string |
