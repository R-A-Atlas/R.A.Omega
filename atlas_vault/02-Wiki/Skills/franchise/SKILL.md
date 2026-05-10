---
name: Franchise Evaluator
description: Evaluates top 25 franchises from Entrepreneur Franchise 500 with FTC FDD investment data; rates each STRONG/GOOD/AVERAGE based on unit count and royalty efficiency
type: reference
agent: B5
division: Business & Startups
---

# Skill: Franchise Evaluator (B5)

## [D] Direction
Return a curated dataset of 25 top US franchises drawn from the 2025 Entrepreneur Franchise
500 ranking and FTC Franchise Disclosure Document (FDD) public filings. Apply STRONG/GOOD/AVERAGE
ratings based on unit scale and royalty rate. Save to data_cache/franchise_latest.json.

Step-by-step:
1. Load FRANCHISES list (25 entries, hardcoded from 2025 Entrepreneur F500 + FDD).
2. Apply rate_franchise() to each entry: STRONG if units>1000 AND royalty<8%; GOOD if units>500 OR royalty<=6%; else AVERAGE.
3. Verify all 5 required brands present (McDonald's, 7-Eleven, Dunkin', The UPS Store, Jersey Mike's).
4. Set generated_at (ISO UTC), record_count = 25.
5. Write to data_cache/franchise_latest.json.
6. Update FRANCHISES each January from new Entrepreneur Franchise 500.

Rules:
- Top 5 brands (McDonald's, 7-Eleven, Dunkin', The UPS Store, Jersey Mike's) must ALWAYS be present.
- rating values: "STRONG", "GOOD", "AVERAGE" only.
- sector values: "Food & Beverage", "Fitness", "Home Services", "Retail", "Education", "Healthcare" only.
- initial_investment_low <= initial_investment_high always.
- Data source is FTC FDD (public) — no scraping needed.

## [B] Blueprints
Pattern:    atlas_agents/business/franchise/AGENT_PROMPT.md (full scraper stub + full dataset)
FTC source: https://www.ftc.gov/tips-advice/business-center/guidance/franchise-rule
Ranking:    https://www.entrepreneur.com/franchise/rankings
Output:     data_cache/franchise_latest.json

Rating logic:
- STRONG: units_total > 1000 AND royalty_pct < 8.0
- GOOD: units_total > 500 OR royalty_pct <= 6.0
- AVERAGE: all others

Required top 5 (by Entrepreneur 2025 rank):
1. McDonald's — Food & Beverage — 40,275 units
2. 7-Eleven — Retail — 13,000 units
3. Dunkin' — Food & Beverage — 9,520 units
4. The UPS Store — Retail — 5,300 units
5. Jersey Mike's — Food & Beverage — 2,800 units

## [S] Solutions
Run scraper:
  python -m atlas_agents.business.franchise.franchise_scraper

Validate top 5 present:
  python -c "import json; d=json.load(open('data_cache/franchise_latest.json')); names={f['name'] for f in d['franchises']}; print(all(n in names for n in [\"McDonald's\",\"7-Eleven\",\"Dunkin'\",\"The UPS Store\",\"Jersey Mike's\"]))"

Run tests:
  python -m pytest tests/test_franchise.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | All 25 franchises present | record_count == 25 |
| 2 | Top 5 brands all present | McDonald's, 7-Eleven, Dunkin', The UPS Store, Jersey Mike's in output |
| 3 | rating values valid | values in {"STRONG","GOOD","AVERAGE"} |
| 4 | investment bounds correct | initial_investment_low <= initial_investment_high for all |
| 5 | generated_at is ISO UTC | datetime.fromisoformat(generated_at.replace("Z","+00:00")) succeeds |
