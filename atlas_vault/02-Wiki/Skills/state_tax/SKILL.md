---
name: State Tax / Act 60 Monitor
description: Aggregates 50-state + DC + Puerto Rico income/sales tax rates and special programs (no-income-tax, Act 60) from Tax Foundation data
type: reference
agent: L2
division: Tax & Legal
---

# Skill: State Tax / Act 60 Monitor (L2)

## [D] Direction
Pull state income tax top rates, state sales tax rates, and average local sales tax from
https://taxfoundation.org/data/all/state/state-income-tax-rates/
Mark 9 no-income-tax states (AK, FL, NV, NH, SD, TN, TX, WA, WY) with income_tax_rate_top=0.0
and special_programs=["No income tax"].
Add Puerto Rico (PR) with Act 60 program: 4% corporate, 0-4% individual.
Fall back to hardcoded 2026 table on scrape failure.
record_count must equal len(states) (52: 50 states + DC + PR).

## [B] Blueprints
Pattern:   atlas_agents/legal/state_tax/state_tax_scraper.py
Source:    https://taxfoundation.org/data/all/state/state-income-tax-rates/
Output:    data_cache/state_tax_latest.json
Fallback:  Hardcoded 2026 state table in scraper

No income tax states: AK, FL, NV, NH, SD, TN, TX, WA, WY
Puerto Rico Act 60: corporate 4%, individual 0-4%, special_programs includes "Act 60 (PR)"
income_tax_rate_top: float as percentage (e.g., 13.3, not 0.133)
special_programs: list of strings, never null

## [S] Solutions
Run scraper:
  python -m atlas_agents.legal.state_tax.state_tax_scraper

Verify Puerto Rico:
  python -c "import json; d=json.load(open('data_cache/state_tax_latest.json')); pr=[s for s in d['states'] if s['state_code']=='PR'][0]; print(pr)"

Run tests:
  python -m pytest tests/test_state_tax.py -v

Compile check:
  python -m py_compile atlas_agents/legal/state_tax/state_tax_scraper.py

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on state_tax_scraper.py |
| 2 | record_count == 52 | 50 states + DC + PR |
| 3 | PR has Act 60 (PR) in special_programs | Puerto Rico entry present with program tag |
| 4 | All 9 no-income-tax states have rate 0.0 | AK/FL/NV/NH/SD/TN/TX/WA/WY income_tax_rate_top == 0.0 |
| 5 | special_programs always a list | no null values in any state's special_programs |
