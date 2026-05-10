---
name: Cost of Living Indexer
description: Ingests BLS regional CPI series and city-level cost snapshots to produce normalized cost-of-living indices (100 = national average) with EXPENSIVE / MODERATE / AFFORDABLE signals.
type: reference
agent: W7
division: Personal Wealth & Debt
---

# Skill: Cost of Living Indexer (W7)

## [D] Direction

**Goal:** Produce `data_cache/col_latest.json` with a city-level cost-of-living index normalized to 100 (national average), classified by signal tier.

**Steps:**
1. Fetch BLS regional CPI series: NE (`CUURA101SA0`), MW (`CUURA207SA0`), S (`CUURA319SA0`), W (`CUURA421SA0`) via `https://api.bls.gov/publicAPI/v2/timeseries/data/`.
2. Fetch national CPI-U (series `CUUR0000SA0`) for the `national_cpi` field.
3. Load static city list (STATIC_CITIES) with grocery_index, gas_avg, rent_1br, overall_index.
4. For each city, compute `signal` from `overall_index`: EXPENSIVE (>= 120), MODERATE (90–119), AFFORDABLE (< 90).
5. Sort cities by `overall_index` descending.
6. Write output JSON to `data_cache/col_latest.json`.

**Stop conditions:**
- BLS API unavailable → use STATIC_CITIES snapshot with last known `national_cpi`, log warning.
- `overall_index` <= 0 → raise ValueError.

**Guardrails:**
- Never store user addresses, relocation data, or personal location history.
- `region` must be Northeast / Midwest / South / West (BLS taxonomy).
- `rent_1br` is always an integer.
- `gas_avg` rounded to 2 decimal places.
- Never call any LLM.

## [B] Blueprints

**BLS API endpoint:**
```
https://api.bls.gov/publicAPI/v2/timeseries/data/
```

**BLS Series IDs:**
```python
BLS_SERIES = {
    "Northeast": "CUURA101SA0",
    "Midwest":   "CUURA207SA0",
    "South":     "CUURA319SA0",
    "West":      "CUURA421SA0",
}
NATIONAL_CPI_SERIES = "CUUR0000SA0"
```

**Signal formula:**
```python
if overall_index >= 120:
    signal = "EXPENSIVE"
elif overall_index >= 90:
    signal = "MODERATE"
else:
    signal = "AFFORDABLE"
```

**Representative city index values (update quarterly):**
- San Francisco, CA, West: grocery=118.5, gas=$4.85, rent=$3,200, index=178.0 → EXPENSIVE
- New York, NY, Northeast: grocery=114.2, gas=$3.75, rent=$3,500, index=187.0 → EXPENSIVE
- Chicago, IL, Midwest: grocery=104.8, gas=$3.40, rent=$1,850, index=107.0 → MODERATE
- Austin, TX, South: grocery=101.2, gas=$3.10, rent=$1,650, index=112.5 → MODERATE
- Memphis, TN, South: grocery=94.3, gas=$2.95, rent=$950, index=82.0 → AFFORDABLE

## [S] Solutions

**BLS API fetch (no auth, single series):**
```python
import requests, json

def fetch_bls_series(series_ids):
    payload = {
        "seriesid": series_ids,
        "startyear": "2025",
        "endyear": "2026",
    }
    try:
        resp = requests.post(
            "https://api.bls.gov/publicAPI/v2/timeseries/data/",
            json=payload, timeout=15
        )
        resp.raise_for_status()
        result = {}
        for s in resp.json().get("Results", {}).get("series", []):
            sid = s["seriesID"]
            vals = [d for d in s["data"] if d.get("value") not in (None, "-")]
            if vals:
                result[sid] = float(vals[0]["value"])
        return result
    except Exception as e:
        print(f"[W7] BLS fetch failed: {e} — using static snapshot")
        return {}
```

**Syntax check:**
```bash
python -m py_compile atlas_agents/wealth/col_indexer/col_indexer_scraper.py
```

## Evals

| # | Assertion | Pass Condition |
|---|-----------|---------------|
| 1 | Package importable | `importlib.import_module("atlas_agents.wealth.col_indexer")` returns without error |
| 2 | AGENT_PROMPT.md exists and non-empty | `pathlib.Path(...AGENT_PROMPT.md).stat().st_size > 0` |
| 3 | SKILL.md exists and non-empty | `pathlib.Path(...col_indexer/SKILL.md).stat().st_size > 0` |
| 4 | All schema fields documented | `national_cpi,city,state,region,grocery_index,gas_avg,rent_1br,overall_index,signal,generated_at,record_count` all in AGENT_PROMPT.md |
| 5 | All 4 BLS series IDs + 3 signals documented | `CUURA101SA0,CUURA207SA0,CUURA319SA0,CUURA421SA0,EXPENSIVE,MODERATE,AFFORDABLE` all in AGENT_PROMPT.md |
