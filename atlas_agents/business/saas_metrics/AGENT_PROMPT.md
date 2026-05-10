# AGENT_PROMPT — B2: B2B SaaS Metrics Bot

## IDENTITY
Agent ID: B2  
Name: B2B SaaS Metrics Bot  
Division: Business & Startups  
Output file: data_cache/saas_metrics_latest.json

---

## DEFINITION
Delivers the definitive B2B SaaS benchmark dataset from OpenView Partners annual report.
Tracks ARR growth, Net Dollar Retention, CAC payback, Magic Number, gross margin, and
Rule of 40 across Growth / Efficiency / Retention / Sales categories. Data is hardcoded
annually from the published OpenView report (released each Q4) and refreshed each year.

---

## DATA SOURCES

| Source | URL | Auth |
|--------|-----|------|
| OpenView Partners SaaS Benchmarks Report | https://openviewpartners.com/saas-benchmarks-report/ | None |

Data is published annually by OpenView Partners as a public PDF/web report. Since the
source is a PDF snapshot (not an API), benchmarks are hardcoded from the 2025 edition
and updated manually each year when the new report is released.

---

## OUTPUT FILE
`data_cache/saas_metrics_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:30:00Z",
  "benchmark_year": 2025,
  "record_count": 6,
  "benchmarks": [
    {
      "metric": "ARR_growth_pct",
      "median": 25.0,
      "p75": 45.0,
      "p90": 72.0,
      "unit": "percent",
      "category": "Growth"
    },
    {
      "metric": "NDR_pct",
      "median": 110.0,
      "p75": 125.0,
      "p90": 140.0,
      "unit": "percent",
      "category": "Retention"
    },
    {
      "metric": "CAC_payback_months",
      "median": 18.0,
      "p75": 12.0,
      "p90": 8.0,
      "unit": "months",
      "category": "Sales"
    },
    {
      "metric": "magic_number",
      "median": 0.75,
      "p75": 1.1,
      "p90": 1.5,
      "unit": "ratio",
      "category": "Efficiency"
    },
    {
      "metric": "gross_margin_pct",
      "median": 72.0,
      "p75": 78.0,
      "p90": 83.0,
      "unit": "percent",
      "category": "Efficiency"
    },
    {
      "metric": "rule_of_40",
      "median": 28.0,
      "p75": 42.0,
      "p90": 60.0,
      "unit": "score",
      "category": "Growth"
    }
  ]
}
```

### Field Definitions
| Field | Type | Description |
|-------|------|-------------|
| generated_at | ISO 8601 UTC string | Timestamp of cache generation |
| benchmark_year | int | Year of the OpenView benchmark data |
| record_count | int | Total benchmarks returned |
| benchmarks[].metric | string | Metric identifier key |
| benchmarks[].median | float | Median value across all surveyed companies |
| benchmarks[].p75 | float | 75th percentile value |
| benchmarks[].p90 | float | 90th percentile value |
| benchmarks[].unit | string | Unit of measurement ("percent", "months", "ratio", "score") |
| benchmarks[].category | string | "Growth", "Efficiency", "Retention", or "Sales" |

---

## SIGNAL / RATING LOGIC

Performance tiers relative to median:
- **ELITE**: value >= p90
- **STRONG**: p75 <= value < p90
- **MEDIAN**: median <= value < p75
- **BELOW**: value < median

For CAC payback: lower is better (elite = below p90 threshold, which is lower months).
For gross margin and NDR: higher is better.
Rule of 40 = ARR growth % + EBITDA margin %. Score >= 40 is considered healthy.

category values: `"Growth"` | `"Efficiency"` | `"Retention"` | `"Sales"`

---

## SCRAPER STRUCTURE

```python
"""saas_metrics_scraper.py — B2 B2B SaaS Metrics Bot"""
import json
import datetime

SOURCE_URL = "https://openviewpartners.com/saas-benchmarks-report/"
BENCHMARK_YEAR = 2025

# 2025 OpenView SaaS Benchmarks (hardcoded from annual report)
# Update this block each Q4 when OpenView publishes the new edition.
BENCHMARKS_2025 = [
    {
        "metric": "ARR_growth_pct",
        "median": 25.0,
        "p75": 45.0,
        "p90": 72.0,
        "unit": "percent",
        "category": "Growth",
    },
    {
        "metric": "NDR_pct",
        "median": 110.0,
        "p75": 125.0,
        "p90": 140.0,
        "unit": "percent",
        "category": "Retention",
    },
    {
        "metric": "CAC_payback_months",
        "median": 18.0,
        "p75": 12.0,
        "p90": 8.0,
        "unit": "months",
        "category": "Sales",
    },
    {
        "metric": "magic_number",
        "median": 0.75,
        "p75": 1.1,
        "p90": 1.5,
        "unit": "ratio",
        "category": "Efficiency",
    },
    {
        "metric": "gross_margin_pct",
        "median": 72.0,
        "p75": 78.0,
        "p90": 83.0,
        "unit": "percent",
        "category": "Efficiency",
    },
    {
        "metric": "rule_of_40",
        "median": 28.0,
        "p75": 42.0,
        "p90": 60.0,
        "unit": "score",
        "category": "Growth",
    },
]


def rate_company(metric: str, value: float, benchmark: dict) -> str:
    """Return performance tier label relative to benchmark."""
    if metric == "CAC_payback_months":
        if value <= benchmark["p90"]:
            return "ELITE"
        if value <= benchmark["p75"]:
            return "STRONG"
        if value <= benchmark["median"]:
            return "MEDIAN"
        return "BELOW"
    else:
        if value >= benchmark["p90"]:
            return "ELITE"
        if value >= benchmark["p75"]:
            return "STRONG"
        if value >= benchmark["median"]:
            return "MEDIAN"
        return "BELOW"


def scrape() -> dict:
    """Return 2025 OpenView SaaS benchmark snapshot."""
    return {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "benchmark_year": BENCHMARK_YEAR,
        "record_count": len(BENCHMARKS_2025),
        "benchmarks": BENCHMARKS_2025,
    }


def save(output_path: str = "data_cache/saas_metrics_latest.json") -> None:
    result = scrape()
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    save()
```

---

## RULES
1. All 6 key metrics must always be present: ARR_growth_pct, NDR_pct, CAC_payback_months, magic_number, gross_margin_pct, rule_of_40.
2. benchmark_year must match the data vintage — never claim 2025 data is 2026 data.
3. Update BENCHMARKS_2025 block each Q4 when new OpenView report releases.
4. category values are strictly: "Growth", "Efficiency", "Retention", "Sales".
5. unit values: "percent", "months", "ratio", "score".
6. generated_at must be ISO 8601 UTC (Z suffix).
7. record_count must equal len(benchmarks).

---

## VALIDATION CHECKLIST
- [ ] All 6 required metrics present
- [ ] benchmark_year is an integer (not a string)
- [ ] record_count == len(benchmarks)
- [ ] generated_at is valid ISO UTC string
- [ ] Each benchmark has: metric, median, p75, p90, unit, category
- [ ] category is one of: Growth, Efficiency, Retention, Sales
- [ ] ARR_growth median = 25, NDR median = 110, CAC_payback median = 18
- [ ] gross_margin median = 72, rule_of_40 median = 28
