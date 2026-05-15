# Agent Architecture

## Two Execution Paths

### Path 1: FourLoopEngine (POST /query — MARKET_DEEP_DIVE)
Deep equity and options analysis. 10 research loops.
- Loop 1: Live market data (yfinance)
- Loop 2: Web scraping (news, analyst notes)
- Loop 3–4: Wave prompts (technical, fundamental, options)
- Loop 5: Personalization (user portfolio, watchlist, positions)
- Loop 6–10: Synthesis, quality check, repair, formatting
- Output: full trade envelope (execution_rules, failure_modes, scenarios)

### Path 2: OmegaAgent (POST /omega — GENERAL_FINANCE and cross-domain)
Fast, cross-domain analysis. Single Gemini call with summary-first data.
- Loads data_cache/ summaries first (token-efficient)
- Enriches with company data when relevant
- Applies OUTPUT_CONTRACTS for correct response shape
- Output: same envelope shape as Path 1

## Intent Router
`classify_intent_route(raw_query: str) -> str`
- Receives ONLY the user's raw plain-text query
- NEVER receives memory, context, request controls, session data
- Routes: MARKET_DEEP_DIVE | GENERAL_FINANCE | COMPANY_RESEARCH | CASUAL | GENERAL_CHAT | HTML_ARTIFACT | DOCUMENT_GENERATION | MARKET_DATA | TRADING_ANALYSIS

## Agent Archetypes (117 agents → 8 archetypes)
Instead of 117 separate giant prompts, all agents use 6–8 prompt archetypes + metadata routing:
1. finance_analyst — equity/macro/options analysis
2. research_specialist — deep research, SEC filings, data aggregation
3. document_generator — reports, PDFs, Excel, PowerPoint
4. trade_planner — only when output_mode == trade_plan
5. company_analyst — company research, competitive analysis
6. chat_responder — casual, non-finance conversations
7. data_visualizer — HTML dashboards, charts, widgets
8. risk_assessor — portfolio review, risk scoring

## Memory Systems
- **atlas_memory.db** — SQLite long-term memory (persistent, grows with every query)
- **atlas_tracker.db** — Trade tracking + win-rate outcomes
- **atlas_rag/** — Chroma vector DB (355 chunks: SOUN/O/NVDA)
- **atlas_memory/memory_injector.py** — get_relevant_context + save_to_memory

## Key Files (Do Not Modify)
- `deep_research.py` — Deep research pipeline
- `gemini_limiter.py` — Gemini rate limiter + cost tracking
- `query_router.py` — Core routing (minimal edits only for Omega data_cache routing)
- `atlas_omega.py` — OmegaAgent (minimal edits only for data_cache ingest)

## Quality Control Pipeline
```
raw_query → classify_intent_route() → resolve_output_mode()
→ synthesis → quality_firewall → [repair loop if needed] → response_judge → frontend
```
