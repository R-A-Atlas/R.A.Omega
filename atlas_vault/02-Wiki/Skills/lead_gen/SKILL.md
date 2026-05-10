---
name: Lead Generation Scraper
description: Fetches Google Maps Places results for a business category+city; classifies HOT_LEAD/WARM_LEAD/COLD_LEAD based on rating, reviews, and site quality
type: reference
agent: G1
division: Business Growth & Ops
---

# Skill: Lead Generation Scraper (G1)

## [D] Direction
Call Google Places Text Search API for a query string.
Classify each result: HOT_LEAD (rating>=4.5, reviews>=50, no modern site),
WARM_LEAD (rating>=4.0), COLD_LEAD (else).
Save to data_cache/leads_latest.json.

## [B] Blueprints
Utils:   atlas_core/utils/agent_utils.py (write_cache_json_pair)
Source:  https://maps.googleapis.com/maps/api/place/textsearch/json
Key env: GOOGLE_MAPS_KEY

## [S] Solutions
Run scraper:
  python -m atlas_agents.growth.lead_gen.lead_gen_scraper "plumbers near Austin TX"

Run tests:
  python -m pytest tests/test_lead_gen.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | signal in valid set | HOT_LEAD/WARM_LEAD/COLD_LEAD |
| 3 | rating in [0, 5] | all leads valid range |
| 4 | record_count == len(leads) | count matches |
| 5 | graceful when key absent | returns empty list, no crash |
