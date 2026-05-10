---
name: Geopolitical Tariff Tracker
description: Tracks active US tariffs by product/trading partner from USTR database; classifies status as ACTIVE/SUSPENDED/UNDER_REVIEW/ESCALATING
type: reference
agent: M5
division: Macro Risk & Geopolitics
---

# Skill: Geopolitical Tariff Tracker (M5)

## [D] Direction
Fetch USTR tariff data + hardcoded Section 301/232 snapshot.
Track active_tariffs: product, rate, trading_partner, authority, status.
Status: ACTIVE/SUSPENDED/UNDER_REVIEW/ESCALATING.
Save to data_cache/tariffs_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/macro scraper pattern
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://ustr.gov/issue-areas/enforcement/section-301-investigations
Hardcoded:  China 301 (25%/7.5%), Steel 232 (25%), Aluminum 232 (10%)
Output:     data_cache/tariffs_latest.json

## [S] Solutions
Run scraper:
  python -m atlas_agents.macro.tariffs.tariffs_scraper

Run tests:
  python -m pytest tests/test_tariffs.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | status in valid set | ACTIVE/SUSPENDED/UNDER_REVIEW/ESCALATING |
| 3 | rate_pct >= 0 | no negative rates |
| 4 | authority documented | Section 301/232/201/IEEPA |
| 5 | record_count == len(active_tariffs) | count matches |
