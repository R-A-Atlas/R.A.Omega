# W7 — Cost of Living Indexer | Division: Personal Wealth & Debt

## IDENTITY
W7 is the Cost of Living Indexer agent for the ATLAS Personal Wealth Division. It ingests BLS regional CPI data and city-level cost snapshots to produce a normalized cost-of-living index where 100 equals the national average. Signals classify cities as EXPENSIVE, MODERATE, or AFFORDABLE. No LLM calls are made.

## DEFINITION

Key terms:
- **CPI (Consumer Price Index)**: BLS measure of price changes for a basket of goods/services.
- **Overall Index**: Normalized score where 100 = national average. >100 = above-average cost. <100 = below.
- **Grocery Index**: Sub-index for food-at-home costs only (BLS food series).
- **Gas Avg**: Average retail gasoline price per gallon (USD) in the city/region.
- **Rent 1BR**: Median monthly rent for a 1-bedroom apartment in the metro area.

BLS Series IDs:
- Northeast CPI: `CUURA101SA0`
- Midwest CPI: `CUURA207SA0`
- South CPI: `CUURA319SA0`
- West CPI: `CUURA421SA0`

BLS API (no auth for single series):
- URL: `https://api.bls.gov/publicAPI/v2/timeseries/data/`

Signal thresholds:
- EXPENSIVE: overall_index >= 120
- MODERATE: 90 <= overall_index < 120
- AFFORDABLE: overall_index < 90

## DATA SOURCES

**Primary:** Bureau of Labor Statistics (BLS) CPI API — Regional Series
- URL: `https://api.bls.gov/publicAPI/v2/timeseries/data/`
- Series: `CUURA101SA0` (NE), `CUURA207SA0` (MW), `CUURA319SA0` (S), `CUURA421SA0` (W)
- No API key required for single-series queries (limited to 10 years of data).

**Secondary (city data):** Hardcoded monthly snapshot of city-level indices from publicly available sources (ERI Cost of Living Index, Council for Community and Economic Research C2ER). Updated quarterly.

## OUTPUT FILE

`data_cache/col_latest.json`

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:00:00Z",
  "national_cpi": 315.4,
  "record_count": 12,
  "cities": [
    {
      "city": "San Francisco",
      "state": "CA",
      "region": "West",
      "grocery_index": 118.5,
      "gas_avg": 4.85,
      "rent_1br": 3200,
      "overall_index": 178.0,
      "signal": "EXPENSIVE"
    },
    {
      "city": "Austin",
      "state": "TX",
      "region": "South",
      "grocery_index": 101.2,
      "gas_avg": 3.10,
      "rent_1br": 1650,
      "overall_index": 112.5,
      "signal": "MODERATE"
    },
    {
      "city": "Memphis",
      "state": "TN",
      "region": "South",
      "grocery_index": 94.3,
      "gas_avg": 2.95,
      "rent_1br": 950,
      "overall_index": 82.0,
      "signal": "AFFORDABLE"
    }
  ]
}
```

Fields:
- `generated_at` (ISO 8601 UTC): cache build timestamp
- `national_cpi` (float): latest BLS national CPI-U all-items value
- `record_count` (int): number of cities returned
- `cities` (array): one object per city
  - `city` (string): city name
  - `state` (string): 2-letter state code
  - `region` (string): one of `Northeast | Midwest | South | West`
  - `grocery_index` (float): food-at-home index (100 = national avg)
  - `gas_avg` (float): average retail gas price per gallon (USD)
  - `rent_1br` (int): median monthly 1BR rent (USD)
  - `overall_index` (float): composite cost-of-living index (100 = national avg)
  - `signal` (string): `EXPENSIVE | MODERATE | AFFORDABLE`

## SIGNAL LOGIC

```
if overall_index >= 120:
    signal = "EXPENSIVE"
elif overall_index >= 90:
    signal = "MODERATE"
else:
    signal = "AFFORDABLE"
```

`national_cpi` is sourced from BLS CUUR0000SA0 (national all-items CPI-U).
Regional CPI series (CUURA101SA0 etc.) are used to scale city-level indices.
Cities are sorted by `overall_index` descending.

## SCRAPER STRUCTURE

```python
# col_indexer_scraper.py

import requests
import json
from datetime import datetime, timezone

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_SERIES = {
    "Northeast": "CUURA101SA0",
    "Midwest": "CUURA207SA0",
    "South": "CUURA319SA0",
    "West": "CUURA421SA0",
}
OUTPUT_PATH = "data_cache/col_latest.json"

STATIC_CITIES = [
    {"city": "San Francisco", "state": "CA", "region": "West",
     "grocery_index": 118.5, "gas_avg": 4.85, "rent_1br": 3200, "overall_index": 178.0},
    {"city": "New York", "state": "NY", "region": "Northeast",
     "grocery_index": 114.2, "gas_avg": 3.75, "rent_1br": 3500, "overall_index": 187.0},
    {"city": "Chicago", "state": "IL", "region": "Midwest",
     "grocery_index": 104.8, "gas_avg": 3.40, "rent_1br": 1850, "overall_index": 107.0},
    {"city": "Atlanta", "state": "GA", "region": "South",
     "grocery_index": 98.6, "gas_avg": 3.05, "rent_1br": 1600, "overall_index": 99.5},
    {"city": "Austin", "state": "TX", "region": "South",
     "grocery_index": 101.2, "gas_avg": 3.10, "rent_1br": 1650, "overall_index": 112.5},
    {"city": "Memphis", "state": "TN", "region": "South",
     "grocery_index": 94.3, "gas_avg": 2.95, "rent_1br": 950, "overall_index": 82.0},
]


def fetch_bls_series(series_ids: list[str]) -> dict[str, float]:
    """Fetch latest CPI values for given BLS series IDs. Returns {series_id: value}."""
    ...


def compute_signal(overall_index: float) -> str:
    """Return EXPENSIVE | MODERATE | AFFORDABLE."""
    ...


def scrape() -> dict:
    """Main entry point. Returns full output schema dict."""
    ...


def save(data: dict) -> None:
    """Write data to OUTPUT_PATH as formatted JSON."""
    ...


if __name__ == "__main__":
    result = scrape()
    save(result)
    print(f"[W7] National CPI={result['national_cpi']} cities={result['record_count']} → {OUTPUT_PATH}")
```

## RULES

- NEVER store user location data, home addresses, or relocation intent beyond what is needed for index lookup.
- `region` must be one of Northeast / Midwest / South / West (BLS regional taxonomy).
- `signal` must be computed fresh from `overall_index` on every run.
- `overall_index` must be a positive float; reject zero or negative values.
- `rent_1br` is an integer (whole dollars).
- `gas_avg` is a float rounded to 2 decimal places.
- If BLS API is unreachable, use STATIC_CITIES snapshot and set `national_cpi` to last known value with warning log.
- Output file must always be valid JSON. Write error envelope on failure.
- Do not call any LLM.

## VALIDATION CHECKLIST

- [ ] `generated_at` is ISO 8601 UTC
- [ ] `national_cpi` is a positive float
- [ ] `record_count` equals `len(cities)`
- [ ] All `region` values are Northeast | Midwest | South | West
- [ ] All `signal` values are EXPENSIVE | MODERATE | AFFORDABLE
- [ ] EXPENSIVE cities have `overall_index` >= 120
- [ ] AFFORDABLE cities have `overall_index` < 90
- [ ] BLS series IDs CUURA101SA0, CUURA207SA0, CUURA319SA0, CUURA421SA0 referenced
- [ ] Output file is valid JSON
- [ ] BLS API failure triggers fallback, not a crash
