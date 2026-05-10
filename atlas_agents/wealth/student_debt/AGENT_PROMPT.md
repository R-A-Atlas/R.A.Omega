# W3 — Student Debt Monitor | Division: Personal Wealth & Debt

## IDENTITY
W3 is the Student Debt Monitor agent for the ATLAS Personal Wealth Division. It tracks federal student loan interest rates, aggregate debt statistics, and the status of major federal forgiveness programs. No LLM calls are made; data is sourced from StudentAid.gov public endpoints and a hardcoded annual snapshot for rate data.

## DEFINITION

Key terms:
- **Aid Year**: The academic year for which rates apply (e.g., "2025-2026").
- **Federal Rate (Undergrad)**: Fixed interest rate on Direct Subsidized/Unsubsidized loans for undergraduates.
- **Federal Rate (Grad)**: Fixed interest rate on Direct Unsubsidized loans for graduate students.
- **Federal Rate (PLUS)**: Fixed interest rate on Direct PLUS loans (parents and grad students).
- **Forgiveness Status**: `ACTIVE` = enrolling new applicants; `PAUSED` = legally blocked; `CLOSED` = no longer accepting.

Forgiveness programs tracked:
- PSLF (Public Service Loan Forgiveness)
- IBR (Income-Based Repayment)
- SAVE (Saving on a Valuable Education)
- PAYE (Pay As You Earn)
- ICR (Income-Contingent Repayment)

## DATA SOURCES

**Primary:** StudentAid.gov public announcements API
- URL: `https://api.studentaid.gov/v1/public/announcements`
- Returns current policy announcements — used to detect forgiveness program status changes.
- No auth required.

**Secondary (rate data):** Federal student loan interest rates page
- URL: `https://studentaid.gov/understand-aid/types/loans/interest-rates`
- Rates are set annually by Congress each June; parsed or hardcoded per aid year.

**Tertiary (aggregate stats):** Federal Reserve / FRED
- Total student debt: approximately $1.77T (2026 snapshot)
- Total borrowers: approximately 43.5 million

## OUTPUT FILE

`data_cache/student_debt_latest.json`

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:00:00Z",
  "aid_year": "2025-2026",
  "federal_rate_undergrad": 6.53,
  "federal_rate_grad": 8.08,
  "federal_rate_plus": 9.08,
  "total_borrowers_millions": 43.5,
  "total_debt_billions": 1770.0,
  "forgiveness_programs": [
    {
      "name": "PSLF",
      "status": "ACTIVE",
      "eligible_loans": "Direct Loans only"
    },
    {
      "name": "IBR",
      "status": "ACTIVE",
      "eligible_loans": "Direct Loans and FFELP"
    },
    {
      "name": "SAVE",
      "status": "PAUSED",
      "eligible_loans": "Direct Loans only"
    },
    {
      "name": "PAYE",
      "status": "ACTIVE",
      "eligible_loans": "Direct Loans only"
    },
    {
      "name": "ICR",
      "status": "ACTIVE",
      "eligible_loans": "Direct Loans and FFELP"
    }
  ]
}
```

Fields:
- `generated_at` (ISO 8601 UTC): cache build timestamp
- `aid_year` (string): academic year label (e.g., "2025-2026")
- `federal_rate_undergrad` (float): Direct Subsidized/Unsubsidized undergrad rate (%)
- `federal_rate_grad` (float): Direct Unsubsidized graduate rate (%)
- `federal_rate_plus` (float): Direct PLUS loan rate (%)
- `total_borrowers_millions` (float): estimated total student loan borrowers (millions)
- `total_debt_billions` (float): total outstanding federal student debt (billions USD)
- `forgiveness_programs` (array of 5): one object per program
  - `name` (string): program acronym — one of PSLF | IBR | SAVE | PAYE | ICR
  - `status` (string): `ACTIVE | PAUSED | CLOSED`
  - `eligible_loans` (string): loan types that qualify

## SIGNAL LOGIC

Program status determination:
```
if announcement text contains "court" or "injunction" or "blocked":
    status = "PAUSED"
elif announcement text contains "closed" or "discontinued":
    status = "CLOSED"
else:
    status = "ACTIVE"   # default
```

Rate change alert:
```
if federal_rate_undergrad > 7.0:
    rate_alert = "HIGH — undergrad rate above 7%"
elif federal_rate_undergrad > 5.5:
    rate_alert = "MODERATE"
else:
    rate_alert = "LOW"
```

## SCRAPER STRUCTURE

```python
# student_debt_scraper.py

import requests
import json
from datetime import datetime, timezone

STUDENTAID_ANNOUNCEMENTS_URL = "https://api.studentaid.gov/v1/public/announcements"
STUDENTAID_RATES_URL = "https://studentaid.gov/understand-aid/types/loans/interest-rates"
OUTPUT_PATH = "data_cache/student_debt_latest.json"

HARDCODED_RATES = {
    "aid_year": "2025-2026",
    "federal_rate_undergrad": 6.53,
    "federal_rate_grad": 8.08,
    "federal_rate_plus": 9.08,
}

PROGRAMS = ["PSLF", "IBR", "SAVE", "PAYE", "ICR"]

PROGRAM_LOAN_TYPES = {
    "PSLF": "Direct Loans only",
    "IBR": "Direct Loans and FFELP",
    "SAVE": "Direct Loans only",
    "PAYE": "Direct Loans only",
    "ICR": "Direct Loans and FFELP",
}


def fetch_announcements() -> list[dict]:
    """Fetch announcements from StudentAid.gov API."""
    ...


def parse_program_status(announcements: list[dict], program: str) -> str:
    """Return ACTIVE | PAUSED | CLOSED based on announcement text."""
    ...


def build_forgiveness_programs(announcements: list[dict]) -> list[dict]:
    """Build forgiveness_programs array for all 5 programs."""
    ...


def scrape() -> dict:
    """Main entry point. Returns full output schema dict."""
    ...


def save(data: dict) -> None:
    """Write data to OUTPUT_PATH as formatted JSON."""
    ...


if __name__ == "__main__":
    result = scrape()
    save(result)
    print(f"[W3] Aid year={result['aid_year']} programs={len(result['forgiveness_programs'])} → {OUTPUT_PATH}")
```

## RULES

- NEVER store user loan balances, account numbers, or FSA IDs.
- `status` must be one of ACTIVE / PAUSED / CLOSED — raise ValueError for any other value.
- `name` must be one of PSLF / IBR / SAVE / PAYE / ICR — no custom programs.
- Rates are fetched from `federal_rate_undergrad`, `federal_rate_grad`, `federal_rate_plus` keys — all floats.
- If StudentAid.gov API is unreachable, use HARDCODED_RATES and set all statuses to "ACTIVE" with a warning log.
- `total_borrowers_millions` and `total_debt_billions` are updated from FRED/public sources — not user data.
- Output file must always be valid JSON. Write error envelope on failure.
- Do not call any LLM.

## VALIDATION CHECKLIST

- [ ] `generated_at` is ISO 8601 UTC
- [ ] `aid_year` matches format "YYYY-YYYY"
- [ ] `federal_rate_undergrad`, `federal_rate_grad`, `federal_rate_plus` are all positive floats
- [ ] `forgiveness_programs` array has exactly 5 items
- [ ] Each program `name` is one of PSLF | IBR | SAVE | PAYE | ICR
- [ ] Each program `status` is one of ACTIVE | PAUSED | CLOSED
- [ ] `total_borrowers_millions` and `total_debt_billions` are positive floats
- [ ] Output file is valid JSON
- [ ] API failure triggers fallback, not a crash
