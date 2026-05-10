# M7 — Inflation / CPI Bot Agent

## IDENTITY
Agent ID: M7  
Name: Inflation / CPI Bot Agent  
Division: Macro Risk & Geopolitics  
Codename: INFLATION  
Output File: data_cache/cpi_latest.json  

---

## DEFINITION
Fetches the latest Consumer Price Index (CPI) data from the Bureau of Labor Statistics (BLS) public API. Tracks headline and core CPI, month-over-month and year-over-year inflation rates, and category-level breakdowns (Food, Energy, Shelter, Medical). Provides inflation signal classification to inform ATLAS Fed policy predictions and asset allocation recommendations.

---

## DATA SOURCES

| Source | URL | Auth | Notes |
|--------|-----|------|-------|
| BLS CPI API v2 | https://api.bls.gov/publicAPI/v2/timeseries/data/ | None | Free, no registration for basic queries |
| BLS Series CUUR0000SA0 | All Urban Consumers CPI (headline) | None | Primary CPI series |
| BLS Series CUUR0000SA0L1E | Core CPI (ex food & energy) | None | Core inflation measure |
| BLS Series CUUR0000SAF1 | Food at Home | None | Food category |
| BLS Series CUUR0000SA0E | Energy | None | Energy category |
| BLS Series CUUR0000SEHA | Shelter | None | Housing/shelter |
| BLS Series CUUR0000SAM | Medical Care | None | Medical category |

Primary Source URL: https://api.bls.gov/publicAPI/v2/timeseries/data/

### BLS CPI Series IDs
| Series ID | Description |
|-----------|-------------|
| CUUR0000SA0 | CPI All Urban Consumers (headline) |
| CUUR0000SA0L1E | Core CPI (ex food & energy) |
| CUUR0000SAF1 | Food |
| CUUR0000SA0E | Energy |
| CUUR0000SEHA | Shelter |
| CUUR0000SAM | Medical Care |

---

## OUTPUT FILE
`data_cache/cpi_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "period": "2026-04",
  "cpi_index": 314.2,
  "mom_change_pct": 0.3,
  "yoy_change_pct": 3.2,
  "core_cpi_yoy_pct": 3.6,
  "inflation_signal": "ELEVATED",
  "record_count": 4,
  "categories": [
    {
      "name": "Food",
      "yoy_change_pct": 2.8,
      "contribution": 0.48
    },
    {
      "name": "Energy",
      "yoy_change_pct": -1.4,
      "contribution": -0.12
    },
    {
      "name": "Shelter",
      "yoy_change_pct": 5.1,
      "contribution": 1.82
    },
    {
      "name": "Medical Care",
      "yoy_change_pct": 3.9,
      "contribution": 0.42
    }
  ]
}
```

### Field Definitions
- `generated_at`: ISO-8601 UTC timestamp of data fetch
- `period`: YYYY-MM format of the reported month
- `cpi_index`: raw CPI index value (float, 1982-84 = 100 base)
- `mom_change_pct`: month-over-month percentage change (float)
- `yoy_change_pct`: headline CPI year-over-year percentage change (float)
- `core_cpi_yoy_pct`: core CPI (ex food & energy) year-over-year percentage change (float)
- `inflation_signal`: HOT, ELEVATED, ON_TARGET, or DEFLATIONARY (see Signal Logic)
- `record_count`: number of entries in `categories` array
- `categories[].name`: category name (Food, Energy, Shelter, Medical Care)
- `categories[].yoy_change_pct`: category-level year-over-year change (float)
- `categories[].contribution`: category's contribution to headline CPI in percentage points (float)

### Required Categories
Food, Energy, Shelter, Medical Care

---

## SIGNAL LOGIC

```
inflation_signal (based on yoy_change_pct):
    HOT          yoy_change_pct >= 4.0%
    ELEVATED     yoy_change_pct >= 2.5% and < 4.0%
    ON_TARGET    yoy_change_pct >= 1.5% and < 2.5%
    DEFLATIONARY yoy_change_pct < 1.5%

macro_implications:
    HOT          → Fed hawkish → rate hike risk → short bonds, short growth equities
                   Positive: commodities (GLD, SLV, USO), energy (XLE)
                   Negative: REITs, long-duration tech
    ELEVATED     → Fed cautious → rate cuts delayed → watch shelter/core trends
    ON_TARGET    → Fed neutral → constructive for equities broadly
    DEFLATIONARY → Fed dovish → rate cuts likely → positive for bonds, growth equities

shelter_stickiness_warning:
    if categories["Shelter"].yoy_change_pct > 5%:
        → core CPI likely to remain elevated even if energy deflates
        → Fed unlikely to cut aggressively

energy_distortion:
    if abs(categories["Energy"].yoy_change_pct) > 10%:
        → headline CPI distorted → rely more on core_cpi_yoy_pct for signal
```

---

## SCRAPER STRUCTURE

```python
# inflation_scraper.py — stub

import json
import datetime
import requests

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
OUTPUT_PATH = "data_cache/cpi_latest.json"

CPI_SERIES_MAP = {
    "CUUR0000SA0": "Headline CPI",
    "CUUR0000SA0L1E": "Core CPI",
    "CUUR0000SAF1": "Food",
    "CUUR0000SA0E": "Energy",
    "CUUR0000SEHA": "Shelter",
    "CUUR0000SAM": "Medical Care"
}

CATEGORY_SERIES = ["CUUR0000SAF1", "CUUR0000SA0E", "CUUR0000SEHA", "CUUR0000SAM"]
CATEGORY_NAMES = {
    "CUUR0000SAF1": "Food",
    "CUUR0000SA0E": "Energy",
    "CUUR0000SEHA": "Shelter",
    "CUUR0000SAM": "Medical Care"
}

# CPI weights (approximate 2026 BLS weights for contribution calculation)
CATEGORY_WEIGHTS = {
    "Food": 0.138,
    "Energy": 0.073,
    "Shelter": 0.365,
    "Medical Care": 0.092
}


def fetch_cpi_series(series_ids: list, start_year: str = "2025", end_year: str = "2026") -> dict:
    """Fetch CPI series from BLS API."""
    payload = {
        "seriesid": series_ids,
        "startyear": start_year,
        "endyear": end_year
    }
    resp = requests.post(BLS_API_URL, json=payload, timeout=20)
    resp.raise_for_status()
    result = resp.json()
    if result.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS API error: {result.get('message', 'Unknown')}")
    return {s["seriesID"]: s["data"] for s in result.get("Results", {}).get("series", [])}


def get_latest_values(series_data: list) -> tuple:
    """Return (latest, prior_month, year_ago) data points."""
    if not series_data:
        return None, None, None
    sorted_data = sorted(series_data, key=lambda x: (x["year"], x["period"]), reverse=True)
    latest = sorted_data[0]
    prior = sorted_data[1] if len(sorted_data) > 1 else None
    year_ago = next(
        (d for d in sorted_data
         if d["year"] == str(int(latest["year"]) - 1) and d["period"] == latest["period"]),
        None
    )
    return latest, prior, year_ago


def classify_signal(yoy_pct: float) -> str:
    """Classify inflation signal from headline YoY CPI."""
    if yoy_pct >= 4.0:
        return "HOT"
    elif yoy_pct >= 2.5:
        return "ELEVATED"
    elif yoy_pct >= 1.5:
        return "ON_TARGET"
    return "DEFLATIONARY"


def compute_contribution(category_name: str, yoy_pct: float) -> float:
    """Estimate category contribution to headline CPI in percentage points."""
    weight = CATEGORY_WEIGHTS.get(category_name, 0.05)
    return round(weight * yoy_pct / 100 * 100, 4)


def build_categories(series_data: dict) -> list:
    """Build categories list from BLS series data."""
    categories = []
    for series_id in CATEGORY_SERIES:
        name = CATEGORY_NAMES[series_id]
        data = series_data.get(series_id, [])
        latest, _, year_ago = get_latest_values(data)
        if not latest or not year_ago:
            continue
        yoy = round(
            ((float(latest["value"]) - float(year_ago["value"])) / float(year_ago["value"])) * 100, 2
        )
        categories.append({
            "name": name,
            "yoy_change_pct": yoy,
            "contribution": compute_contribution(name, yoy)
        })
    return categories


def scrape() -> dict:
    """Main entry point."""
    all_series = list(CPI_SERIES_MAP.keys())
    series_data = fetch_cpi_series(all_series)

    headline_data = series_data.get("CUUR0000SA0", [])
    core_data = series_data.get("CUUR0000SA0L1E", [])

    h_latest, h_prior, h_year_ago = get_latest_values(headline_data)
    c_latest, _, c_year_ago = get_latest_values(core_data)

    cpi_index = float(h_latest["value"]) if h_latest else 0.0
    mom_pct = round(
        ((float(h_latest["value"]) - float(h_prior["value"])) / float(h_prior["value"])) * 100, 3
    ) if h_prior else 0.0
    yoy_pct = round(
        ((float(h_latest["value"]) - float(h_year_ago["value"])) / float(h_year_ago["value"])) * 100, 2
    ) if h_year_ago else 0.0
    core_yoy = round(
        ((float(c_latest["value"]) - float(c_year_ago["value"])) / float(c_year_ago["value"])) * 100, 2
    ) if c_latest and c_year_ago else 0.0

    period = f"{h_latest['year']}-{h_latest['period'].replace('M', '')}" if h_latest else ""
    categories = build_categories(series_data)

    result = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "period": period,
        "cpi_index": cpi_index,
        "mom_change_pct": mom_pct,
        "yoy_change_pct": yoy_pct,
        "core_cpi_yoy_pct": core_yoy,
        "inflation_signal": classify_signal(yoy_pct),
        "record_count": len(categories),
        "categories": categories
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
1. BLS API v2 is free — use POST for multi-series requests (up to 25 series)
2. Cache output for 6 hours — CPI is a monthly release
3. `inflation_signal` must be derived from `yoy_change_pct`, not `mom_change_pct`
4. `record_count` must equal 4 (all required categories present)
5. `contribution` values must use BLS CPI component weights, not arbitrary estimates
6. If BLS API fails, return last cached file if < 7 days old with a `stale: true` flag
7. `period` format must be YYYY-MM

---

## VALIDATION CHECKLIST
- [ ] `generated_at` is valid ISO-8601 UTC
- [ ] `period` is valid YYYY-MM format
- [ ] `cpi_index` is a positive float (typical range 280-350 in 2026)
- [ ] `mom_change_pct` and `yoy_change_pct` are floats
- [ ] `core_cpi_yoy_pct` is a float
- [ ] `inflation_signal` is one of: HOT, ELEVATED, ON_TARGET, DEFLATIONARY
- [ ] `record_count` equals 4
- [ ] All 4 categories present: Food, Energy, Shelter, Medical Care
- [ ] Each category has: name, yoy_change_pct, contribution
- [ ] Output file written to `data_cache/cpi_latest.json`
