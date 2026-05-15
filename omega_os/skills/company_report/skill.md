# Skill: company_report

## name
company_report

## description
Generate a structured institutional-grade company intelligence report covering overview,
business model, financials, leadership, recent news, risks, and competitive position.

## when_to_use
- User asks "give me everything on [company]"
- User asks "research [company]" or "company report on [company]"
- intent == COMPANY_RESEARCH
- output_mode == company_report

## inputs_required
- Company name or ticker (required)
- Optional: specific focus area (e.g., "focus on their AI strategy")
- Optional: time horizon (current state vs 3-year outlook)

## steps
1. Detect company name via detect_company_name(raw_query) in query_router.py
2. Route to OmegaAgent (POST /omega) with intent=COMPANY_RESEARCH
3. Enrich with live data: yfinance fundamentals, recent news scrape
4. If SEC_USER_AGENT is configured: call omega_sec_edgar.get_filing_summary(company_name)
   - Inject latest_10k, latest_10q, latest_8k dates and links into synthesis prompt
   - Set sec_filings_used=True in response metadata
5. Build synthesis prompt with OUTPUT_CONTRACTS["company_report"] requirements
   - Include SEC filing context via prompt_builder.build_synthesis_prompt(sec_filing_context=...)
6. Run Gemini synthesis (Pro model for company reports)
7. Validate response against quality_firewall (company_report contract)
8. Run repair loop if quality check fails (one attempt)
9. Format output with required sections:
   - Overview (what the company does, size, stage)
   - Business Model (how they make money)
   - Financial Snapshot (revenue, AUM, market cap, margins)
   - Leadership (CEO, key executives)
   - Recent News (last 30 days, top 3 events)
   - Risks (regulatory, competitive, macro)
   - Competitive Position (market share, moat, key competitors)
10. Return structured response — NO trade plan sections

## outputs
- Structured company report (all 7 required sections)
- No entry price, stop loss, take profit, or execution rules
- Sources cited where available

## safety_rules
- NEVER include trade plan sections (entry, stop loss, take profit, execution rules)
- Do not make buy/sell recommendations — report facts, not investment advice
- Cite sources for all financial data
- Flag if data is from cache (not live) — label as "as of [date]"
- Do not include user portfolio data in the report

## related_files
- query_router.py — detect_company_name(), INTENT_COMPANY_RESEARCH
- atlas_omega.py — OmegaAgent synthesis
- output_contracts.py — OUTPUT_CONTRACTS["company_report"]
- quality_firewall.py — validate_response()
- prompt_builder.py — build_synthesis_prompt(sec_filing_context=...) and build_synthesis_prompt_meta()
- omega_sec_edgar.py — get_filing_summary(), search_company_cik(), get_recent_filings()
- omega_os/references/report_templates/README.md — company report template

## quality_checks
- [ ] All 7 required sections present (Overview, Business Model, Financial Snapshot, Leadership, Recent News, Risks, Competitive Position)
- [ ] No trade plan language in output (forbidden phrases check)
- [ ] quality_firewall returns PASS
- [ ] At least one live data source cited (yfinance or news)
- [ ] output_mode == "company_report" confirmed before synthesis
- [ ] If SEC_USER_AGENT configured: sec_filings_used=True in response metadata
- [ ] Latest 10-K and 10-Q dates referenced in Financial Snapshot if available
