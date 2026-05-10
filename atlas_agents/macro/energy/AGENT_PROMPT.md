# M3 — Energy Grid Monitor Agent

## IDENTITY
Agent ID: M3  
Name: Energy Grid Monitor Agent  
Division: Macro Risk & Geopolitics  
Codename: ENERGY  
Output File: data_cache/energy_latest.json  

---

## DEFINITION
Fetches electricity generation mix, retail electricity prices, and national gasoline prices from the U.S. Energy Information Administration (EIA) public APIs. Monitors the grid's transition toward renewables versus fossil fuels, flags energy price spikes, and feeds macro risk signals into ATLAS for energy-sector exposure assessment.

---

## DATA SOURCES

| Source | URL | Auth | Notes |
|--------|-----|------|-------|
| EIA Retail Electricity Prices | https://api.eia.gov/v2/electricity/retail-sales/data/?api_key=&frequency=monthly&data[0]=price&facets[sectorName][]=all-sectors | None | No API key required for basic queries |
| EIA Gas Prices (weekly) | https://api.eia.gov/v2/petroleum/pri/gnd/data/?api_key=&frequency=weekly | None | National average gasoline price |
| EIA Electricity Generation Mix | https://api.eia.gov/v2/electricity/electric-power-operational-data/data/?api_key=&frequency=monthly | None | Generation by fuel type |

Primary Source URL: https://api.eia.gov/v2/

---

## OUTPUT FILE
`data_cache/energy_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "electricity_avg_kwh_cents": 12.84,
  "gas_national_avg_gallon": 3.42,
  "renewables_pct_grid": 24.7,
  "grid_trend": "GREENING",
  "record_count": 7,
  "breakdown": [
    {
      "source": "Coal",
      "pct_of_grid": 16.2,
      "yoy_change_pct": -3.1
    },
    {
      "source": "Natural Gas",
      "pct_of_grid": 43.5,
      "yoy_change_pct": 1.2
    },
    {
      "source": "Nuclear",
      "pct_of_grid": 18.4,
      "yoy_change_pct": 0.0
    },
    {
      "source": "Wind",
      "pct_of_grid": 10.2,
      "yoy_change_pct": 2.4
    },
    {
      "source": "Solar",
      "pct_of_grid": 6.8,
      "yoy_change_pct": 3.1
    },
    {
      "source": "Hydro",
      "pct_of_grid": 6.4,
      "yoy_change_pct": -0.5
    },
    {
      "source": "Other",
      "pct_of_grid": 2.5,
      "yoy_change_pct": 0.2
    }
  ]
}
```

### Field Definitions
- `generated_at`: ISO-8601 UTC timestamp of data fetch
- `electricity_avg_kwh_cents`: National average retail electricity price in cents per kWh (float)
- `gas_national_avg_gallon`: National average gasoline price in USD per gallon (float)
- `renewables_pct_grid`: Combined percentage of Wind + Solar + Hydro + Other renewables (float)
- `grid_trend`: GREENING, STABLE, or FOSSIL_RECOVERY (see Signal Logic)
- `record_count`: number of entries in `breakdown` array
- `breakdown[].source`: one of Coal, Natural Gas, Nuclear, Wind, Solar, Hydro, Other
- `breakdown[].pct_of_grid`: percentage share of total electricity generation (float)
- `breakdown[].yoy_change_pct`: year-over-year change in percentage points (float)

### Required Sources
Coal, Natural Gas, Nuclear, Wind, Solar, Hydro, Other

---

## SIGNAL LOGIC

```
renewables_pct_grid = sum of Wind + Solar + Hydro + Other pct_of_grid

renewables_yoy_delta = sum of Wind + Solar + Hydro + Other yoy_change_pct

grid_trend:
    GREENING       renewables_yoy_delta >= 2.0 pct points
    STABLE         renewables_yoy_delta > -2.0 and < 2.0
    FOSSIL_RECOVERY renewables_yoy_delta <= -2.0

macro_signal:
    GREENING       → positive for clean energy ETFs (ICLN, TAN), negative for coal
    STABLE         → sector neutral
    FOSSIL_RECOVERY → positive for XLE, DVN, MPC; monitor inflation risk
```

---

## SCRAPER STRUCTURE

```python
# energy_scraper.py — stub

import json
import datetime
import requests

EIA_BASE = "https://api.eia.gov/v2"
EIA_ELECTRICITY_URL = f"{EIA_BASE}/electricity/retail-sales/data/"
EIA_GAS_URL = f"{EIA_BASE}/petroleum/pri/gnd/data/"
EIA_GENERATION_URL = f"{EIA_BASE}/electricity/electric-power-operational-data/data/"
OUTPUT_PATH = "data_cache/energy_latest.json"

RENEWABLE_SOURCES = {"Wind", "Solar", "Hydro", "Other"}
ALL_SOURCES = ["Coal", "Natural Gas", "Nuclear", "Wind", "Solar", "Hydro", "Other"]


def fetch_electricity_price() -> float:
    """Fetch national average retail electricity price from EIA."""
    params = {
        "frequency": "monthly",
        "data[0]": "price",
        "facets[sectorName][]": "all-sectors",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 1
    }
    resp = requests.get(EIA_ELECTRICITY_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return float(data["response"]["data"][0]["price"])


def fetch_gas_price() -> float:
    """Fetch national average gasoline price from EIA weekly series."""
    params = {
        "frequency": "weekly",
        "data[0]": "value",
        "facets[duoarea][]": "NUS",
        "facets[product][]": "EPM0",
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 1
    }
    resp = requests.get(EIA_GAS_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return float(data["response"]["data"][0]["value"])


def fetch_generation_mix() -> list:
    """Fetch electricity generation by fuel type from EIA."""
    # Returns list of {source, pct_of_grid, yoy_change_pct}
    raise NotImplementedError("Implement EIA generation mix parser")


def classify_grid_trend(breakdown: list) -> str:
    """Classify renewable growth trend."""
    renewable_delta = sum(
        b.get("yoy_change_pct", 0)
        for b in breakdown
        if b["source"] in RENEWABLE_SOURCES
    )
    if renewable_delta >= 2.0:
        return "GREENING"
    elif renewable_delta <= -2.0:
        return "FOSSIL_RECOVERY"
    return "STABLE"


def build_output(electricity_price: float, gas_price: float, breakdown: list) -> dict:
    """Assemble output envelope."""
    renewables_pct = sum(
        b.get("pct_of_grid", 0) for b in breakdown if b["source"] in RENEWABLE_SOURCES
    )
    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "electricity_avg_kwh_cents": electricity_price,
        "gas_national_avg_gallon": gas_price,
        "renewables_pct_grid": round(renewables_pct, 2),
        "grid_trend": classify_grid_trend(breakdown),
        "record_count": len(breakdown),
        "breakdown": breakdown
    }


def scrape() -> dict:
    """Main entry point."""
    electricity_price = fetch_electricity_price()
    gas_price = fetch_gas_price()
    breakdown = fetch_generation_mix()
    result = build_output(electricity_price, gas_price, breakdown)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    data = scrape()
    print(json.dumps(data, indent=2))
```

---

## RULES
1. EIA API is free and does not require an API key for basic queries
2. Cache electricity data for 24 hours (monthly updates), gas for 12 hours (weekly)
3. If EIA generation mix endpoint unavailable, use FRED or EIA bulk download as fallback
4. `record_count` must equal 7 (all required sources present)
5. `renewables_pct_grid` must equal sum of Wind + Solar + Hydro + Other shares
6. Percentage shares must sum to approximately 100% (±2% tolerance for rounding)
7. Write output atomically

---

## VALIDATION CHECKLIST
- [ ] `generated_at` is valid ISO-8601 UTC
- [ ] `electricity_avg_kwh_cents` is a positive float (typical range 8-25)
- [ ] `gas_national_avg_gallon` is a positive float (typical range 2-6)
- [ ] `record_count` equals 7
- [ ] All 7 required sources present in `breakdown`
- [ ] `renewables_pct_grid` matches computed sum of renewable sources
- [ ] `grid_trend` is one of: GREENING, STABLE, FOSSIL_RECOVERY
- [ ] `breakdown` pct_of_grid values sum to ~100% (±2%)
- [ ] Output file written to `data_cache/energy_latest.json`
