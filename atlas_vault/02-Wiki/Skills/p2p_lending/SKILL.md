---
name: P2P Lending Bot
description: Fetches public LendingClub and Prosper statistics; tracks avg_return_pct, default_rate_12m_pct, and platform status; signals ATTRACTIVE/MODERATE/AVOID
type: reference
agent: A4
division: Alternative Assets & Niche
---

# Skill: P2P Lending Bot (A4)

## [D] Direction
Fetch public performance data from LendingClub and Prosper websites.
Parse net annualized returns and 12-month default rates from public summary sections.
Fall back to hardcoded quarterly snapshot when login walls block full data.
Classify signal: ATTRACTIVE (return >= 8% AND default <= 5%), MODERATE (return >= 5%), AVOID (default > 10%).
Save to data_cache/p2p_latest.json.

Steps:
1. GET https://www.lendingclub.com/info/statistics.action — parse public stats.
2. GET https://www.prosper.com/invest/performance/ — parse public returns.
3. For CLOSED_TO_RETAIL platforms (Funding Circle): use hardcoded snapshot.
4. Classify signal per SIGNAL LOGIC priority order.
5. Sleep 1.0s between platform requests.
6. Write payload to data_cache/p2p_latest.json via write_cache_json_pair.

## [B] Blueprints
Pattern:    atlas_agents/realestate/residential/residential_scraper.py (HTML fetch + parse)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://www.lendingclub.com/info/statistics.action
Secondary:  https://www.prosper.com/invest/performance/
Output:     data_cache/p2p_latest.json
Schema fields: name, avg_return_pct, default_rate_12m_pct, active_loans_count, min_investment, accredited_only, status, signal

Platform Universe:
  LendingClub   (ACTIVE, no accreditation required, min $1,000)
  Prosper        (ACTIVE, no accreditation required, min $25)
  Funding Circle (CLOSED_TO_RETAIL, accredited only, min $50,000)
  Upstart        (ACTIVE, accredited only, min $100)

## [S] Solutions
Run scraper:
  python -m atlas_agents.alternative.p2p_lending.p2p_scraper

Test LendingClub connectivity:
  python -c "import requests; r = requests.get('https://www.lendingclub.com/info/statistics.action', headers={'User-Agent':'Mozilla/5.0'}); print(r.status_code)"

Run tests:
  python -m pytest tests/test_p2p_lending.py -v

Verify output:
  python -c "import json,pathlib; d=json.loads(pathlib.Path('data_cache/p2p_latest.json').read_text()); print(d['record_count'], [(p['name'], p['signal']) for p in d['platforms']])"

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on p2p_scraper.py |
| 2 | all 4 platforms present | record_count == 4 |
| 3 | signal is valid enum value | each signal in {ATTRACTIVE, MODERATE, AVOID} |
| 4 | status is valid enum value | each status in {ACTIVE, CLOSED_TO_RETAIL} |
| 5 | generated_at is ISO UTC string | parseable as datetime, ends with Z |
