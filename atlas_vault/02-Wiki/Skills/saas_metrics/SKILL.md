---
name: B2B SaaS Metrics Bot
description: Delivers OpenView Partners annual SaaS benchmark data for ARR growth, NDR, CAC payback, Magic Number, gross margin, and Rule of 40 across Growth/Efficiency/Retention/Sales categories
type: reference
agent: B2
division: Business & Startups
---

# Skill: B2B SaaS Metrics Bot (B2)

## [D] Direction
Return the 6 canonical B2B SaaS benchmark metrics from the 2025 OpenView Partners annual
report. Data is hardcoded (PDF source, not API). Each metric includes median, p75, and p90.
Save result to data_cache/saas_metrics_latest.json.

Step-by-step:
1. Load BENCHMARKS_2025 constant (6 metrics, hardcoded from OpenView 2025 report).
2. Set benchmark_year = 2025.
3. Set generated_at (ISO UTC), record_count = len(benchmarks).
4. Write to data_cache/saas_metrics_latest.json.
5. Update BENCHMARKS_2025 each Q4 when new OpenView report publishes.

Rules:
- All 6 metrics must always be present: ARR_growth_pct, NDR_pct, CAC_payback_months,
  magic_number, gross_margin_pct, rule_of_40.
- category values: "Growth", "Efficiency", "Retention", "Sales" only.
- benchmark_year is an int, not a string.
- 2025 medians are fixed: ARR 25%, NDR 110%, CAC 18mo, gross_margin 72%, rule_of_40 28%.

## [B] Blueprints
Pattern:    atlas_agents/business/saas_metrics/AGENT_PROMPT.md (full scraper stub)
Primary:    https://openviewpartners.com/saas-benchmarks-report/
Output:     data_cache/saas_metrics_latest.json

2025 benchmark medians (hardcoded reference):
- ARR_growth_pct: median=25, p75=45, p90=72 (percent)
- NDR_pct: median=110, p75=125, p90=140 (percent)
- CAC_payback_months: median=18, p75=12, p90=8 (months; lower=better)
- magic_number: median=0.75, p75=1.1, p90=1.5 (ratio)
- gross_margin_pct: median=72, p75=78, p90=83 (percent)
- rule_of_40: median=28, p75=42, p90=60 (score)

## [S] Solutions
Run scraper:
  python -m atlas_agents.business.saas_metrics.saas_metrics_scraper

Run tests:
  python -m pytest tests/test_saas_metrics.py -v

Validate output:
  python -c "import json; d=json.load(open('data_cache/saas_metrics_latest.json')); print(d['benchmark_year'], [b['metric'] for b in d['benchmarks']])"

Check ARR median value:
  python -c "import json; d=json.load(open('data_cache/saas_metrics_latest.json')); arr=[b for b in d['benchmarks'] if b['metric']=='ARR_growth_pct'][0]; print('ARR median:', arr['median'])"

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | All 6 metrics present | metric keys include all 6 required names |
| 2 | benchmark_year is int | type(benchmark_year) == int |
| 3 | ARR median == 25.0 | benchmarks[ARR_growth_pct].median == 25.0 |
| 4 | NDR median == 110.0 | benchmarks[NDR_pct].median == 110.0 |
| 5 | generated_at is ISO UTC | datetime.fromisoformat(generated_at.replace("Z","+00:00")) succeeds |
