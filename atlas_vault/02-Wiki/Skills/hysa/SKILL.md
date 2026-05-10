---
name: HYSA Tracker
description: Collects current HYSA/Money Market/CD APYs from FDIC-insured institutions and benchmarks them against the FRED FEDFUNDS rate with TOP_PICK / COMPETITIVE / AVERAGE ratings.
type: reference
agent: W4
division: Personal Wealth & Debt
---

# Skill: HYSA Tracker (W4)

## [D] Direction

**Goal:** Produce `data_cache/hysa_latest.json` with a ranked list of high-yield deposit accounts benchmarked against the current Fed Funds rate.

**Steps:**
1. Fetch current Fed Funds rate from FRED series `FEDFUNDS` (latest observation).
2. Load static account list (STATIC_ACCOUNTS) with bank, APY, min_balance, account_type.
3. For each account, compute `spread_vs_fed = apy - fed_funds_rate` and apply rating:
   - TOP_PICK: spread >= -0.50
   - COMPETITIVE: spread >= -1.50
   - AVERAGE: spread < -1.50
4. Optionally validate FDIC status by querying FDIC BankFind API for institution name.
5. Sort by `apy` descending within each `account_type`.
6. Write output JSON to `data_cache/hysa_latest.json`.

**Stop conditions:**
- FRED API unavailable → use `FALLBACK_FED_FUNDS = 4.33`, log warning.
- Non-FDIC-insured product detected → exclude from output (never include).

**Guardrails:**
- All included accounts must have `fdic_insured = true`.
- `account_type` must be HYSA / Money Market / CD only.
- Never store user account numbers or routing numbers.
- Never call any LLM.

## [B] Blueprints

**FDIC BankFind API (institution validation):**
```
https://banks.data.fdic.gov/api/institutions?filters=ACTIVE%3A1&fields=NAME,REPDTE,ASSET,STALP&limit=10&offset=0&sort_by=ASSET&sort_order=DESC&output=json
```

**FRED FEDFUNDS:**
```
https://api.stlouisfed.org/fred/series/observations?series_id=FEDFUNDS&api_key=public&file_type=json
```

**Rating formula:**
```python
spread = round(apy - fed_funds_rate, 4)
if spread >= -0.50:
    rating = "TOP_PICK"
elif spread >= -1.50:
    rating = "COMPETITIVE"
else:
    rating = "AVERAGE"
```

**Static account list (update monthly):**
- Marcus by Goldman Sachs — HYSA 4.50% APY, $0 min
- Ally Bank — HYSA 4.35% APY, $0 min
- Synchrony Bank — Money Market 4.75% APY, $0 min
- Discover Bank 12-Mo CD — CD 4.80% APY, $2,500 min

## [S] Solutions

**FRED FEDFUNDS fetch:**
```python
import requests

def fetch_fed_funds_rate(fallback=4.33):
    try:
        resp = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": "FEDFUNDS", "api_key": "public", "file_type": "json"},
            timeout=10
        )
        resp.raise_for_status()
        obs = [o for o in resp.json()["observations"] if o["value"] != "."]
        return float(sorted(obs, key=lambda x: x["date"])[-1]["value"])
    except Exception as e:
        print(f"[W4] FRED fetch failed: {e} — using fallback {fallback}")
        return fallback
```

**Syntax check:**
```bash
python -m py_compile atlas_agents/wealth/hysa/hysa_scraper.py
```

## Evals

| # | Assertion | Pass Condition |
|---|-----------|---------------|
| 1 | Package importable | `importlib.import_module("atlas_agents.wealth.hysa")` returns without error |
| 2 | AGENT_PROMPT.md exists and non-empty | `pathlib.Path(...AGENT_PROMPT.md).stat().st_size > 0` |
| 3 | SKILL.md exists and non-empty | `pathlib.Path(...hysa/SKILL.md).stat().st_size > 0` |
| 4 | All schema fields documented | `fed_funds_rate,apy,min_balance,fdic_insured,account_type,rating,spread_vs_fed,generated_at,record_count` all in AGENT_PROMPT.md |
| 5 | All 3 ratings + FDIC/FRED URLs documented | `TOP_PICK,COMPETITIVE,AVERAGE,banks.data.fdic.gov,FEDFUNDS` all in AGENT_PROMPT.md |
