---
name: Insider Tracker
description: Scrapes SEC Form 4 RSS feed for CEO/CFO/Director stock purchases and sales; flags BUY as BULLISH_INSIDER and SELL as BEARISH_INSIDER
type: reference
agent: T4
division: Trading Desk
---

# Skill: Insider Tracker (T4)

## [D] Direction
Fetch SEC EDGAR Form 4 RSS feed (public, no auth). Parse each filing for
ticker, insider name, role, transaction type, shares, and price. Keep only
C-suite and Director roles. Label purchases BULLISH_INSIDER, sales BEARISH_INSIDER.
Exclude compensation grants. Save to data_cache/insider_trades_latest.json.

## [B] Blueprints
Pattern:    atlas_agents/crypto/crypto_scraper.py
Utils:      atlas_core/utils/agent_utils.py
Parser:     feedparser (already in requirements.txt) or xml.etree.ElementTree
Output:     data_cache/insider_trades_latest.json

SEC EDGAR RSS (always-live, no auth):
  https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&dateb=&owner=include&count=40&output=atom

User-Agent required by SEC:
  "ATLAS-InsiderTracker/1.0 (educational; contact@example.com)"

Signal logic:
  Form 4 transaction code P (Purchase) → BUY → BULLISH_INSIDER
  Form 4 transaction code S (Sale)     → SELL → BEARISH_INSIDER
  Codes A/M/G (awards/grants)          → exclude

Roles to keep: CEO, CFO, COO, President, Director, Chairman

## [S] Solutions
Run scraper:
  python -m atlas_agents.trading.insider_tracker.insider_tracker_scraper

Check SEC rate limit compliance:
  grep -n "sleep" insider_tracker_scraper.py  # must have delay between requests

Run tests:
  python -m pytest tests/test_insider_tracker.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | generated_at present | non-empty ISO string |
| 3 | all filings have required fields | ticker, insider_name, role, transaction_type, date |
| 4 | no GRANT/AWARD in output | signal only BULLISH_INSIDER or BEARISH_INSIDER |
| 5 | stable file written | data_cache/insider_trades_latest.json exists |
