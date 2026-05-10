---
name: Physical Metals Bot
description: Fetches Gold/Silver/Platinum/Palladium spot prices via yfinance (GC=F, SI=F, PL=F, PA=F); applies hardcoded dealer premiums to compute physical coin/bar prices; signals TIGHT_SPREAD/NORMAL_SPREAD/WIDE_SPREAD
type: reference
agent: A5
division: Alternative Assets & Niche
---

# Skill: Physical Metals Bot (A5)

## [D] Direction
Fetch spot prices for 4 precious metals using yfinance futures tickers (GC=F, SI=F, PL=F, PA=F).
Apply hardcoded dealer premiums (APMEX/JM Bullion typical patterns) to derive physical
coin and bar buy prices. Compute spread_pct and classify TIGHT_SPREAD / NORMAL_SPREAD / WIDE_SPREAD.
Save to data_cache/metals_latest.json.

Steps:
1. Iterate METAL_UNIVERSE (4 metals: Gold, Silver, Platinum, Palladium).
2. For each: spot_price = yf.Ticker(symbol).fast_info["lastPrice"].
3. buy_price = spot_price * (1 + coin_premium_pct / 100).
4. sell_price = spot_price (dealer buy-back approximation).
5. spread_pct = coin_premium_pct (= (buy - sell) / sell * 100).
6. Classify: TIGHT_SPREAD (<=2%), NORMAL_SPREAD (<=5%), WIDE_SPREAD (>5%).
7. Write payload to data_cache/metals_latest.json via write_cache_json_pair.

## [B] Blueprints
Pattern:    atlas_agents/equities/equities_scraper.py (yfinance fetch pattern)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Data:       yfinance — GC=F (Gold), SI=F (Silver), PL=F (Platinum), PA=F (Palladium)
Output:     data_cache/metals_latest.json
Schema fields: metal, spot_price, coin_type, coin_premium_pct, bar_type, bar_premium_pct, buy_price, sell_price, spread_pct, signal

Dealer Premiums (hardcoded):
  Gold:      coin 5%, bar 2%
  Silver:    coin 30%, bar 15%
  Platinum:  coin 8%,  bar 4%
  Palladium: coin 10%, bar 5%

## [S] Solutions
Run scraper:
  python -m atlas_agents.alternative.metals.metals_scraper

Test yfinance connectivity:
  python -c "import yfinance as yf; print(yf.Ticker('GC=F').fast_info['lastPrice'])"

Run tests:
  python -m pytest tests/test_metals.py -v

Verify output:
  python -c "import json,pathlib; d=json.loads(pathlib.Path('data_cache/metals_latest.json').read_text()); print(d['record_count'], [(m['metal'], m['signal']) for m in d['metals']])"

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on metals_scraper.py |
| 2 | all 4 metals present | record_count == 4 |
| 3 | signal is valid enum value | each signal in {TIGHT_SPREAD, NORMAL_SPREAD, WIDE_SPREAD} |
| 4 | spread_pct == coin_premium_pct | within 0.001 tolerance |
| 5 | generated_at is ISO UTC string | parseable as datetime, ends with Z |
