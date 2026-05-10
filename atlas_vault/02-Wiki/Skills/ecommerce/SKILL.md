---
name: Ecommerce Trends Bot
description: Tracks 8 ecommerce niches using Google Trends (via pytrends); classifies each as RISING/STABLE/DECLINING with competition level and average price estimates for dropshippers and D2C founders
type: reference
agent: B3
division: Business & Startups
---

# Skill: Ecommerce Trends Bot (B3)

## [D] Direction
Use the pytrends library (Google Trends unofficial API, no auth) to fetch 3-month relative
search interest for 8 predefined ecommerce niches. Classify each as RISING/STABLE/DECLINING.
Enrich with hardcoded avg price estimates and competition levels. Save to
data_cache/ecommerce_latest.json.

Step-by-step:
1. Define NICHES list (8 niches, fixed).
2. Call TrendReq().build_payload(kw_list, timeframe="today 3-m", geo="US").
3. Compute avg score per niche from interest_over_time() DataFrame.
4. Classify direction: >=70=RISING, 40-69=STABLE, <40=DECLINING.
5. Apply hardcoded NICHE_META (avg_price_estimate, competition_level).
6. Set generated_at (ISO UTC), record_count = 8.
7. Write to data_cache/ecommerce_latest.json.

Rules:
- Batch pytrends requests to <=5 keywords (API restriction). Sleep 1s between batches.
- pytrends failure must NOT crash the scraper — return score=0, direction=DECLINING.
- trend_direction values: "RISING", "STABLE", "DECLINING" only.
- competition_level values: "HIGH", "MEDIUM", "LOW" only (hardcoded, not live).
- avg_price_estimate is hardcoded — not scraped.
- All 8 niches must always appear in output.

## [B] Blueprints
Pattern:    atlas_agents/business/ecommerce/AGENT_PROMPT.md (full scraper stub)
Library:    pytrends (pip install pytrends)
Docs:       https://github.com/GeneralMills/pytrends
Primary:    https://trends.google.com/trends/
Output:     data_cache/ecommerce_latest.json

Hardcoded metadata:
- "AI gadgets": price=$89.99, competition=HIGH
- "sustainable fashion": price=$65.00, competition=MEDIUM
- "home gym equipment": price=$245.00, competition=HIGH
- "pet tech": price=$49.99, competition=MEDIUM
- "meal prep": price=$34.99, competition=MEDIUM
- "travel accessories": price=$42.00, competition=HIGH
- "smart home": price=$119.99, competition=HIGH
- "vintage clothing": price=$38.00, competition=LOW

## [S] Solutions
Install pytrends:
  pip install pytrends

Run scraper:
  python -m atlas_agents.business.ecommerce.ecommerce_scraper

Quick test (single niche):
  python -c "from pytrends.request import TrendReq; pt=TrendReq(); pt.build_payload(['AI gadgets'],timeframe='today 3-m',geo='US'); print(pt.interest_over_time()['AI gadgets'].mean())"

Run tests:
  python -m pytest tests/test_ecommerce.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | All 8 niches present | len(trending_niches) == 8 |
| 2 | trend_score in 0-100 | all(0 <= n["trend_score"] <= 100 for n in niches) |
| 3 | trend_direction valid | values in {"RISING","STABLE","DECLINING"} |
| 4 | competition_level valid | values in {"HIGH","MEDIUM","LOW"} |
| 5 | pytrends failure graceful | scraper returns record with score=0, not exception |
