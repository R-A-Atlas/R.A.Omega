---
name: Bankruptcy Parser
description: Scrapes US Courts bankruptcy filing statistics (Ch.7/11/13), computes YoY change, and classifies trend as SURGING/RISING/STABLE/DECLINING
type: reference
agent: L3
division: Tax & Legal
---

# Skill: Bankruptcy Parser (L3)

## [D] Direction
Fetch bankruptcy filing totals from https://www.uscourts.gov/statistics-reports/caseload-statistics-data-tables
Parse ch7_filings, ch11_filings, ch13_filings for the most recent period.
Compute total_filings = ch7 + ch11 + ch13.
Compute yoy_change_pct = ((total - prior_year) / prior_year) * 100, rounded to 2dp.
Classify trend_signal:
  yoy >= 20% → SURGING | yoy >= 5% → RISING | -5% to 5% → STABLE | <= -5% → DECLINING
Fall back to hardcoded 2024 data on scrape failure.
Save to data_cache/bankruptcy_latest.json.

## [B] Blueprints
Pattern:   atlas_agents/legal/bankruptcy/bankruptcy_scraper.py
Source:    https://www.uscourts.gov/statistics-reports/caseload-statistics-data-tables
Stats:     https://www.uscourts.gov/statistics/table/f/bankruptcy-filings/2024/12/31
Output:    data_cache/bankruptcy_latest.json
Fallback:  Ch.7: 387,721 | Ch.11: 6,067 | Ch.13: 132,282 | Prior total: 467,737

Trend thresholds:
  yoy_change_pct >= 20.0  → "SURGING"
  yoy_change_pct >= 5.0   → "RISING"
  yoy_change_pct <= -5.0  → "DECLINING"
  else                    → "STABLE"

top_sectors: ["Retail", "Healthcare", "Real Estate"] (hardcoded context list)

## [S] Solutions
Run scraper:
  python -m atlas_agents.legal.bankruptcy.bankruptcy_scraper

Verify totals:
  python -c "import json; d=json.load(open('data_cache/bankruptcy_latest.json')); print(d['total_filings'], d['trend_signal'], d['yoy_change_pct'])"

Run tests:
  python -m pytest tests/test_bankruptcy.py -v

Compile check:
  python -m py_compile atlas_agents/legal/bankruptcy/bankruptcy_scraper.py

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on bankruptcy_scraper.py |
| 2 | total == ch7 + ch11 + ch13 | arithmetic check |
| 3 | trend_signal in valid set | one of SURGING/RISING/STABLE/DECLINING |
| 4 | yoy_change_pct is float rounded to 2dp | isinstance float, str(x).split('.')[-1] len <= 2 |
| 5 | top_sectors is non-empty list | len > 0 |
