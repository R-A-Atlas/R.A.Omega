# OUTPUT RENDERER RESET — COMPLETE

Date: 2026-05-15
Branch: codex/chat-modes-settings
Tests: **1940 passed, 0 failed**

Builds on: OUTPUT_RENDERER_RESET_PHASE1_DONE.md (1876 tests)
New tests added this session: 64

---

## Goal Met

- apple pie → plain chat text, no trade cards, no risk bars
- BlackRock → clean paper/document company report, no trade sections
- No non-trade output shows HOLD, ACTION, risk bars, setup cards, options play, hedge fund brief, rules, or tripwires
- Trade cards only appear for explicit trade setup requests (output_mode = trade_plan)
- All tests pass

---

## PHASE 1 — Prompt/Output Contract Cleanup

### `output_contracts.py`

**Added to `COMPANY_REPORT_TRADE_FORBIDDEN`:**
- `"hedge fund brief"` — now blocked in company_report (was only in CHAT_TRADE_FORBIDDEN)
- `"best contract"` — now blocked
- `"best options contract"` — now blocked

**Added `general_chat` contract** (alias for `chat`, same forbidden phrases via `CHAT_TRADE_FORBIDDEN`):
```python
"general_chat": OutputContract(
    required_sections=(),
    forbidden_phrases=tuple(CHAT_TRADE_FORBIDDEN),
    tone="casual, direct, helpful",
    requires_sources=False,
)
```

### `output_modes.py`

Added constant:
```python
OUTPUT_GENERAL_CHAT = "general_chat"
```

Added `OUTPUT_GENERAL_CHAT` to `NON_TRADE_MODES` frozenset.

### `prompt_builder.py`

Added `GENERAL CHAT MODE` instruction block for `output_mode in ("chat", "general_chat")`:
```
GENERAL CHAT MODE:
The user is asking a normal question. Answer conversationally in plain text.
Do NOT structure this as a finance report, trade plan, or trading document.
Do NOT include any of the following sections or phrases:
THE SETUP, YOUR RULES, WHAT BREAKS THIS, HOW THIS PLAYS OUT,
Action: buy/sell/avoid/short, Rating: buy/sell/hold/avoid,
Entry, Stop Loss, Take Profit, Options Play, Best Contract,
Hedge Fund Brief, Intelligence Brief, Intelligence Memo,
Hold Period, Position Size, Position Sizing, Tripwire, Trade Rating, Risk/Reward.
Answer the user's actual question directly in conversational plain text.
```

Block is injected at synthesis time, before `company_instruction`.

---

## PHASE 2 — Quality Firewall Hard Blocks

### `quality_firewall.py`

**Added to `_COMPANY_REPORT_BLEED_HEADERS` tuple:**
- `"hedge fund brief"`
- `"best contract"`
- `"best options contract"`

These now trigger early bleed detection (same as `"the setup"`, `"your rules"`, etc.) for company_report mode.

**Extended chat bleed detection to `general_chat`:**
```python
if output_mode in {"chat", "finance_answer", "general_chat"}:
```

Previously only `chat` and `finance_answer` were checked.

---

## PHASE 3 — Tests

New file: `tests/test_output_renderer_reset_phase3.py` — **64 tests**

### `TestGeneralChatContract` (12 tests)
- `general_chat` contract exists in OUTPUT_CONTRACTS
- Forbids the_setup, your_rules, what_breaks_this, how_this_plays_out, hedge_fund_brief, intelligence_brief, action_buy, stop_loss
- Same forbidden phrases as `chat`
- `OUTPUT_GENERAL_CHAT` constant exists; `general_chat` in NON_TRADE_MODES

### `TestPromptBuilderChatInstruction` (9 tests)
- chat/general_chat prompt includes "GENERAL CHAT MODE" header
- Prompt forbids THE SETUP, Stop Loss, Hedge Fund Brief phrases
- Prompt says "conversational" / "plain text"
- company_report prompt does NOT include chat instruction
- trade_plan prompt does NOT include chat instruction

### `TestCompanyReportNewForbiddenPhrases` (5 tests)
- `COMPANY_REPORT_TRADE_FORBIDDEN` now contains hedge_fund_brief, best_contract, best_options_contract
- `OUTPUT_CONTRACTS["company_report"].forbidden_phrases` contains these

### `TestOutputModeDefaults` (5 tests)
- Casual/non-finance queries default to `chat` not `trade_plan`
- apple_pie → chat, BlackRock → company_report, TSLA trade → trade_plan

### `TestFirewallNewCompanyReportBlocks` (8 tests)
- hedge_fund_brief in answer → company_report fails with bleed_detected=True
- best_contract, best_options_contract, options_play, how_this_plays_out, your_rules → fail
- Clean company report still passes
- Repair instruction mentions "company"

### `TestFirewallGeneralChatMode` (6 tests)
- Clean chat passes for general_chat mode
- Trade bleed, the_setup, hedge_fund_brief → fail for general_chat mode
- Returns QualityResult for None inputs
- Trade plan still passes

### `TestEndToEndScenarios` (11 tests)
- Full chain: apple_pie → chat → firewall PASS
- apple_pie clean answer has no trade sections
- Full chain: BlackRock → company_report → firewall PASS
- Clean report has no hold/action/options_play/how_this_plays_out/your_rules/hedge_fund_brief
- Full chain: TSLA → trade_plan → firewall PASS

### `TestHTMLRendererNonTradeGates` (8 tests)
- QuickStatsStrip gated by isTradePlan (risk/impact meters only for trade_plan)
- isTradePlan is exact === comparison to 'trade_plan'
- _srIsTradePlan is exact === comparison to 'trade_plan'
- shouldRenderStructuredResponse whitelist only
- chat mode renders as plain text
- Missing/empty output_mode renders as plain
- No ungated THE SETUP, YOUR RULES, WHAT BREAKS THIS occurrences

---

## py_compile Results

```
python -m py_compile api_server.py query_router.py atlas_omega.py prompt_builder.py output_modes.py output_contracts.py quality_firewall.py response_judge.py progress_state.py
# ALL PASS — no output
```

---

## pytest Results

```
1940 passed, 0 failed, 16 warnings in 67.42s
```

---

## Remaining Issues

None blocking. The output renderer reset is fully complete across both phases:

| Layer | Status |
|---|---|
| Frontend gates (isTradePlan) | ✅ Phase 1 done |
| isPlainChatResponse / shouldRenderStructuredResponse | ✅ Phase 1 done |
| Standalone report (_srIsTradePlan) | ✅ Phase 1 done |
| Output contracts (CHAT_TRADE_FORBIDDEN) | ✅ Phase 1 done |
| Quality firewall chat bleed | ✅ Phase 1 done |
| Prompt builder chat instruction | ✅ This session |
| general_chat contract/mode | ✅ This session |
| company_report + hedge fund brief / best contract | ✅ This session |
| general_chat firewall bleed detection | ✅ This session |
| Phase 3 tests (64 new) | ✅ This session |

Visual screenshot confirmation (Priority 1 in CLAUDE.md) recommended after server restart.
