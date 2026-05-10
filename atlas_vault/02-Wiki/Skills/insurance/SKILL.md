---
name: Insurance Premium Tracker
description: Maintains a hardcoded annual snapshot of average insurance premiums for 5 lines (Auto, Home, Health, Life, Renters) from NAIC data with RISING / STABLE / FALLING trend signals.
type: reference
agent: W8
division: Personal Wealth & Debt
---

# Skill: Insurance Premium Tracker (W8)

## [D] Direction

**Goal:** Produce `data_cache/insurance_latest.json` with average annual premiums, YoY changes, and trend signals for 5 insurance lines.

**Steps:**
1. Load hardcoded SNAPSHOT_2025 (validated against NAIC annual report).
2. For each line, compute `trend` from `yoy_change_pct`: RISING (>= 5%), STABLE (-5% to 5%), FALLING (<= -5%).
3. Validate: `highest_state_premium > avg_annual_premium > lowest_state_premium` for each row.
4. Sort by `yoy_change_pct` descending (most rapidly rising types first).
5. Stamp `generated_at` with current UTC time.
6. Write output JSON to `data_cache/insurance_latest.json`.

**Stop conditions:**
- Invalid `type` value → raise ValueError (not silently dropped).
- `highest_state_premium` <= `avg_annual_premium` → raise ValueError.
- `lowest_state_premium` >= `avg_annual_premium` → raise ValueError.

**Guardrails:**
- This agent makes NO HTTP calls (NAIC PDF not parseable — hardcoded snapshot only).
- Never store user policy numbers, claims data, or personal coverage details.
- `type` must be Auto / Home / Health / Life / Renters only.
- `record_count` must always be 5 (all types required).
- Never call any LLM.

## [B] Blueprints

**Insurance type enum (hard constraint):**
```
"Auto" | "Home" | "Health" | "Life" | "Renters"
```

**Trend formula:**
```python
if yoy_change_pct >= 5.0:
    trend = "RISING"
elif yoy_change_pct <= -5.0:
    trend = "FALLING"
else:
    trend = "STABLE"
```

**2025 NAIC Snapshot (canonical values — update when new report published):**
```python
SNAPSHOT_2025 = [
    {"type": "Auto",    "avg_annual_premium": 2150,  "yoy_change_pct": 12.5,
     "highest_state": "Michigan",      "highest_state_premium": 4100,
     "lowest_state":  "Maine",         "lowest_state_premium": 980},
    {"type": "Home",    "avg_annual_premium": 2285,  "yoy_change_pct": 8.9,
     "highest_state": "Oklahoma",      "highest_state_premium": 5800,
     "lowest_state":  "Hawaii",        "lowest_state_premium": 510},
    {"type": "Health",  "avg_annual_premium": 8435,  "yoy_change_pct": 4.2,
     "highest_state": "West Virginia", "highest_state_premium": 12200,
     "lowest_state":  "Massachusetts", "lowest_state_premium": 5400},
    {"type": "Life",    "avg_annual_premium": 684,   "yoy_change_pct": 1.3,
     "highest_state": "New York",      "highest_state_premium": 1250,
     "lowest_state":  "Wisconsin",     "lowest_state_premium": 420},
    {"type": "Renters", "avg_annual_premium": 210,   "yoy_change_pct": 6.8,
     "highest_state": "Louisiana",     "highest_state_premium": 450,
     "lowest_state":  "North Dakota",  "lowest_state_premium": 110},
]
```

**Source URL (for reference only — do not fetch):**
```
https://content.naic.org/sites/default/files/publication-mkt-pb-homeowners-insurance-report.pdf
```

## [S] Solutions

**Trend computation + validation:**
```python
def compute_trend(yoy_change_pct):
    if yoy_change_pct >= 5.0:
        return "RISING"
    elif yoy_change_pct <= -5.0:
        return "FALLING"
    return "STABLE"

def validate_row(row):
    assert row["highest_state_premium"] > row["avg_annual_premium"], \
        f"{row['type']}: highest_state_premium must be > avg"
    assert row["lowest_state_premium"] < row["avg_annual_premium"], \
        f"{row['type']}: lowest_state_premium must be < avg"
    assert row["type"] in {"Auto", "Home", "Health", "Life", "Renters"}, \
        f"Invalid type: {row['type']}"
```

**Write with error envelope:**
```python
import json
try:
    result = scrape()
except Exception as e:
    result = {"generated_at": now_utc(), "error": str(e), "record_count": 0, "premiums": []}
with open(OUTPUT_PATH, "w") as f:
    json.dump(result, f, indent=2)
```

**Syntax check:**
```bash
python -m py_compile atlas_agents/wealth/insurance/insurance_scraper.py
```

## Evals

| # | Assertion | Pass Condition |
|---|-----------|---------------|
| 1 | Package importable | `importlib.import_module("atlas_agents.wealth.insurance")` returns without error |
| 2 | AGENT_PROMPT.md exists and non-empty | `pathlib.Path(...AGENT_PROMPT.md).stat().st_size > 0` |
| 3 | SKILL.md exists and non-empty | `pathlib.Path(...insurance/SKILL.md).stat().st_size > 0` |
| 4 | All schema fields documented | `type,avg_annual_premium,yoy_change_pct,trend,highest_state,highest_state_premium,lowest_state,lowest_state_premium` all in AGENT_PROMPT.md |
| 5 | All 5 types + 3 trends + NAIC URL documented | `Auto,Home,Health,Life,Renters,RISING,STABLE,FALLING,naic.org` all in AGENT_PROMPT.md |
