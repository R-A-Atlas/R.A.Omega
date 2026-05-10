---
name: Commercial Property Bot
description: Tracks CRE lease rates and vacancy by segment (Office/Industrial/Retail/Multifamily) via FRED CRE indices; classifies trend as TIGHTENING/STABLE/SOFTENING
type: reference
agent: R4
division: Real Estate & Property
---

# Skill: Commercial Property Bot (R4)

## [D] Direction
Fetch FRED CRE price index series (RCPIATOT, RCPIAINTR, RCPIAOFC) for national
commercial real estate trends. Classify segment trend from YoY vacancy change:
>= +1% → SOFTENING, <= -1% → TIGHTENING, else STABLE.
Fall back to hardcoded Q1 2026 snapshot if FRED unavailable.
Save to data_cache/commercial_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/equities/equities_scraper.py (REST fetch + classify)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://api.stlouisfed.org/fred/series/observations (FRED, no auth)
Fallback:   Hardcoded Q1 2026 snapshot (Office 18.5%, Industrial 5.2%, Retail 4.1%, MF 6.8%)
Output:     data_cache/commercial_latest.json

Trend logic:
  yoy_vacancy_change >= 1.0   → SOFTENING
  yoy_vacancy_change <= -1.0  → TIGHTENING
  else                        → STABLE

## [S] Solutions
Run scraper:
  python -m atlas_agents.realestate.commercial.commercial_scraper

Test FRED series:
  python -c "import requests; r = requests.get('https://api.stlouisfed.org/fred/series/observations?series_id=RCPIATOT&file_type=json&limit=2&sort_order=desc'); print(r.status_code, r.json().get('observations', [])[:1])"

Run tests:
  python -m pytest tests/test_commercial.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | trend in valid set | TIGHTENING or STABLE or SOFTENING |
| 3 | avg_lease_rate > 0 | all segments positive |
| 4 | vacancy_rate in [0, 100] | percentage not decimal |
| 5 | record_count == len(segments) | count matches list length |
