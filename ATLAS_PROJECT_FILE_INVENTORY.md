# ATLAS Project — Complete File Inventory (for LLM context)

**Generated:** 2026-05-08 05:40 UTC  
**Purpose:** Single document listing **every tracked file** in the repo (excluding `.git`, `__pycache__`, `.cursor`, `venv`) with a short purpose. Use when the full codebase is too large to paste.

**Security:** Listing mentions `.env` — **never paste secrets** into an LLM; redact or omit that file when sharing.

**How to regenerate:** `python generate_project_inventory.py`

---

## Summary counts

- **Total files:** 87

---

## File listing (path → size → description)

### `.env`
- **Size:** 1,583 bytes
- **Role:** Secrets — GOOGLE_API_KEY, broker keys (never commit).

### `.gitignore`
- **Size:** 39 bytes
- **Role:** Git ignore rules.

### `alerts.py`
- **Size:** 21,202 bytes
- **Role:** Price/user alerts; notifications (winsound guarded).

### `api_server.py`
- **Size:** 16,830 bytes
- **Role:** FastAPI app: POST /omega, /query, /research, positions, watchlist, GET /health, /v2 dashboard (v4-first).

### `atlas_alerts.json`
- **Size:** 2,032 bytes
- **Role:** Alert definitions persisted.

### `atlas_alerts.log`
- **Size:** 0 bytes
- **Role:** Alert log (may be empty).

### `atlas_dashboard_v2.html`
- **Size:** 55,839 bytes
- **Role:** Financial Intelligence UI (older; light theme).

### `atlas_dashboard_v3.html`
- **Size:** 36,376 bytes
- **Role:** Alternative dark / bento-style UI experiment.

### `atlas_dashboard_v4.html`
- **Size:** 57,036 bytes
- **Role:** Primary SPA dashboard — dark/light toggle; calls /omega then /query.

### `ATLAS_FULL_AGENT_AUDIT.docx`
- **Size:** 44,681 bytes
- **Role:** Word export of the audit.

### `ATLAS_FULL_AGENT_AUDIT.md`
- **Size:** 14,486 bytes
- **Role:** Technical + product audit of the agent (Markdown).

### `ATLAS_Master_Roadmap_to_1B (1).docx`
- **Size:** 30,876 bytes
- **Role:** Business roadmap document.

### `atlas_memory.db`
- **Size:** 49,152 bytes
- **Role:** SQLite — long-lived memories.

### `atlas_memory_data/watcher_captures/watcher_20260507T003158_b215226954.jpg`
- **Size:** 310 bytes
- **Role:** Screen / watcher capture image.

### `atlas_omega.py`
- **Size:** 32,523 bytes
- **Role:** OmegaAgent — cross-domain financial agent: classifier, parallel data workers, stock_universe discovery, Gemini JSON synthesis.

### `ATLAS_OUTPUT_MAP.html`
- **Size:** 6,880 bytes
- **Role:** Static map / overview of outputs.

### `ATLAS_OVERVIEW.html`
- **Size:** 53,261 bytes
- **Role:** Static overview HTML.

### `atlas_pending_deep.json`
- **Size:** 98 bytes
- **Role:** Queue or pending deep research jobs.

### `ATLAS_PROJECT_FILE_INVENTORY.docx`
- **Size:** 40,424 bytes
- **Role:** Microsoft Word document.

### `ATLAS_PROJECT_FILE_INVENTORY.md`
- **Size:** 10,729 bytes
- **Role:** Markdown documentation.

### `atlas_rag/7c964c7f-8404-42f1-b691-1714a329301c/data_level0.bin`
- **Size:** 167,600 bytes
- **Role:** Chroma HNSW / vector storage binary.

### `atlas_rag/7c964c7f-8404-42f1-b691-1714a329301c/header.bin`
- **Size:** 100 bytes
- **Role:** Chroma index header.

### `atlas_rag/7c964c7f-8404-42f1-b691-1714a329301c/length.bin`
- **Size:** 400 bytes
- **Role:** Chroma index lengths.

### `atlas_rag/7c964c7f-8404-42f1-b691-1714a329301c/link_lists.bin`
- **Size:** 0 bytes
- **Role:** Chroma graph link storage.

### `atlas_rag/backtest_cache.json`
- **Size:** 3,259 bytes
- **Role:** RAG folder cache for backtests.

### `atlas_rag/chroma.sqlite3`
- **Size:** 5,693,440 bytes
- **Role:** Chroma vector DB (RAG embeddings metadata + segments).

### `atlas_rag/ingested.json`
- **Size:** 226 bytes
- **Role:** RAG ingestion manifest (which docs embedded).

### `atlas_tracker.db`
- **Size:** 40,960 bytes
- **Role:** SQLite — recommendations / P&L history.

### `atlas_tracking_state.json`
- **Size:** 132 bytes
- **Role:** Auto-tracker / bot tracking state.

### `ATLAS_v3_Full_Audit.docx`
- **Size:** 27,947 bytes
- **Role:** Earlier audit / notes (Word).

### `auto_bot.py`
- **Size:** 125,176 bytes
- **Role:** Scheduled / intraday bot, scans, LIVE_DASHBOARD generation.

### `auto_tuner.py`
- **Size:** 23,985 bytes
- **Role:** Config/weight tuning surface for agents.

### `backtest_sandbox.py`
- **Size:** 36,251 bytes
- **Role:** Backtesting experiments.

### `broker_alpaca.py`
- **Size:** 21,919 bytes
- **Role:** Alpaca API integration (paper/real).

### `broker_tradier.py`
- **Size:** 19,074 bytes
- **Role:** Tradier API integration.

### `build_audit_docx.py`
- **Size:** 5,090 bytes
- **Role:** Converts ATLAS_FULL_AGENT_AUDIT.md → .docx.

### `CANVAS_1_Roadmap.html`
- **Size:** 5,607 bytes
- **Role:** Roadmap canvas / presentation HTML.

### `CANVAS_3_ATLAS_vs_World.html`
- **Size:** 13,699 bytes
- **Role:** Comparison canvas HTML.

### `CANVAS_4_Intelligence_Layers.html`
- **Size:** 15,523 bytes
- **Role:** Architecture layers canvas HTML.

### `CLAUDE.md`
- **Size:** 48,409 bytes
- **Role:** Long internal spec / task list for ATLAS development.

### `congress_cache/all_trades.json`
- **Size:** 23,927 bytes
- **Role:** Cached congressional trades JSON.

### `congress_tracker.py`
- **Size:** 20,442 bytes
- **Role:** Congressional trade disclosures; cache under congress_cache/.

### `dashboard.html`
- **Size:** 134,297 bytes
- **Role:** Legacy live portfolio / regime HTML dashboard.

### `dashboard_server.py`
- **Size:** 83,120 bytes
- **Role:** HTTP 8765: dashboard.html, /state, refresh, reports, /v2 financial UI.

### `dashboard_state.json`
- **Size:** 5,814 bytes
- **Role:** Cached JSON for dashboard_server UI.

### `deep_reports/DISCOVERY_Best_US-listed_stocks_and_tactical_optio.html`
- **Size:** 1,794 bytes
- **Role:** Saved deep-research HTML output.

### `deep_reports/O_deep.html`
- **Size:** 41,407 bytes
- **Role:** Saved deep-research HTML output.

### `deep_reports/O_research_log.json`
- **Size:** 1,758 bytes
- **Role:** JSON log for a deep research run.

### `deep_reports/SOUN_deep.html`
- **Size:** 42,688 bytes
- **Role:** Saved deep-research HTML output.

### `deep_reports/SOUN_research_log.json`
- **Size:** 765 bytes
- **Role:** JSON log for a deep research run.

### `deep_reports/WEEKLY_INSIGHT.html`
- **Size:** 1,794 bytes
- **Role:** Saved deep-research HTML output.

### `deep_research.py`
- **Size:** 116,432 bytes
- **Role:** Heavy ticker / discovery pipeline: scrape + structured Gemini reports; CLI and /research fallback.

### `delta_reporter.py`
- **Size:** 32,453 bytes
- **Role:** Delta-style HTML reports under reports/.

### `delta_snapshots/SOUN_snapshot.json`
- **Size:** 2,516 bytes
- **Role:** JSON snapshot of delta / ticker state.

### `gemini_limiter.py`
- **Size:** 3,970 bytes
- **Role:** Global rate limit / spacing for all Gemini calls.

### `generate_project_inventory.py`
- **Size:** 11,900 bytes
- **Role:** This script — regenerates project file inventory.

### `LIVE_DASHBOARD.html`
- **Size:** 19,139 bytes
- **Role:** Generated live tactical dashboard (auto_bot).

### `LIVE_REPORTS.html`
- **Size:** 2,348 bytes
- **Role:** Index of live reports.

### `market_scanner.py`
- **Size:** 35,879 bytes
- **Role:** Market regime, squeeze-style metrics, full_awareness for tickers.

### `memory.py`
- **Size:** 37,533 bytes
- **Role:** Persistent ticker memory (SQLite); used in research context.

### `min.png`
- **Size:** 62 bytes
- **Role:** PNG image asset.

### `multi_ranker.py`
- **Size:** 17,891 bytes
- **Role:** Scores/ranks candidates (used by stock_universe pass 4).

### `news_scanner.py`
- **Size:** 64,187 bytes
- **Role:** News scanning loop / CLI.

### `options_simulator.py`
- **Size:** 26,276 bytes
- **Role:** Options P/L and structure math.

### `paper_trader.py`
- **Size:** 35,174 bytes
- **Role:** Paper trading monitor and logging.

### `paper_trades.json`
- **Size:** 2 bytes
- **Role:** Paper trade log for personalization.

### `playwright_scraper.py`
- **Size:** 41,312 bytes
- **Role:** JS-heavy sites via Playwright.

### `position_sizer.py`
- **Size:** 21,059 bytes
- **Role:** Position sizing utilities.

### `positions_cache.json`
- **Size:** 333 bytes
- **Role:** Manual stock/option positions for API and loop 5.

### `Prompt.md`
- **Size:** 854 bytes
- **Role:** Short prompt notes (e.g. /omega vs /query testing).

### `query_router.py`
- **Size:** 56,757 bytes
- **Role:** QueryRouter + FourLoopEngine — 10-loop equity/options pipeline (scrape → synthesize → personalize → rules → scenarios → memory → adversarial → narrative).

### `rag_engine.py`
- **Size:** 23,771 bytes
- **Role:** SEC/document RAG helpers; Chroma-backed when enabled.

### `reports/ATLAS_DELTA_SOUN.html`
- **Size:** 3,866 bytes
- **Role:** Generated equity research / delta HTML report.

### `requirements.txt`
- **Size:** 1,400 bytes
- **Role:** Python dependencies (FastAPI, yfinance, genai, playwright, etc.).

### `research_history.json`
- **Size:** 480 bytes
- **Role:** History of research runs.

### `screen_watcher.py`
- **Size:** 22,214 bytes
- **Role:** Screen capture watcher pipeline.

### `sector_tracker.py`
- **Size:** 24,540 bytes
- **Role:** Sector rotation / wind context.

### `self_coder.py`
- **Size:** 28,625 bytes
- **Role:** Self-modification / codegen experiments.

### `START_ATLAS.py`
- **Size:** 625 bytes
- **Role:** Launches auto_bot --watch + dashboard_server; opens browser.

### `stock_universe.py`
- **Size:** 33,127 bytes
- **Role:** Progressive Finviz + yfinance funnel (universe → filter → signals → optional deep rank); omega_discovery_to_scan_params.

### `test_omega.py`
- **Size:** 3,703 bytes
- **Role:** Integration test: /query or /omega + health; saves test_result_soun.json.

### `test_result_soun.json`
- **Size:** 10,253 bytes
- **Role:** Saved API test response (e.g. Omega or /query).

### `tracker.py`
- **Size:** 27,800 bytes
- **Role:** Recommendation history & outcomes; personalization loops 5 & 8.

### `volume_profile.py`
- **Size:** 19,267 bytes
- **Role:** Volume profile POC/VAH/VAL for synthesis context.

### `watchlist.json`
- **Size:** 34 bytes
- **Role:** Watchlist tickers for API.

### `web_scraper.py`
- **Size:** 81,481 bytes
- **Role:** Omnivore scraper: Finviz, news, SEC, many sources; builds context blobs for research.

### `weekly_insight.json`
- **Size:** 588 bytes
- **Role:** Weekly insight artifact for dashboards/bot.

---

*End of inventory.*