---
name: Watch Market Bot
description: Scrapes Chrono24 public listing pages for 8 top collectible watch references; computes avg secondary-market price, premium over retail, and APPRECIATING/PREMIUM/AT_RETAIL/BELOW_RETAIL trend signal
type: reference
agent: A1
division: Alternative Assets & Niche
---

# Skill: Watch Market Bot (A1)

## [D] Direction
Query Chrono24 public listing search for each of 8 hardcoded watch references
(Rolex, Patek Philippe, AP, Omega). Parse HTML listing prices, compute avg_price,
compare against hardcoded retail_price to derive premium_over_retail_pct and trend signal.
Save to data_cache/watches_latest.json.

Steps:
1. Iterate WATCH_UNIVERSE (8 references).
2. For each: GET https://www.chrono24.com/search/index.htm?query={reference}&resultview=block
3. Parse price elements from listing cards using BeautifulSoup.
4. Compute avg_price = mean of found prices (int USD).
5. Compute premium_over_retail_pct = ((avg_price - retail_price) / retail_price) * 100.
6. Classify trend: APPRECIATING (>=50% premium), PREMIUM (>0%), AT_RETAIL (within 10%), BELOW_RETAIL.
7. Sleep 1.0s between requests.
8. Write payload to data_cache/watches_latest.json via write_cache_json_pair.

## [B] Blueprints
Pattern:    atlas_agents/realestate/residential/residential_scraper.py (HTML fetch + parse)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://www.chrono24.com/search/index.htm?query={reference}&resultview=block
Output:     data_cache/watches_latest.json
Schema fields: brand, model, reference, avg_price, retail_price, premium_over_retail_pct, trend, listings_count

Watch Universe:
  Rolex:          116610LN ($9,100), 126710BLNR ($10,800), 116500LN ($14,550)
  Patek Philippe: 5711/1A ($35,000), 5167A ($28,000)
  AP:             15400ST ($24,100), 15202ST ($29,000)
  Omega:          311.30.42.30.01.005 ($6,100)

## [S] Solutions
Run scraper:
  python -m atlas_agents.alternative.watches.watches_scraper

Test Chrono24 connectivity:
  python -c "import requests; r = requests.get('https://www.chrono24.com/search/index.htm?query=116610LN&resultview=block', headers={'User-Agent':'Mozilla/5.0'}); print(r.status_code)"

Run tests:
  python -m pytest tests/test_watches.py -v

Verify output:
  python -c "import json,pathlib; d=json.loads(pathlib.Path('data_cache/watches_latest.json').read_text()); print(d['record_count'], [m['trend'] for m in d['models']])"

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on watches_scraper.py |
| 2 | all 8 models present in output | record_count == 8 |
| 3 | premium_over_retail_pct computed correctly | ((avg_price - retail_price) / retail_price) * 100 within 0.01 tolerance |
| 4 | trend is valid enum value | each trend in {APPRECIATING, PREMIUM, AT_RETAIL, BELOW_RETAIL} |
| 5 | generated_at is ISO UTC string | parseable as datetime, ends with Z |
