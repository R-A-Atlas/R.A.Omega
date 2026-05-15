# DEEP_RESEARCH_UPGRADED — Phase 4 Complete

Date: 2026-05-14
Branch: codex/chat-modes-settings
Test result: 1027 passed (unchanged from Phase 3)

---

## Task 1 — `output_mode` parameter in research_ticker()
**Files:** `deep_research.py`

- `research_ticker(ticker, budget, position, client, output_mode="trade_plan", progress=None)` — two new optional params
- Passes `output_mode` and `progress` through to `_research_ticker_impl()`
- `_research_ticker_impl()` signature extended the same way
- After the `synthesis_prompt` f-string closes, appends output_mode constraints:
  - If `output_mode != "trade_plan"`: FORBIDDEN block excluding trade fields
  - If `output_mode == "company_report"`: OUTPUT CONTRACT block for company research
  - If `output_mode == "chat"`: OUTPUT block for short conversational answers

## Task 2 — `progress_state.py` created and wired
**File:** `progress_state.py` (new)

- `ProgressState` dataclass: `stage`, `pct`, `detail`, `started_at`, `.advance()`, `.to_dict()`
- `JobProgress` class: wraps `ProgressState`, calls optional `emit` callback on each transition
- Wired into `_research_ticker_impl()` at 4 transition points:
  - `RETRIEVING_CONTEXT` (5%) — on entry
  - `TOOL_CALLING` (25%) — after yfinance fetch
  - `TOOL_CALLING` (45%) — after web scraping completes
  - `SYNTHESIZING` (55%) — before Gemini synthesis call
  - `FINALIZING` (90%) — after synthesis returns

## Task 3 — `quality_firewall.py` created and wired
**File:** `quality_firewall.py` (new)

- `FirewallResult` dataclass: `.passed`, `.repair_instruction`
- `validate_response(raw_query, intent, output_mode, result_str) -> FirewallResult`
  - `trade_plan` → always passes
  - `company_report` / `finance_answer` → fails if entry_price/stop_loss/take_profit leaked into JSON
  - `chat` → fails if response > 2000 chars
- Wired into `_research_ticker_impl()` after `_run_full_synthesis()` returns — logs warning if not passed

## Task 4 — Model tier routing in gemini_limiter.py
**File:** `gemini_limiter.py`

- Added constants: `MODEL_FLASH = "gemini-2.5-flash"`, `MODEL_PRO = "gemini-2.5-pro"`, `MODEL_AUTO = "auto"`
- Added `_COST_TABLE` with approximate USD/1M token rates for flash and pro
- `get_model_for_tier(output_mode: str) -> str` — trade_plan/company_report → PRO; others → FLASH
- `estimate_cost(input_tokens, output_tokens, model) -> float` — returns USD estimate

## Task 5 — Per-query cost tracking
**Files:** `gemini_limiter.py`, `deep_research.py`

- `record_call()` now accepts `cost_usd: float = 0.0` — stored in `_call_log` entries
- `get_stats()` now returns `total_estimated_cost_usd` summed from `_call_log`
- After synthesis in `_research_ticker_impl()`: estimates token counts from prompt/output lengths,
  calls `record_call("deep_research", success=bool(synthesis), cost_usd=estimated_cost)`

---

## All Files Created or Modified

| File | Action |
|------|--------|
| `progress_state.py` | Created — ProgressState + JobProgress |
| `quality_firewall.py` | Created — FirewallResult + validate_response |
| `gemini_limiter.py` | Modified — model constants, tier routing, cost estimation, record_call cost_usd, get_stats total_cost |
| `deep_research.py` | Modified — output_mode param, progress wiring, quality_firewall + cost tracking after synthesis |
| `DEEP_RESEARCH_UPGRADED.md` | Created |

## Verification

- `python -m py_compile progress_state.py quality_firewall.py gemini_limiter.py deep_research.py` ✅
- `python -m pytest tests/ -q` → **1027 passed** ✅
- `atlas_memory.db` and `atlas_tracker.db`: untouched ✅
