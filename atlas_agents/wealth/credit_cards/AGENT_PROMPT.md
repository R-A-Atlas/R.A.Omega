# W1 — Credit Card Optimizer | Division: Personal Wealth & Debt

## IDENTITY
W1 is the Credit Card Optimizer agent for the ATLAS Personal Wealth Division. It fetches, scores, and ranks consumer credit cards by total value — weighing APR, signup bonuses, annual fees, and category fit. No LLM calls are made; all scoring is deterministic rule-based logic.

## DEFINITION

Key terms:
- **APR**: Annual Percentage Rate — the annualized cost of carrying a balance.
- **Signup Bonus**: One-time reward (points, miles, or cash) earned after meeting a spend threshold.
- **Annual Fee**: Fixed yearly cost charged by the issuer.
- **Net Value Score**: `signup_bonus_usd - annual_fee - (avg_daily_balance * APR / 365 * 365)` — simplified 1-year net value.

Thresholds:
- BEST_VALUE: APR < 20% AND signup_bonus > 500
- GOOD: APR < 25%
- AVERAGE: all others

Category values (enum): `"Cash Back"`, `"Travel"`, `"Balance Transfer"`, `"Secured"`, `"Business"`

## DATA SOURCES

**Primary:** CFPB Consumer Complaint Database (public REST API)
- URL: `https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/`
- No auth required. Query param: `product=Credit card or prepaid card`

**Secondary (static snapshot):** Hardcoded representative cards updated quarterly.
- Rationale: CFPB complaints API yields complaint metadata, not rate/bonus data. Static snapshot provides structured card terms until a live rate API is available.

## OUTPUT FILE

`data_cache/credit_cards_latest.json`

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:00:00Z",
  "record_count": 12,
  "cards": [
    {
      "name": "Chase Sapphire Preferred",
      "issuer": "Chase",
      "apr": 21.49,
      "signup_bonus": 60000,
      "signup_bonus_usd": 600,
      "annual_fee": 95,
      "category": "Travel",
      "signal": "BEST_VALUE",
      "net_value_year1_usd": 505
    },
    {
      "name": "Citi Double Cash",
      "issuer": "Citi",
      "apr": 19.24,
      "signup_bonus": 0,
      "signup_bonus_usd": 0,
      "annual_fee": 0,
      "category": "Cash Back",
      "signal": "GOOD",
      "net_value_year1_usd": 0
    }
  ]
}
```

Fields:
- `generated_at` (ISO 8601 UTC string): when the cache was built
- `record_count` (int): number of cards returned
- `cards` (array): list of card objects
  - `name` (string): product name
  - `issuer` (string): bank/credit union name
  - `apr` (float): variable APR as of snapshot date (%)
  - `signup_bonus` (int): raw points/miles value; 0 if cash-back card
  - `signup_bonus_usd` (float): estimated USD value of signup bonus
  - `annual_fee` (float): annual fee in USD
  - `category` (string): one of `Cash Back | Travel | Balance Transfer | Secured | Business`
  - `signal` (string): `BEST_VALUE | GOOD | AVERAGE`
  - `net_value_year1_usd` (float): estimated 1-year net value assuming $0 balance carried

## SIGNAL LOGIC

```
if apr < 20.0 and signup_bonus_usd > 500:
    signal = "BEST_VALUE"
elif apr < 25.0:
    signal = "GOOD"
else:
    signal = "AVERAGE"
```

Cards are sorted: BEST_VALUE first, then GOOD, then AVERAGE. Within each tier, sorted by `net_value_year1_usd` descending.

## SCRAPER STRUCTURE

```python
# credit_cards_scraper.py

import requests
import json
from datetime import datetime, timezone

CFPB_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
OUTPUT_PATH = "data_cache/credit_cards_latest.json"

STATIC_CARDS = [
    {"name": "Chase Sapphire Preferred", "issuer": "Chase", "apr": 21.49,
     "signup_bonus": 60000, "signup_bonus_usd": 600, "annual_fee": 95, "category": "Travel"},
    {"name": "Citi Double Cash", "issuer": "Citi", "apr": 19.24,
     "signup_bonus": 0, "signup_bonus_usd": 0, "annual_fee": 0, "category": "Cash Back"},
    {"name": "Discover it Balance Transfer", "issuer": "Discover", "apr": 18.74,
     "signup_bonus": 0, "signup_bonus_usd": 0, "annual_fee": 0, "category": "Balance Transfer"},
    {"name": "Capital One Secured Mastercard", "issuer": "Capital One", "apr": 30.74,
     "signup_bonus": 0, "signup_bonus_usd": 0, "annual_fee": 0, "category": "Secured"},
    {"name": "Amex Blue Cash Preferred", "issuer": "American Express", "apr": 19.24,
     "signup_bonus": 250, "signup_bonus_usd": 250, "annual_fee": 95, "category": "Cash Back"},
    {"name": "Chase Ink Business Cash", "issuer": "Chase", "apr": 18.49,
     "signup_bonus": 75000, "signup_bonus_usd": 750, "annual_fee": 0, "category": "Business"},
]


def score_card(card: dict) -> dict:
    """Apply signal logic and compute net_value_year1_usd."""
    ...


def fetch_cfpb_complaint_count(product: str = "Credit card or prepaid card") -> int:
    """Return total complaint count from CFPB API for context."""
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
    print(f"[W1] Saved {result['record_count']} cards → {OUTPUT_PATH}")
```

## RULES

- NEVER store or log raw card numbers, SSNs, or user PII.
- ALWAYS use the static card list as fallback if CFPB API is unreachable (503/timeout).
- APR values must be floats — never strings.
- `signup_bonus_usd` must be separately estimated; points ≠ USD (use 1 cpp for travel, 1:1 for cash).
- `category` must be one of the five enum values — raise ValueError for any other input.
- `signal` must be computed fresh on every run — never cached from a prior run.
- Output file must always be valid JSON. Wrap scrape() in try/except and write a minimal error envelope if it fails:
  `{"generated_at": "...", "error": "...", "record_count": 0, "cards": []}`
- Do not call any LLM. All logic is deterministic.

## VALIDATION CHECKLIST

- [ ] `generated_at` is ISO 8601 UTC
- [ ] `record_count` equals `len(cards)`
- [ ] Every card has all 9 schema fields
- [ ] `category` is one of the 5 enum values
- [ ] `signal` is one of BEST_VALUE / GOOD / AVERAGE
- [ ] APR < 20% + bonus > $500 → BEST_VALUE (no exceptions)
- [ ] Output file is valid JSON (json.loads roundtrip passes)
- [ ] CFPB API timeout does not crash the agent (fallback fires)
