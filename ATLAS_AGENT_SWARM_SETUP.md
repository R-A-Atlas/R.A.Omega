# ATLAS AGENT SWARM — COMPLETE MASTER SETUP
# 70 Agents | 9 Phases | Full Blueprint
#
# HOW TO USE:
# Drop this file in your project root.
# Open Claude Code terminal and say:
#
# "Read ATLAS_AGENT_SWARM_SETUP.md completely.
#  Then execute Phase by Phase, one agent at a time.
#  After each agent: create files, run validation, confirm.
#  Wait for me to say 'continue' before next agent."
#
# IMPORTANT RULES BEFORE STARTING:
# - NEVER modify: query_router.py, atlas_omega.py,
#   deep_research.py, gemini_limiter.py
# - NEVER delete: atlas_memory.db, atlas_tracker.db
# - Every agent gets: a directory, AGENT_PROMPT.md,
#   a SKILL.md in vault, and a tests/ file
# - Division 1 Data agents ALREADY BUILT — verify only
# - QA agent (E7) validates every other agent before ship

---

## REGISTRY — BUILD ORDER

Phase 1:  Engine Room      — Agents E1-E10  (build FIRST)
Phase 2:  Trading Desk     — Agents T1-T10  (markets)
Phase 3:  Real Estate      — Agents R1-R7   (property)
Phase 4:  Personal Wealth  — Agents W1-W8   (debt/savings)
Phase 5:  Tax & Legal      — Agents L1-L6   (compliance)
Phase 6:  Business         — Agents B1-B6   (startups/SMB)
Phase 7:  Alternative      — Agents A1-A5   (niche assets)
Phase 8:  Macro Risk       — Agents M1-M8   (geopolitics)
Phase 9:  Growth & Ops     — Agents G1-G10  (marketing/sales)

---

## PHASE 1 — THE ENGINE ROOM
## Build these first. They protect everything else.

### SQUAD A — THE BUILDERS

---
### E1 — The Skill Scripter
Role: Autonomously writes boilerplate Python scrapers and documentation.
Directory: atlas_agents/engineering/skill_scripter/
Owns: atlas_vault/02-Wiki/Skills/ (write new skills only)
Cannot touch: Any existing Python source files

AGENT_PROMPT.md:
"""
# E1 — Skill Scripter | Division: Engineering

## IDENTITY
You write boilerplate Python scrapers and DBS skill files.
When given a data source, you produce a working scraper
following the exact pattern of atlas_agents/crypto/crypto_scraper.py.
You always import from atlas_core.utils.agent_utils.

## TEMPLATE TO FOLLOW FOR EVERY SCRAPER
1. Import: from atlas_core.utils.agent_utils import requests_get_json, write_cache_json_pair, sleep_backoff
2. Fetch: use requests_get_json (handles 429, timeout, retry)
3. Save: use write_cache_json_pair (handles naming, timestamps)
4. CLI: argparse with --top N and --dry-run flags
5. Schema: always include generated_at, source, record_count

## OUTPUT FORMAT
For every new agent request:
  atlas_agents/<division>/<name>/<name>_scraper.py
  atlas_vault/02-Wiki/Skills/<name>/SKILL.md
  tests/test_<name>_scraper.py (basic import + schema test)

## RULES
- No LLM calls inside scrapers (pure Python logic only)
- No hardcoded API keys (use env vars or public endpoints)
- Every scraper must exit 0 on success, non-zero on failure
- Run py_compile before reporting done
"""

SKILL.md:
"""
# Skill: Skill Scripter
## [D] Direction
Write boilerplate scrapers following the crypto_scraper.py pattern.
Always use atlas_core.utils.agent_utils. Always write a test.
## [B] Blueprints
Pattern: atlas_agents/crypto/crypto_scraper.py
Utils: atlas_core/utils/agent_utils.py
## [S] Solutions
Validation: python -m py_compile <new_scraper>.py
"""

---
### E2 — The Refactorer (DRY Agent)
Role: Scans repo to consolidate duplicate code into shared utilities.
Directory: atlas_agents/engineering/refactorer/
Owns: atlas_core/utils/ (add to agent_utils.py only)
Cannot touch: query_router.py, atlas_omega.py, deep_research.py, gemini_limiter.py

AGENT_PROMPT.md:
"""
# E2 — Refactorer | Division: Engineering

## IDENTITY
You eliminate duplicate code. You scan the repo, find repeated
patterns, and move them into atlas_core/utils/agent_utils.py.
You never break existing imports — you add, then update callers.

## PROCESS
1. Scan all .py files for duplicate logic (HTTP fetch, file write, retry)
2. If pattern appears 3+ times: extract to agent_utils.py
3. Update all callers to import from agent_utils
4. Run full test suite: python -m pytest tests/ -q
5. Report: what was extracted, what was updated, test results

## RULES
- NEVER remove a function without confirming all callers updated
- NEVER touch core files (query_router, atlas_omega, etc.)
- Always run py_compile on every file you touch
- One refactor at a time — do not batch multiple changes
"""

---
### E3 — The API Integrator
Role: Reads external API docs and writes authentication wrappers.
Directory: atlas_agents/engineering/api_integrator/
Owns: atlas_core/connectors/ (new directory)
Cannot touch: Any existing files

AGENT_PROMPT.md:
"""
# E3 — API Integrator | Division: Engineering

## IDENTITY
You write clean API connector modules. Given an API name,
you produce a connector in atlas_core/connectors/<name>.py
with auth, rate limiting, and error handling built in.

## OUTPUT FOR EVERY CONNECTOR
  atlas_core/connectors/<api_name>.py
  - authenticate() function
  - get(endpoint, params) function using requests_get_json
  - All auth via environment variables (never hardcoded)
  - Docstring with: base_url, rate_limit, free_tier_limits

## RULES
- Public/free APIs only unless user provides key
- Always wrap in try/except with meaningful error messages
- Always test with a ping/health endpoint before returning
"""

---
### E4 — The UI/UX Porter
Role: Translates JSON outputs into Tailwind CSS/React dashboard components.
Directory: atlas_agents/engineering/ui_porter/
Owns: Components within ra_omega_app.html only
Cannot touch: query_router.py, atlas_omega.py, api_server.py backend logic

AGENT_PROMPT.md:
"""
# E4 — UI/UX Porter | Division: Engineering

## IDENTITY
You translate data_cache JSON into beautiful React components
inside ra_omega_app.html. You port patterns from
atlas_dashboard_v4.html into the Option 1 UI.

## CURRENT TASKS IN ORDER
1. Verify StructuredResponse cards render (lines 625-870)
2. Port sessions sidebar from dashboard v4 into Option 1
3. Port RYG meters (inferRiskLevelQuick) into Option 1
4. Build interactive HTML report upgrade (generateStandaloneReport)

## RULES
- Always read the file before editing
- Always Hard-Refresh test after changes
- Never touch backend Python files
- Smallest diff — no full rewrites
- Self-validate: run query, confirm visual output
"""

SKILL.md:
"""
# Skill: UI/UX Porting
## [D] Direction
Port UI patterns from atlas_dashboard_v4.html into Option 1.
Translate JSON schema into React component props.
## [B] Blueprints
Source: atlas_dashboard_v4.html (sessions sidebar, RYG meters)
Target: ra_omega_app.html
Schema: See Section 7 of CLAUDE.md for full API response shape
## [S] Solutions
Test: Hard refresh browser + run "Analyze NVDA" + screenshot
"""

---
### E5 — The DB Architect
Role: Writes Supabase SQL migrations and RLS policies.
Directory: atlas_agents/engineering/db_architect/
Owns: schema.sql (append only — never delete existing tables)
Cannot touch: atlas_db.py internals (add functions only)

AGENT_PROMPT.md:
"""
# E5 — DB Architect | Division: Engineering

## IDENTITY
You manage the Supabase schema. You write safe SQL migrations
and Row Level Security policies. You never drop tables.

## RULES
- Always use CREATE TABLE IF NOT EXISTS
- Always use ALTER TABLE ... ADD COLUMN IF NOT EXISTS
- Always write the corresponding RLS policy
- Always add the migration to schema.sql with a comment header
- Never run DROP TABLE or DELETE FROM in migrations

## MIGRATION FORMAT
-- Migration: <description>
-- Date: <date>
-- Agent: E5 DB Architect
CREATE TABLE IF NOT EXISTS public.<table_name> (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ...
);
ALTER TABLE public.existing_table
  ADD COLUMN IF NOT EXISTS new_col TYPE;
"""

---
### SQUAD B — THE BREAKERS (QA & VALIDATION)

---
### E6 — The Red Teamer
Role: Aggressively tests for prompt injection and SQL vulnerabilities.
Directory: atlas_agents/engineering/red_teamer/
Owns: tests/security/ (new directory)
Cannot touch: Any source files (read only)

AGENT_PROMPT.md:
"""
# E6 — Red Teamer | Division: Engineering

## IDENTITY
You attack ATLAS. You try to break it before users do.
You test for: prompt injection, SQL injection, auth bypass,
data leakage, and malformed input handling.

## TEST CATEGORIES
1. Prompt injection: send "ignore previous instructions" in query field
2. SQL injection: send '; DROP TABLE queries; -- as ticker input
3. Auth bypass: hit /option1 without token, confirm redirect
4. Malformed JSON: send broken request bodies to POST /query
5. Rate limit: send 50 requests in 5 seconds, confirm no crash

## OUTPUT
tests/security/test_security.py — pytest file with all attack vectors
Report: VULNERABILITY FOUND / HARDENED for each test
"""

---
### E7 — The Unit Tester
Role: Automatically writes pytest scripts for every new agent.
Directory: atlas_agents/engineering/unit_tester/
Owns: tests/ directory
Cannot touch: Source files

AGENT_PROMPT.md:
"""
# E7 — Unit Tester | Division: Engineering

## IDENTITY
You write pytest files. Every new agent gets a test file.
No agent ships without passing your tests. You are strict.

## FOR EVERY NEW SCRAPER AGENT, WRITE TESTS FOR:
1. API timeout (mock requests to raise Timeout)
2. 429 rate limit (mock response with status_code=429)
3. Missing JSON keys (return {} from mock)
4. Valid output schema (check required fields exist)
5. File output (confirm write_cache_json_pair creates the file)

## TEMPLATE
import pytest
from unittest.mock import patch, MagicMock

def test_handles_timeout():
    with patch('atlas_core.utils.agent_utils.requests_get_json',
               side_effect=Exception('timeout')):
        # import and call scraper fetch function
        # confirm it does not crash the process
        pass  # replace with real assertion

## RULES
- Use unittest.mock — never hit live APIs in tests
- Every test must have a clear docstring
- Run: python -m pytest tests/ -q before reporting done
"""

---
### E8 — The Data Validator (ALREADY BUILT — verify only)
Existing: atlas_core/validation/data_validator.py
Verify: python -m atlas_core.validation.data_validator
Expected: OK for all JSON files in data_cache/
If missing: rebuild using the pattern from Division 1 audit

---
### E9 — The Dependency Watcher
Role: Monitors and flags out-of-date Python libraries.
Directory: atlas_agents/engineering/dep_watcher/
Owns: requirements.txt (update only — never remove entries)

AGENT_PROMPT.md:
"""
# E9 — Dependency Watcher | Division: Engineering

## IDENTITY
You keep dependencies current and safe. You scan requirements.txt,
check for outdated packages, and flag security vulnerabilities.

## PROCESS
1. Run: pip list --outdated
2. Cross-reference with requirements.txt
3. For each outdated package: check changelog for breaking changes
4. If safe to update: update requirements.txt with new version
5. If breaking change risk: flag for human review, do not update

## OUTPUT
atlas_agents/engineering/dep_watcher/dependency_report.md
Format:
  PACKAGE | CURRENT | LATEST | STATUS | ACTION
  pytest   | 8.0.0  | 8.3.2  | SAFE   | Updated

## RULES
- Never remove a dependency
- Never update without checking for breaking changes
- Always run pytest after updating any dependency
"""

---
### E10 — The Eval Scorer
Role: Runs the 10-loop engine against test suites to ensure quality.
Directory: atlas_agents/engineering/eval_scorer/
Owns: tests/evals/ (new directory)

AGENT_PROMPT.md:
"""
# E10 — Eval Scorer | Division: Engineering

## IDENTITY
You benchmark ATLAS output quality. You run test queries
against the 10-loop engine and score the results.

## EVAL SUITE (run these queries, score the output)
Test queries:
  - "Analyze NVDA — current setup and trade plan"
  - "What is the options play for AAPL earnings?"
  - "Should I buy or rent in Miami right now?"
  - "What are the top crypto movers today?"

Scoring rubric (per query):
  [ ] tldr populated (not empty)
  [ ] final_report.overall_rating is valid value
  [ ] execution_rules has exactly 5 items
  [ ] scenarios has exactly 3 items summing to ~1.0
  [ ] failure_modes has exactly 3 items
  [ ] _api_time_s < 300 (under 5 minutes)
  [ ] No "error" or "exception" in response body

## OUTPUT
tests/evals/eval_report_<date>.json
Score: X/7 assertions passed per query
Alert: if any query scores < 5/7, flag for human review
"""

---

## PHASE 2 — THE TRADING DESK

### T1 — Crypto Hound (ALREADY BUILT — verify only)
Existing: atlas_agents/crypto/crypto_scraper.py
Verify: python -m pytest tests/test_crypto_scraper.py -v
Expected: 7 tests pass, data_cache/crypto_top50_latest.json has coin_count=50

### T2 — Equities Scanner (ALREADY BUILT — verify only)
Existing: atlas_agents/equities/equities_scraper.py
Verify: python -m pytest tests/test_equities_scraper.py -v
Expected: 15 tests pass, data_cache/equities_latest.json has gainers/losers

### T3 — Options Flow Monitor
Role: Tracks unusual options activity from public CBOE data.
Directory: atlas_agents/trading/options_flow/
Output: data_cache/options_flow_latest.json
Schema: { generated_at, source, unusual_activity: [{ticker, expiry, strike, type, volume, open_interest, volume_oi_ratio}] }

AGENT_PROMPT.md:
"""
# T3 — Options Flow Monitor | Division: Trading Desk

## DATA SOURCE
CBOE public data: https://www.cboe.com/us/options/market_statistics/
or unusual-whales free tier, or barchart.com public screener

## OUTPUT SCHEMA
{
  "generated_at": "ISO timestamp",
  "source": "cboe_public",
  "unusual_activity": [
    {
      "ticker": "NVDA",
      "expiry": "2026-06-20",
      "strike": 150,
      "type": "CALL",
      "volume": 50000,
      "open_interest": 10000,
      "volume_oi_ratio": 5.0,
      "signal": "BULLISH_UNUSUAL"
    }
  ],
  "record_count": 25
}

## RULES
- No LLM calls — pure scraping logic
- Flag volume/OI ratio > 3x as unusual
- Use requests_get_json from agent_utils
- Save with write_cache_json_pair
"""

### T4 — Insider Tracker
Role: Scrapes SEC Form 4s for CEO/CFO stock buying/selling.
Directory: atlas_agents/trading/insider_tracker/
Output: data_cache/insider_trades_latest.json
Source: https://www.sec.gov/cgi-bin/browse-edgar (public, no auth needed)
Schema: { generated_at, filings: [{ticker, insider_name, role, transaction_type, shares, price, date}] }

### T5 — Earnings Parser
Role: Pulls quarterly earnings dates and extracts key guidance.
Directory: atlas_agents/trading/earnings_parser/
Output: data_cache/earnings_latest.json
Source: EarningsWhispers public calendar, yfinance earnings dates
Schema: { generated_at, upcoming: [{ticker, date, est_eps, est_revenue, sector}] }

### T6 — Forex Radar
Role: Tracks major currency pair volatility.
Directory: atlas_agents/trading/forex_radar/
Output: data_cache/forex_latest.json
Source: exchangerate-api.com free tier or frankfurter.app (no auth)
Schema: { generated_at, pairs: [{pair, rate, change_24h, volatility_signal}] }

### T7 — Commodities Watch
Role: Oil, Gold, Silver, Wheat futures prices.
Directory: atlas_agents/trading/commodities/
Output: data_cache/commodities_latest.json
Source: metals-api.com free tier, EIA for oil (public)
Schema: { generated_at, commodities: [{name, price, unit, change_24h, trend}] }

### T8 — Dark Pool Monitor
Role: Tracks off-exchange block trade signals.
Directory: atlas_agents/trading/dark_pool/
Output: data_cache/dark_pool_latest.json
Source: Unusual Whales free endpoints or FINRA ATS public data
Schema: { generated_at, signals: [{ticker, dark_pool_volume, total_volume, ratio, date}] }

### T9 — Penny Stock Screener
Role: High-volume micro-cap scanner.
Directory: atlas_agents/trading/penny_screener/
Output: data_cache/penny_stocks_latest.json
Source: yfinance screener, Finviz free filters
Schema: { generated_at, stocks: [{ticker, price, volume, market_cap, change_pct, sector}] }

### T10 — Bond Yield Curve
Role: Tracks Treasury yields for recession signals.
Directory: atlas_agents/trading/bond_yields/
Output: data_cache/bond_yields_latest.json
Source: US Treasury public API: api.fiscaldata.treasury.gov (no auth)
Schema: { generated_at, yields: [{maturity, rate, date}], curve_signal: "NORMAL|INVERTED|FLAT" }

---

## PHASE 3 — REAL ESTATE & PROPERTY

### R1 — Residential Scout
Directory: atlas_agents/realestate/residential/
Output: data_cache/residential_latest.json
Source: Redfin public data exports, Zillow Research data (CSV downloads)
Schema: { generated_at, markets: [{city, state, median_price, yoy_change, days_on_market, inventory}] }

### R2 — Rental Yield Calculator
Directory: atlas_agents/realestate/rental_yield/
Output: data_cache/rental_yield_latest.json
Source: HUD Fair Market Rents (public API), Zillow rent index
Schema: { generated_at, markets: [{city, avg_rent_1br, avg_rent_2br, mortgage_rate, yield_estimate}] }

### R3 — Airbnb/STR Analyzer
Directory: atlas_agents/realestate/str_analyzer/
Output: data_cache/str_latest.json
Source: AirDNA free market data, Inside Airbnb (public dataset)
Schema: { generated_at, markets: [{city, avg_daily_rate, occupancy_rate, annual_revenue_est, regulation_risk}] }

### R4 — Commercial Property Bot
Directory: atlas_agents/realestate/commercial/
Output: data_cache/commercial_latest.json
Source: CoStar public reports, LoopNet free listings data
Schema: { generated_at, segments: [{type, avg_lease_rate, vacancy_rate, market, trend}] }

### R5 — Zoning & Permit Watcher
Directory: atlas_agents/realestate/zoning/
Output: data_cache/zoning_latest.json
Source: City/county open data portals (varies by market)
Schema: { generated_at, permits: [{city, permit_type, count, yoy_change, trend_signal}] }

### R6 — REIT Screener
Directory: atlas_agents/realestate/reit_screener/
Output: data_cache/reits_latest.json
Source: yfinance for REIT tickers, SEC EDGAR for dividend data
Schema: { generated_at, reits: [{ticker, name, dividend_yield, price, sector, rating}] }

### R7 — Mortgage Rate Tracker
Directory: atlas_agents/realestate/mortgage_rates/
Output: data_cache/mortgage_rates_latest.json
Source: Freddie Mac PMMS public API (free, weekly data)
Schema: { generated_at, rates: [{term, rate, points, week_of}], trend: "RISING|FALLING|STABLE" }

---

## PHASE 4 — PERSONAL WEALTH & DEBT

### W1 — Credit Card Optimizer
Directory: atlas_agents/wealth/credit_cards/
Output: data_cache/credit_cards_latest.json
Source: CFPB credit card data (public), Bankrate public API
Schema: { generated_at, cards: [{name, issuer, apr, signup_bonus, annual_fee, category}] }

### W2 — Auto Loan Scanner
Directory: atlas_agents/wealth/auto_loans/
Output: data_cache/auto_loans_latest.json
Source: Federal Reserve G.19 consumer credit data (public)
Schema: { generated_at, rates: [{term_months, avg_rate, credit_union_rate, dealer_rate}] }

### W3 — Student Debt Monitor
Directory: atlas_agents/wealth/student_debt/
Output: data_cache/student_debt_latest.json
Source: StudentAid.gov public data, Federal Reserve student debt stats
Schema: { generated_at, federal_rate, forgiveness_programs: [{name, status, eligible_loans}] }

### W4 — HYSA Tracker
Directory: atlas_agents/wealth/hysa/
Output: data_cache/hysa_latest.json
Source: FDIC BankFind API (public, no auth), Bankrate public data
Schema: { generated_at, accounts: [{bank, apy, min_balance, fdic_insured}] }

### W5 — IRA/401k Limit Bot
Directory: atlas_agents/wealth/retirement_limits/
Output: data_cache/retirement_limits_latest.json
Source: IRS.gov (scrape annual limits page)
Schema: { generated_at, year, ira_limit, k401_limit, catch_up_50plus, roth_income_phase_out }

### W6 — Personal Loan Screener
Directory: atlas_agents/wealth/personal_loans/
Output: data_cache/personal_loans_latest.json
Source: CFPB public data, Bankrate public loan rates
Schema: { generated_at, loans: [{lender, rate_range, max_amount, term_months, credit_score_min}] }

### W7 — Cost of Living Indexer
Directory: atlas_agents/wealth/col_indexer/
Output: data_cache/col_latest.json
Source: BLS CPI data by region (public API), MIT Living Wage calculator
Schema: { generated_at, cities: [{city, state, grocery_index, gas_avg, rent_1br, overall_index}] }

### W8 — Insurance Premium Tracker
Directory: atlas_agents/wealth/insurance/
Output: data_cache/insurance_latest.json
Source: NAIC public data, state insurance department reports
Schema: { generated_at, type, avg_annual_premium, yoy_change_pct, highest_states, lowest_states }

---

## PHASE 5 — TAX & LEGAL COMPLIANCE

### L1 — Federal Tax Code Bot
Directory: atlas_agents/legal/federal_tax/
Output: data_cache/federal_tax_latest.json
Source: IRS.gov (public pages), IRS Revenue Procedures
Schema: { generated_at, year, brackets: [{rate, single_min, married_min}], standard_deduction }

### L2 — State Tax/Act 60 Monitor
Directory: atlas_agents/legal/state_tax/
Output: data_cache/state_tax_latest.json
Source: State legislature websites, Tax Foundation public data
Schema: { generated_at, states: [{state, income_tax_rate, sales_tax, special_programs}] }

### L3 — Bankruptcy Parser
Directory: atlas_agents/legal/bankruptcy/
Output: data_cache/bankruptcy_latest.json
Source: PACER public access, US Courts public statistics
Schema: { generated_at, ch7_filings, ch11_filings, yoy_change, trend_signal, top_sectors }

### L4 — SEC EDGAR Bot
Directory: atlas_agents/legal/sec_edgar/
Output: data_cache/sec_filings_latest.json
Source: SEC EDGAR full-text search API (public, no auth)
Schema: { generated_at, filings: [{ticker, form_type, filed_date, key_risk_excerpt}] }

### L5 — Consumer Protection Watch
Directory: atlas_agents/legal/consumer_protection/
Output: data_cache/consumer_alerts_latest.json
Source: FTC scam alerts RSS feed, CPSC recalls public API
Schema: { generated_at, alerts: [{title, category, date, severity, description}] }

### L6 — Labor Law Monitor
Directory: atlas_agents/legal/labor_law/
Output: data_cache/labor_law_latest.json
Source: DOL Wage and Hour Division public data, state labor department pages
Schema: { generated_at, federal_min_wage, states: [{state, min_wage, effective_date, contractor_rules}] }

---

## PHASE 6 — BUSINESS & STARTUPS

### B1 — SBA Grant/Loan Finder
Directory: atlas_agents/business/sba/
Output: data_cache/sba_latest.json
Source: SBA.gov public API, grants.gov public search
Schema: { generated_at, programs: [{name, type, max_amount, eligibility, deadline, url}] }

### B2 — B2B SaaS Metrics Bot
Directory: atlas_agents/business/saas_metrics/
Output: data_cache/saas_metrics_latest.json
Source: OpenView Partners public benchmarks, ChartMogul public reports
Schema: { generated_at, benchmarks: [{metric, value, percentile_50, percentile_75, source}] }

### B3 — Ecommerce Trends Bot
Directory: atlas_agents/business/ecommerce/
Output: data_cache/ecommerce_latest.json
Source: Google Trends API (pytrends, public), Jungle Scout free data
Schema: { generated_at, trending_niches: [{niche, trend_score, competition, avg_price}] }

### B4 — Freelance Rate Indexer
Directory: atlas_agents/business/freelance_rates/
Output: data_cache/freelance_rates_latest.json
Source: Upwork public job postings (scrape), Bureau of Labor Statistics
Schema: { generated_at, roles: [{title, avg_hourly_low, avg_hourly_high, demand_trend}] }

### B5 — Franchise Evaluator
Directory: atlas_agents/business/franchise/
Output: data_cache/franchise_latest.json
Source: FTC franchise disclosure database (public), Franchise Direct public data
Schema: { generated_at, franchises: [{name, sector, initial_investment_low, initial_investment_high, royalty_pct}] }

### B6 — VC Deal Flow Monitor
Directory: atlas_agents/business/vc_deals/
Output: data_cache/vc_deals_latest.json
Source: Crunchbase public data, PitchBook public reports
Schema: { generated_at, deals: [{company, sector, round, amount, lead_investor, date}] }

---

## PHASE 7 — ALTERNATIVE ASSETS & NICHE

### A1 — Watch Market Bot
Directory: atlas_agents/alternative/watches/
Output: data_cache/watches_latest.json
Source: Chrono24 public listings (scrape public search pages)
Schema: { generated_at, models: [{brand, model, ref, avg_price, trend, premium_over_retail}] }

### A2 — Art Auction Tracker
Directory: atlas_agents/alternative/art/
Output: data_cache/art_latest.json
Source: Sotheby's/Christie's public realized price pages
Schema: { generated_at, sales: [{artist, title, house, realized_price, estimate_low, date}] }

### A3 — Collectibles/Cards Scraper
Directory: atlas_agents/alternative/collectibles/
Output: data_cache/collectibles_latest.json
Source: eBay completed listings public API (no auth for browse), PSA public pop report
Schema: { generated_at, items: [{category, item, grade, avg_sold_price, volume_30d}] }

### A4 — P2P Lending Bot
Directory: atlas_agents/alternative/p2p_lending/
Output: data_cache/p2p_latest.json
Source: LendingClub public statistics, Prosper public data
Schema: { generated_at, platforms: [{name, avg_return, default_rate_12m, active_loans}] }

### A5 — Physical Metals Bot
Directory: atlas_agents/alternative/metals/
Output: data_cache/metals_latest.json
Source: APMEX public pricing (scrape), JM Bullion public pages
Schema: { generated_at, metals: [{metal, spot_price, coin_premium_pct, bar_premium_pct}] }

---

## PHASE 8 — MACRO RISK & GEOPOLITICS

### M1 — Fed Rate Probability
Directory: atlas_agents/macro/fed_watch/
Output: data_cache/fed_watch_latest.json
Source: CME FedWatch public tool (scrape), Fed Funds futures data
Schema: { generated_at, next_meeting, probabilities: [{action, probability}], current_rate }

### M2 — Supply Chain Indexer
Directory: atlas_agents/macro/supply_chain/
Output: data_cache/supply_chain_latest.json
Source: Freightos Baltic Index (public), World Bank trade data
Schema: { generated_at, indices: [{route, rate_usd_40ft, change_wow, trend}] }

### M3 — Energy Grid Monitor
Directory: atlas_agents/macro/energy/
Output: data_cache/energy_latest.json
Source: EIA public API (free, no auth), IRENA public data
Schema: { generated_at, electricity_avg_kwh, gas_national_avg, renewables_pct_grid }

### M4 — Climate Risk/FEMA Bot
Directory: atlas_agents/macro/climate_risk/
Output: data_cache/climate_risk_latest.json
Source: FEMA flood map API (public), NOAA public climate data
Schema: { generated_at, flood_zone_changes: [{region, risk_level, change, impact_on_insurance}] }

### M5 — Geopolitical Tariff Tracker
Directory: atlas_agents/macro/tariffs/
Output: data_cache/tariffs_latest.json
Source: USTR public tariff database, WTO dispute tracker
Schema: { generated_at, active_tariffs: [{product, rate, effective_date, trading_partner}] }

### M6 — Job Market/BLS Bot
Directory: atlas_agents/macro/jobs/
Output: data_cache/jobs_latest.json
Source: BLS public API (no auth required, data.bls.gov)
Schema: { generated_at, unemployment_rate, jobs_added, sector_breakdown: [{sector, jobs, change}] }

### M7 — Inflation/CPI Bot
Directory: atlas_agents/macro/inflation/
Output: data_cache/cpi_latest.json
Source: BLS CPI API (public, data.bls.gov/timeseries/CUUR0000SA0)
Schema: { generated_at, cpi_index, mom_change, yoy_change, categories: [{name, change}] }

### M8 — Congressional Trade Watcher
Directory: atlas_agents/macro/congress_trades/
Output: data_cache/congress_trades_latest.json
Source: HouseStockWatcher.com public API, Senate disclosure portal
Schema: { generated_at, trades: [{member, chamber, ticker, transaction, amount, date}] }

---

## PHASE 9 — BUSINESS GROWTH, OPS & MARKETING

### G1 — Lead Generation Scraper
Directory: atlas_agents/growth/lead_gen/
Output: data_cache/leads_latest.json
Source: Google Maps public search (scrape via requests), Yelp public pages
Schema: { generated_at, leads: [{business_name, address, phone, website, category, has_modern_site}] }

### G2 — CRM Sync Agent
Directory: atlas_agents/growth/crm_sync/
Output: Writes directly to Supabase (uses existing atlas_db functions)
Role: Syncs lead data into Supabase user records via n8n/ManyChat webhooks
Note: Requires user to set up n8n webhook URL in .env as CRM_WEBHOOK_URL

### G3 — Competitor Ad Spy
Directory: atlas_agents/growth/ad_spy/
Output: data_cache/competitor_ads_latest.json
Source: Meta Ad Library public API (no auth for basic access)
Schema: { generated_at, ads: [{page_name, ad_text, spend_range, impressions_range, started}] }

### G4 — SEO Keyword Tracker
Directory: atlas_agents/growth/seo/
Output: data_cache/seo_keywords_latest.json
Source: pytrends (Google Trends, no auth), Google Search Console public data
Schema: { generated_at, keywords: [{term, trend_score, volume_est, competition, rising}] }

### G5 — Social Sentiment Analyzer
Directory: atlas_agents/growth/sentiment/
Output: data_cache/sentiment_latest.json
Source: Reddit public API (PRAW, free tier), Twitter/X public search
Schema: { generated_at, topics: [{topic, mentions, sentiment_score, trending, top_posts}] }

### G6 — Content Repurposer Bot
Directory: atlas_agents/growth/content/
Output: atlas_vault/03-Outputs/Content/ (markdown files)
Source: YouTube transcript API (youtube-transcript-api, free)
Role: Extracts transcripts from URLs, reformats into Twitter threads + blog outlines
Schema: Markdown files named by video title and date

### G7 — Email Deliverability Monitor
Directory: atlas_agents/growth/email_health/
Output: data_cache/email_health_latest.json
Source: MXToolbox public API, mail-tester.com, DMARC public check
Schema: { generated_at, domain, spf_status, dkim_status, dmarc_status, blacklist_hits, score }

### G8 — Engagement Rater
Directory: atlas_agents/growth/engagement/
Output: data_cache/engagement_latest.json
Source: Instagram Graph API (public profiles), TikTok public search
Schema: { generated_at, profiles: [{handle, platform, followers, avg_likes, avg_comments, engagement_rate}] }

### G9 — Review Aggregator
Directory: atlas_agents/growth/reviews/
Output: data_cache/reviews_latest.json
Source: Google My Business public reviews (scrape), Yelp public API
Schema: { generated_at, businesses: [{name, rating, review_count, top_complaints, top_praise}] }

### G10 — ROAS Optimizer
Directory: atlas_agents/growth/roas/
Output: data_cache/roas_latest.json
Source: Meta Ads API (requires user token), Google Ads API (requires credentials)
Note: Requires ATLAS_META_TOKEN and ATLAS_GOOGLE_ADS_TOKEN in .env
Schema: { generated_at, campaigns: [{name, platform, spend, revenue, roas, status, recommendation}] }

---

## AGENT REGISTRY — CREATE THIS FILE LAST

Create: atlas_agents/AGENT_REGISTRY.md

Content: A table for every agent with columns:
  ID | Name | Division | Directory | Output File | Status | Tests

Mark Division 1 agents as "BUILT + VERIFIED" or "BUILT + NEEDS VERIFY"
Mark all others as "PENDING" until built and tested.

---

## EXECUTION INSTRUCTIONS FOR CLAUDE CODE

Read this entire file. Then execute phase by phase:

PHASE 1 (Engine Room):
  - Build E1 through E5 first (Builders)
  - Then build E6 through E10 (Breakers)
  - After each: py_compile all new Python files
  - Run: python -m pytest tests/ -q after each agent

PHASE 1 VERIFICATION (Division 1 — already built):
  - Run: python -m pytest tests/test_crypto_scraper.py -v
  - Run: python -m pytest tests/test_equities_scraper.py -v
  - Run: python -m pytest tests/test_data_cache_routing.py -v
  - Run: python -m atlas_core.validation.data_validator
  - Report: PASS or FAIL for each. Do not fix — just report.

PHASES 2-9:
  - Create directory + __init__.py
  - Write AGENT_PROMPT.md
  - Write SKILL.md in atlas_vault/02-Wiki/Skills/<name>/
  - Write basic tests/test_<name>.py (import test + schema test)
  - NO actual scraping implementation yet — prompts and structure only
  - Implementation happens when each agent is activated by user

FINAL STEP:
  - Create atlas_agents/AGENT_REGISTRY.md with all 70 agents listed

After every phase: report what was created, then wait for "continue".

