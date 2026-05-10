---
name: Eval Scorer
description: Benchmarks ATLAS output quality by running 4 test queries and scoring each against a 7-assertion rubric; saves dated JSON report
type: reference
agent: E10
division: Engineering
---

# Skill: Eval Scorer (E10)

## [D] Direction
Run 4 canonical test queries against POST /query. Score each response on
7 binary assertions. Save a dated JSON report. Alert if any query scores < 6/7.
Compare to previous report and flag regressions. Never modify source files.

## [B] Blueprints
Runner:      tests/evals/eval_suite.py
Reports:     tests/evals/eval_report_<YYYY-MM-DD>.json
Queries:
  Q1: "Analyze NVDA — current setup and trade plan"
  Q2: "What is the options play for AAPL earnings?"
  Q3: "Should I buy or rent in Miami right now?"
  Q4: "What are the top crypto movers today?"

7-assertion rubric (per query):
  1. tldr populated (len > 20)
  2. final_report.overall_rating non-empty
  3. execution_rules exactly 5 items
  4. scenarios exactly 3 items
  5. failure_modes exactly 3 items
  6. response_time_s < 300
  7. no top-level error key in response

Alert threshold: >= 6/7 per query = PASS; 5/7 = WARN; <= 4/7 = FAIL

## [S] Solutions
Run full suite:
  python tests/evals/eval_suite.py

Run single query:
  python tests/evals/eval_suite.py --query "Analyze TSLA"

Dry-run (no live calls):
  python tests/evals/eval_suite.py --dry-run

Check for regressions:
  ls tests/evals/eval_report_*.json  (compare dates)

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | dry-run exits 0 | exit code 0 |
| 2 | eval_suite.py py_compile clean | exit code 0 |
| 3 | _score_response returns 7 keys | len(assertions) == 7 |
| 4 | report JSON saved to tests/evals/ | file exists after run |
| 5 | regression check works | check_regression() returns str or None |
