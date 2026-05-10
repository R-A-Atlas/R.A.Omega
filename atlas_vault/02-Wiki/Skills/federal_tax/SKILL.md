---
name: Federal Tax Code Bot
description: Fetches IRS 2026 federal income tax brackets and standard deductions; uses hardcoded fallback when IRS page is unavailable
type: reference
agent: L1
division: Tax & Legal
---

# Skill: Federal Tax Code Bot (L1)

## [D] Direction
Retrieve IRS 2026 tax brackets (7 brackets: 10%–37%) and standard deductions
(single: $15,000; married: $30,000) from https://www.irs.gov/newsroom/irs-provides-tax-inflation-adjustments-for-tax-year-2026
When the IRS page is unavailable, fall back to the hardcoded 2026 table.
Save structured output to data_cache/federal_tax_latest.json.
record_count must equal len(brackets) before write.

## [B] Blueprints
Pattern:   atlas_agents/legal/federal_tax/federal_tax_scraper.py
Utils:     atlas_core/utils/agent_utils.py (write_cache_json_pair)
Source:    https://www.irs.gov/newsroom/irs-provides-tax-inflation-adjustments-for-tax-year-2026
Output:    data_cache/federal_tax_latest.json
Fallback:  Hardcoded 2026 dict in scraper (IRS adjusts annually in October/November)

Bracket thresholds (2026 hardcoded):
  10%: $0–$11,925 (single) / $0–$23,850 (married)
  12%: $11,925–$48,475 / $23,850–$96,950
  22%: $48,475–$103,350 / $96,950–$206,700
  24%: $103,350–$197,300 / $206,700–$394,600
  32%: $197,300–$250,525 / $394,600–$501,050
  35%: $250,525–$626,350 / $501,050–$751,600
  37%: $626,350+ (null) / $751,600+ (null)

standard_deduction_single:  15000
standard_deduction_married: 30000

## [S] Solutions
Run scraper:
  python -m atlas_agents.legal.federal_tax.federal_tax_scraper

Verify output:
  python -c "import json; d=json.load(open('data_cache/federal_tax_latest.json')); print(d['year'], d['record_count'], len(d['brackets']))"

Run tests:
  python -m pytest tests/test_federal_tax.py -v

Compile check:
  python -m py_compile atlas_agents/legal/federal_tax/federal_tax_scraper.py

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on federal_tax_scraper.py |
| 2 | record_count == 7 | top-level int equals 7 |
| 3 | standard_deduction_single == 15000 | integer field present |
| 4 | standard_deduction_married == 30000 | integer field present |
| 5 | top bracket single_max == null | 37% bracket has null upper bound |
