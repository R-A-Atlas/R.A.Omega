# Skill: watchlist_update

## name
watchlist_update

## description
Update the watchlist with fresh data, flag tickers that need attention, and remove stale
or no-longer-relevant tickers. Runs daily or on-demand.

## when_to_use
- Daily (cadence job: daily_watchlist_refresh)
- User says "update my watchlist" or "check my watchlist"
- User says "add [ticker] to watchlist" or "remove [ticker] from watchlist"
- After receiving a tip or news item about a new ticker

## inputs_required
- Current watchlist: GET /watchlist
- Optional: new ticker to add or ticker to remove
- Optional: context for addition ("I'm watching NVDA for earnings")

## steps
1. Fetch current watchlist via GET /watchlist or atlas_db
2. For each ticker on watchlist:
   a. Fetch live price (yfinance)
   b. Check for news in last 24 hours (web scraper)
   c. Check for upcoming earnings or events (next 7 days)
   d. Flag as: GREEN (all clear) / YELLOW (watch, news or event) / RED (urgent, major move or catalyst)
3. Add new ticker if provided: POST /watchlist with ticker + optional context
4. Remove ticker if requested: DELETE /watchlist/{ticker}
5. Save updated watchlist status to atlas_memory.db
6. Surface tickers flagged RED or YELLOW for immediate attention
7. Archive removed tickers with removal reason and date

## outputs
- Updated watchlist with RYG status for each ticker
- List of tickers flagged RED or YELLOW (needs attention)
- Upcoming events for next 7 days (earnings, Fed, CPI)
- Removal confirmation if ticker was removed

## safety_rules
- Do not automatically remove tickers from watchlist without explicit user instruction
- Do not automatically trade or place alerts based on watchlist status — surface for user review
- Flag earnings and FDA events prominently (these can cause major overnight moves)
- Never add tickers to watchlist that belong to another user

## related_files
- atlas_db.py — watchlist add/remove, GET /watchlist, POST /watchlist, DELETE /watchlist/{ticker}
- api_server.py — watchlist routes
- atlas_dashboard_v4.html — syncWatchlistFromServer()
- alerts.py — price alerts for watchlist tickers
- atlas_memory/memory_injector.py — save watchlist context

## quality_checks
- [ ] All watchlist tickers have a RYG status after update
- [ ] Live prices fetched (not stale)
- [ ] Upcoming events (next 7 days) checked for all tickers
- [ ] RED/YELLOW tickers surfaced prominently
- [ ] No tickers removed without explicit user instruction
- [ ] Removed tickers archived with reason and date
