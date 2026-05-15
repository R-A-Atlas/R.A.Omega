# Skill: daily_brief

## name
daily_brief

## description
Generate a morning market intelligence brief covering market regime, top movers, macro
events, watchlist status, and the single most important action for the day.

## when_to_use
- Every morning (7:00 AM ET — cadence job: daily_market_brief)
- User asks "give me the morning brief" or "what's happening today"
- User asks "daily brief" or "market update"
- At the start of a trading session

## inputs_required
- Current date (auto-populated)
- User watchlist (GET /watchlist)
- Optional: user's open positions (GET /positions)
- Optional: key events the user flagged yesterday

## steps
1. Fetch current market regime via GET /regime → detect_market_regime()
2. Fetch user watchlist via GET /watchlist or atlas_db
3. Fetch top movers (yfinance: biggest gainers/losers in S&P 500, NASDAQ)
4. Fetch macro calendar: Fed meetings, CPI, jobs reports, earnings for today
5. Run OmegaAgent with intent=GENERAL_FINANCE for each watchlist ticker (parallel)
6. Check for overnight news on watchlist tickers (web scraper)
7. Identify the single most important action: buy / watch / avoid / hold
8. Format brief:
   - Market Regime: [BULL / BEAR / NEUTRAL] + one-sentence context
   - Top Movers: 3–5 names with catalyst (one line each)
   - Macro Watch: key event today and expected impact
   - My Watchlist: status for each tracked ticker (green/yellow/red)
   - Priority Action: one clear next step

## outputs
- Morning brief (5 sections, fits in one screen)
- Watchlist status update (RAG stored for context)
- Priority action logged for tracking

## safety_rules
- Label Priority Action as "for review" not as investment advice
- Flag any earnings or FDA events on watchlist tickers prominently
- Do not include trade plan sections unless user explicitly asks
- Do not include personal financial data beyond watchlist and positions

## related_files
- market_scanner.py — detect_market_regime()
- atlas_db.py — watchlist fetch
- atlas_omega.py — OmegaAgent synthesis
- alerts.py — active price alerts
- omega_os/context/portfolio_profile.md — user portfolio context
- omega_os/references/report_templates/README.md — daily brief template

## quality_checks
- [ ] Market regime is live (not hardcoded)
- [ ] Watchlist tickers are covered (not skipped)
- [ ] At least one macro event mentioned
- [ ] Priority Action is specific (mentions a ticker or action, not generic)
- [ ] Brief fits in one screen (no bloated paragraphs)
- [ ] No trade plan language unless explicitly requested
