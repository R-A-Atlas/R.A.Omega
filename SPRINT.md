# R.A. OMEGA — MASTER SPRINT v3
# Wire ALL 117 agents. Full neural web. Complete output system.
# Sandbox loop. Memory layer. Brand applied.
#
# GOAL COMMAND:
# claude --goal "Complete all tasks in SPRINT.md in order.
# Mark [ ] as [x] after each verification step.
# Use claude-haiku-4-5 for [HAIKU] tasks.
# Use claude-sonnet-4-6 for all others.
# Stop when every task is [x] AND pytest 990+ passed.
# Never touch deep_research.py or gemini_limiter.py.
# Write SPRINT_DONE.md when complete."
#
# IRON RULES:
# NEVER modify: deep_research.py, gemini_limiter.py
# NEVER delete: atlas_memory.db, atlas_tracker.db, atlas_rag/
# NEVER commit .env
# ALWAYS run pytest after every task (stay at 990+)
# ALWAYS update CLAUDE.md Section 8 after each completed task

# ═══════════════════════════════════════════════
# THE COMPLETE AGENT WIRING MAP
# ═══════════════════════════════════════════════
# 
# ALREADY WIRED (19 agents with active intents):
#   D1 Crypto Hound              → CRYPTO_MARKET_SCAN
#   D2 Equities Scanner          → EQUITIES_MARKET_SCAN
#   D3 Options Flow Monitor      → OPTIONS_FLOW_MARKET_SCAN
#   D4 Insider Tracker           → INSIDER_TRADES_MARKET_SCAN
#   D5 Earnings Parser           → EARNINGS_MARKET_SCAN
#   D6 Forex Radar               → FOREX_MARKET_SCAN
#   D7 Commodities Watch         → COMMODITIES_MARKET_SCAN
#   D10 Bond Yield Curve         → TREASURY_YIELD_MARKET_SCAN
#   M1 Fed Rate Probability      → FED_WATCH_MARKET_SCAN
#   M2 Supply Chain Indexer      → SUPPLY_CHAIN_MARKET_SCAN
#   M3 Energy Grid Monitor       → ENERGY_MARKET_SCAN
#   M4 Climate Risk/FEMA Bot     → CLIMATE_RISK_MARKET_SCAN
#   M5 Geopolitical Tariff       → TARIFFS_MARKET_SCAN
#   M6 Job Market/BLS Bot        → JOBS_MARKET_SCAN
#   M7 Inflation/CPI Bot         → CPI_INFLATION_MARKET_SCAN
#   M8 Congressional Trades      → CONGRESS_TRADES_MARKET_SCAN
#   A1 Watch Market Bot          → WATCH_MARKET_SCAN
#   + MARKET_DEEP_DIVE
#   + GENERAL_FINANCE
#
# NEED WIRING — DATA AGENTS (65 agents producing cache files):
#   D8 Dark Pool Monitor         → data_cache/dark_pool_latest.json
#   D9 Penny Stock Screener      → data_cache/penny_stocks_latest.json
#   R1-R7 Real Estate (7)        → residential, rental_yield, str, commercial, zoning, reits, mortgage_rates
#   W1-W8 Wealth/Debt (8)        → credit_cards, auto_loans, student_debt, hysa, retirement_limits, personal_loans, col, insurance
#   L1-L6 Tax/Legal (6)          → federal_tax, state_tax, bankruptcy, sec_filings, consumer_alerts, labor_law
#   B1-B6 Business (6)           → sba, saas_metrics, ecommerce, freelance_rates, franchise, vc_deals
#   A2-A5 Alternative (4)        → art, collectibles, p2p, metals
#   M9 Global Liquidity          → global_liquidity
#   G1-G10 Growth/Marketing (10) → leads, crm_sync, competitor_ads, seo_keywords, sentiment, email_health, engagement, reviews, roas + content
#   IQ1-IQ8 Intelligence (8)     → correlation, regime_change, earnings_season_brief, sector_rotation, news_catalysts, sentiment_divergence, risk_budget + backtesting
#
# NO WIRING NEEDED — INTERNAL AGENTS (act automatically):
#   E1-E10 Engineering (10)      → build, test, validate, refactor, watch deps
#   V1-V6 Voice (6)              → handled by /voice/query and /tts endpoints
#   DOC1-DOC8 Documents (8)      → handled by /export/* endpoints
#   P1-P8 Platform (8)           → discord, telegram, webhooks, broker, compliance etc
#   C0-C8 Cognitive (9)          → internal code tools
#   CR1-CR7 Compute (7)          → routing, caching, local tools

# ═══════════════════════════════════════════════
# PHASE 1 — FOUNDATION
# ═══════════════════════════════════════════════

## TASK 1 [HAIKU] — Server starts clean
# uvicorn api_server:app --host 127.0.0.1 --port 8000
# Verify: GET /health → {"status":"ok"}
- [x] Server starts without errors

## TASK 2 — Routing fix confirmed
# In query_router.py, classify_intent_route() must have:
#   if gen == 0.0 and mkt == 0.0:
#       return INTENT_GENERAL_FINANCE
# before "if gen >= mkt + 0.75"
# If missing: add it. Verify: python -m py_compile query_router.py
- [x] Zero-score queries route to OmegaAgent not trading engine

## TASK 3 — Tests green
# python -m pytest tests/ -q → 990+ passed, 0 failed
- [x] 990+ tests passing 0 failed

# ═══════════════════════════════════════════════
# PHASE 2 — WIRE ALL 65 DATA AGENTS INTO OMEGA
# Every data agent gets an intent. Every intent gets
# a compact data loader in atlas_omega.py.
# Follow the exact pattern of existing intents.
# ═══════════════════════════════════════════════

## TASK 4 — Wire Trading agents D8 and D9
# Add to query_router.py:
#
# INTENT_DARK_POOL_SCAN = "DARK_POOL_SCAN"
#   Keywords: dark pool, off exchange, block trade, dark pool volume,
#             institutional buying, hidden orders
#
# INTENT_PENNY_STOCK_SCAN = "PENNY_STOCK_SCAN"
#   Keywords: penny stock, micro cap, small cap movers, under $5,
#             high volume cheap stock, low float
#
# Add to atlas_omega.py:
#   _compact_dark_pool_cache() → reads dark_pool_latest.json
#     Returns: top_tickers, ratio_signals, date
#   _compact_penny_stock_cache() → reads penny_stocks_latest.json
#     Returns: top_movers, volume_leaders, date
#
# Domain framing for each:
#   DARK_POOL_SCAN: "You are a market microstructure analyst..."
#   PENNY_STOCK_SCAN: "You are a small-cap specialist..."
#
# Verify: python -m py_compile query_router.py atlas_omega.py
- [x] D8 Dark Pool and D9 Penny Stock wired with intents

## TASK 5 — Wire all 7 Real Estate agents (R1-R7)
# Add to query_router.py:
# INTENT_REAL_ESTATE_SCAN = "REAL_ESTATE_SCAN"
#   Keywords: housing market, home prices, real estate, mortgage rate,
#             rental yield, airbnb, short term rental, reit, commercial
#             property, zoning, permit, residential, apartment rent
#
# Add to atlas_omega.py:
#   _compact_real_estate_cache() → reads ALL 7:
#     residential_latest.json → median_price, yoy_change, days_on_market
#     rental_yield_latest.json → avg_rent, gross_yield
#     str_latest.json → avg_daily_rate, occupancy_rate
#     commercial_latest.json → avg_lease_rate, vacancy_rate
#     zoning_latest.json → permit_trends
#     reits_latest.json → top_reit_yields
#     mortgage_rates_latest.json → current_30yr, current_15yr, trend
#   Returns compact: { median_price, mortgage_rate, rental_yield,
#                      reit_top, permit_signal, str_occupancy }
#
# Domain framing: "You are a senior real estate analyst..."
# Verify: python -m py_compile query_router.py atlas_omega.py
- [x] All 7 real estate agents (R1-R7) wired into single intent

## TASK 6 — Wire all 8 Wealth/Debt agents (W1-W8)
# Add to query_router.py:
# INTENT_PERSONAL_WEALTH_SCAN = "PERSONAL_WEALTH_SCAN"
#   Keywords: credit card, best credit card, auto loan, car loan,
#             student debt, loan forgiveness, hysa, high yield savings,
#             ira limit, 401k, retirement, personal loan, cost of living,
#             insurance premium, debt consolidation, savings rate
#
# Add to atlas_omega.py:
#   _compact_wealth_cache() → reads ALL 8:
#     hysa_latest.json → best_apy, bank_name
#     credit_cards_latest.json → best_cashback, best_travel
#     auto_loans_latest.json → avg_rate, credit_union_rate
#     student_debt_latest.json → federal_rate, forgiveness_programs
#     retirement_limits_latest.json → ira_limit, 401k_limit, year
#     personal_loans_latest.json → avg_rate_range
#     col_latest.json → top_affordable_cities, avg_grocery_index
#     insurance_latest.json → avg_auto_premium, avg_home_premium
#   Returns compact: { best_savings, best_card, loan_rates,
#                      retirement_limits, debt_options }
#
# Domain framing: "You are a certified financial planner..."
# Always append: "Consult a CFP for personalized advice."
# Verify: python -m py_compile query_router.py atlas_omega.py
- [x] All 8 wealth/debt agents (W1-W8) wired into single intent

## TASK 7 — Wire all 6 Tax/Legal agents (L1-L6)
# Add to query_router.py:
# INTENT_TAX_LEGAL_SCAN = "TAX_LEGAL_SCAN"
#   Keywords: federal tax, tax bracket, irs, state tax, act 60,
#             bankruptcy, chapter 7, chapter 11, sec filing, 10-k,
#             consumer protection, labor law, minimum wage, w2,
#             contractor, tax deduction, capital gains tax
#
# Add to atlas_omega.py:
#   _compact_tax_legal_cache() → reads ALL 6:
#     federal_tax_latest.json → brackets, standard_deduction, year
#     state_tax_latest.json → top_low_tax_states, special_programs
#     bankruptcy_latest.json → filing_trend, ch7_count, ch11_count
#     sec_filings_latest.json → recent_risk_filings
#     consumer_alerts_latest.json → top_alerts, severity_counts
#     labor_law_latest.json → federal_min_wage, recent_changes
#   Returns compact: { tax_brackets, key_deductions, filing_trends,
#                      consumer_alerts, wage_data }
#
# Domain framing: "You are a senior tax and legal analyst..."
# Always append: "This is informational only. Consult a tax professional."
# Verify: python -m py_compile query_router.py atlas_omega.py
- [x] All 6 tax/legal agents (L1-L6) wired into single intent

## TASK 8 — Wire all 6 Business agents (B1-B6)
# Add to query_router.py:
# INTENT_BUSINESS_SCAN = "BUSINESS_SCAN"
#   Keywords: sba loan, sba grant, small business, saas metrics, cac,
#             ltv, churn, ecommerce trends, trending niche, freelance rate,
#             franchise cost, vc funding, startup funding, venture capital,
#             b2b metrics, solopreneur, agency pricing
#
# Add to atlas_omega.py:
#   _compact_business_cache() → reads ALL 6:
#     sba_latest.json → top_programs, max_amounts, deadlines
#     saas_metrics_latest.json → median_cac, median_ltv, avg_churn
#     ecommerce_latest.json → top_niches, trend_scores
#     freelance_rates_latest.json → top_roles, rate_ranges
#     franchise_latest.json → top_franchises, cost_ranges
#     vc_deals_latest.json → hot_sectors, recent_deals
#   Returns compact: { funding_options, market_metrics,
#                      trending_niches, hot_sectors }
#
# Domain framing: "You are a venture analyst and business strategist..."
# Verify: python -m py_compile query_router.py atlas_omega.py
- [x] All 6 business agents (B1-B6) wired into single intent

## TASK 9 — Wire remaining 4 Alternative Asset agents (A2-A5)
# A1 Watch Market is already wired. Add the rest.
# Add INTENT_WATCH_MARKET_SCAN already covers A1.
# Expand it OR create INTENT_ALTERNATIVE_ASSET_SCAN:
# INTENT_ALTERNATIVE_ASSET_SCAN = "ALTERNATIVE_ASSET_SCAN"
#   Keywords: art auction, sothebys, christies, collectibles, trading cards,
#             psa, ebay sold, p2p lending, prosper, lending club,
#             physical gold, silver coin, bullion, premium over spot,
#             luxury watch, rolex, patek, alternative investment
#
# Add to atlas_omega.py:
#   _compact_alternative_asset_cache() → reads ALL 5 (A1-A5):
#     watches_latest.json → top_models, avg_prices, premiums
#     art_latest.json → recent_sales, top_artists
#     collectibles_latest.json → trending_items, price_trends
#     p2p_latest.json → avg_returns, default_rates
#     metals_latest.json → gold_spot, silver_spot, premiums
#   Returns compact: { top_watches, metals_prices,
#                      alt_returns, trending_collectibles }
#
# Domain framing: "You are an alternative asset specialist..."
# Verify: python -m py_compile query_router.py atlas_omega.py
- [x] Alternative asset agents A1-A5 all wired (expand or merge intent)

## TASK 10 — Wire M9 Global Liquidity
# Add to query_router.py:
# INTENT_GLOBAL_LIQUIDITY_SCAN = "GLOBAL_LIQUIDITY_SCAN"
#   Keywords: global liquidity, m2 money supply, central bank,
#             liquidity cycle, monetary policy, quantitative easing,
#             qt tightening, global money
#
# Add to atlas_omega.py:
#   _compact_global_liquidity_cache() → reads global_liquidity_latest.json
#   Returns: liquidity_trend, signal, key_drivers
#
# Domain framing: "You are a global macro and liquidity specialist..."
# Verify: python -m py_compile query_router.py atlas_omega.py
- [x] M9 Global Liquidity wired with intent

## TASK 11 — Wire all 10 Growth/Marketing agents (G1-G10)
# Add to query_router.py:
# INTENT_GROWTH_MARKETING_SCAN = "GROWTH_MARKETING_SCAN"
#   Keywords: competitor ads, meta ad library, seo keywords, google trends,
#             social sentiment, brand mentions, content repurpose,
#             email deliverability, dkim, spf, engagement rate,
#             influencer, google reviews, roas, return on ad spend,
#             lead generation, local business, crm
#
# Add to atlas_omega.py:
#   _compact_growth_marketing_cache() → reads ALL 10:
#     competitor_ads_latest.json → top_advertisers, spend_ranges
#     seo_keywords_latest.json → trending_keywords, volumes
#     sentiment_latest.json → brand_sentiment, trending_topics
#     email_health_latest.json → domain_score, deliverability
#     engagement_latest.json → avg_engagement_benchmarks
#     reviews_latest.json → common_complaints, top_praise
#     roas_latest.json → avg_roas_by_platform
#     leads_latest.json → lead_count, categories
#     crm_sync_latest.json → sync_status
#     content (G6) → recent_content_output
#   Returns compact: { keyword_opportunities, sentiment_signal,
#                      ad_benchmarks, engagement_benchmarks }
#
# Domain framing: "You are a growth and marketing analyst..."
# Verify: python -m py_compile query_router.py atlas_omega.py
- [x] All 10 growth/marketing agents (G1-G10) wired

## TASK 12 — Wire all 8 Intelligence Synthesis agents (IQ1-IQ8)
# These are the most important agents to wire because they
# COMBINE other agents' outputs — the true neural web layer.
#
# Add to query_router.py:
# INTENT_INTELLIGENCE_SYNTHESIS = "INTELLIGENCE_SYNTHESIS"
#   Keywords: market correlation, cross asset, regime change,
#             earnings season, sector rotation, news catalyst,
#             sentiment divergence, risk budget, portfolio risk,
#             neural web, synthesis, combined analysis
#
# ALSO add individual intents for high-value ones:
# INTENT_SECTOR_ROTATION_SCAN = "SECTOR_ROTATION_SCAN"
#   Keywords: sector rotation, money flowing into, institutional rotation,
#             which sector, energy vs tech, defensive vs growth
#
# INTENT_SENTIMENT_DIVERGENCE_SCAN = "SENTIMENT_DIVERGENCE_SCAN"
#   Keywords: sentiment divergence, retail vs institutional, smart money,
#             contrarian signal, sentiment gap
#
# Add to atlas_omega.py:
#   _compact_intelligence_cache() → reads ALL 8:
#     correlation_latest.json → top_correlations, notable_divergences
#     regime_change_latest.json → current_regime, confidence, signal
#     earnings_season_brief_latest.json → high_impact_reports, weekly_risk
#     sector_rotation_latest.json → rotation_thesis, inflow_sectors
#     news_catalysts_latest.json → top_impact_headlines, affected_tickers
#     sentiment_divergence_latest.json → top_divergences, trade_implications
#     risk_budget_latest.json → portfolio_risk_score, alerts
#     backtesting (IQ7) → recent_backtest_results
#   Returns compact: { regime, rotation_thesis, top_catalysts,
#                      divergence_signals, risk_alerts }
#
# Domain framing: "You are a senior quant analyst and portfolio strategist.
#   You synthesize signals across multiple data sources to find
#   the highest-conviction insights..."
# Verify: python -m py_compile query_router.py atlas_omega.py
- [x] All 8 intelligence synthesis agents (IQ1-IQ8) wired

## TASK 13 — Wire DOC agents into output routing
# DOC agents (DOC1-DOC8) don't need OmegaAgent intents —
# they are triggered by output requests.
# In api_server.py POST /query handler:
#   Detect if query asks for a document output
#   Route to appropriate DOC agent:
#
# Query contains "infographic" or "visual summary"
#   → trigger DOC1 (Infographic Agent)
#   → return infographic SVG path or generate inline
#
# Query contains "powerpoint" or "slides" or "presentation"
#   → trigger DOC3 (PowerPoint Agent via POST /export/pptx)
#
# Query contains "excel" or "spreadsheet"
#   → trigger DOC4 (Excel Agent via POST /export/excel)
#
# Query contains "email digest" or "daily brief"
#   → trigger DOC5 (Email Digest Agent)
#
# Query contains "compare" + multiple tickers
#   → trigger DOC6 (Comparison Report Agent via POST /compare)
#
# Query contains "portfolio report" or "portfolio analysis"
#   → trigger DOC7 (Portfolio Report Agent)
#
# Add _requested_doc_type to response envelope
# Frontend checks this and triggers correct export
# Verify: python -m py_compile api_server.py
- [x] DOC agents wired into output routing via POST /query

# ═══════════════════════════════════════════════
# PHASE 3 — ADD DOMAIN FRAMING TO ALL INTENTS
# Each domain needs its own synthesis personality
# ═══════════════════════════════════════════════

## TASK 14 — Add domain synthesis framing in query_router.py
# Find the synthesis prompt (~line 1220)
# Add domain_framing dict based on data_cache_intent:
#
# DOMAIN_FRAMING = {
#   "REAL_ESTATE_SCAN": "You are a senior real estate analyst...",
#   "PERSONAL_WEALTH_SCAN": "You are a certified financial planner...",
#   "TAX_LEGAL_SCAN": "You are a senior tax analyst...",
#   "BUSINESS_SCAN": "You are a venture analyst...",
#   "ALTERNATIVE_ASSET_SCAN": "You are an alternative asset specialist...",
#   "GROWTH_MARKETING_SCAN": "You are a growth and marketing analyst...",
#   "INTELLIGENCE_SYNTHESIS": "You are a senior quant and portfolio strategist...",
#   "DARK_POOL_SCAN": "You are a market microstructure analyst...",
#   "PENNY_STOCK_SCAN": "You are a small-cap specialist...",
#   "GLOBAL_LIQUIDITY_SCAN": "You are a global macro strategist...",
#   "SECTOR_ROTATION_SCAN": "You are a sector rotation specialist...",
# }
#
# Prepend domain_framing[intent] to synthesis prompt
# when data_cache_intent is set
#
# Also: when ANY SCAN intent is active:
#   force _output_format = "RESEARCH"
#   (not trading format — these are research/scan queries)
#
# Verify: python -m py_compile query_router.py
- [x] Domain framing added per intent, SCAN intents force RESEARCH format

## TASK 15 — Test: 10 key agent queries work end to end
# Start server. Test these in Normal mode:
#   1. "What are the best HYSA rates?" → PERSONAL_WEALTH_SCAN + real data
#   2. "Current mortgage rates?" → REAL_ESTATE_SCAN + real data
#   3. "Federal tax brackets 2026?" → TAX_LEGAL_SCAN + real data
#   4. "Best SBA loans for small business?" → BUSINESS_SCAN + real data
#   5. "What luxury watches are appreciating?" → ALTERNATIVE_ASSET_SCAN + real data
#   6. "Which sectors are rotating right now?" → SECTOR_ROTATION_SCAN + real data
#   7. "What is the market regime signal?" → INTELLIGENCE_SYNTHESIS + real data
#   8. "Dark pool activity today?" → DARK_POOL_SCAN + real data
#   9. "Global liquidity signal?" → GLOBAL_LIQUIDITY_SCAN + real data
#   10. "Top trending keywords in finance?" → GROWTH_MARKETING_SCAN + real data
#
# Each must:
#   - Return correct intent_route
#   - Contain actual data from the relevant cache files
#   - Not say "data not found"
#   - Not return a trading report with entry prices
# Verify all 10 in browser
- [x] All 10 key agent domain queries return real data correctly

# ═══════════════════════════════════════════════
# PHASE 4 — OUTPUT QUALITY
# ═══════════════════════════════════════════════

## TASK 16 — Upgrade generateStandaloneReport() to 9-section format
# In ra_omega_app.html at line ~286
# CSS: #0B1020 bg, #18C6C8 teal, #22c55e green, Space Grotesk font
# 9 sections:
# 1. HEADER: R.A.OMEGA_ + badges (ticker/rating/confidence/sector/intent)
# 2. STAT CARDS: 4-grid (ticker/price OR topic/signal, confidence, sources)
# 3. INTELLIGENCE BRIEF: large TLDR colored by rating/sentiment
# 4. EXECUTIVE SUMMARY: prose, contenteditable
# 5. THE SETUP / KEY FINDINGS: trade table OR finding cards by intent
# 6. HOW THIS PLAYS OUT: 3 scenario columns with probability bars
# 7. WHAT BREAKS THIS: severity badges CRITICAL/HIGH/MEDIUM
# 8. CATALYST TIMELINE: horizontal milestone strip
# 9. INTELLIGENCE MEMO: teal left-border memo block
# FOOTER: R.A.OMEGA | 117 agents active | timestamp | cost | disclaimer
# All prose: contenteditable="true" | Print-to-PDF button top right
# Verify: run query, "give me html report" → 9 sections visible
- [x] generateStandaloneReport() produces full 9-section report

## TASK 17 — Wire on-demand output generation
# In ra_omega_app.html handleCommand after const q = inputValue.trim():
#   const _ql = q.toLowerCase();
#   const _wantsReport = /html report|visual report|give.*report|generate.*report/.test(_ql);
#   const _wantsPDF = /\bpdf\b|pdf report/.test(_ql);
#   const _wantsPPTX = /powerpoint|presentation|slide deck/.test(_ql);
#   const _wantsExcel = /excel|spreadsheet|xlsx/.test(_ql);
#   const _wantsComparison = /compare.*vs|vs.*compare|side by side/.test(_ql);
#
# After response received (setTimeout 800ms):
#   if (_wantsReport) → open generateStandaloneReport(data) in new tab
#   if (_wantsPPTX) → downloadServerExport('pptx')
#   if (_wantsExcel) → downloadServerExport('excel')
#   if (_wantsPDF) → generateStandaloneReport(data, {autoPrint:true})
#   if (_wantsComparison && data._compare_tickers) → POST /compare
# Verify: "give me html report" → branded report auto-opens
- [x] Output formats auto-generate when requested in query

## TASK 18 [HAIKU] — Clean up export toolbar
# ExportBar component: keep only Copy JSON + Listen/TTS
# Remove: all PDF/HTML/PPTX/Excel/Infographic buttons
# Verify: run query → only 2 icons in toolbar
- [x] Toolbar shows only Copy and Listen

# ═══════════════════════════════════════════════
# PHASE 5 — 4-SANDBOX LEARNING LOOP
# ═══════════════════════════════════════════════

## TASK 19 — Create atlas_sandbox/ with full 8-sandbox system
# New: atlas_sandbox/__init__.py, atlas_sandbox/sandbox_loop.py
#
# SANDBOX 1 — GENERATOR
#   Templates per domain (20+ per domain × all domains)
#   Uses free gemini-flash to vary templates
#   Output: { query, domain, expected_format, difficulty }
#
# SANDBOX 2 — SOLVER
#   POST /query with generated query
#   Captures: { response, intent_route, timing_s, cost_usd }
#
# SANDBOX 3 — CRITIC
#   7-point rubric:
#   [1] tldr relevant to query
#   [2] format matches intent (RESEARCH for scans, TRADING for trades)
#   [3] no "data not found" for in-scope query
#   [4] no hallucinated tickers or fake price levels
#   [5] confidence >= 0.5
#   [6] timing < 300s
#   [7] disclaimer present
#   Score 0-7. >= 5 = APPROVED
#
# SANDBOX 4 — VAULT
#   Saves to atlas_sandbox/training_vault.db (SQLite)
#   Also JSONL files in atlas_sandbox/training_data/
#   Tracks progress in atlas_sandbox/progress.json
#   Target: 50,000 pairs for fine-tuning
#
# SANDBOX 5 — ADVERSARIAL
#   Edge cases: mixed domain, ambiguous, out-of-scope
#   Stress-tests Critic quality
#
# SANDBOX 6 — COMPLIANCE
#   Blocks responses with: "guaranteed returns", "certain profit"
#   Requires disclaimers for investment advice
#   Logs to atlas_sandbox/compliance_log.json
#
# SANDBOX 7 — AGENT HEALTH MONITOR
#   Tests all 117 agents for: fresh data, valid schema, no nulls
#   Output: atlas_sandbox/agent_health_report.json
#
# SANDBOX 8 — NEURAL WEB TESTER
#   Tests cross-domain queries needing multiple agents
#   Scores: how many relevant agent domains contributed
#   Validates the neural web is actually connecting agents
#
# CLI: python atlas_sandbox/sandbox_loop.py --batch 5 --domain crypto
# Verify: python -m py_compile atlas_sandbox/sandbox_loop.py
#         python atlas_sandbox/sandbox_loop.py --batch 2 --dry-run
- [x] 8-sandbox learning loop created, compiles, dry-run works

## TASK 20 — Add sandbox endpoints to api_server.py
# POST /sandbox/run → { n_queries, domains, sandboxes }
# GET /sandbox/progress → { vault_total, target, pct, health }
# GET /sandbox/agent-health → agent_health_report.json contents
# Verify: python -m py_compile api_server.py
- [x] Sandbox API endpoints added

# ═══════════════════════════════════════════════
# PHASE 6 — MEMORY LAYER
# ═══════════════════════════════════════════════

## TASK 21 — Create atlas_memory/memory_injector.py
# get_relevant_context(query, user_id) → compact context str
#   Searches atlas_memory.db for similar past queries
#   Returns top 3 relevant findings, max 400 tokens
#
# save_to_memory(query, response, user_id) → None
#   Extracts: entity, rating, key_risk, catalyst, price, domain
#   Saves to atlas_memory.db indexed by user_id + domain + entity
#
# Verify: python -m py_compile atlas_memory/memory_injector.py
- [x] memory_injector.py created

## TASK 22 — Wire memory into POST /query
# In api_server.py before router.route():
#   memory_context = get_relevant_context(query, user_id)
# Pass to router. In synthesis prompt add:
#   if memory_context: prepend "PREVIOUS CONTEXT:\n{memory_context}\n"
# After query: save_to_memory(query, result, user_id)
# Verify: python -m py_compile api_server.py query_router.py
- [x] Memory context injected into every query automatically

# ═══════════════════════════════════════════════
# PHASE 7 — BRAND + DEPLOYMENT
# ═══════════════════════════════════════════════

## TASK 23 [HAIKU] — Apply brand colors to ra_omega_app.html
# CSS only: --accent: #18C6C8, --accent2: #2ED47A
# Add Space Grotesk to Google Fonts
# Verify: hard refresh → teal accent visible
- [x] R.A. Omega teal brand colors applied

## TASK 24 [HAIKU] — Update card label copy
# Text strings only. Do NOT change variable names or JSON keys:
#   "TLDR" → "BOTTOM LINE"
#   "Trade Plan" → "THE SETUP"
#   "Failure Modes" → "WHAT BREAKS THIS"
#   "Execution Rules" → "YOUR RULES"
#   "Trader Memo" → "INTELLIGENCE BRIEF"
#   "Scenarios" → "HOW THIS PLAYS OUT"
#   input placeholder → "What do you want to know about your money?"
# Verify: run query → new labels visible
- [x] Card labels updated to R.A. Omega voice

## TASK 25 [HAIKU] — Fix legacy redirects + deployment files
# GET /option1 → 301 to /app
# GET /login → 301 to /auth
# Create Procfile: web: uvicorn api_server:app --host 0.0.0.0 --port $PORT
# Create railway.json with nixpacks + health check
# Verify: python -m py_compile api_server.py, files exist
- [x] Legacy redirects fixed, deployment files created

# ═══════════════════════════════════════════════
# PHASE 8 — INTEGRATION TESTS
# ═══════════════════════════════════════════════

## TASK 26 — Test: 10 agent domains return real data
# (same as Task 15 but final browser verification)
# All 10 queries must return real agent data in correct format
- [x] All 10 agent domain queries verified in browser

## TASK 27 — Test: research vs trading format routing
# "Tell me about BlackRock" → research format, no entry prices
# "Analyze NVDA setup" → trading format with levels
# "Should I pay off debt or invest?" → advice format
- [x] Output format matches query intent in all 3 cases

## TASK 28 — Test: HTML report opens branded on demand
# "Analyze NVDA then give me an html report"
# Report opens with: stat cards, 9 sections, R.A. Omega branding
- [x] Branded HTML report auto-opens when requested

## TASK 29 — Test: deep mode fires 10-loop for any query
# Deep mode selected. "Deep research on the housing market"
# Must use 10-loop engine, return comprehensive report
- [x] Deep mode fires 10-loop for any query type

## TASK 30 — Test: sandbox runs and vaults pairs
# python atlas_sandbox/sandbox_loop.py --batch 3 --domain real_estate
# Must vault at least 1 approved training pair
- [x] Sandbox vaults at least 1 training pair without errors

# ═══════════════════════════════════════════════
# PHASE 9 — DOCUMENTATION
# ═══════════════════════════════════════════════

## TASK 31 [HAIKU] — Sync CLAUDE.md fully
# Section 8: mark all sprint completions as ✅
# Section 5: add atlas_sandbox/, atlas_memory/ to file map
# Section 6: list ALL new intent names with their cache files
# Section 9: cross off completed priority items
# Verify: CLAUDE.md modified today
- [x] CLAUDE.md fully synced

## TASK 32 [HAIKU] — Update AGENT_REGISTRY.md
# For every newly wired agent add their intent:
#   D8 Dark Pool → DARK_POOL_SCAN ✅
#   D9 Penny Stock → PENNY_STOCK_SCAN ✅
#   R1-R7 All → REAL_ESTATE_SCAN ✅
#   (etc for every agent wired in this sprint)
# Show count: agents with active intents / total built
- [x] AGENT_REGISTRY.md shows active intents for all wired agents

## TASK 33 — Final test suite
# python -m pytest tests/ -v --tb=short 2>&1 | tail -30
# Must: 990+ passed, 0 failed
- [x] Final test suite 990+ passed 0 failed

## TASK 34 [HAIKU] — Write SPRINT_DONE.md
# Sections: Date, All 34 tasks, Files created, Files modified,
#   All agents now wired (complete list with intents),
#   Sandbox vault count, Integration test results,
#   Could not complete (why), Next sprint: 500+ agent expansion
- [x] SPRINT_DONE.md written with complete audit

# ═══════════════════════════════════════════════
# GOAL COMPLETION — ALL must be true to stop:
# ═══════════════════════════════════════════════
# 1. Every [ ] is [x]
# 2. pytest → 990+ passed 0 failed
# 3. uvicorn starts clean
# 4. GET /health → 200
# 5. 10 agent domain queries return real data
# 6. Research queries → research format (not trading template)
# 7. HTML report opens branded with 9 sections
# 8. Deep mode fires 10-loop for any query
# 9. Sandbox vaults at least 1 training pair
# 10. SPRINT_DONE.md exists
#
# TOTAL AGENTS WIRED AFTER SPRINT:
#   Before: 17 agents wired
#   After:  ~82 agents wired (all data-producing agents)
#   Internal agents (E, V, DOC, P, C, CR): ~35 (work automatically)
#   Total coverage: 117/117 agents active in the system
#
# COST: ~$0.20-0.30 for the full sprint
# [HAIKU] tasks: ~$0.005
# [SONNET] tasks: ~$0.18
