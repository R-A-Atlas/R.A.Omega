# R.A. Omega — Claude Code Implementation Brief

**Goal:** Turn R.A. Omega from a rigid trade-plan generator into a stable, modular, conversational finance-specialized AI system that gives the right answer in the right format every time.

This brief is written for Claude Code / Cursor. Read it fully before editing.

---

## 0. Core Diagnosis

R.A. Omega does **not** mainly need more agents right now. It needs a stronger execution and quality-control layer.

Current problems:

1. **Routing pollution**
   - `classify_intent_route()` is receiving request controls, JSON packets, memory blocks, or other prepended context.
   - It must receive **only the user’s raw plain-text query**.

2. **Trade-template contamination**
   - The system keeps outputting:
     - Trade Plan
     - Entry
     - Stop Loss
     - Take Profit
     - Execution Rules
     - Risk/Reward
   - This happens even when the user asks normal questions or company research questions like:
     - “Give me everything on BlackRock”
     - “What was the score last night?”
     - “Make me a report”

3. **Missing output-mode layer**
   - The system has intents, but the final renderer/output format is not cleanly separated.
   - Intent answers “what is the user asking?”
   - Output mode answers “what shape should the final answer take?”

4. **Weak response validation**
   - Nothing is strongly checking whether the answer actually matched the user’s request.
   - The system needs a quality firewall before the answer reaches the frontend.

5. **Fake/broken progress lifecycle**
   - The frontend progress feed continues even after the model answer appears.
   - Final answer and progress state are not controlled by one authoritative job lifecycle.

6. **Too many agent prompts without enough archetype structure**
   - 117 agents should not mean 117 totally separate giant prompts.
   - Use 6–8 prompt archetypes and map the 117 agents through metadata.

---

## 1. Non-Negotiable Rules

Do **not** modify:

```txt
deep_research.py
gemini_limiter.py
```

Do **not** permanently delete trading logic.

Instead:

```txt
Quarantine / bypass trading renderers unless the user explicitly asks for trade analysis.
```

Must keep tests passing:

```bash
pytest --maxfail=1 --disable-warnings -q
```

Must compile:

```bash
python -m py_compile api_server.py query_router.py atlas_omega.py
```

Also compile all new files:

```bash
python -m py_compile output_modes.py output_contracts.py quality_firewall.py response_judge.py progress_state.py prompt_builder.py
```

Target:

```txt
995+ tests passing
```

---

## 2. Desired Final Behavior

### Example 1 — Company Research

User:

```txt
Give me everything on BlackRock
```

Expected behavior:

```txt
Intent: COMPANY_RESEARCH or GENERAL_FINANCE
Output mode: company_report
Uses web/current data: yes
Forbidden: trade plan, entry, stop loss, execution rules
```

Expected answer sections:

```txt
- Overview
- What BlackRock does
- Business model
- AUM / revenue / financial snapshot
- Key executives
- Recent news
- Competitive position
- Risks
- Sources
```

---

### Example 2 — Casual Question

User:

```txt
hey what was the score from last night's game?
```

Expected behavior:

```txt
Intent: GENERAL_CHAT
Output mode: chat
Tone: casual, direct
Use web/current source if needed
No finance/trading framing
```

---

### Example 3 — Document Request

User:

```txt
Make me a professional report on AI finance companies
```

Expected behavior:

```txt
Intent: DOCUMENT_GENERATION
Output mode: document
Answer: professional report structure
Can generate HTML/Markdown/PDF-ready content
No trade plan unless requested
```

---

### Example 4 — HTML Dashboard Request

User:

```txt
Create a high-visual HTML dashboard for my finance model
```

Expected behavior:

```txt
Intent: HTML_ARTIFACT
Output mode: html_artifact
Answer: polished HTML/CSS/JS or saved artifact
No trading template unless requested
```

---

### Example 5 — Actual Trade Request

User:

```txt
Give me a trade setup for TSLA tomorrow
```

Expected behavior:

```txt
Intent: TRADING_ANALYSIS
Output mode: trade_plan
Trade template allowed
Must include risk disclaimer
```

---

## 3. Required Architecture

Implement this pipeline:

```txt
User raw query
  ↓
Raw-query-only router
  ↓
Intent resolver
  ↓
Output mode resolver
  ↓
Context/data retriever
  ↓
Prompt builder
  ↓
Specialized agent/model synthesis
  ↓
Quality firewall
  ↓
Response judge
  ↓
Repair loop if failed
  ↓
Final response
  ↓
Progress state = COMPLETE
```

---

## 4. Files to Add

Create these new files:

```txt
output_modes.py
output_contracts.py
quality_firewall.py
response_judge.py
progress_state.py
prompt_builder.py
```

Optional later:

```txt
prompt_registry.py
agent_archetypes.py
eval_cases.yaml
tracing.py
memory_vault.py
```

---

## 5. Implementation Task A — Raw Query Routing

### File

```txt
api_server.py
```

### Requirement

Find the POST `/query` handler.

Ensure the router only receives the original user query.

Bad:

```python
raw = router.route(route_input, ...)
```

Good:

```python
raw = router.route(q_store, ...)
```

Where `q_store` must be the stripped raw user query only.

### Iron Rule

Never pass these into routing:

```txt
request controls
agent packet JSON
memory JSON
progress metadata
system instructions
synthesis hints
```

Those can be added later to the synthesis prompt, but **not** to intent classification.

---

## 6. Implementation Task B — Intent Upgrades

### File

```txt
query_router.py
```

Add/confirm these intents:

```python
INTENT_GENERAL_CHAT = "GENERAL_CHAT"
INTENT_GENERAL_FINANCE = "GENERAL_FINANCE"
INTENT_COMPANY_RESEARCH = "COMPANY_RESEARCH"
INTENT_DOCUMENT_GENERATION = "DOCUMENT_GENERATION"
INTENT_HTML_ARTIFACT = "HTML_ARTIFACT"
INTENT_MARKET_DATA = "MARKET_DATA"
INTENT_TRADING_ANALYSIS = "TRADING_ANALYSIS"
```

### Company Detection Before Scoring

Add company detection **before** keyword scoring.

Avoid naive substring-only matching.

Use aliases and disambiguation.

```python
import re
from typing import Optional

KNOWN_COMPANIES = {
    "blackrock": ["blackrock", "blk"],
    "apple": ["apple", "apple inc", "aapl"],
    "microsoft": ["microsoft", "msft"],
    "google": ["google", "alphabet", "goog", "googl"],
    "amazon": ["amazon", "amzn"],
    "tesla": ["tesla", "tsla"],
    "jpmorgan": ["jpmorgan", "jp morgan", "jpm"],
    "goldman sachs": ["goldman sachs", "gs"],
    "morgan stanley": ["morgan stanley", "ms"],
    "berkshire": ["berkshire", "berkshire hathaway", "brk"],
    "warren buffett": ["warren buffett", "buffett"],
    "vanguard": ["vanguard"],
    "fidelity": ["fidelity"],
    "citadel": ["citadel"],
    "bridgewater": ["bridgewater"],
    "sequoia": ["sequoia capital", "sequoia"],
    "softbank": ["softbank"],
    "blackstone": ["blackstone", "bx"],
}

NON_COMPANY_CONTEXT = {
    "apple": ["pie", "fruit", "cider", "juice", "recipe", "orchard"],
    "amazon": ["rainforest", "river", "jungle", "forest"],
    "tesla": ["coil", "inventor", "nikola"],
}

def _contains_phrase(text: str, phrase: str) -> bool:
    escaped = re.escape(phrase.lower())
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text.lower()) is not None

def detect_company_name(raw_query: str) -> Optional[str]:
    q = (raw_query or "").lower()

    for canonical, aliases in KNOWN_COMPANIES.items():
        for alias in aliases:
            if _contains_phrase(q, alias):
                blocked_terms = NON_COMPANY_CONTEXT.get(canonical, [])
                if any(_contains_phrase(q, term) for term in blocked_terms):
                    continue
                return canonical

    return None
```

Then in `classify_intent_route()`:

```python
def classify_intent_route(raw: str) -> str:
    q = (raw or "").strip()
    if not q:
        return INTENT_GENERAL_CHAT

    company = detect_company_name(q)
    if company:
        return INTENT_COMPANY_RESEARCH

    # Existing scoring continues below
```

### General Chat Fallback

If no strong finance/trading/document intent exists:

```python
return INTENT_GENERAL_CHAT
```

Do not force every query into finance/trading.

---

## 7. Implementation Task C — Output Mode Resolver

### New File

```txt
output_modes.py
```

### Purpose

Separate final answer format from intent.

```python
OUTPUT_CHAT = "chat"
OUTPUT_FINANCE_ANSWER = "finance_answer"
OUTPUT_COMPANY_REPORT = "company_report"
OUTPUT_DOCUMENT = "document"
OUTPUT_HTML_ARTIFACT = "html_artifact"
OUTPUT_MARKET_SNAPSHOT = "market_snapshot"
OUTPUT_TRADE_PLAN = "trade_plan"

TRADE_TRIGGER_WORDS = {
    "trade setup", "entry", "stop loss", "take profit", "risk reward",
    "scalp", "swing trade", "day trade", "options play", "calls", "puts"
}

DOCUMENT_TRIGGER_WORDS = {
    "report", "document", "pdf", "brief", "deck", "proposal", "memo"
}

HTML_TRIGGER_WORDS = {
    "html", "dashboard", "landing page", "website", "interactive", "reactive", "visual"
}

def _has_any(q: str, words: set[str]) -> bool:
    ql = q.lower()
    return any(w in ql for w in words)

def user_explicitly_requested_trade(raw_query: str) -> bool:
    return _has_any(raw_query, TRADE_TRIGGER_WORDS)

def resolve_output_mode(raw_query: str, intent: str) -> str:
    q = raw_query or ""

    if _has_any(q, HTML_TRIGGER_WORDS):
        return OUTPUT_HTML_ARTIFACT

    if _has_any(q, DOCUMENT_TRIGGER_WORDS):
        return OUTPUT_DOCUMENT

    if intent == "TRADING_ANALYSIS" or user_explicitly_requested_trade(q):
        return OUTPUT_TRADE_PLAN

    if intent == "COMPANY_RESEARCH":
        return OUTPUT_COMPANY_REPORT

    if intent == "GENERAL_FINANCE":
        return OUTPUT_FINANCE_ANSWER

    if intent == "MARKET_DATA":
        return OUTPUT_MARKET_SNAPSHOT

    return OUTPUT_CHAT
```

---

## 8. Implementation Task D — Output Contracts

### New File

```txt
output_contracts.py
```

### Purpose

Every output mode has required and forbidden sections.

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class OutputContract:
    required_sections: list[str] = field(default_factory=list)
    forbidden_phrases: list[str] = field(default_factory=list)
    tone: str = "clear and helpful"
    requires_sources: bool = False

COMMON_TRADE_FORBIDDEN = [
    "trade plan",
    "entry",
    "stop loss",
    "take profit",
    "execution rules",
    "risk/reward",
    "risk reward",
    "position size",
    "invalidation level",
]

OUTPUT_CONTRACTS = {
    "chat": OutputContract(
        required_sections=[],
        forbidden_phrases=COMMON_TRADE_FORBIDDEN,
        tone="casual, direct, helpful",
        requires_sources=False,
    ),

    "finance_answer": OutputContract(
        required_sections=[],
        forbidden_phrases=COMMON_TRADE_FORBIDDEN,
        tone="professional but readable",
        requires_sources=False,
    ),

    "company_report": OutputContract(
        required_sections=[
            "Overview",
            "Business Model",
            "Financial Snapshot",
            "Leadership",
            "Recent News",
            "Risks",
            "Competitive Position",
        ],
        forbidden_phrases=COMMON_TRADE_FORBIDDEN,
        tone="professional, structured, data-driven",
        requires_sources=True,
    ),

    "document": OutputContract(
        required_sections=[],
        forbidden_phrases=COMMON_TRADE_FORBIDDEN,
        tone="polished, professional, publication-ready",
        requires_sources=False,
    ),

    "html_artifact": OutputContract(
        required_sections=["<!DOCTYPE html", "<html"],
        forbidden_phrases=[],
        tone="high-visual, polished, interactive where appropriate",
        requires_sources=False,
    ),

    "market_snapshot": OutputContract(
        required_sections=[],
        forbidden_phrases=["guaranteed profit", "risk-free"],
        tone="concise, data-driven, market-aware",
        requires_sources=True,
    ),

    "trade_plan": OutputContract(
        required_sections=[
            "Setup",
            "Entry",
            "Invalidation",
            "Risk",
            "Scenarios",
        ],
        forbidden_phrases=["guaranteed profit", "risk-free"],
        tone="precise, risk-aware, educational",
        requires_sources=True,
    ),
}
```

---

## 9. Implementation Task E — Quality Firewall

### New File

```txt
quality_firewall.py
```

### Purpose

Validate the answer before the user sees it.

```python
from dataclasses import dataclass
from output_contracts import OUTPUT_CONTRACTS

@dataclass
class QualityResult:
    passed: bool
    reason: str
    repair_instruction: str = ""

def validate_response(raw_query: str, intent: str, output_mode: str, answer: str) -> QualityResult:
    contract = OUTPUT_CONTRACTS.get(output_mode)
    if not contract:
        return QualityResult(
            passed=False,
            reason=f"Unknown output_mode: {output_mode}",
            repair_instruction="Regenerate using a valid output mode."
        )

    text = (answer or "").lower()

    for phrase in contract.forbidden_phrases:
        if phrase.lower() in text:
            return QualityResult(
                passed=False,
                reason=f"Forbidden phrase found for output_mode={output_mode}: {phrase}",
                repair_instruction=(
                    f"Regenerate the answer as output_mode={output_mode}. "
                    f"Remove all trade-plan language including '{phrase}'. "
                    "Answer the user's actual request directly."
                ),
            )

    missing = []
    for section in contract.required_sections:
        if section.lower() not in text:
            missing.append(section)

    if missing and output_mode not in {"chat", "finance_answer"}:
        return QualityResult(
            passed=False,
            reason=f"Missing required sections: {missing}",
            repair_instruction=(
                f"Regenerate as output_mode={output_mode}. "
                f"Include these required sections: {', '.join(missing)}."
            ),
        )

    if not answer or len(answer.strip()) < 20:
        return QualityResult(
            passed=False,
            reason="Answer too short or empty.",
            repair_instruction="Regenerate with a complete answer."
        )

    return QualityResult(passed=True, reason="Passed quality firewall.")
```

---

## 10. Implementation Task F — Response Judge

### New File

```txt
response_judge.py
```

### Purpose

A final strict judge decides whether the answer satisfies the user request.

Start deterministic. Later this can call an LLM.

```python
from dataclasses import dataclass
from quality_firewall import validate_response

@dataclass
class JudgeResult:
    verdict: str
    reason: str
    repair_instruction: str = ""

def judge_response(raw_query: str, intent: str, output_mode: str, answer: str) -> JudgeResult:
    quality = validate_response(raw_query, intent, output_mode, answer)

    if not quality.passed:
        return JudgeResult(
            verdict="FAIL",
            reason=quality.reason,
            repair_instruction=quality.repair_instruction,
        )

    return JudgeResult(
        verdict="PASS",
        reason="Answer satisfies output contract.",
        repair_instruction="",
    )
```

Future optional LLM judge prompt:

```txt
You are the R.A. Omega Response Judge.

Your only job is to check if the final answer satisfies the user's request.

Return strict JSON:
{
  "verdict": "PASS" or "FAIL",
  "reason": "...",
  "repair_instruction": "..."
}

User raw query:
{{raw_query}}

Intent:
{{intent}}

Output mode:
{{output_mode}}

Forbidden sections:
{{forbidden_sections}}

Answer:
{{answer}}

Rules:
- If the user did not ask for trading, fail any answer containing trade plan, entry, stop loss, take profit, execution rules, or risk/reward.
- If the user asked for company research, require company overview, business model, financial snapshot, leadership, recent news, risks, and competitive position.
- If the answer is generic or dodges the user request, fail it.
- Be strict.
```

---

## 11. Implementation Task G — Progress State Machine

### New File

```txt
progress_state.py
```

### Purpose

Stop fake/frozen progress.

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

class ProgressState(str, Enum):
    QUEUED = "QUEUED"
    ROUTING = "ROUTING"
    RETRIEVING_CONTEXT = "RETRIEVING_CONTEXT"
    TOOL_CALLING = "TOOL_CALLING"
    SYNTHESIZING = "SYNTHESIZING"
    VALIDATING = "VALIDATING"
    FINALIZING = "FINALIZING"
    COMPLETE = "COMPLETE"
    ERROR = "ERROR"

TERMINAL_STATES = {ProgressState.COMPLETE, ProgressState.ERROR}

@dataclass
class JobProgress:
    job_id: str
    state: ProgressState = ProgressState.QUEUED
    message: str = ""
    updated_at: datetime = datetime.utcnow()
    error: Optional[str] = None

    def transition(self, state: ProgressState, message: str = "", error: Optional[str] = None):
        if self.state in TERMINAL_STATES:
            return

        self.state = state
        self.message = message
        self.error = error
        self.updated_at = datetime.utcnow()

    @property
    def is_done(self) -> bool:
        return self.state in TERMINAL_STATES
```

### API Integration Rule

When final response is returned:

```python
progress.transition(ProgressState.COMPLETE, "Complete")
close_progress_stream(job_id)
cancel_progress_task(job_id)
```

If any exception happens:

```python
progress.transition(ProgressState.ERROR, str(exc), error=str(exc))
close_progress_stream(job_id)
```

The progress feed must never continue after final answer.

---

## 12. Implementation Task H — Prompt Builder

### New File

```txt
prompt_builder.py
```

### Purpose

Stop random prompt concatenation.

```python
from output_contracts import OUTPUT_CONTRACTS

def build_synthesis_prompt(
    *,
    raw_query: str,
    intent: str,
    output_mode: str,
    memory_context: str = "",
    live_data: str = "",
    request_controls: str = "",
    company_name: str | None = None,
) -> str:
    contract = OUTPUT_CONTRACTS.get(output_mode)

    required = contract.required_sections if contract else []
    forbidden = contract.forbidden_phrases if contract else []
    tone = contract.tone if contract else "clear and helpful"

    company_instruction = ""
    if output_mode == "company_report" and company_name:
        company_instruction = f"""
LIVE COMPANY RESEARCH REQUIRED:
Search or use current data for {company_name}.
Include:
- What the company does
- Business model
- AUM / revenue / market cap when applicable
- Key executives
- Recent news
- Risks
- Competitive position
- Sources
"""

    return f"""
SYSTEM ROLE:
You are R.A. Omega, a finance-specialized intelligence assistant.
You behave like a general conversational AI when the user asks normal questions.
You only use trading/trade-plan formatting when the user explicitly asks for trading analysis.

RAW USER QUERY:
{raw_query}

INTENT:
{intent}

OUTPUT MODE:
{output_mode}

TONE:
{tone}

{company_instruction}

RELEVANT MEMORY:
{memory_context or "None"}

LIVE DATA / TOOL RESULTS:
{live_data or "None"}

REQUEST CONTROLS:
{request_controls or "None"}

REQUIRED SECTIONS:
{required or "None"}

FORBIDDEN SECTIONS / PHRASES:
{forbidden or "None"}

OUTPUT CONTRACT:
- Answer the raw user query directly.
- Match the output mode exactly.
- Do not include forbidden sections.
- Do not force finance framing on casual non-finance questions.
- Do not force trading language unless output_mode is trade_plan.
- If data is unavailable, say what is missing and what would be needed.
""".strip()
```

---

## 13. Implementation Task I — Company Web Enrichment

### File

```txt
atlas_omega.py
```

### Requirement

When:

```txt
intent == COMPANY_RESEARCH or GENERAL_FINANCE with company detected
```

Then:

```txt
Enable web/current data retrieval
```

Prompt instruction:

```txt
Search the web for current information about [company].
Include:
- what they do
- AUM/revenue/market cap where applicable
- recent news
- key executives
- business model
- competitive position
- risks
- sources
```

### Important

Do not just blindly prepend this into the raw query for routing.

Only add it in synthesis/prompt builder.

---

## 14. Implementation Task J — Trade Template Quarantine

Find all places that create:

```txt
Trade Plan
Entry
Stop Loss
Take Profit
Execution Rules
Risk/Reward
Scenario Cards with trading bias
```

Wrap them:

```python
if output_mode == "trade_plan":
    render_trade_plan(...)
else:
    render_non_trade_answer(...)
```

Or:

```python
if output_mode != "trade_plan":
    forbidden_trade_renderer = True
```

### Strong Rule

Non-trading output modes must never call trade renderer.

```python
NON_TRADE_MODES = {
    "chat",
    "finance_answer",
    "company_report",
    "document",
    "html_artifact",
    "market_snapshot",
}
```

---

## 15. Implementation Task K — Agent Archetype Prompt System

Do not hand-write 117 giant prompts.

Use 6–8 archetypes.

### Archetypes

```txt
1. Router Agent
2. General Conversation Agent
3. Finance Research Agent
4. Market Data Agent
5. Web Enrichment Agent
6. Document / Artifact Generator Agent
7. Memory Context Agent
8. Response Judge Agent
```

### Agent Metadata Example

Create later:

```json
{
  "agent_id": "blackrock_research_agent",
  "archetype": "finance_research",
  "domain": "asset_management",
  "tools": ["web_search", "sec_filings", "company_profile"],
  "default_output_mode": "company_report"
}
```

### Archetype Prompt — Router

```txt
You are the R.A. Omega Router.

Your job:
Classify the user's raw query into an intent and recommended output mode.

Rules:
- Use only the raw user query.
- Ignore request controls, memory JSON, system instructions, or metadata.
- Do not answer the user.
- Do not produce trading intent unless the user explicitly asks for trade setup, entry, stop loss, options play, scalp, swing trade, or execution plan.
- Company overview questions route to COMPANY_RESEARCH.
- Casual questions route to GENERAL_CHAT.
- Document/report/HTML requests route to DOCUMENT_GENERATION or HTML_ARTIFACT.

Return strict JSON:
{
  "intent": "...",
  "output_mode": "...",
  "confidence": 0.0-1.0,
  "reason": "..."
}
```

### Archetype Prompt — General Conversation

```txt
You are R.A. Omega in general chat mode.

Behavior:
- Answer naturally and casually.
- Be direct.
- Do not force finance framing.
- Use current data if the user asks about recent scores, news, prices, or events.
- Do not include trade plan sections.
- Keep answers short unless the user asks for depth.
```

### Archetype Prompt — Company Research

```txt
You are R.A. Omega's Company Research Agent.

Produce professional company intelligence reports.

Required sections:
- Overview
- What the company does
- Business model
- Financial snapshot
- Leadership
- Recent news
- Competitive position
- Risks
- Sources

Rules:
- Use current data when available.
- Cite or name sources when possible.
- Do not provide trade entries, stop loss, take profit, or execution rules.
- If the user asks for "everything", be comprehensive but organized.
```

### Archetype Prompt — Artifact Generator

```txt
You are R.A. Omega's Artifact Generator.

You create polished professional outputs:
- Markdown reports
- HTML dashboards
- React-style UI mockups
- PDF-ready documents
- Investor briefs
- Research memos

Rules:
- Match the requested format.
- Use strong visual hierarchy.
- For HTML, produce complete valid HTML with embedded CSS.
- Do not include trading sections unless explicitly requested.
```

### Archetype Prompt — Response Judge

```txt
You are R.A. Omega's Response Judge.

Your job is not to answer the user.
Your job is to determine if the answer should be shown.

Return JSON:
{
  "verdict": "PASS" or "FAIL",
  "reason": "...",
  "repair_instruction": "..."
}

Fail if:
- Answer uses the wrong output format.
- Answer contains forbidden trade sections.
- Answer ignores the user's actual request.
- Company research lacks core company sections.
- Casual questions are answered with rigid finance/trading templates.
```

---

## 16. Implementation Task L — Memory Vault / Second Brain

Add later after the output system is fixed.

Suggested folder:

```txt
/memory
  user_profile.md
  project_context.md
  decisions.md
  bugs_to_fix.md
  prompt_rules.md
  agent_notes.md
  company_watchlist.md
```

Rule:

```txt
Retrieve only relevant memory chunks.
Never dump the entire memory vault into the prompt.
```

Memory context should enter only through `prompt_builder.py`.

---

## 17. Implementation Task M — Artifact / HTML Output System

Support these output modes:

```txt
document
html_artifact
```

For HTML:

```txt
- complete HTML
- embedded CSS
- responsive design
- dark-mode finance aesthetic by default
- cards, sections, tables, charts placeholders
- professional typography
```

HTML contract:

```txt
Must include:
<!DOCTYPE html>
<html>
<head>
<style>
<body>
```

Do not mix HTML with trade plan unless requested.

---

## 18. Implementation Task N — AI Output Evals

Add Promptfoo or internal eval tests later.

Minimum internal tests now:

```python
def test_blackrock_not_trade_plan():
    q = "Give me everything on BlackRock"
    intent = classify_intent_route(q)
    output_mode = resolve_output_mode(q, intent)
    assert output_mode in {"company_report", "finance_answer"}
    assert output_mode != "trade_plan"

def test_apple_pie_not_company():
    q = "how do I make apple pie"
    intent = classify_intent_route(q)
    assert intent == "GENERAL_CHAT"

def test_casual_sports_chat():
    q = "who won last night's game?"
    intent = classify_intent_route(q)
    output_mode = resolve_output_mode(q, intent)
    assert output_mode == "chat"

def test_trade_request_trade_plan():
    q = "give me a trade setup for TSLA"
    intent = classify_intent_route(q)
    output_mode = resolve_output_mode(q, intent)
    assert output_mode == "trade_plan"

def test_quality_firewall_blocks_trade_bleed():
    result = validate_response(
        raw_query="Give me everything on BlackRock",
        intent="COMPANY_RESEARCH",
        output_mode="company_report",
        answer="Trade Plan: Entry at $100. Stop loss at $90."
    )
    assert result.passed is False
```

---

## 19. API Server Integration Sketch

Inside POST `/query`:

```python
from output_modes import resolve_output_mode
from quality_firewall import validate_response
from response_judge import judge_response
from progress_state import ProgressState
from prompt_builder import build_synthesis_prompt

def handle_query(req):
    progress.transition(ProgressState.ROUTING, "Routing query")

    raw_query = (req.query or "").strip()
    q_store = raw_query

    intent = classify_intent_route(q_store)
    output_mode = resolve_output_mode(q_store, intent)

    progress.transition(ProgressState.RETRIEVING_CONTEXT, "Retrieving context")

    memory_context = get_relevant_memory(q_store)
    live_data = maybe_get_live_data(q_store, intent, output_mode)

    progress.transition(ProgressState.SYNTHESIZING, "Synthesizing answer")

    prompt = build_synthesis_prompt(
        raw_query=q_store,
        intent=intent,
        output_mode=output_mode,
        memory_context=memory_context,
        live_data=live_data,
        request_controls=request_controls,
        company_name=detect_company_name(q_store),
    )

    answer = synthesize_with_model(prompt)

    progress.transition(ProgressState.VALIDATING, "Validating answer")

    quality = validate_response(q_store, intent, output_mode, answer)
    if not quality.passed:
        repair_prompt = prompt + "\n\nREPAIR INSTRUCTION:\n" + quality.repair_instruction
        answer = synthesize_with_model(repair_prompt)

    judge = judge_response(q_store, intent, output_mode, answer)
    if judge.verdict == "FAIL":
        repair_prompt = prompt + "\n\nJUDGE REPAIR INSTRUCTION:\n" + judge.repair_instruction
        answer = synthesize_with_model(repair_prompt)

    progress.transition(ProgressState.FINALIZING, "Finalizing response")

    response = {
        "answer": answer,
        "intent": intent,
        "output_mode": output_mode,
    }

    progress.transition(ProgressState.COMPLETE, "Complete")
    close_progress_stream(req.session_id)

    return response
```

---

## 20. Expected Behavior Matrix

| Query | Intent | Output Mode | Trade Template Allowed? |
|---|---|---|---|
| Give me everything on BlackRock | COMPANY_RESEARCH | company_report | No |
| What does Apple do? | COMPANY_RESEARCH | company_report | No |
| How do I make apple pie? | GENERAL_CHAT | chat | No |
| What was the score last night? | GENERAL_CHAT | chat | No |
| Make me a PDF report | DOCUMENT_GENERATION | document | No |
| Create an HTML dashboard | HTML_ARTIFACT | html_artifact | No |
| Show me TSLA market data | MARKET_DATA | market_snapshot | No |
| Give me a trade setup for TSLA | TRADING_ANALYSIS | trade_plan | Yes |

---

## 21. Final Claude Code Command

Paste this directly into Claude Code:

```txt
Read the full project before editing.

Implement the R.A. Omega quality-control and output-mode architecture described in this markdown.

Primary goal:
Stop R.A. Omega from outputting trade plans for non-trade questions. Make it behave like a general conversational AI with finance specialization.

Do not modify:
- deep_research.py
- gemini_limiter.py

Do not permanently delete trading logic. Quarantine it so it only runs when output_mode == trade_plan.

Add these files:
- output_modes.py
- output_contracts.py
- quality_firewall.py
- response_judge.py
- progress_state.py
- prompt_builder.py

Modify:
- api_server.py
- query_router.py
- atlas_omega.py
- frontend/progress stream code if needed

Implement:
1. Router receives raw user query only.
2. Add GENERAL_CHAT, COMPANY_RESEARCH, DOCUMENT_GENERATION, HTML_ARTIFACT, TRADING_ANALYSIS.
3. Add company detection before scoring, with alias matching and false-positive disambiguation.
4. Add resolve_output_mode(raw_query, intent).
5. Add output contracts with required and forbidden sections.
6. Add quality firewall that blocks trade-plan contamination.
7. Add response judge and one repair loop.
8. Add prompt builder with clean prompt sections.
9. Add company web enrichment only during synthesis, not routing.
10. Add authoritative progress states and force COMPLETE when final answer is returned.
11. Add tests for BlackRock, apple pie, sports chat, document request, HTML request, trade setup, and progress completion.

Run:
python -m py_compile api_server.py query_router.py atlas_omega.py output_modes.py output_contracts.py quality_firewall.py response_judge.py progress_state.py prompt_builder.py
pytest --maxfail=1 --disable-warnings -q

Return:
- concise diff summary
- test results
- remaining issues
```

---

## 22. Success Criteria

The implementation is successful only if:

```txt
"Give me everything on BlackRock"
```

returns a company report and **does not** contain:

```txt
Trade Plan
Entry
Stop Loss
Take Profit
Execution Rules
Risk/Reward
```

And:

```txt
"who won last night's game?"
```

returns a normal casual answer, not a finance report.

And:

```txt
"give me a trade setup for TSLA"
```

is the only kind of query allowed to use trade-plan sections.

And:

```txt
Final answer shown = progress state COMPLETE
```

No frozen fake progress after the answer appears.

---

## 23. Implementation Priority

Build in this exact order:

```txt
1. output_modes.py
2. output_contracts.py
3. quality_firewall.py
4. response_judge.py
5. progress_state.py
6. prompt_builder.py
7. query_router.py company/general chat changes
8. api_server.py integration
9. atlas_omega.py company web enrichment
10. progress frontend/backend cleanup
11. tests
12. py_compile
13. pytest
```

---

## 24. Long-Term Additions After This Works

After the base system is clean:

```txt
1. Promptfoo eval suite
2. LangSmith or Phoenix tracing
3. OpenTelemetry backend traces
4. Firecrawl company research layer
5. Memory vault / Obsidian-style second brain
6. HTML artifact studio
7. 6–8 archetype prompt registry for all 117 agents
8. Model router for cheap/fast/strong/judge models
9. LangGraph or Temporal workflow engine
10. Self-improvement loop from failed quality-firewall outputs
```

Do not start with these until the output-mode and quality-firewall system works.

---

## 25. Most Important Rule

```txt
More agents will not fix bad architecture.
Correct routing + output mode + quality firewall + progress lifecycle will.
```
