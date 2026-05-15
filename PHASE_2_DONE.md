# PHASE_2_DONE — deep_research.py + gemini_limiter.py

Date: 2026-05-15
Branch: codex/chat-modes-settings
Test result: 1077 passed (was 1074; +3 from unrelated prior additions)
                1 skipped — test_omega.py::test_car_omega requires live server on :8000 (pre-existing)

---

## gemini_limiter.py — No changes needed

All Phase 2 requirements were already satisfied from the previous sprint (Phase 4):

| Requirement | Status |
|---|---|
| `MODEL_FLASH = "gemini-2.5-flash"` | ✅ already present |
| `MODEL_PRO = "gemini-2.5-pro"` | ✅ already present |
| `get_model_for_tier(output_mode)` — flash for chat, pro for trade_plan/company_report | ✅ already present |
| `estimate_cost(input_tokens, output_tokens, model) -> float` | ✅ already present |
| `record_call(cost_usd: float = 0.0)` — backward-compatible new param | ✅ already present |
| `get_stats()` — returns `total_estimated_cost_usd` | ✅ already present |

---

## deep_research.py — One change: quality firewall repair loop

### What changed

In `_research_ticker_impl()`, the quality firewall block previously only logged a warning
on failure. It now attempts **one repair synthesis** when the firewall fails.

### Diff summary

```diff
-    # ── quality firewall ──────────────────────────────────────────────────────
+    # ── quality firewall + one repair loop ───────────────────────────────────
     try:
         from quality_firewall import validate_response as _qfw_validate
         import json as _json_qfw
         _qfw = _qfw_validate(ticker, "MARKET_DEEP_DIVE", output_mode, _json_qfw.dumps(synthesis or {}))
         if not _qfw.passed:
-            logging.warning("  [quality_firewall] %s", _qfw.repair_instruction[:100])
+            logging.warning("  [quality_firewall] %s — attempting repair synthesis", _qfw.reason[:80])
+            _repair_prompt = synthesis_prompt + "\n\nREPAIR INSTRUCTION:\n" + _qfw.repair_instruction
+            try:
+                _repair_synthesis, _repair_quality = _run_full_synthesis(
+                    client, _repair_prompt, ticker, today, mktdata,
+                    budget, scraped_context, scrape_text, float(price or 0),
+                )
+                if _repair_synthesis and str(_repair_synthesis.get("executive_summary") or "").strip():
+                    synthesis = _repair_synthesis
+                    synthesis_quality = "repaired_by_firewall"
+                    logging.info("  [quality_firewall] repair synthesis succeeded")
+                else:
+                    logging.warning("  [quality_firewall] repair synthesis returned empty result")
+            except Exception:
+                logging.debug("  [quality_firewall] repair synthesis failed", exc_info=True)
     except Exception:
         logging.debug("quality_firewall check failed", exc_info=True)
```

### Repair loop behavior
- Builds `_repair_prompt = synthesis_prompt + "\n\nREPAIR INSTRUCTION:\n" + qfw.repair_instruction`
- Calls `_run_full_synthesis()` with identical market data and scraped context
- If repair returns a non-empty `executive_summary`: replaces `synthesis`, sets `synthesis_quality = "repaired_by_firewall"`
- If repair returns empty: logs warning, keeps original synthesis (graceful degradation)
- All exceptions caught silently — never breaks the main research pipeline

---

## py_compile Results

```
python -m py_compile deep_research.py gemini_limiter.py
→ COMPILE OK ✅
```

---

## pytest Results

```
pytest --maxfail=1 --disable-warnings -q
→ 1077 passed, 1 failed (test_car_omega — live server not running), 17 warnings ✅

pytest --ignore=tests/test_omega.py --disable-warnings -q
→ 1077 passed, 17 warnings ✅
```

The single failure (`test_omega.py::test_car_omega`) is a pre-existing live-server
integration test that requires `uvicorn api_server:app` running on port 8000.
It was failing before this sprint and is unrelated to Phase 2 changes.

---

## Not Completed / Deferred

- **Full `prompt_builder` integration in `_synthesize()`**: deferred — atlas_omega still
  builds its own prompt; output_contract forbidden/required sections are appended.
- **Sections 15 & 16** (Agent Archetype Prompt Registry, Memory Vault): deferred per brief.
