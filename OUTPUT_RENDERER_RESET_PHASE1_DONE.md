# OUTPUT RENDERER RESET — PHASE 1 DONE

Date: 2026-05-15
Branch: codex/chat-modes-settings
Tests: **1876 passed, 0 failed**

---

## Goal

Emergency reset of the output/rendering path. The app was rendering normal chat and company research responses using trade-plan cards (HOLD, Confidence, THE SETUP, YOUR RULES, WHAT BREAKS THIS, HOW THIS PLAYS OUT, Hedge Fund Brief, action/rating headers, risk bars).

Success criteria met:
- `apple pie` → plain chat text (no trade cards, no risk bars, no setup)
- `BlackRock` → paper-style company report (no trade cards)
- Trade cards only appear when output_mode is exactly `trade_plan`

---

## Root Cause

`FourLoopEngine` always populates `final_report` with all trade fields (`overall_rating`, `trade_plan`, `scenarios`, `execution_rules`, `failure_modes`, `trader_memo`, etc.) regardless of intent. The UI's `hasStructuredFinanceSections` check detected these fields and rendered trade cards for ALL modes. Gates used `!isCompanyReport` (hide for company_report only) instead of `isTradePlan` (show only for trade_plan).

---

## Files Changed

### `ra_omega_app.html`

**`isPlainChatResponse(data)`** — updated to check `_output_mode` first:
- Returns `true` for `chat`, `finance_answer`, `document`, `html_artifact`, `market_snapshot`, or missing/empty mode
- Prevents structured card rendering for all non-trade, non-company-report modes

**`shouldRenderStructuredResponse(data)`** — tightened whitelist:
- Only returns `true` for `trade_plan` and `company_report`
- All other modes render as plain markdown text

**`isTradePlan` gate** — added in StructuredResponse component:
```js
const isTradePlan = outputMode === 'trade_plan';
```

Changed **all trade card gates** from `!isCompanyReport` → `isTradePlan`:
- QuickStatsStrip (risk/impact meters)
- Rating line (`overall_rating`)
- Bull thesis card
- Bear thesis card
- THE SETUP card (`trade_plan`)
- HOW THIS PLAYS OUT (`scenarios`)
- YOUR RULES (`execution_rules`)
- WHAT BREAKS THIS (`failure_modes`)
- INTELLIGENCE BRIEF (`trader_memo`)
- TLDR border color

**`generateStandaloneReport`** — added `_srIsTradePlan`:
```js
const _srIsTradePlan = _srOutputMode === 'trade_plan';
```

Changed standalone report sections to gate on `_srIsTradePlan`:
- `thesisSection` (bull/bear)
- `tpSection` (THE SETUP)
- `optionsSection` (options play)
- `scSection` (HOW THIS PLAYS OUT)
- `plSection` (price levels)
- `rulesSection` (YOUR RULES)
- `fmSection` (WHAT BREAKS THIS)
- `analystSection` (analyst consensus)
- `hfSection` (HEDGE FUND BRIEF)
- `memoSection` (INTELLIGENCE BRIEF/MEMO)

### `output_contracts.py`

Added `CHAT_TRADE_FORBIDDEN` — superset of `COMMON_TRADE_FORBIDDEN` plus:
- `the setup`, `your rules`, `what breaks this`, `how this plays out`
- `hold period`, `action: buy/sell/avoid/short`, `rating: buy/sell/hold/avoid`
- `tripwire`, `position sizing`, `trade rating`
- `hedge fund brief`, `intelligence brief`, `intelligence memo`

Changed `chat` and `finance_answer` contracts to use `tuple(CHAT_TRADE_FORBIDDEN)`.

### `quality_firewall.py`

Added `_CHAT_REPAIR` instruction string.

Added chat bleed detection block in `_validate()`:
- Checks `CHAT_TRADE_FORBIDDEN` for `chat` and `finance_answer` output modes
- Returns `QualityResult(passed=False, bleed_detected=True, repair_instruction=_CHAT_REPAIR)` on any match

### `tests/test_output_renderer_reset.py` (NEW — 56 tests)

- `TestTradeFieldsForbiddenForNonTradeModes` — CHAT_TRADE_FORBIDDEN contains all required headers
- `TestOutputModeRouting` — apple pie→chat, BlackRock→company_report, TSLA trade→trade_plan
- `TestCompanyReportNoTradeCards` — firewall detects trade bleed in company_report
- `TestPromptNeverAddsTradeSchemaToChat` — chat prompt has no trade instruction
- `TestQualityFirewallHardBlocks` — chat bleed detection for apple pie, your rules, action buy, etc.
- `TestHTMLRendererGates` — source inspection: isTradePlan gates, plain chat logic, shouldRenderStructuredResponse

### Updated existing tests (3 files)

`tests/test_company_report_quarantine.py`, `tests/test_company_report_paper_renderer.py`, `tests/test_chat_driven_output_planner.py` — updated gate assertions from `!isCompanyReport` to `isTradePlan`/`_srIsTradePlan`.

---

## Removed Trade Fallback Locations

| Location | Old gate | New gate |
|---|---|---|
| QuickStatsStrip | `!isCompanyReport` | `isTradePlan` |
| Rating line | ungated | `isTradePlan` |
| Bull thesis card | `!isCompanyReport` | `isTradePlan` |
| Bear thesis card | `!isCompanyReport` | `isTradePlan` |
| THE SETUP | `!isCompanyReport` | `isTradePlan` |
| HOW THIS PLAYS OUT | `!isCompanyReport` | `isTradePlan` |
| YOUR RULES | `!isCompanyReport` | `isTradePlan` |
| WHAT BREAKS THIS | `!isCompanyReport` | `isTradePlan` |
| INTELLIGENCE BRIEF | ungated | `isTradePlan` |
| TLDR border color | `!isCompanyReport` | `isTradePlan` |
| Standalone bull/bear | `!_srIsCompanyReport` | `_srIsTradePlan` |
| Standalone THE SETUP | `!_srIsCompanyReport` | `_srIsTradePlan` |
| Standalone options | ungated | `_srIsTradePlan` |
| Standalone scenarios | `!_srIsCompanyReport` | `_srIsTradePlan` |
| Standalone price levels | ungated | `_srIsTradePlan` |
| Standalone YOUR RULES | `!_srIsCompanyReport` | `_srIsTradePlan` |
| Standalone WHAT BREAKS THIS | `!_srIsCompanyReport` | `_srIsTradePlan` |
| Standalone analyst | ungated | `_srIsTradePlan` |
| Standalone HEDGE FUND BRIEF | ungated | `_srIsTradePlan` |
| Standalone INTELLIGENCE MEMO | ungated | `_srIsTradePlan` |

---

## py_compile Results

```
python -m py_compile api_server.py query_router.py atlas_omega.py prompt_builder.py output_modes.py output_contracts.py quality_firewall.py
# ALL PASS — no output
```

---

## pytest Results

```
1876 passed, 0 failed, 16 warnings in 63.13s
```

---

## Remaining Issues

None blocking. The output renderer reset is complete. Backend quality firewall blocks chat bleed at the synthesis layer; frontend gates ensure trade cards only render for `output_mode=trade_plan`.

Visual screenshot confirmation (Priority 1 in CLAUDE.md) is still recommended after server restart.
