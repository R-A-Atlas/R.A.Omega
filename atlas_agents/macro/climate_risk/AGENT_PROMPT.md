# M4 — Climate Risk / FEMA Bot Agent

## IDENTITY
Agent ID: M4  
Name: Climate Risk / FEMA Bot Agent  
Division: Macro Risk & Geopolitics  
Codename: CLIMATE_RISK  
Output File: data_cache/climate_risk_latest.json  

---

## DEFINITION
Queries the FEMA National Flood Insurance Program (NFIP) public API and NOAA climate data to monitor flood zone risk changes, insurance premium shifts, and climate-driven property risk across U.S. regions. Enables ATLAS to contextualize real estate exposure, insurance sector risk, and climate-driven macro headwinds for portfolio companies.

---

## DATA SOURCES

| Source | URL | Auth | Notes |
|--------|-----|------|-------|
| FEMA NFIP Policies API | https://www.fema.gov/api/open/v1/fimaNfipPolicies | None | OpenFEMA public API |
| FEMA Flood Map Service | https://www.fema.gov/flood-maps | None | Flood zone mapping |
| OpenFEMA API Base | https://www.fema.gov/api/open/v1/ | None | Dataset explorer |
| NOAA Climate Data | https://www.ncdc.noaa.gov/cag/national/time-series | None | National climate summaries |
| NOAA CDO API | https://www.ncdc.noaa.gov/cdo-web/api/v2/data | Token | Free token registration |

Primary Source URL: https://www.fema.gov/flood-maps

---

## OUTPUT FILE
`data_cache/climate_risk_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "record_count": 5,
  "national_flood_risk_trend": "INCREASING",
  "flood_zone_changes": [
    {
      "region": "Gulf Coast",
      "state": "LA",
      "risk_level": "EXTREME",
      "change": "INCREASING",
      "annual_premium_avg": 3200,
      "impact_on_insurance": "HIGH_PREMIUM"
    },
    {
      "region": "Southeast",
      "state": "FL",
      "risk_level": "HIGH",
      "change": "INCREASING",
      "annual_premium_avg": 2800,
      "impact_on_insurance": "HIGH_PREMIUM"
    },
    {
      "region": "Mid-Atlantic",
      "state": "NJ",
      "risk_level": "MODERATE",
      "change": "STABLE",
      "annual_premium_avg": 1100,
      "impact_on_insurance": "NORMAL"
    },
    {
      "region": "Great Plains",
      "state": "KS",
      "risk_level": "LOW",
      "change": "STABLE",
      "annual_premium_avg": 450,
      "impact_on_insurance": "LOW_PREMIUM"
    },
    {
      "region": "Pacific Northwest",
      "state": "WA",
      "risk_level": "HIGH",
      "change": "INCREASING",
      "annual_premium_avg": 1900,
      "impact_on_insurance": "HIGH_PREMIUM"
    }
  ]
}
```

### Field Definitions
- `generated_at`: ISO-8601 UTC timestamp of data fetch
- `record_count`: number of flood_zone_changes entries
- `national_flood_risk_trend`: INCREASING, STABLE, or DECREASING (aggregate)
- `flood_zone_changes[].region`: U.S. region name (string)
- `flood_zone_changes[].state`: two-letter state code
- `flood_zone_changes[].risk_level`: EXTREME, HIGH, MODERATE, or LOW (per FEMA zone)
- `flood_zone_changes[].change`: INCREASING, STABLE, or DECREASING
- `flood_zone_changes[].annual_premium_avg`: average annual NFIP premium in USD (integer)
- `flood_zone_changes[].impact_on_insurance`: UNINSURABLE, HIGH_PREMIUM, NORMAL, or LOW_PREMIUM

### Risk Level Mapping
- EXTREME: FEMA Flood Zone AE (100-year floodplain with BFE)
- HIGH: FEMA Flood Zone A (100-year floodplain)
- MODERATE: FEMA Flood Zone X500 (500-year floodplain)
- LOW: FEMA Flood Zone X (minimal flood hazard)

### Insurance Impact Mapping
- UNINSURABLE: risk_level EXTREME + change INCREASING + premium > $5,000
- HIGH_PREMIUM: annual_premium_avg > $1,500
- NORMAL: $500 - $1,500
- LOW_PREMIUM: < $500

---

## SIGNAL LOGIC

```
national_flood_risk_trend:
    INCREASING  if majority of regions show change == "INCREASING"
    DECREASING  if majority show change == "DECREASING"
    STABLE      otherwise

macro_signal:
    INCREASING → negative for homebuilders (DHI, LEN), insurance (ALL, TRV)
                 positive for reinsurers (RNR) as premiums rise
                 flag RE holdings in Gulf Coast / FL for review
    STABLE     → monitor only
    DECREASING → rare — would indicate large-scale mitigation success
```

---

## SCRAPER STRUCTURE

```python
# climate_risk_scraper.py — stub

import json
import datetime
import requests

FEMA_API_BASE = "https://www.fema.gov/api/open/v1"
FEMA_NFIP_URL = f"{FEMA_API_BASE}/fimaNfipPolicies"
FEMA_FLOOD_MAPS_URL = "https://www.fema.gov/flood-maps"
OUTPUT_PATH = "data_cache/climate_risk_latest.json"

RISK_ZONES = {
    "AE": "EXTREME",
    "A": "HIGH",
    "X500": "MODERATE",
    "X": "LOW"
}


def fetch_nfip_policies(state: str = None, limit: int = 100) -> list:
    """Fetch NFIP policy data from OpenFEMA API."""
    params = {
        "$top": limit,
        "$orderby": "reportedZipCode asc"
    }
    if state:
        params["$filter"] = f"propertyState eq '{state}'"
    resp = requests.get(FEMA_NFIP_URL, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json().get("FimaNfipPolicies", [])


def classify_risk_level(fema_zone: str) -> str:
    """Map FEMA flood zone to risk_level enum."""
    for zone_key, level in RISK_ZONES.items():
        if zone_key in fema_zone.upper():
            return level
    return "LOW"


def classify_insurance_impact(annual_premium: float, risk_level: str, change: str) -> str:
    """Determine insurance impact category."""
    if risk_level == "EXTREME" and change == "INCREASING" and annual_premium > 5000:
        return "UNINSURABLE"
    elif annual_premium > 1500:
        return "HIGH_PREMIUM"
    elif annual_premium >= 500:
        return "NORMAL"
    return "LOW_PREMIUM"


def aggregate_by_region(policies: list) -> list:
    """Group NFIP policies by region and compute aggregated risk metrics."""
    # TODO: group by state → region mapping, compute avg premium, modal risk zone
    raise NotImplementedError("Implement region aggregation from NFIP policy data")


def classify_national_trend(flood_zones: list) -> str:
    """Determine national flood risk trend from regional data."""
    counts = {"INCREASING": 0, "DECREASING": 0, "STABLE": 0}
    for zone in flood_zones:
        counts[zone.get("change", "STABLE")] += 1
    if counts["INCREASING"] > counts["DECREASING"] and counts["INCREASING"] > counts["STABLE"]:
        return "INCREASING"
    elif counts["DECREASING"] > counts["INCREASING"] and counts["DECREASING"] > counts["STABLE"]:
        return "DECREASING"
    return "STABLE"


def build_output(flood_zone_changes: list) -> dict:
    """Assemble output envelope."""
    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "record_count": len(flood_zone_changes),
        "national_flood_risk_trend": classify_national_trend(flood_zone_changes),
        "flood_zone_changes": flood_zone_changes
    }


def scrape() -> dict:
    """Main entry point."""
    policies = fetch_nfip_policies()
    flood_zone_changes = aggregate_by_region(policies)
    result = build_output(flood_zone_changes)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    data = scrape()
    print(json.dumps(data, indent=2))
```

---

## RULES
1. OpenFEMA API is public and free — no auth required for fimaNfipPolicies
2. Cache output for 24 hours — flood risk data changes slowly
3. Never use exact homeowner addresses — aggregate to region/state level only
4. If FEMA API returns 503, retry once after 30 seconds before falling back
5. `record_count` must equal `len(flood_zone_changes)`
6. All `risk_level` values must be in: EXTREME, HIGH, MODERATE, LOW
7. All `change` values must be in: INCREASING, STABLE, DECREASING
8. All `impact_on_insurance` values must be in: UNINSURABLE, HIGH_PREMIUM, NORMAL, LOW_PREMIUM

---

## VALIDATION CHECKLIST
- [ ] `generated_at` is valid ISO-8601 UTC
- [ ] `record_count` equals `len(flood_zone_changes)`
- [ ] All `risk_level` values are in: EXTREME, HIGH, MODERATE, LOW
- [ ] All `change` values are in: INCREASING, STABLE, DECREASING
- [ ] All `impact_on_insurance` values are in: UNINSURABLE, HIGH_PREMIUM, NORMAL, LOW_PREMIUM
- [ ] `national_flood_risk_trend` is INCREASING, STABLE, or DECREASING
- [ ] Each entry has: region, state, risk_level, change, annual_premium_avg, impact_on_insurance
- [ ] Output file written to `data_cache/climate_risk_latest.json`
