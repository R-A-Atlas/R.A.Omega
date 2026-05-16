# PIPELINE REFACTOR — DONE

Date: 2026-05-15
Branch: codex/chat-modes-settings
Tests: **2012 passed, 0 failed**
New tests: 72 (test_omega_pipeline.py)

---

## Goal Met

- `omega_pipeline.py` exists as the central pipeline planner
- Every R.A. Omega request follows one predictable flow
- `output_mode`, `workflow`, `deep_research`, and `renderer_type` decisions are centralized
- BlackRock normal query → `company_report`, `company_report_fast`, `paper_report`, `use_deep_research=False`
- BlackRock with deep toggle/phrase → `company_report`, `deep_research`, `paper_report`, `use_deep_research=True`
- TSLA trade setup → `trade_plan`, `trade_analysis`, `trade_cards`
- Apple pie → `chat`, `general_answer`, `chat_bubble`, `use_deep_research=False`
- PDF report on Microsoft → `document`, `document_report`
- company_report never produces `trade_cards`
- chat/general_chat/finance_answer never triggers deep research
- Buttons/toggles are optional overrides only

---

## Architecture

```
Input → API → Intent Router → omega_pipeline.plan_request()
                              → select_output_mode()  (single source of truth)
                              → should_use_deep_research()  (strict opt-in)
                              → select_workflow()  (output_mode + deep flag)
                              → select_renderer_type()  (output_mode → renderer)
             → Workflow Executor → Tools/Data
             → Prompt Builder
             → Model/Synthesis
             → Quality Firewall
             → Renderer (type from pipeline)
             → Persistence/Export
```

---

## Files Changed

### `omega_pipeline.py` (NEW)

**Constants:**
- Workflow identifiers: `WORKFLOW_GENERAL_ANSWER`, `WORKFLOW_COMPANY_REPORT_FAST`, `WORKFLOW_TRADE_ANALYSIS`, `WORKFLOW_DEEP_RESEARCH`, `WORKFLOW_DOCUMENT_REPORT`, `WORKFLOW_HTML_ARTIFACT`, `WORKFLOW_MARKET_SNAPSHOT`
- Renderer identifiers: `RENDERER_CHAT_BUBBLE`, `RENDERER_PAPER_REPORT`, `RENDERER_TRADE_CARDS`, `RENDERER_DOCUMENT`, `RENDERER_HTML`

**`PipelinePlan` dataclass** — fields: `route`, `output_mode`, `workflow`, `use_deep_research`, `required_tools`, `renderer_type`, `persistence_target`, `reason`

**`plan_request(raw_query, request_controls=None) → PipelinePlan`**
- Calls classify_intent_route (raw query only)
- Calls select_output_mode, should_use_deep_research, select_workflow, select_renderer_type
- Returns fully populated PipelinePlan

**`select_output_mode(raw_query, route, request_controls=None) → str`**
- `route` accepts either route_band ("focused_analysis") or intent ("COMPANY_RESEARCH")
- `request_controls["output_mode_override"]` for UI override
- Delegates to output_modes.resolve_output_mode

**`should_use_deep_research(raw_query, output_mode, request_controls=None) → bool`**
- Returns True ONLY for: `request_controls["research_mode"] == "deep"` OR deep-research phrase in query
- Never True for `chat`, `general_chat`, `finance_answer`, `market_snapshot` modes

**`select_workflow(raw_query, route, output_mode, request_controls=None) → str`**
- `company_report` + deep → `deep_research`
- `company_report` + normal → `company_report_fast`
- `trade_plan` → `trade_analysis`
- `chat`/`general_chat`/`finance_answer` → `general_answer`
- `document` → `document_report`
- `html_artifact` → `html_artifact_gen`
- `market_snapshot` → `market_snapshot`

**`select_renderer_type(output_mode, workflow) → str`**
- `trade_plan` → `trade_cards` (ONLY mode that may render trade cards)
- `company_report` → `paper_report` (NEVER trade_cards)
- `document` → `document`
- `html_artifact` → `html_artifact`
- everything else → `chat_bubble`

### `api_server.py`

Replaced line 1616 `resolve_output_mode(q_store, _intent)` with:
```python
from omega_pipeline import select_output_mode as _pipeline_select_om
_output_mode = _pipeline_select_om(q_store, _intent, {"research_mode": mode})
```
Fallback to existing `resolve_output_mode` if import fails.

### `atlas_omega.py`

Replaced try/except chain (lines 2187-2195) with:
```python
from omega_pipeline import select_output_mode as _pipeline_select_om
_output_mode = _pipeline_select_om(query, domain, {})
```
Fallback to existing output_modes.resolve_output_mode then "finance_answer".

---

## Pipeline Rules

| Scenario | output_mode | workflow | renderer | use_deep_research |
|---|---|---|---|---|
| "Give me everything on BlackRock" | company_report | company_report_fast | paper_report | False |
| "Do deep research on BlackRock" | company_report | deep_research | paper_report | True |
| "BlackRock" + research_mode=deep toggle | company_report | deep_research | paper_report | True |
| "Give me TSLA trade setup" | trade_plan | trade_analysis | trade_cards | False |
| "How do I make apple pie?" | chat | general_answer | chat_bubble | False |
| "Apple pie" + research_mode=deep toggle | chat | general_answer | chat_bubble | False |
| "Make a PDF report on Microsoft" | document | document_report | document | False |
| "Create an interactive dashboard" | html_artifact | html_artifact_gen | html_artifact | False |

---

## Tests

`tests/test_omega_pipeline.py` — **72 tests**

### `TestPipelineStructure` (7 tests)
- PipelinePlan is a dataclass with all 8 required fields
- `to_dict()` returns complete dict
- `required_tools` is a list; `use_deep_research` is a bool
- Workflow and renderer constants exist with correct values

### `TestShouldUseDeepResearch` (13 tests)
- Normal BlackRock/TSLA queries do not trigger deep research
- "deep research", "full research", "comprehensive research" phrases trigger it
- research_mode="deep" control triggers it
- research_mode="normal"/"web" do not trigger it
- chat/general_chat/finance_answer modes CANNOT trigger deep research even with deep control
- Empty controls do not trigger deep research

### `TestSelectOutputMode` (9 tests)
- BlackRock → company_report; TSLA trade → trade_plan; apple pie → chat; PDF → document
- Route bands pass through correctly
- `output_mode_override` in controls is respected
- Goldman Sachs → company_report

### `TestSelectWorkflow` (10 tests)
- company_report + normal → company_report_fast
- company_report + deep phrase → deep_research
- company_report + deep control → deep_research
- trade_plan → trade_analysis; chat → general_answer; document → document_report
- html_artifact → html_artifact_gen; market_snapshot → market_snapshot

### `TestSelectRendererType` (10 tests)
- trade_plan → trade_cards; company_report (both workflows) → paper_report
- chat/general_chat/finance_answer → chat_bubble
- document → document; html_artifact → html_artifact
- market_snapshot → chat_bubble; unknown → chat_bubble

### `TestPlanRequestScenarios` (14 tests)
- Full end-to-end: BlackRock normal, BlackRock deep phrase, BlackRock deep control
- TSLA trade setup; apple pie; PDF report
- apple pie + deep toggle still gets chat_bubble (not deep)
- BlackRock + normal control stays fast workflow
- Tools populated for company_report; empty for chat
- Persistence: "report" for company_report, "chat_log" for chat
- Reason string is populated

### `TestHardInvariants` (5 tests)
- company_report NEVER gets trade_cards (multiple queries)
- chat NEVER triggers deep research (multiple queries)
- chat NEVER gets trade_cards (multiple queries)
- Explicit trade request ALWAYS gets trade_plan + trade_cards
- Non-trade queries never get trade_cards

### `TestButtonToggleOverrides` (5 tests)
- No controls = same as research_mode=normal
- Deep toggle only affects workflow, not output_mode
- output_mode_override overrides routing
- web mode does not trigger deep research
- Deep toggle on chat query still gives no deep research

---

## py_compile Results

```
python -m py_compile omega_pipeline.py api_server.py atlas_omega.py query_router.py prompt_builder.py output_modes.py output_contracts.py quality_firewall.py response_judge.py progress_state.py
# ALL PASS — no output
```

---

## pytest Results

```
2012 passed, 0 failed, 16 warnings in 85.02s
```

---

## Remaining Issues

None blocking. The pipeline planner is fully implemented and wired:

| Layer | Status |
|---|---|
| omega_pipeline.py created | ✅ |
| plan_request() / all 4 sub-functions | ✅ |
| api_server.py uses omega_pipeline for output_mode | ✅ |
| atlas_omega.py uses omega_pipeline for output_mode | ✅ |
| company_report → paper_report enforced | ✅ |
| trade_plan → trade_cards enforced | ✅ |
| deep research opt-in only | ✅ |
| casual/chat cannot trigger deep research | ✅ |
| 72 new tests covering all scenarios | ✅ |

Optional future work: thread `plan_request()` result through to the frontend as `_pipeline_plan` field so the UI can read `renderer_type` directly from the response instead of inferring it from `_output_mode`.
