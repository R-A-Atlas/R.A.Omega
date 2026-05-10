---
name: Earnings Parser
description: Pulls upcoming S&P 500 earnings dates and EPS/revenue estimates from yfinance; flags all as CATALYST_UPCOMING within a 14-day window
type: reference
agent: T5
division: Trading Desk
---

# Skill: Earnings Parser (T5)

## [D] Direction
Use yfinance to fetch earnings calendar for S&P 500 tickers. Keep only those
within the next 14 days. Extract date, time (BMO/AMC), est_eps, est_revenue,
sector. Label all CATALYST_UPCOMING. Skip failures silently. Save to
data_cache/earnings_latest.json. Add 0.1s sleep between ticker lookups.

## [B] Blueprints
Pattern:     atlas_agents/crypto/crypto_scraper.py
Utils:       atlas_core/utils/agent_utils.py (write_cache_json_pair)
yfinance:    yf.Ticker(t).calendar  →  Earnings Date, EPS Estimate, Revenue Estimate
SP500 list:  reuse load_sp500_symbols() pattern from equities_scraper.py
Output:      data_cache/earnings_latest.json

Schema:
  { generated_at, source, window_days, record_count,
    upcoming: [{ticker, company_name, date, time, est_eps,
                est_revenue, sector, days_until, signal}] }

signal is always "CATALYST_UPCOMING" — downstream ATLAS loops use days_until for urgency.

## [S] Solutions
Run scraper:
  python -m atlas_agents.trading.earnings_parser.earnings_parser_scraper

Test single ticker:
  python -c "import yfinance as yf; print(yf.Ticker('AAPL').calendar)"

Run tests:
  python -m pytest tests/test_earnings_parser.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | generated_at present | non-empty ISO string |
| 3 | all items within window | days_until >= 0 for all |
| 4 | signal always CATALYST_UPCOMING | no other signal values |
| 5 | stable file written | data_cache/earnings_latest.json exists |
