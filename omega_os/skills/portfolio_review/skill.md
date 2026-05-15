# Skill: portfolio_review

## name
portfolio_review

## description
Review all open positions: performance summary, risk exposure, rebalancing needs,
and a watchlist for next week. Runs as a weekly cadence job or on-demand.

## when_to_use
- Weekly — every Sunday evening (cadence job: weekly_portfolio_review)
- User asks "review my portfolio" or "how are my positions doing?"
- User asks "should I rebalance?" or "what's my risk exposure?"
- After a major market event that may affect open positions

## inputs_required
- User positions: GET /positions (Supabase) or positions_cache.json (legacy)
- Optional: risk_profile.md for max drawdown and position size rules
- Optional: current market regime (GET /regime)

## steps
1. Fetch open positions via GET /positions or atlas_db.fetch_positions_cache_shapes(user_id)
2. For each position, fetch live price via yfinance
3. Calculate P&L, % change from entry, current risk as % of portfolio
4. Fetch market regime via GET /regime
5. Run OmegaAgent analysis for any position flagged as high-risk (>10% drawdown or near stop)
6. Check for earnings, FDA events, or macro events in next 7 days for each held ticker
7. Compare current risk exposure to risk_profile.md rules
8. Identify rebalancing needs: overweight positions, underperforming positions
9. Build watchlist for next week: new opportunities based on macro regime
10. Format weekly portfolio review report:
    - Performance Summary (overall P&L, best/worst positions)
    - Position Review (table: ticker, entry, current, P&L%, risk%)
    - Risk Exposure (total portfolio risk vs max acceptable)
    - Rebalancing Needs (positions to trim or exit)
    - Next Week Watchlist (3–5 new opportunities)

## outputs
- Weekly portfolio review report
- Risk exposure summary
- Rebalancing recommendations
- Next week watchlist

## safety_rules
- Never execute trades automatically — all recommendations require user confirmation
- Rebalancing suggestions are labeled "for review" not as instructions
- Do not expose other users' portfolio data
- Do not hardcode broker credentials — use environment variables only
- Flag any positions approaching stop loss or maximum loss threshold

## related_files
- atlas_db.py — fetch_positions_cache_shapes()
- atlas_tracker.db — trade tracking and win-rate history
- positions_cache.json — legacy local positions
- market_scanner.py — detect_market_regime()
- omega_os/context/risk_profile.md — user risk rules
- omega_os/context/portfolio_profile.md — portfolio style

## quality_checks
- [ ] All open positions are covered (none skipped)
- [ ] Live prices fetched (not stale cache)
- [ ] P&L calculated correctly for each position
- [ ] Risk exposure compared to risk_profile limits
- [ ] No automatic trade execution
- [ ] Rebalancing recommendations labeled "for review"
- [ ] Upcoming earnings/events flagged for held tickers
