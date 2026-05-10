# AGENT_PROMPT — B5: Franchise Evaluator

## IDENTITY
Agent ID: B5  
Name: Franchise Evaluator  
Division: Business & Startups  
Output file: data_cache/franchise_latest.json

---

## DEFINITION
Evaluates the top 25 franchises from the Entrepreneur Franchise 500 annual ranking,
enriched with FTC Franchise Disclosure Document (FDD) investment data. Rates each
franchise as STRONG / GOOD / AVERAGE based on unit count and ROI proxy. Designed for
prospective franchisees comparing initial investment, fees, and scale.

---

## DATA SOURCES

| Source | URL | Auth |
|--------|-----|------|
| FTC Franchise Disclosure (guidance) | https://www.ftc.gov/tips-advice/business-center/guidance/franchise-rule | None |
| Entrepreneur Franchise 500 | https://www.entrepreneur.com/franchise/rankings | None |

Data is hardcoded from the 2025 Entrepreneur Franchise 500 and corresponding FDD filings.
FTC does not expose a machine-readable API for FDD data — figures come from publicly
available annual FDD Item 5 (fees), Item 7 (initial investment), and Item 20 (unit count).

---

## OUTPUT FILE
`data_cache/franchise_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:30:00Z",
  "record_count": 25,
  "franchises": [
    {
      "name": "McDonald's",
      "sector": "Food & Beverage",
      "initial_investment_low": 1008000,
      "initial_investment_high": 2214080,
      "royalty_pct": 4.0,
      "franchise_fee": 45000,
      "units_total": 40275,
      "rating": "STRONG"
    },
    {
      "name": "7-Eleven",
      "sector": "Retail",
      "initial_investment_low": 37550,
      "initial_investment_high": 1149900,
      "royalty_pct": 52.0,
      "franchise_fee": 0,
      "units_total": 13000,
      "rating": "STRONG"
    },
    {
      "name": "Dunkin'",
      "sector": "Food & Beverage",
      "initial_investment_low": 526900,
      "initial_investment_high": 1787700,
      "royalty_pct": 5.9,
      "franchise_fee": 40000,
      "units_total": 9520,
      "rating": "STRONG"
    },
    {
      "name": "The UPS Store",
      "sector": "Retail",
      "initial_investment_low": 138433,
      "initial_investment_high": 460031,
      "royalty_pct": 5.0,
      "franchise_fee": 29950,
      "units_total": 5300,
      "rating": "STRONG"
    },
    {
      "name": "Jersey Mike's",
      "sector": "Food & Beverage",
      "initial_investment_low": 194035,
      "initial_investment_high": 954611,
      "royalty_pct": 6.5,
      "franchise_fee": 18500,
      "units_total": 2800,
      "rating": "STRONG"
    },
    {
      "name": "Anytime Fitness",
      "sector": "Fitness",
      "initial_investment_low": 107285,
      "initial_investment_high": 611470,
      "royalty_pct": 700.0,
      "franchise_fee": 42500,
      "units_total": 5000,
      "rating": "STRONG"
    },
    {
      "name": "Sonic Drive-In",
      "sector": "Food & Beverage",
      "initial_investment_low": 1204000,
      "initial_investment_high": 3537000,
      "royalty_pct": 5.0,
      "franchise_fee": 45000,
      "units_total": 3500,
      "rating": "GOOD"
    },
    {
      "name": "RE/MAX",
      "sector": "Home Services",
      "initial_investment_low": 43000,
      "initial_investment_high": 289000,
      "royalty_pct": 3.0,
      "franchise_fee": 20000,
      "units_total": 9000,
      "rating": "STRONG"
    },
    {
      "name": "Kumon",
      "sector": "Education",
      "initial_investment_low": 67753,
      "initial_investment_high": 162000,
      "royalty_pct": 34.0,
      "franchise_fee": 1000,
      "units_total": 26000,
      "rating": "STRONG"
    },
    {
      "name": "The Learning Experience",
      "sector": "Education",
      "initial_investment_low": 599500,
      "initial_investment_high": 1074500,
      "royalty_pct": 7.0,
      "franchise_fee": 60000,
      "units_total": 350,
      "rating": "GOOD"
    },
    {
      "name": "Ace Hardware",
      "sector": "Retail",
      "initial_investment_low": 286000,
      "initial_investment_high": 2100000,
      "royalty_pct": 0.0,
      "franchise_fee": 5000,
      "units_total": 5400,
      "rating": "STRONG"
    },
    {
      "name": "Planet Fitness",
      "sector": "Fitness",
      "initial_investment_low": 969600,
      "initial_investment_high": 4242500,
      "royalty_pct": 7.0,
      "franchise_fee": 20000,
      "units_total": 2400,
      "rating": "GOOD"
    },
    {
      "name": "Servpro",
      "sector": "Home Services",
      "initial_investment_low": 216362,
      "initial_investment_high": 272142,
      "royalty_pct": 10.0,
      "franchise_fee": 65000,
      "units_total": 2000,
      "rating": "GOOD"
    },
    {
      "name": "Great Clips",
      "sector": "Healthcare",
      "initial_investment_low": 136300,
      "initial_investment_high": 258250,
      "royalty_pct": 6.0,
      "franchise_fee": 20000,
      "units_total": 4400,
      "rating": "STRONG"
    },
    {
      "name": "Sport Clips",
      "sector": "Healthcare",
      "initial_investment_low": 228800,
      "initial_investment_high": 373300,
      "royalty_pct": 6.0,
      "franchise_fee": 25000,
      "units_total": 1800,
      "rating": "GOOD"
    },
    {
      "name": "Orangetheory Fitness",
      "sector": "Fitness",
      "initial_investment_low": 563529,
      "initial_investment_high": 998080,
      "royalty_pct": 8.0,
      "franchise_fee": 59950,
      "units_total": 1300,
      "rating": "GOOD"
    },
    {
      "name": "Subway",
      "sector": "Food & Beverage",
      "initial_investment_low": 116000,
      "initial_investment_high": 263000,
      "royalty_pct": 8.0,
      "franchise_fee": 15000,
      "units_total": 20500,
      "rating": "GOOD"
    },
    {
      "name": "Taco Bell",
      "sector": "Food & Beverage",
      "initial_investment_low": 575600,
      "initial_investment_high": 3370000,
      "royalty_pct": 5.5,
      "franchise_fee": 45000,
      "units_total": 8300,
      "rating": "STRONG"
    },
    {
      "name": "Marriott International",
      "sector": "Healthcare",
      "initial_investment_low": 5000000,
      "initial_investment_high": 100000000,
      "royalty_pct": 5.5,
      "franchise_fee": 100000,
      "units_total": 8500,
      "rating": "STRONG"
    },
    {
      "name": "Supercuts",
      "sector": "Healthcare",
      "initial_investment_low": 144575,
      "initial_investment_high": 296500,
      "royalty_pct": 6.0,
      "franchise_fee": 19500,
      "units_total": 2400,
      "rating": "AVERAGE"
    },
    {
      "name": "Budget Blinds",
      "sector": "Home Services",
      "initial_investment_low": 135000,
      "initial_investment_high": 211000,
      "royalty_pct": 9.0,
      "franchise_fee": 19950,
      "units_total": 1300,
      "rating": "AVERAGE"
    },
    {
      "name": "Jiffy Lube",
      "sector": "Home Services",
      "initial_investment_low": 228000,
      "initial_investment_high": 440000,
      "royalty_pct": 3.5,
      "franchise_fee": 35000,
      "units_total": 2000,
      "rating": "GOOD"
    },
    {
      "name": "Primrose Schools",
      "sector": "Education",
      "initial_investment_low": 658540,
      "initial_investment_high": 6254490,
      "royalty_pct": 7.0,
      "franchise_fee": 80000,
      "units_total": 400,
      "rating": "GOOD"
    },
    {
      "name": "uBreakiFix",
      "sector": "Retail",
      "initial_investment_low": 91050,
      "initial_investment_high": 204500,
      "royalty_pct": 6.0,
      "franchise_fee": 30000,
      "units_total": 700,
      "rating": "AVERAGE"
    },
    {
      "name": "BrightSpring Health Services",
      "sector": "Healthcare",
      "initial_investment_low": 85000,
      "initial_investment_high": 165000,
      "royalty_pct": 5.0,
      "franchise_fee": 45000,
      "units_total": 500,
      "rating": "AVERAGE"
    }
  ]
}
```

### Field Definitions
| Field | Type | Description |
|-------|------|-------------|
| generated_at | ISO 8601 UTC string | Timestamp of cache generation |
| record_count | int | Total franchises in dataset |
| franchises[].name | string | Franchise brand name |
| franchises[].sector | string | Sector classification |
| franchises[].initial_investment_low | int | Minimum initial investment in USD |
| franchises[].initial_investment_high | int | Maximum initial investment in USD |
| franchises[].royalty_pct | float | Ongoing royalty as % of gross sales |
| franchises[].franchise_fee | int | One-time franchise fee in USD |
| franchises[].units_total | int | Total units operating worldwide |
| franchises[].rating | string | "STRONG", "GOOD", or "AVERAGE" |

---

## SIGNAL / RATING LOGIC

rating classification:
- **STRONG**: units_total > 1000 AND estimated ROI proxy > 20%
  - ROI proxy = (avg_investment / franchise_fee) > threshold
  - Simplified rule: units_total > 1000 (proven scale) AND royalty_pct < 8%
- **GOOD**: units_total > 500 OR estimated ROI > 10%
  - Rule: units_total > 500 OR royalty_pct <= 6%
- **AVERAGE**: all others (high investment, limited scale, high royalty)

sector values: "Food & Beverage" | "Fitness" | "Home Services" | "Retail" | "Education" | "Healthcare"

Top 5 always guaranteed in output: McDonald's, 7-Eleven, Dunkin', The UPS Store, Jersey Mike's

---

## SCRAPER STRUCTURE

```python
"""franchise_scraper.py — B5 Franchise Evaluator"""
import json
import datetime

FTC_SOURCE_URL = "https://www.ftc.gov/tips-advice/business-center/guidance/franchise-rule"
ENTREPRENEUR_SOURCE_URL = "https://www.entrepreneur.com/franchise/rankings"

REQUIRED_TOP5 = ["McDonald's", "7-Eleven", "Dunkin'", "The UPS Store", "Jersey Mike's"]

# Top 25 franchises — hardcoded from 2025 Entrepreneur Franchise 500 + FDD filings
FRANCHISES = [
    # ... (full list as in OUTPUT SCHEMA above)
]


def rate_franchise(f: dict) -> str:
    """Apply rating logic: STRONG / GOOD / AVERAGE."""
    units = f.get("units_total", 0)
    royalty = f.get("royalty_pct", 100.0)
    if units > 1000 and royalty < 8.0:
        return "STRONG"
    if units > 500 or royalty <= 6.0:
        return "GOOD"
    return "AVERAGE"


def scrape() -> dict:
    """Run B5: return ranked franchise dataset with ratings applied."""
    franchises_out = []
    for f in FRANCHISES:
        entry = dict(f)
        entry["rating"] = rate_franchise(f)
        franchises_out.append(entry)
    # Verify top 5 always present
    names_out = {f["name"] for f in franchises_out}
    for name in REQUIRED_TOP5:
        assert name in names_out, f"Missing required franchise: {name}"
    return {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "record_count": len(franchises_out),
        "franchises": franchises_out,
    }


def save(output_path: str = "data_cache/franchise_latest.json") -> None:
    result = scrape()
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    save()
```

---

## RULES
1. Top 5 (McDonald's, 7-Eleven, Dunkin', The UPS Store, Jersey Mike's) must always be present.
2. rating values are strictly: "STRONG", "GOOD", "AVERAGE".
3. sector values are strictly: "Food & Beverage", "Fitness", "Home Services", "Retail", "Education", "Healthcare".
4. initial_investment_low must always be <= initial_investment_high.
5. Data is hardcoded annually — update each January from Entrepreneur Franchise 500.
6. generated_at must be ISO 8601 UTC (Z suffix).
7. record_count must equal len(franchises).
8. FDD data source is FTC disclosure (public, no scraping needed).

---

## VALIDATION CHECKLIST
- [ ] All 25 franchises present
- [ ] Top 5 required brands all present
- [ ] rating is one of: STRONG, GOOD, AVERAGE
- [ ] sector is one of the 6 valid values
- [ ] initial_investment_low <= initial_investment_high for every entry
- [ ] franchise_fee >= 0 for all entries
- [ ] record_count == 25
- [ ] generated_at is valid ISO UTC string
