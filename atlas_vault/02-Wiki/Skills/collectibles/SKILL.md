---
name: Collectibles/Cards Scraper
description: Tracks 5 graded collectible items across Sports Cards, Pokemon, Magic, Comic Books, Coins via eBay sold listings; signals HOT/RISING/STABLE/COOLING based on volume and MoM price change
type: reference
agent: A3
division: Alternative Assets & Niche
---

# Skill: Collectibles/Cards Scraper (A3)

## [D] Direction
Query eBay sold listings for 5 graded collectible items (PSA 10 Charizard, PSA 10 LeBron James RC,
PSA 10 Tom Brady RC, CGC 9.8 Amazing Fantasy 15, MS-65 Morgan Silver Dollar).
Compute avg_sold_price and volume_30d from search results. Classify trend: HOT / RISING / STABLE / COOLING.
Save to data_cache/collectibles_latest.json.

Steps:
1. Iterate TRACKED_ITEMS (5 items).
2. For each: try eBay Browse API; fall back to public HTML sold search.
   Fallback URL: https://www.ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1
3. Parse sold prices from results.
4. Compute avg_sold_price = mean of prices (float, 2dp).
5. volume_30d = count of sold listings found.
6. Classify trend (HOT first): HOT if volume >= 100 AND price up >= 10%; RISING if up >= 5%; COOLING if down > 5%; else STABLE.
7. Sleep 1.0s between item requests.
8. Write payload to data_cache/collectibles_latest.json via write_cache_json_pair.

## [B] Blueprints
Pattern:    atlas_agents/realestate/residential/residential_scraper.py (HTML parse pattern)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://api.ebay.com/buy/browse/v1/item_summary/search?q={query}&filter=buyingOptions:{FIXED_PRICE},conditions:{3000}&limit=10
Fallback:   https://www.ebay.com/sch/i.html?_nkw={query}&LH_Sold=1&LH_Complete=1
Output:     data_cache/collectibles_latest.json
Schema fields: category, item, grade, avg_sold_price, volume_30d, trend

Tracked Items:
  PSA 10 Charizard Base Set       (Pokemon)
  PSA 10 LeBron James RC          (Sports Cards)
  PSA 10 Tom Brady RC             (Sports Cards)
  CGC 9.8 Amazing Fantasy 15 reprint (Comic Books)
  MS-65 Morgan Silver Dollar       (Coins)

## [S] Solutions
Run scraper:
  python -m atlas_agents.alternative.collectibles.collectibles_scraper

Test eBay HTML fallback:
  python -c "import requests; r = requests.get('https://www.ebay.com/sch/i.html?_nkw=PSA+10+Charizard&LH_Sold=1&LH_Complete=1', headers={'User-Agent':'Mozilla/5.0'}); print(r.status_code)"

Run tests:
  python -m pytest tests/test_collectibles.py -v

Verify output:
  python -c "import json,pathlib; d=json.loads(pathlib.Path('data_cache/collectibles_latest.json').read_text()); print(d['record_count'], [i['trend'] for i in d['items']])"

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on collectibles_scraper.py |
| 2 | all 5 items present | record_count == 5 |
| 3 | trend is valid enum value | each trend in {HOT, RISING, STABLE, COOLING} |
| 4 | category is valid enum value | each category in {Sports Cards, Pokemon, Magic: The Gathering, Comic Books, Coins} |
| 5 | generated_at is ISO UTC string | parseable as datetime, ends with Z |
