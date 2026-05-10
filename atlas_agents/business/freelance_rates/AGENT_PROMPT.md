# AGENT_PROMPT — B4: Freelance Rate Indexer

## IDENTITY
Agent ID: B4  
Name: Freelance Rate Indexer  
Division: Business & Startups  
Output file: data_cache/freelance_rates_latest.json

---

## DEFINITION
Aggregates hourly freelance rate data for 10 key roles by combining BLS Occupational
Employment Statistics (OES) wage data with hardcoded 2025 Upwork rate ranges from the
annual Upwork Freelancer Report. Tracks demand trend and YoY rate change per role.
Designed for freelancers pricing their services and hiring managers benchmarking contractors.

---

## DATA SOURCES

| Source | URL | Auth |
|--------|-----|------|
| BLS OES API | https://api.bls.gov/publicAPI/v2/timeseries/data/ | Optional API key (not required for public data) |
| Upwork 2025 Freelancer Report (hardcoded) | https://www.upwork.com/research/freelance-forward | None |
| BLS OES landing page | https://www.bls.gov/oes/ | None |

BLS OES series examples:
- OES151252 — Software Developers
- OES151211 — Computer Systems Analysts
- OES151299 — Computer Occupations, All Other
- OES131161 — Market Research Analysts

---

## OUTPUT FILE
`data_cache/freelance_rates_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:30:00Z",
  "record_count": 10,
  "roles": [
    {
      "title": "Software Engineer",
      "avg_hourly_low": 75,
      "avg_hourly_high": 175,
      "demand_trend": "HIGH_DEMAND",
      "top_platform": "Upwork",
      "yoy_rate_change_pct": 8.5
    },
    {
      "title": "Data Scientist",
      "avg_hourly_low": 85,
      "avg_hourly_high": 200,
      "demand_trend": "HIGH_DEMAND",
      "top_platform": "Toptal",
      "yoy_rate_change_pct": 12.0
    },
    {
      "title": "UI/UX Designer",
      "avg_hourly_low": 45,
      "avg_hourly_high": 125,
      "demand_trend": "MODERATE",
      "top_platform": "Upwork",
      "yoy_rate_change_pct": 3.0
    },
    {
      "title": "Copywriter",
      "avg_hourly_low": 30,
      "avg_hourly_high": 90,
      "demand_trend": "MODERATE",
      "top_platform": "Upwork",
      "yoy_rate_change_pct": 1.5
    },
    {
      "title": "Video Editor",
      "avg_hourly_low": 35,
      "avg_hourly_high": 95,
      "demand_trend": "HIGH_DEMAND",
      "top_platform": "Fiverr",
      "yoy_rate_change_pct": 6.0
    },
    {
      "title": "SEO Specialist",
      "avg_hourly_low": 40,
      "avg_hourly_high": 110,
      "demand_trend": "MODERATE",
      "top_platform": "Upwork",
      "yoy_rate_change_pct": 2.5
    },
    {
      "title": "Virtual Assistant",
      "avg_hourly_low": 15,
      "avg_hourly_high": 40,
      "demand_trend": "MODERATE",
      "top_platform": "Upwork",
      "yoy_rate_change_pct": -1.0
    },
    {
      "title": "Accountant",
      "avg_hourly_low": 40,
      "avg_hourly_high": 110,
      "demand_trend": "MODERATE",
      "top_platform": "Upwork",
      "yoy_rate_change_pct": 4.0
    },
    {
      "title": "Financial Analyst",
      "avg_hourly_low": 55,
      "avg_hourly_high": 140,
      "demand_trend": "HIGH_DEMAND",
      "top_platform": "Toptal",
      "yoy_rate_change_pct": 7.0
    },
    {
      "title": "DevOps Engineer",
      "avg_hourly_low": 80,
      "avg_hourly_high": 185,
      "demand_trend": "HIGH_DEMAND",
      "top_platform": "Toptal",
      "yoy_rate_change_pct": 11.0
    }
  ]
}
```

### Field Definitions
| Field | Type | Description |
|-------|------|-------------|
| generated_at | ISO 8601 UTC string | Timestamp of cache generation |
| record_count | int | Total roles returned |
| roles[].title | string | Role name (consistent label) |
| roles[].avg_hourly_low | int | Lower bound of typical hourly rate (USD) |
| roles[].avg_hourly_high | int | Upper bound of typical hourly rate (USD) |
| roles[].demand_trend | string | "HIGH_DEMAND", "MODERATE", or "DECLINING" |
| roles[].top_platform | string | Platform with highest volume for this role |
| roles[].yoy_rate_change_pct | float | Year-over-year rate change in percent |

---

## SIGNAL / RATING LOGIC

demand_trend classification (hardcoded from Upwork annual report + BLS projections):
- **HIGH_DEMAND**: Software Engineer, Data Scientist, Video Editor, Financial Analyst, DevOps Engineer
- **MODERATE**: UI/UX Designer, Copywriter, SEO Specialist, Virtual Assistant, Accountant
- **DECLINING**: (none in current 10 — reserved for future additions)

yoy_rate_change_pct:
- Positive = rates rising YoY
- Negative = rates falling YoY
- Source: Upwork 2025 Freelancer Report + BLS OES annual wage comparison

BLS OES data enhances avg_hourly bounds when available. Hardcoded Upwork ranges serve as
fallback if BLS API is unreachable.

---

## SCRAPER STRUCTURE

```python
"""freelance_rates_scraper.py — B4 Freelance Rate Indexer"""
import json
import datetime
import requests

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_SOURCE_URL = "https://www.bls.gov/oes/"
UPWORK_REPORT_URL = "https://www.upwork.com/research/freelance-forward"

# Hardcoded 2025 Upwork rate ranges + demand classification
ROLES_BASELINE = [
    {
        "title": "Software Engineer",
        "avg_hourly_low": 75,
        "avg_hourly_high": 175,
        "demand_trend": "HIGH_DEMAND",
        "top_platform": "Upwork",
        "yoy_rate_change_pct": 8.5,
        "bls_series": "OES151252",
    },
    {
        "title": "Data Scientist",
        "avg_hourly_low": 85,
        "avg_hourly_high": 200,
        "demand_trend": "HIGH_DEMAND",
        "top_platform": "Toptal",
        "yoy_rate_change_pct": 12.0,
        "bls_series": "OES152051",
    },
    {
        "title": "UI/UX Designer",
        "avg_hourly_low": 45,
        "avg_hourly_high": 125,
        "demand_trend": "MODERATE",
        "top_platform": "Upwork",
        "yoy_rate_change_pct": 3.0,
        "bls_series": "OES271024",
    },
    {
        "title": "Copywriter",
        "avg_hourly_low": 30,
        "avg_hourly_high": 90,
        "demand_trend": "MODERATE",
        "top_platform": "Upwork",
        "yoy_rate_change_pct": 1.5,
        "bls_series": "OES273043",
    },
    {
        "title": "Video Editor",
        "avg_hourly_low": 35,
        "avg_hourly_high": 95,
        "demand_trend": "HIGH_DEMAND",
        "top_platform": "Fiverr",
        "yoy_rate_change_pct": 6.0,
        "bls_series": "OES274014",
    },
    {
        "title": "SEO Specialist",
        "avg_hourly_low": 40,
        "avg_hourly_high": 110,
        "demand_trend": "MODERATE",
        "top_platform": "Upwork",
        "yoy_rate_change_pct": 2.5,
        "bls_series": "OES131161",
    },
    {
        "title": "Virtual Assistant",
        "avg_hourly_low": 15,
        "avg_hourly_high": 40,
        "demand_trend": "MODERATE",
        "top_platform": "Upwork",
        "yoy_rate_change_pct": -1.0,
        "bls_series": "OES436014",
    },
    {
        "title": "Accountant",
        "avg_hourly_low": 40,
        "avg_hourly_high": 110,
        "demand_trend": "MODERATE",
        "top_platform": "Upwork",
        "yoy_rate_change_pct": 4.0,
        "bls_series": "OES132011",
    },
    {
        "title": "Financial Analyst",
        "avg_hourly_low": 55,
        "avg_hourly_high": 140,
        "demand_trend": "HIGH_DEMAND",
        "top_platform": "Toptal",
        "yoy_rate_change_pct": 7.0,
        "bls_series": "OES132051",
    },
    {
        "title": "DevOps Engineer",
        "avg_hourly_low": 80,
        "avg_hourly_high": 185,
        "demand_trend": "HIGH_DEMAND",
        "top_platform": "Toptal",
        "yoy_rate_change_pct": 11.0,
        "bls_series": "OES151244",
    },
]


def fetch_bls_hourly(series_id: str) -> float | None:
    """Fetch annual mean hourly wage from BLS OES API. Returns None on failure."""
    try:
        payload = {
            "seriesid": [series_id],
            "startyear": "2024",
            "endyear": "2024",
        }
        resp = requests.post(BLS_API_URL, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        series_data = data.get("Results", {}).get("series", [{}])[0]
        latest = series_data.get("data", [{}])[0]
        return float(latest.get("value", 0)) if latest.get("value") else None
    except Exception:
        return None


def scrape() -> dict:
    """Run B4: enrich baseline with BLS data where available, fallback to hardcoded."""
    roles_out = []
    for role in ROLES_BASELINE:
        bls_hourly = fetch_bls_hourly(role["bls_series"])
        entry = {
            "title": role["title"],
            "avg_hourly_low": role["avg_hourly_low"],
            "avg_hourly_high": role["avg_hourly_high"],
            "demand_trend": role["demand_trend"],
            "top_platform": role["top_platform"],
            "yoy_rate_change_pct": role["yoy_rate_change_pct"],
        }
        # If BLS data available, use it to anchor the midpoint
        if bls_hourly and bls_hourly > 0:
            entry["avg_hourly_low"] = max(role["avg_hourly_low"], int(bls_hourly * 0.8))
            entry["avg_hourly_high"] = max(role["avg_hourly_high"], int(bls_hourly * 1.4))
        roles_out.append(entry)
    return {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "record_count": len(roles_out),
        "roles": roles_out,
    }


def save(output_path: str = "data_cache/freelance_rates_latest.json") -> None:
    result = scrape()
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    save()
```

---

## RULES
1. All 10 roles must always be present — never drop any.
2. BLS API failure must be silently caught — fall back to hardcoded Upwork ranges.
3. demand_trend values are strictly: "HIGH_DEMAND", "MODERATE", "DECLINING".
4. avg_hourly_low must always be < avg_hourly_high.
5. yoy_rate_change_pct may be negative (rates declining).
6. generated_at must be ISO 8601 UTC (Z suffix).
7. record_count must equal len(roles).
8. Do not expose bls_series in output JSON — internal metadata only.

---

## VALIDATION CHECKLIST
- [ ] All 10 roles present in output
- [ ] record_count == 10
- [ ] generated_at is valid ISO UTC string
- [ ] avg_hourly_low < avg_hourly_high for every role
- [ ] demand_trend is one of: HIGH_DEMAND, MODERATE, DECLINING
- [ ] yoy_rate_change_pct is a float (may be negative)
- [ ] top_platform is a non-empty string
- [ ] BLS API failure does not crash the scraper
