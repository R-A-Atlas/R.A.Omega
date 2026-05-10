---
name: Dark Pool Monitor
description: Parses FINRA ATS weekly CSV to surface S&P 500 tickers with dark pool volume ratio >= 30%; flags ELEVATED_DARK_POOL or HIGH_DARK_POOL
type: reference
agent: T8
division: Trading Desk
---

# Skill: Dark Pool Monitor (T8)

## [D] Direction
Download FINRA weekly ATS pipe-delimited CSV. Compute dark_pool_ratio =
ShortVolume / TotalVolume for each S&P 500 ticker. Keep only ratio >= 0.30.
Label >= 0.45 as HIGH_DARK_POOL, >= 0.30 as ELEVATED_DARK_POOL.
Sort descending, top 50. Save to data_cache/dark_pool_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/crypto/crypto_scraper.py
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Source:     https://cdn.finra.org/equity/regsho/weekly/CNMSshvol<YYYYMMDD>.txt
Format:     Pipe-delimited | Date | Symbol | ShortVolume | ShortExemptVolume | TotalVolume | Market
Filter:     Market == "FINRA" rows only; S&P 500 universe only
Output:     data_cache/dark_pool_latest.json

Signal thresholds:
  ratio >= 0.45  → HIGH_DARK_POOL
  ratio >= 0.30  → ELEVATED_DARK_POOL
  ratio < 0.30   → exclude

## [S] Solutions
Run scraper:
  python -m atlas_agents.trading.dark_pool.dark_pool_scraper

Find latest FINRA file date (most recent Monday):
  python -c "from datetime import date, timedelta; d=date.today(); print(d - timedelta(days=d.weekday()))"

Run tests:
  python -m pytest tests/test_dark_pool.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | generated_at present | non-empty ISO string |
| 3 | all signals ratio >= 0.30 | min(dark_pool_ratio) >= 0.30 |
| 4 | signal only valid values | ELEVATED_DARK_POOL or HIGH_DARK_POOL |
| 5 | stable file written | data_cache/dark_pool_latest.json exists |
