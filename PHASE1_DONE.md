# PHASE 1 DONE — Tasks 1-5

Date: 2026-05-14
Branch: codex/chat-modes-settings
Test result: 1027 passed (was 1010; +17 new tests)

---

## Task 1 — `resolve_output_mode()` in query_router.py
**File:** `query_router.py`

- Added new intent constants:
  - `INTENT_GENERAL_CHAT = "GENERAL_CHAT"`
  - `INTENT_COMPANY_RESEARCH = "COMPANY_RESEARCH"`
  - `INTENT_DOCUMENT_GENERATION = "DOCUMENT_GENERATION"`
- Added `_OUTPUT_MODE_TRADE_RE` regex (matches: trade/entry/setup/options/scalp/swing/stop loss/take profit/call/put/strike/expir/position size/risk-reward)
- Added `_OUTPUT_MODE_DOC_RE` regex (matches: report/pdf/html/document/generate/presentation/deck/spreadsheet/workbook/export)
- Added `resolve_output_mode(raw_query: str, intent: str) -> str` — returns one of: `chat`, `finance_answer`, `company_report`, `document`, `html_artifact`, `trade_plan`
- Wired into `api_server.py`: after `_ensure_query_ui_envelope`, computes `_output_mode` from the parsed intent and stores it as `shaped["_output_mode"]`
- Import added to `api_server.py` line ~122; fallback stub added to ImportError except block

## Task 2 — Disable trade templates for non-trading queries
**File:** `atlas_omega.py:_synthesize()`

After building the Gemini prompt, lazily imports `resolve_output_mode` from `query_router` and computes `_output_mode`. Then appends to the prompt:
- If `_output_mode != "trade_plan"`: `FORBIDDEN: Do not include entry_price, stop_loss, take_profit, execution_rules, trade_plan, risk_reward. This is not a trading query.`
- If `_output_mode == "company_report"`: `OUTPUT CONTRACT: Provide company overview, business model, revenue/AUM, key executives, recent news, risks, competitive position, sources. No trade plan.`
- If `_output_mode == "chat"`: `OUTPUT: Short casual conversational answer. No finance jargon unless asked.`

## Task 3 — GENERAL_CHAT intent and casual fallback
**Files:** `query_router.py`, `atlas_omega.py`

- Added `INTENT_GENERAL_CHAT = "GENERAL_CHAT"` constant
- Added `CASUAL_SIGNALS` module-level tuple: hey/hello/hi/how are you/who won/last night/write me/make me/joke/weather
- In `classify_intent_route()`: after the CASUAL_PATTERNS check (which returns INTENT_CASUAL), added: `if mkt == 0.0 and any(re.search(p, lc) for p in CASUAL_SIGNALS): return INTENT_GENERAL_CHAT`
- In `route()`: updated routing condition to `(INTENT_GENERAL_FINANCE, INTENT_CASUAL, INTENT_GENERAL_CHAT)` — all three route to OmegaAgent with `intent_route=route_kind`
- In `atlas_omega.py:OmegaAgent.query()`: updated `if intent_route in ("CASUAL", "GENERAL_CHAT"):` to route both to `_respond_casual()`

## Task 4 — Fix progress lifecycle
**File:** `api_server.py`

When a research job completes successfully, added a COMPLETE event to the `update_job` call:
```python
event={
    "type": "complete",
    "label": "Done",
    "detail": "Final answer ready. Progress stream closed.",
    "ts": datetime.now(timezone.utc).isoformat(),
}
```
This ensures the frontend receives a definitive `complete` event in the job's event log when the final response is ready. Error paths already set `status="failed"` before this change.

## Task 5 — Tests
**File:** `tests/test_output_modes.py` — 17 tests

| Test | Result |
|------|--------|
| BlackRock query → `output_mode = company_report` | ✅ |
| BlackRock envelope → `entry_price = None`, `stop_loss = None` | ✅ |
| "apple pie recipe" → NOT GENERAL_FINANCE | ✅ |
| "who won last night" → GENERAL_CHAT | ✅ |
| "give me a trade setup on NVDA" → `output_mode = trade_plan` | ✅ |
| "write me an email" → GENERAL_CHAT | ✅ |
| resolve_output_mode constants/rules | ✅ (11 more tests) |

---

## All Files Created or Modified

| File | Action |
|------|--------|
| `query_router.py` | Modified — 3 new constants, CASUAL_SIGNALS, resolve_output_mode, GENERAL_CHAT routing |
| `atlas_omega.py` | Modified — GENERAL_CHAT handling, output_mode prompt constraints in _synthesize |
| `api_server.py` | Modified — _output_mode in response, resolve_output_mode import, COMPLETE event |
| `tests/test_output_modes.py` | Created — 17 new tests |
| `PHASE1_DONE.md` | Created |

## Verification
- `python -m py_compile query_router.py api_server.py atlas_omega.py` ✅
- `python -m pytest tests/ -q` → **1027 passed** ✅
- `deep_research.py` and `gemini_limiter.py`: untouched ✅
- `atlas_memory.db` and `atlas_tracker.db`: untouched ✅
