---
name: Congressional Trade Watcher
description: Fetches HouseStockWatcher API for congressional stock trades; flags LATE_DISCLOSURE (>45 days) vs ON_TIME
type: reference
agent: M8
division: Macro Risk & Geopolitics
---

# Skill: Congressional Trade Watcher (M8)

## [D] Direction
Fetch HouseStockWatcher public API for recent House member stock disclosures.
Compute days_to_disclose = disclosed_date - trade_date.
Flag: >45 days → LATE_DISCLOSURE, <=45 → ON_TIME (STOCK Act requirement).
Save to data_cache/congress_trades_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/trading/insider_tracker (SEC disclosure pattern)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://housestockwatcher.com/api (public JSON, no auth)
Output:     data_cache/congress_trades_latest.json

## [S] Solutions
Run scraper:
  python -m atlas_agents.macro.congress_trades.congress_trades_scraper

Test API:
  python -c "import requests; r = requests.get('https://housestockwatcher.com/api'); print(r.status_code)"

Run tests:
  python -m pytest tests/test_congress_trades.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | disclosure_signal in valid set | LATE_DISCLOSURE or ON_TIME |
| 3 | days_to_disclose >= 0 | non-negative |
| 4 | chamber in valid set | House or Senate |
| 5 | record_count == len(trades) | count matches |
