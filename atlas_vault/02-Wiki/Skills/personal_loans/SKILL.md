---
name: Personal Loan Screener
description: Benchmarks personal loan offerings against the FRED TERMCBPER24NS average rate and assigns COMPETITIVE / AVERAGE ratings across four lender categories.
type: reference
agent: W6
division: Personal Wealth & Debt
---

# Skill: Personal Loan Screener (W6)

## [D] Direction

**Goal:** Produce `data_cache/personal_loans_latest.json` with a rated list of personal loan offerings benchmarked against the FRED 24-month personal loan average rate.

**Steps:**
1. Fetch latest observation from FRED series `TERMCBPER24NS` (24-month personal loan commercial bank rate).
2. Load static lender list (STATIC_LOANS) with rate ranges, max amounts, terms, credit minimums, and categories.
3. For each loan, apply rating: COMPETITIVE if `rate_low <= fred_avg - 2.0%`, else AVERAGE.
4. Sort: COMPETITIVE first, then AVERAGE; within tier sort by `rate_low` ascending.
5. Write output JSON to `data_cache/personal_loans_latest.json`.

**Stop conditions:**
- FRED API unavailable → use `FALLBACK_FRED_AVG = 11.48`, log warning.
- `rate_low >= rate_high` → raise ValueError before writing output.
- Invalid category → raise ValueError.

**Guardrails:**
- Never store SSNs, credit reports, or personal loan applications.
- `category` must be Online Lender / Credit Union / Bank / Marketplace only.
- `credit_score_min` must be in [300, 850] (valid FICO range).
- Never call any LLM.

## [B] Blueprints

**FRED series:** `TERMCBPER24NS`
- URL: `https://api.stlouisfed.org/fred/series/observations?series_id=TERMCBPER24NS&api_key=public&file_type=json`

**Rating formula:**
```python
if loan["rate_low"] <= fred_avg - 2.0:
    rating = "COMPETITIVE"
else:
    rating = "AVERAGE"
```

**Category enum:**
```
"Online Lender" | "Credit Union" | "Bank" | "Marketplace"
```

**Static lender list (update quarterly):**
- LightStream: 6.99–25.49%, $100K max, 144mo, 660 FICO, Online Lender
- SoFi: 8.99–29.99%, $100K max, 84mo, 650 FICO, Online Lender
- Navy Federal CU: 7.49–18.00%, $50K max, 60mo, 620 FICO, Credit Union
- Wells Fargo: 7.49–23.74%, $100K max, 84mo, 660 FICO, Bank

## [S] Solutions

**FRED fetch with fallback:**
```python
import requests

def fetch_fred_avg(series_id="TERMCBPER24NS", api_key="public", fallback=11.48):
    try:
        resp = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
            timeout=10
        )
        resp.raise_for_status()
        obs = [o for o in resp.json()["observations"] if o["value"] != "."]
        return float(sorted(obs, key=lambda x: x["date"])[-1]["value"])
    except Exception as e:
        print(f"[W6] FRED fetch failed: {e} — using fallback {fallback}")
        return fallback
```

**Validation guards:**
```python
VALID_CATEGORIES = {"Online Lender", "Credit Union", "Bank", "Marketplace"}

def validate_loan(loan):
    assert loan["rate_low"] < loan["rate_high"], "rate_low must be < rate_high"
    assert loan["category"] in VALID_CATEGORIES, f"Invalid category: {loan['category']}"
    assert 300 <= loan["credit_score_min"] <= 850, "credit_score_min out of FICO range"
```

**Syntax check:**
```bash
python -m py_compile atlas_agents/wealth/personal_loans/personal_loans_scraper.py
```

## Evals

| # | Assertion | Pass Condition |
|---|-----------|---------------|
| 1 | Package importable | `importlib.import_module("atlas_agents.wealth.personal_loans")` returns without error |
| 2 | AGENT_PROMPT.md exists and non-empty | `pathlib.Path(...AGENT_PROMPT.md).stat().st_size > 0` |
| 3 | SKILL.md exists and non-empty | `pathlib.Path(...personal_loans/SKILL.md).stat().st_size > 0` |
| 4 | All schema fields documented | `lender,rate_low,rate_high,max_amount,term_months_max,credit_score_min,category,rating,fred_avg_rate` all in AGENT_PROMPT.md |
| 5 | FRED series + both ratings documented | `TERMCBPER24NS,COMPETITIVE,AVERAGE` all in AGENT_PROMPT.md |
