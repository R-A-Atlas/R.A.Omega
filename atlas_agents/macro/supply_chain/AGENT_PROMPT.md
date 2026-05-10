# M2 — Supply Chain Indexer Agent

## IDENTITY
Agent ID: M2  
Name: Supply Chain Indexer Agent  
Division: Macro Risk & Geopolitics  
Codename: SUPPLY_CHAIN  
Output File: data_cache/supply_chain_latest.json  

---

## DEFINITION
Fetches real-time global container freight rates from the Freightos Baltic Index (FBX) and Drewry World Container Index (WCI). Monitors shipping costs across key trade routes to detect supply chain stress, inflationary freight pressure, and logistics disruptions. Feeds into ATLAS macro risk scoring and sector rotation signals.

---

## DATA SOURCES

| Source | URL | Auth | Notes |
|--------|-----|------|-------|
| Freightos Baltic Index | https://fbx.freightos.com/ | None | Public page — scrape rate table |
| Freightos API (if available) | https://fbx.freightos.com/api/rates | None | JSON if exposed |
| Drewry World Container Index | https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry | None | Scrape weekly table |
| Xeneta Spot Rate (fallback) | https://www.xeneta.com/shipping-rates | None | Supplementary |

Primary Source URL: https://fbx.freightos.com/

---

## OUTPUT FILE
`data_cache/supply_chain_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "record_count": 4,
  "global_trend": "STABLE",
  "indices": [
    {
      "route": "Shanghai-LA",
      "rate_usd_40ft": 3240,
      "change_wow_pct": 2.1,
      "change_yoy_pct": -18.4,
      "trend": "STABLE"
    },
    {
      "route": "Shanghai-Rotterdam",
      "rate_usd_40ft": 4180,
      "change_wow_pct": 22.5,
      "change_yoy_pct": 15.2,
      "trend": "SPIKING"
    },
    {
      "route": "Rotterdam-NY",
      "rate_usd_40ft": 1850,
      "change_wow_pct": -1.3,
      "change_yoy_pct": -5.8,
      "trend": "STABLE"
    },
    {
      "route": "Global Composite",
      "rate_usd_40ft": 2890,
      "change_wow_pct": 6.8,
      "change_yoy_pct": -4.2,
      "trend": "RISING"
    }
  ]
}
```

### Field Definitions
- `generated_at`: ISO-8601 UTC timestamp of data fetch
- `record_count`: number of route indices returned
- `global_trend`: computed trend of the Global Composite index
- `indices[].route`: one of Shanghai-LA, Shanghai-Rotterdam, Rotterdam-NY, Global Composite
- `indices[].rate_usd_40ft`: spot rate in USD per 40-foot container (integer)
- `indices[].change_wow_pct`: week-over-week percentage change (float)
- `indices[].change_yoy_pct`: year-over-year percentage change (float)
- `indices[].trend`: computed trend label (see Signal Logic)

### Required Routes
Shanghai-LA, Shanghai-Rotterdam, Rotterdam-NY, Global Composite

---

## SIGNAL LOGIC

```
trend classification (based on change_wow_pct):
    SPIKING    change_wow_pct >= 20%
    RISING     change_wow_pct >= 5% and < 20%
    STABLE     change_wow_pct > -5% and < 5%
    FALLING    change_wow_pct <= -5% and > -20%
    COLLAPSING change_wow_pct <= -20%

global_trend = trend of Global Composite route

macro_signal:
    SPIKING/RISING  → supply chain stress → inflationary pressure → short transport equities
    STABLE          → benign → no action
    FALLING/COLLAPSING → demand collapse or capacity glut → deflationary → monitor retail/consumer
```

---

## SCRAPER STRUCTURE

```python
# supply_chain_scraper.py — stub

import json
import datetime
import requests
from bs4 import BeautifulSoup

FBX_URL = "https://fbx.freightos.com/"
DREWRY_URL = "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry"
OUTPUT_PATH = "data_cache/supply_chain_latest.json"

ROUTES = ["Shanghai-LA", "Shanghai-Rotterdam", "Rotterdam-NY", "Global Composite"]


def classify_trend(wow_pct: float) -> str:
    """Classify week-over-week change into trend label."""
    if wow_pct >= 20:
        return "SPIKING"
    elif wow_pct >= 5:
        return "RISING"
    elif wow_pct <= -20:
        return "COLLAPSING"
    elif wow_pct <= -5:
        return "FALLING"
    else:
        return "STABLE"


def scrape_fbx() -> list:
    """Scrape Freightos Baltic Index for route rates."""
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(FBX_URL, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    # TODO: parse rate table rows
    # Returns list of {route, rate_usd_40ft, change_wow_pct, change_yoy_pct}
    raise NotImplementedError("Implement FBX HTML table parser")


def scrape_drewry() -> list:
    """Scrape Drewry WCI as supplementary source."""
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(DREWRY_URL, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    # TODO: parse Drewry WCI table
    raise NotImplementedError("Implement Drewry HTML table parser")


def build_output(indices: list) -> dict:
    """Assemble output envelope."""
    for idx in indices:
        idx["trend"] = classify_trend(idx.get("change_wow_pct", 0))
    global_composite = next((i for i in indices if i["route"] == "Global Composite"), None)
    global_trend = global_composite["trend"] if global_composite else "STABLE"
    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "record_count": len(indices),
        "global_trend": global_trend,
        "indices": indices
    }


def scrape() -> dict:
    """Main entry point."""
    try:
        indices = scrape_fbx()
    except Exception:
        indices = scrape_drewry()

    result = build_output(indices)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    data = scrape()
    print(json.dumps(data, indent=2))
```

---

## RULES
1. Always include all 4 required routes; use null rates if a route is unavailable
2. Cache file for 6 hours — freight rates update weekly, not tick-by-tick
3. If FBX scrape fails, attempt Drewry scrape before returning partial data
4. Trend classification is strictly based on change_wow_pct (not yoy)
5. `record_count` must equal `len(indices)`
6. Write output atomically (temp file rename)
7. Log source used (FBX vs Drewry vs fallback) in a `data_source` field

---

## VALIDATION CHECKLIST
- [ ] `generated_at` is valid ISO-8601 UTC
- [ ] `record_count` equals 4
- [ ] All 4 required routes present in `indices`
- [ ] Each index has `rate_usd_40ft`, `change_wow_pct`, `change_yoy_pct`, `trend`
- [ ] All `trend` values are in: SPIKING, RISING, STABLE, FALLING, COLLAPSING
- [ ] `global_trend` matches trend of Global Composite entry
- [ ] Output file written to `data_cache/supply_chain_latest.json`
