---
name: Student Debt Monitor
description: Tracks federal student loan interest rates, aggregate debt statistics, and the status of 5 major federal forgiveness programs via StudentAid.gov public API.
type: reference
agent: W3
division: Personal Wealth & Debt
---

# Skill: Student Debt Monitor (W3)

## [D] Direction

**Goal:** Produce `data_cache/student_debt_latest.json` with current federal loan rates, macro debt stats, and status of PSLF / IBR / SAVE / PAYE / ICR forgiveness programs.

**Steps:**
1. Load hardcoded federal loan rates for current aid year (rates set by Congress annually in June; scraped from StudentAid.gov or hardcoded after June announcement).
2. Fetch announcements from `https://api.studentaid.gov/v1/public/announcements`.
3. For each of the 5 programs (PSLF, IBR, SAVE, PAYE, ICR), scan announcement text for keywords: "court"/"injunction"/"blocked" → PAUSED; "closed"/"discontinued" → CLOSED; else ACTIVE.
4. Populate aggregate stats (`total_borrowers_millions`, `total_debt_billions`) from hardcoded annual snapshot.
5. Write output JSON to `data_cache/student_debt_latest.json`.

**Stop conditions:**
- StudentAid.gov API unavailable → use hardcoded rates, set all statuses to "ACTIVE" (safe default), log warning.
- Unknown program name → raise ValueError.

**Guardrails:**
- Never store FSA IDs, user loan balances, or personal financial data.
- `status` must be ACTIVE / PAUSED / CLOSED only.
- Program names are exactly: PSLF, IBR, SAVE, PAYE, ICR.
- Never call any LLM.

## [B] Blueprints

**2025-2026 Aid Year Rates (hardcoded):**
```python
HARDCODED_RATES = {
    "aid_year": "2025-2026",
    "federal_rate_undergrad": 6.53,
    "federal_rate_grad": 8.08,
    "federal_rate_plus": 9.08,
}
```

**Status keyword mapping:**
```python
PAUSED_KEYWORDS = ["court", "injunction", "blocked", "stayed", "halted"]
CLOSED_KEYWORDS = ["closed", "discontinued", "eliminated", "ended"]
```

**Program loan types (static):**
```python
PROGRAM_LOAN_TYPES = {
    "PSLF": "Direct Loans only",
    "IBR": "Direct Loans and FFELP",
    "SAVE": "Direct Loans only",
    "PAYE": "Direct Loans only",
    "ICR": "Direct Loans and FFELP",
}
```

**Aggregate stats snapshot (update annually):**
```python
total_borrowers_millions = 43.5
total_debt_billions = 1770.0
```

## [S] Solutions

**StudentAid.gov fetch with fallback:**
```python
import requests

def fetch_announcements():
    try:
        resp = requests.get(
            "https://api.studentaid.gov/v1/public/announcements",
            timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[W3] StudentAid API failed: {e} — using defaults")
        return []
```

**Status parse:**
```python
def parse_status(announcements, program):
    text = " ".join(str(a) for a in announcements).lower()
    prog_lower = program.lower()
    prog_text = text[max(0, text.find(prog_lower)-200):text.find(prog_lower)+200] if prog_lower in text else ""
    if any(k in prog_text for k in ["court", "injunction", "blocked"]):
        return "PAUSED"
    if any(k in prog_text for k in ["closed", "discontinued"]):
        return "CLOSED"
    return "ACTIVE"
```

**Syntax check:**
```bash
python -m py_compile atlas_agents/wealth/student_debt/student_debt_scraper.py
```

## Evals

| # | Assertion | Pass Condition |
|---|-----------|---------------|
| 1 | Package importable | `importlib.import_module("atlas_agents.wealth.student_debt")` returns without error |
| 2 | AGENT_PROMPT.md exists and non-empty | `pathlib.Path(...AGENT_PROMPT.md).stat().st_size > 0` |
| 3 | SKILL.md exists and non-empty | `pathlib.Path(...student_debt/SKILL.md).stat().st_size > 0` |
| 4 | All schema fields documented | `aid_year,federal_rate_undergrad,federal_rate_grad,federal_rate_plus,total_borrowers_millions,total_debt_billions,forgiveness_programs` all in AGENT_PROMPT.md |
| 5 | All 5 programs + StudentAid URL documented | `PSLF,IBR,SAVE,PAYE,ICR,api.studentaid.gov` all in AGENT_PROMPT.md |
