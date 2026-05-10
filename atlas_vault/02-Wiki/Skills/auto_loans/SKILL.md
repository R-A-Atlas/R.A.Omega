---
name: Auto Loan Scanner
description: Retrieves current auto loan rate benchmarks from FRED and computes week-over-week trend signals for 5 standard loan terms (24–72 months).
type: reference
agent: W2
division: Personal Wealth & Debt
---

# Skill: Auto Loan Scanner (W2)

## [D] Direction

**Goal:** Produce `data_cache/auto_loans_latest.json` containing a 5-row rate table for auto loan terms with WoW trend signal (RISING / FALLING / STABLE).

**Steps:**
1. Fetch latest observations from FRED series `DTCTHFNM` (new car 48-month commercial bank rate).
2. Extract the two most recent observations to compute WoW change on the 60-month equivalent rate.
3. Apply trend threshold: WoW >= 0.10% → RISING; WoW <= -0.10% → FALLING; else STABLE.
4. Build a 5-row rate table for terms [24, 36, 48, 60, 72] months, estimating credit union (-0.70%) and dealer (+0.75%) spreads from the FRED base rate.
5. Determine `period` from the latest FRED observation date.
6. Write output JSON to `data_cache/auto_loans_latest.json`.

**Stop conditions:**
- FRED API unavailable → use STATIC_RATES with `trend = "STABLE"` and log warning.
- FRED returns null/negative value → raise ValueError, use fallback.

**Guardrails:**
- Never store user VINs, credit scores, or personal loan applications.
- `term_months` values are strictly [24, 36, 48, 60, 72] — no custom terms.
- Never call any LLM.

## [B] Blueprints

**FRED series:**
- `TERMCBCCALLNS`: credit card baseline reference
- `DTCTHFNM`: new car installment loan rate (primary)
- URL: `https://api.stlouisfed.org/fred/series/observations?series_id=DTCTHFNM&api_key=public&file_type=json`

**Trend formula:**
```python
curr = float(observations[-1]["value"])
prev = float(observations[-2]["value"])
wow_change = round(curr - prev, 4)

if wow_change >= 0.10:
    trend = "RISING"
elif wow_change <= -0.10:
    trend = "FALLING"
else:
    trend = "STABLE"
```

**Rate spread model:**
```python
cu_rate  = round(base_rate - 0.70, 2)   # credit union advantage
dlr_rate = round(base_rate + 0.75, 2)   # dealer/bank premium
```

**Static fallback rates (update quarterly):**
```python
STATIC_RATES = {24: 6.45, 36: 6.85, 48: 7.10, 60: 7.45, 72: 7.90}
```

## [S] Solutions

**FRED fetch with fallback:**
```python
import requests

def fetch_fred_series(series_id, api_key="public"):
    try:
        resp = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
            timeout=10
        )
        resp.raise_for_status()
        obs = [o for o in resp.json()["observations"] if o["value"] != "."]
        return sorted(obs, key=lambda x: x["date"])
    except Exception as e:
        print(f"[W2] FRED fetch failed: {e} — using static fallback")
        return []
```

**Syntax check:**
```bash
python -m py_compile atlas_agents/wealth/auto_loans/auto_loans_scraper.py
```

## Evals

| # | Assertion | Pass Condition |
|---|-----------|---------------|
| 1 | Package importable | `importlib.import_module("atlas_agents.wealth.auto_loans")` returns without error |
| 2 | AGENT_PROMPT.md exists and non-empty | `pathlib.Path(...AGENT_PROMPT.md).stat().st_size > 0` |
| 3 | SKILL.md exists and non-empty | `pathlib.Path(...auto_loans/SKILL.md).stat().st_size > 0` |
| 4 | All schema fields documented | `generated_at,record_count,period,trend,wow_change_60mo,term_months,avg_rate,credit_union_rate,dealer_rate` all in AGENT_PROMPT.md |
| 5 | All 3 trends + FRED series documented | `RISING`, `FALLING`, `STABLE`, `DTCTHFNM`, `TERMCBCCALLNS` all in AGENT_PROMPT.md |
