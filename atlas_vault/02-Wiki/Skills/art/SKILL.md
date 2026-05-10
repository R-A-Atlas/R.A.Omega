---
name: Art Auction Tracker
description: Scrapes MutualArt public auction results pages; tracks realized prices vs estimates; signals ABOVE_ESTIMATE/IN_RANGE/BELOW_ESTIMATE; benchmarks against hardcoded Artprice100 index
type: reference
agent: A2
division: Alternative Assets & Niche
---

# Skill: Art Auction Tracker (A2)

## [D] Direction
Fetch public auction result pages from MutualArt. Parse realized prices, pre-sale
estimate ranges, artist name, title, medium, auction house, and sale date.
Compute premium_over_estimate_pct and classify ABOVE_ESTIMATE / IN_RANGE / BELOW_ESTIMATE.
Include hardcoded Artprice100 benchmark index in output.
Save to data_cache/art_latest.json.

Steps:
1. GET https://www.mutualart.com/Auction-Results (up to 3 pages, 10 records each).
2. Parse HTML for auction result rows: artist, title, medium, house, realized, estimate low/high, date.
3. For each sale: compute premium_over_estimate_pct = ((realized - est_high) / est_high) * 100.
4. Classify signal: ABOVE_ESTIMATE (realized > est_high), IN_RANGE, BELOW_ESTIMATE (< est_low).
5. Sleep 1.5s between pages.
6. Include ARTPRICE100_INDEX = 1842 (Q1 2026) in payload.
7. Write payload to data_cache/art_latest.json via write_cache_json_pair.

## [B] Blueprints
Pattern:    atlas_agents/realestate/residential/residential_scraper.py (paginated HTML scrape)
Utils:      atlas_core/utils/agent_utils.py (write_cache_json_pair)
Primary:    https://www.mutualart.com/Auction-Results
Benchmark:  Artprice100 = 1842 (Q1 2026 — update quarterly)
Output:     data_cache/art_latest.json
Schema fields: artist, title, medium, house, realized_price_usd, estimate_low_usd, estimate_high_usd, sold_date, premium_over_estimate_pct, signal

## [S] Solutions
Run scraper:
  python -m atlas_agents.alternative.art.art_scraper

Test MutualArt connectivity:
  python -c "import requests; r = requests.get('https://www.mutualart.com/Auction-Results', headers={'User-Agent':'Mozilla/5.0'}); print(r.status_code)"

Run tests:
  python -m pytest tests/test_art.py -v

Verify output:
  python -c "import json,pathlib; d=json.loads(pathlib.Path('data_cache/art_latest.json').read_text()); print(d['record_count'], d['artprice100_index'], [s['signal'] for s in d['sales']])"

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on art_scraper.py |
| 2 | artprice100_index present in output | d["artprice100_index"] == 1842 |
| 3 | premium_over_estimate_pct computed correctly | ((realized - est_high) / est_high) * 100 within 0.01 tolerance |
| 4 | signal is valid enum value | each signal in {ABOVE_ESTIMATE, IN_RANGE, BELOW_ESTIMATE} |
| 5 | generated_at is ISO UTC string | parseable as datetime, ends with Z |
