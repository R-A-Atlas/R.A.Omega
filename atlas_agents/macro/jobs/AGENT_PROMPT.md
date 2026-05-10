# M6 — Job Market / BLS Bot Agent

## IDENTITY
Agent ID: M6  
Name: Job Market / BLS Bot Agent  
Division: Macro Risk & Geopolitics  
Codename: JOBS  
Output File: data_cache/jobs_latest.json  

---

## DEFINITION
Fetches the latest U.S. employment data from the Bureau of Labor Statistics (BLS) public API. Retrieves total nonfarm payroll, unemployment rate, and sector-level job counts for 9 major sectors. Synthesizes labor market health signals to inform ATLAS macro regime assessment and sector rotation recommendations.

---

## DATA SOURCES

| Source | URL | Auth | Notes |
|--------|-----|------|-------|
| BLS Public API v2 | https://api.bls.gov/publicAPI/v2/timeseries/data/ | None | Free, no registration for basic queries |
| BLS Series CES0000000001 | Total nonfarm payroll (thousands) | None | Main payroll series |
| BLS Series LNS14000000 | Civilian unemployment rate (%) | None | U-3 unemployment |
| BLS Sector Series | See sector table below | None | 9 supersector series |

Primary Source URL: https://api.bls.gov/publicAPI/v2/timeseries/data/

### BLS Series IDs
| Series ID | Sector |
|-----------|--------|
| CES0000000001 | Total Nonfarm |
| LNS14000000 | Unemployment Rate |
| CES1000000001 | Mining & Logging |
| CES2000000001 | Construction |
| CES3000000001 | Manufacturing |
| CES4000000001 | Trade, Transportation & Utilities |
| CES5000000001 | Information |
| CES6000000001 | Financial Activities |
| CES6500000001 | Professional & Business Services |
| CES7000000001 | Leisure & Hospitality |
| CES8000000001 | Government |

---

## OUTPUT FILE
`data_cache/jobs_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "period": "2026-04",
  "unemployment_rate": 4.1,
  "jobs_added_thousands": 175,
  "prior_month_revision_thousands": 12,
  "labor_market_signal": "HEALTHY",
  "record_count": 9,
  "sector_breakdown": [
    {
      "sector": "Mining & Logging",
      "jobs_thousands": 642,
      "mom_change_thousands": 2,
      "yoy_change_pct": -1.2
    },
    {
      "sector": "Construction",
      "jobs_thousands": 8240,
      "mom_change_thousands": 14,
      "yoy_change_pct": 2.8
    },
    {
      "sector": "Manufacturing",
      "jobs_thousands": 12980,
      "mom_change_thousands": -8,
      "yoy_change_pct": -0.6
    },
    {
      "sector": "Trade, Transportation & Utilities",
      "jobs_thousands": 27400,
      "mom_change_thousands": 22,
      "yoy_change_pct": 1.1
    },
    {
      "sector": "Information",
      "jobs_thousands": 3020,
      "mom_change_thousands": -5,
      "yoy_change_pct": -3.4
    },
    {
      "sector": "Financial Activities",
      "jobs_thousands": 9180,
      "mom_change_thousands": 6,
      "yoy_change_pct": 0.9
    },
    {
      "sector": "Professional & Business Services",
      "jobs_thousands": 22800,
      "mom_change_thousands": 18,
      "yoy_change_pct": 1.7
    },
    {
      "sector": "Leisure & Hospitality",
      "jobs_thousands": 16900,
      "mom_change_thousands": 31,
      "yoy_change_pct": 2.3
    },
    {
      "sector": "Government",
      "jobs_thousands": 22600,
      "mom_change_thousands": 5,
      "yoy_change_pct": 0.4
    }
  ]
}
```

### Field Definitions
- `generated_at`: ISO-8601 UTC timestamp of data fetch
- `period`: YYYY-MM format of the reported month
- `unemployment_rate`: U-3 civilian unemployment rate (float, percent)
- `jobs_added_thousands`: total nonfarm payroll change from prior month (integer, thousands)
- `prior_month_revision_thousands`: revision to previous month's jobs figure (integer, thousands)
- `labor_market_signal`: STRONG, HEALTHY, WEAK, or RECESSIONARY (see Signal Logic)
- `record_count`: number of sectors in `sector_breakdown`
- `sector_breakdown[].sector`: sector name string
- `sector_breakdown[].jobs_thousands`: total employment in sector (integer, thousands)
- `sector_breakdown[].mom_change_thousands`: month-over-month change (integer, thousands)
- `sector_breakdown[].yoy_change_pct`: year-over-year percentage change (float)

---

## SIGNAL LOGIC

```
labor_market_signal:
    STRONG       jobs_added_thousands >= 200 AND unemployment_rate <= 4.5
    HEALTHY      jobs_added_thousands >= 100 AND NOT STRONG
    WEAK         jobs_added_thousands >= 0 AND jobs_added_thousands < 100
    RECESSIONARY jobs_added_thousands < 0

macro_signal:
    STRONG       → risk-on, equities positive, Fed rate cut less likely
    HEALTHY      → stable expansion, monitor next CPI
    WEAK         → watch for Fed pivot signal, defensive rotation
    RECESSIONARY → high alert: recession indicator, add bonds, reduce cyclicals

sector_rotation:
    Information jobs down YoY  → tech sector pressure (FAANG scrutiny)
    Leisure up MoM             → consumer discretionary positive
    Manufacturing down         → industrial sector caution (DE, CAT)
    Government down            → budget pressure (watch defense)
```

---

## SCRAPER STRUCTURE

```python
# jobs_scraper.py — stub

import json
import datetime
import requests

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
OUTPUT_PATH = "data_cache/jobs_latest.json"

SERIES_MAP = {
    "CES0000000001": "Total Nonfarm",
    "LNS14000000": "Unemployment Rate",
    "CES1000000001": "Mining & Logging",
    "CES2000000001": "Construction",
    "CES3000000001": "Manufacturing",
    "CES4000000001": "Trade, Transportation & Utilities",
    "CES5000000001": "Information",
    "CES6000000001": "Financial Activities",
    "CES6500000001": "Professional & Business Services",
    "CES7000000001": "Leisure & Hospitality",
    "CES8000000001": "Government"
}

SECTOR_SERIES = [k for k in SERIES_MAP if k not in ("CES0000000001", "LNS14000000")]


def fetch_bls_series(series_ids: list, start_year: str = "2025", end_year: str = "2026") -> dict:
    """Fetch multiple BLS series in a single API call."""
    payload = {
        "seriesid": series_ids,
        "startyear": start_year,
        "endyear": end_year
    }
    resp = requests.post(BLS_API_URL, json=payload, timeout=20)
    resp.raise_for_status()
    result = resp.json()
    if result.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS API error: {result.get('message', 'Unknown error')}")
    return {s["seriesID"]: s["data"] for s in result.get("Results", {}).get("series", [])}


def get_latest_value(series_data: list) -> tuple:
    """Extract most recent and prior month values from BLS series data."""
    if not series_data:
        return None, None, None
    sorted_data = sorted(series_data, key=lambda x: (x["year"], x["period"]), reverse=True)
    latest = sorted_data[0]
    prior = sorted_data[1] if len(sorted_data) > 1 else None
    year_ago = next(
        (d for d in sorted_data if d["year"] == str(int(latest["year"]) - 1)
         and d["period"] == latest["period"]), None
    )
    return latest, prior, year_ago


def classify_signal(jobs_added: int, unemployment: float) -> str:
    """Classify labor market signal."""
    if jobs_added < 0:
        return "RECESSIONARY"
    elif jobs_added >= 200 and unemployment <= 4.5:
        return "STRONG"
    elif jobs_added >= 100:
        return "HEALTHY"
    return "WEAK"


def build_sector_breakdown(series_data: dict) -> list:
    """Build sector breakdown list from BLS series data."""
    sectors = []
    for series_id in SECTOR_SERIES:
        sector_name = SERIES_MAP[series_id]
        data = series_data.get(series_id, [])
        latest, prior, year_ago = get_latest_value(data)
        if not latest:
            continue
        current_val = float(latest["value"])
        prior_val = float(prior["value"]) if prior else current_val
        year_ago_val = float(year_ago["value"]) if year_ago else current_val
        yoy_pct = round(((current_val - year_ago_val) / year_ago_val) * 100, 2) if year_ago_val else 0
        sectors.append({
            "sector": sector_name,
            "jobs_thousands": int(current_val),
            "mom_change_thousands": int(current_val - prior_val),
            "yoy_change_pct": yoy_pct
        })
    return sectors


def scrape() -> dict:
    """Main entry point."""
    all_series = list(SERIES_MAP.keys())
    series_data = fetch_bls_series(all_series)

    nonfarm_data = series_data.get("CES0000000001", [])
    unemp_data = series_data.get("LNS14000000", [])

    nonfarm_latest, nonfarm_prior, _ = get_latest_value(nonfarm_data)
    unemp_latest, _, _ = get_latest_value(unemp_data)

    jobs_added = int(float(nonfarm_latest["value"]) - float(nonfarm_prior["value"])) if nonfarm_prior else 0
    unemployment_rate = float(unemp_latest["value"]) if unemp_latest else 0.0
    period = f"{nonfarm_latest['year']}-{nonfarm_latest['period'].replace('M', '')}" if nonfarm_latest else ""

    sector_breakdown = build_sector_breakdown(series_data)

    result = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "period": period,
        "unemployment_rate": unemployment_rate,
        "jobs_added_thousands": jobs_added,
        "prior_month_revision_thousands": 0,  # TODO: fetch from BLS benchmark revision
        "labor_market_signal": classify_signal(jobs_added, unemployment_rate),
        "record_count": len(sector_breakdown),
        "sector_breakdown": sector_breakdown
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    data = scrape()
    print(json.dumps(data, indent=2))
```

---

## RULES
1. BLS API v2 is free with no registration for up to 25 series per request
2. Cache output for 6 hours — BLS releases monthly, not tick-by-tick
3. Use POST endpoint (not GET) for multi-series requests
4. `record_count` must equal 9 (all required sectors)
5. `labor_market_signal` must be one of: STRONG, HEALTHY, WEAK, RECESSIONARY
6. If BLS API fails, log error and return last cached file if < 7 days old
7. `period` format must be YYYY-MM (e.g., "2026-04")

---

## VALIDATION CHECKLIST
- [ ] `generated_at` is valid ISO-8601 UTC
- [ ] `period` is valid YYYY-MM format
- [ ] `unemployment_rate` is a float between 0 and 20
- [ ] `jobs_added_thousands` is an integer
- [ ] `labor_market_signal` is one of: STRONG, HEALTHY, WEAK, RECESSIONARY
- [ ] `record_count` equals 9
- [ ] All 9 required sectors present in `sector_breakdown`
- [ ] Each sector has: jobs_thousands, mom_change_thousands, yoy_change_pct
- [ ] Output file written to `data_cache/jobs_latest.json`
