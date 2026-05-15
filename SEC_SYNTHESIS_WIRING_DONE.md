# SEC EDGAR Synthesis Wiring — DONE

**Date:** 2026-05-15
**Branch:** codex/chat-modes-settings

---

## Files Changed

| File | Change |
|------|--------|
| `atlas_omega.py` | Minimal edit — SEC enrichment block in `query()` + prompt note in `_synthesize()` |
| `tests/test_sec_synthesis_wiring.py` | Created — 32 unit tests, all passing |

No changes to `prompt_builder.py`, `query_router.py`, `api_server.py`, `omega_sec_edgar.py`.

---

## What Was Built

### atlas_omega.py — OmegaAgent.query() change

Added a SEC EDGAR enrichment block between the market intel block and the `_synthesize()` call (analogous pattern to `d2_d3_d4_market_intelligence` enrichment).

**Trigger conditions:**
- `_enriched_company` is not None (company was detected from query)
- `intent_route` is NOT "CASUAL" or "GENERAL_CHAT"

**When triggered:**
1. Calls `omega_sec_edgar.is_available()` — skips if returns False
2. Calls `omega_sec_edgar.get_filing_summary(_enriched_company)` — lazy import inside try/except
3. If filings found: adds `sec_edgar_filings` dict to `bundle["data"]` (reaches `_synthesize()` via `data_str`)
4. Sets `_sec_meta` with `sec_filings_used`, `sec_status`, `cik`, `latest_10k`, `latest_10q`, `latest_8k`

**After synthesis:**
- `_sec_meta` merged into `report["_meta"]`
- All existing `_meta` fields (`domain`, `fetch_time_s`, etc.) preserved

**Graceful degradation:**
- `is_available()` returns False → `sec_status: "unavailable"`
- `get_filing_summary()` returns `sec_filings_used: False` → `sec_status: "not_found"`
- Any exception → `sec_status: "unavailable"`, logged at DEBUG level only

### atlas_omega.py — _synthesize() company_report block

Added one line when `_output_mode == "company_report"` and SEC data is in `worker_data`:
```
SEC EDGAR: DATA contains sec_edgar_filings with official filing dates. Cite 10-K and 10-Q dates in the Financial Snapshot section.
```

---

## Routing Purity

- `omega_sec_edgar` is imported inside `OmegaAgent.query()` body (synthesis-time only)
- Import position is always after `def query(` — verified by test
- `classify_intent_route()` still takes exactly one parameter
- `omega_sec_edgar` not imported anywhere in `query_router.py`
- `prompt_builder.py` does not import `query_router`

---

## Trade Plan Contamination Blocked

- `company_report` OUTPUT_CONTRACT forbids: entry price, stop loss, take profit, execution rules, trade plan
- `quality_firewall.validate_response()` returns FAIL on any forbidden phrase
- `NON_TRADE_MODES` frozenset includes `company_report`
- SEC filing context injected via `prompt_builder.build_synthesis_prompt()` only for `output_mode == "company_report"` — not for trade_plan

---

## py_compile Results

```
python -m py_compile atlas_omega.py prompt_builder.py omega_sec_edgar.py api_server.py query_router.py
# ALL PASS
```

---

## Test Results

```
tests/test_sec_synthesis_wiring.py: 32 passed
Full suite (excluding live-server test_omega.py): 1468 passed, 0 failures
```

### Test coverage
- `TestCompanyReportCallsSec` (5): SEC called for COMPANY_RESEARCH, meta has sec_filings_used/sec_status/cik/10k/10q, bundle contains sec_edgar_filings key
- `TestNonCompanyQueriesNoSec` (5): apple pie, sports chat, CASUAL, GENERAL_CHAT, no company detected — all skip SEC
- `TestSecFailureGraceful` (4): exception no crash, is_available=False → unavailable, not_found → not_found, content still returned
- `TestSecMetadataFields` (7): all metadata keys present, types correct, JSON-serializable
- `TestSecNeverEntersRouting` (4): classify_intent_route 1 param, not in query_router, synthesis-time-only import, prompt_builder no query_router import
- `TestTradeplanContaminationBlocked` (5): company_report forbids trade phrases, quality_firewall FAIL on trade language, quality_firewall PASS on clean report, NON_TRADE_MODES contains company_report, SEC context not injected for trade_plan
- `TestCompileChecks` (2): py_compile passes for atlas_omega.py and omega_sec_edgar.py

---

## Remaining / Next Steps

- `detect_company_name()` is called from `query_router.py` (not touched). The SEC lookup uses whatever company name `detect_company_name()` returns — this is correct.
- The `/omega` endpoint does not pass `intent_route` — SEC enrichment for direct `/omega` calls depends on `_enriched_company` being set (which requires `domain == "GENERAL_FINANCE"` or the classifier detecting the company). This is safe and correct.
- For `/query` → `COMPANY_RESEARCH` route: `intent_route="COMPANY_RESEARCH"` is passed explicitly to `omega.query()` — SEC enrichment always runs when a company is found.
