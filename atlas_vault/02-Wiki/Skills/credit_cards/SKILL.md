---
name: Credit Card Optimizer
description: Fetches, scores, and ranks consumer credit cards by APR, signup bonus, and annual fee using CFPB public data and a static snapshot.
type: reference
agent: W1
division: Personal Wealth & Debt
---

# Skill: Credit Card Optimizer (W1)

## [D] Direction

**Goal:** Produce `data_cache/credit_cards_latest.json` containing a ranked list of credit cards with deterministic signal scoring (BEST_VALUE / GOOD / AVERAGE).

**Steps:**
1. Attempt to fetch complaint volume from CFPB API as contextual metadata (`product=Credit card or prepaid card`).
2. Load the static card list (STATIC_CARDS) with issuer, APR, signup bonus (points + USD value), annual fee, and category.
3. For each card, compute `net_value_year1_usd = signup_bonus_usd - annual_fee` (assuming zero balance carried).
4. Apply signal logic: BEST_VALUE if APR < 20% and signup_bonus_usd > 500; GOOD if APR < 25%; AVERAGE otherwise.
5. Sort: BEST_VALUE → GOOD → AVERAGE; within tier sort by `net_value_year1_usd` descending.
6. Write output JSON to `data_cache/credit_cards_latest.json`.

**Stop conditions:**
- CFPB API 503/timeout → log warning, continue with static data (never crash).
- Invalid category value → raise ValueError before writing output.

**Guardrails:**
- Never store PII. No user card numbers, SSNs, or personal data in output.
- Never call any LLM.
- Output must be valid JSON at all times (write error envelope on unexpected exception).

## [B] Blueprints

**Category enum (hard constraint):**
```
"Cash Back" | "Travel" | "Balance Transfer" | "Secured" | "Business"
```

**Signal formula:**
```python
if card["apr"] < 20.0 and card["signup_bonus_usd"] > 500:
    signal = "BEST_VALUE"
elif card["apr"] < 25.0:
    signal = "GOOD"
else:
    signal = "AVERAGE"
```

**Output envelope (error case):**
```json
{
  "generated_at": "2026-05-09T14:00:00Z",
  "error": "CFPB API timeout",
  "record_count": 0,
  "cards": []
}
```

**Reference cards (minimum set):**
- Chase Sapphire Preferred (Travel, APR 21.49%, $600 bonus, $95 fee)
- Citi Double Cash (Cash Back, APR 19.24%, $0 bonus, $0 fee)
- Discover it Balance Transfer (Balance Transfer, APR 18.74%)
- Capital One Secured Mastercard (Secured, APR 30.74%)
- Amex Blue Cash Preferred (Cash Back, APR 19.24%, $250 bonus, $95 fee)
- Chase Ink Business Cash (Business, APR 18.49%, $750 bonus, $0 fee)

## [S] Solutions

**CFPB API health check:**
```python
import requests
resp = requests.get(
    "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/",
    params={"product": "Credit card or prepaid card", "size": 1},
    timeout=10
)
resp.raise_for_status()
total = resp.json().get("_metadata", {}).get("total_record_count", 0)
```

**Write with error envelope:**
```python
import json, traceback
try:
    result = scrape()
except Exception as e:
    result = {"generated_at": now_utc(), "error": str(e), "record_count": 0, "cards": []}
with open(OUTPUT_PATH, "w") as f:
    json.dump(result, f, indent=2)
```

**Syntax check:**
```bash
python -m py_compile atlas_agents/wealth/credit_cards/credit_cards_scraper.py
```

## Evals

| # | Assertion | Pass Condition |
|---|-----------|---------------|
| 1 | Package importable | `importlib.import_module("atlas_agents.wealth.credit_cards")` returns without error |
| 2 | AGENT_PROMPT.md exists and non-empty | `pathlib.Path(...AGENT_PROMPT.md).stat().st_size > 0` |
| 3 | SKILL.md exists and non-empty | `pathlib.Path(...credit_cards/SKILL.md).stat().st_size > 0` |
| 4 | All 9 schema fields documented | Each of `name,issuer,apr,signup_bonus,annual_fee,category,signal,net_value_year1_usd,generated_at` in AGENT_PROMPT.md |
| 5 | All 3 signals documented | `BEST_VALUE`, `GOOD`, `AVERAGE` all present in AGENT_PROMPT.md |
