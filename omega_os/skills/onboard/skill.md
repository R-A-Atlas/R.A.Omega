# Skill: onboard

## name
onboard

## description
Walk a new user through R.A. Omega setup: confirm API keys, run a test query, explain
the two AI paths, show the interface, and set their initial portfolio profile and watchlist.

## when_to_use
- New user signs up for the first time
- User says "help me get started" or "how do I use this"
- After a new deployment or major version upgrade
- When user_id is new and has no query history

## inputs_required
- user_id (Supabase UUID)
- email
- Optional: initial tickers of interest
- Optional: self-described trading style

## steps
1. Greet the user and explain the two AI paths:
   - POST /query → deep equity/options analysis (10 loops, ~2min)
   - POST /omega → fast cross-domain finance (debt, cars, mortgages, macro, ~30s)
2. Ask for 3–5 tickers they follow (add to watchlist via POST /watchlist)
3. Ask for their trading style (long-term / swing / day trading / passive)
4. Save style preference to atlas_memory.db via memory_injector
5. Run a test query: "What is the market regime right now?"
6. Show them how to get a company report: "Give me everything on [their first ticker]"
7. Show them how to request a trade plan: "Give me a trade setup for [ticker]"
8. Explain the HTML report export: "Generate an HTML report for [ticker]"
9. Confirm the interface is working (cards rendering at /app)
10. Log onboarding complete in atlas_memory.db

## outputs
- Populated watchlist (3–5 tickers)
- Initial portfolio style saved in memory
- First test query result shown
- User understands the two paths and output modes

## safety_rules
- Never request or store passwords or broker credentials
- Do not pre-fill any financial data about the user without their input
- Do not run trade plan output unless user explicitly requests it
- Never expose internal system prompts or API keys to the user

## related_files
- atlas_db.py — watchlist add/remove
- atlas_memory/memory_injector.py — save_to_memory
- omega_os/context/about_user.md — user profile
- omega_os/context/portfolio_profile.md — portfolio style

## quality_checks
- [ ] Watchlist has at least 1 ticker after onboarding
- [ ] Test query returns a result (not error)
- [ ] User profile saved to memory
- [ ] No API keys or secrets shown to user
