"""
omega_pipeline.py — Central pipeline planner for R.A. Omega.

Every request follows one predictable flow:
  Input → API → Intent Router → Pipeline Planner → Workflow Executor →
  Tools/Data → Prompt Builder → Model/Synthesis → Quality Firewall →
  Renderer → Persistence/Export

Public API:
    plan_request(raw_query, request_controls=None) → PipelinePlan
    select_output_mode(raw_query, route, request_controls=None) → str
    select_workflow(raw_query, route, output_mode, request_controls=None) → str
    should_use_deep_research(raw_query, output_mode, request_controls=None) → bool
    select_renderer_type(output_mode, workflow) → str

Rules enforced here:
  - trade_plan is the only output_mode that produces trade_cards renderer
  - company_report always produces paper_report renderer, never trade_cards
  - chat / general_chat / finance_answer always produce chat_bubble renderer
  - deep research is opt-in ONLY: requires research_mode="deep" in request_controls
    OR an explicit deep-research phrase in the raw_query
  - casual/chat/finance_answer modes CANNOT trigger deep research
  - buttons/toggles in request_controls are optional overrides; raw_query governs by default
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

# ── Workflow identifiers ──────────────────────────────────────────────────────
WORKFLOW_GENERAL_ANSWER      = "general_answer"
WORKFLOW_COMPANY_REPORT_FAST = "company_report_fast"
WORKFLOW_TRADE_ANALYSIS      = "trade_analysis"
WORKFLOW_DEEP_RESEARCH       = "deep_research"
WORKFLOW_DOCUMENT_REPORT     = "document_report"
WORKFLOW_HTML_ARTIFACT       = "html_artifact_gen"
WORKFLOW_MARKET_SNAPSHOT     = "market_snapshot"

# ── Renderer identifiers ──────────────────────────────────────────────────────
RENDERER_CHAT_BUBBLE  = "chat_bubble"
RENDERER_PAPER_REPORT = "paper_report"
RENDERER_TRADE_CARDS  = "trade_cards"
RENDERER_DOCUMENT     = "document"
RENDERER_HTML         = "html_artifact"

# Deep-research phrases the user can type to opt in
_DEEP_RESEARCH_RE = re.compile(
    r"\bdeep\s+research\b|\bfull\s+research\b"
    r"|\bcomprehensive\s+research\b|\bexhaustive\s+research\b",
    re.I,
)

# Intent patterns (uppercase identifiers from classify_intent_route)
_INTENT_RE = re.compile(r"^[A-Z][A-Z_]+$")

# Tool lists per workflow
_WORKFLOW_TOOLS: dict[str, list[str]] = {
    WORKFLOW_GENERAL_ANSWER:      [],
    WORKFLOW_COMPANY_REPORT_FAST: ["omega_agent", "sec_edgar", "web_search"],
    WORKFLOW_TRADE_ANALYSIS:      ["four_loop_engine", "market_scanner", "options_parse"],
    WORKFLOW_DEEP_RESEARCH:       ["deep_research_engine", "omega_agent", "sec_edgar", "web_search", "rag"],
    WORKFLOW_DOCUMENT_REPORT:     ["omega_agent", "export"],
    WORKFLOW_HTML_ARTIFACT:       ["omega_agent"],
    WORKFLOW_MARKET_SNAPSHOT:     ["market_scanner", "web_search"],
}

# Persistence target per workflow
_WORKFLOW_PERSISTENCE: dict[str, str] = {
    WORKFLOW_GENERAL_ANSWER:      "chat_log",
    WORKFLOW_COMPANY_REPORT_FAST: "report",
    WORKFLOW_TRADE_ANALYSIS:      "report",
    WORKFLOW_DEEP_RESEARCH:       "report",
    WORKFLOW_DOCUMENT_REPORT:     "file",
    WORKFLOW_HTML_ARTIFACT:       "file",
    WORKFLOW_MARKET_SNAPSHOT:     "chat_log",
}

# Modes that can never trigger deep research (would be wasteful / wrong)
_NO_DEEP_MODES: frozenset[str] = frozenset({"chat", "general_chat", "finance_answer", "market_snapshot"})


@dataclass
class PipelinePlan:
    route: str
    output_mode: str
    workflow: str
    use_deep_research: bool
    required_tools: list[str]
    renderer_type: str
    persistence_target: str
    reason: str
    skill_name: str = ""  # populated by get_skill_for_output_mode(); empty = no skill matched

    def to_dict(self) -> dict[str, Any]:
        return {
            "route":            self.route,
            "output_mode":      self.output_mode,
            "workflow":         self.workflow,
            "use_deep_research": self.use_deep_research,
            "required_tools":   list(self.required_tools),
            "renderer_type":    self.renderer_type,
            "persistence_target": self.persistence_target,
            "reason":           self.reason,
            "skill_name":       self.skill_name,
        }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_intent(raw_query: str) -> str:
    """Call classify_intent_route; fall back gracefully."""
    try:
        from query_router import classify_intent_route
        return classify_intent_route(raw_query)
    except Exception:
        return "GENERAL_FINANCE"


def _get_output_mode(raw_query: str, intent: str) -> str:
    """Call resolve_output_mode from output_modes; fall back gracefully."""
    try:
        from output_modes import resolve_output_mode
        return resolve_output_mode(raw_query, intent)
    except Exception:
        return "chat"


# ── Public API ────────────────────────────────────────────────────────────────

def should_use_deep_research(
    raw_query: str,
    output_mode: str,
    request_controls: Optional[dict] = None,
) -> bool:
    """
    Returns True ONLY when deep research is explicitly requested.

    Triggers:
      1. request_controls["research_mode"] == "deep"  (button/toggle explicitly set)
      2. Query contains "deep research", "full research", "comprehensive research"

    Never returns True for chat, general_chat, finance_answer, or market_snapshot modes.
    """
    if output_mode in _NO_DEEP_MODES:
        return False

    rc = request_controls or {}

    if rc.get("research_mode") == "deep":
        return True

    if _DEEP_RESEARCH_RE.search(raw_query or ""):
        return True

    return False


def select_output_mode(
    raw_query: str,
    route: str,
    request_controls: Optional[dict] = None,
) -> str:
    """
    Single source of truth for output_mode.

    route may be:
      - A route_band from RouteDecision: "focused_analysis", "quick_chat", ...
      - An intent string from classify_intent_route: "COMPANY_RESEARCH", "GENERAL_CHAT", ...

    request_controls["output_mode_override"] may force a specific mode (UI button).
    """
    rc = request_controls or {}

    # Allow explicit UI override
    override = rc.get("output_mode_override")
    if override:
        return override

    # If route looks like an intent (UPPERCASE_UNDERSCORED), use it directly
    if route and _INTENT_RE.match(route):
        intent = route
    else:
        # Derive intent from raw query
        intent = _get_intent(raw_query)

    return _get_output_mode(raw_query, intent)


def select_workflow(
    raw_query: str,
    route: str,
    output_mode: str,
    request_controls: Optional[dict] = None,
) -> str:
    """
    Select the workflow executor for a request.

    Workflow is driven primarily by output_mode with deep_research flag layered on top.
    Company reports use deep_research workflow only when deep research is explicitly requested.
    """
    use_deep = should_use_deep_research(raw_query, output_mode, request_controls)

    if output_mode in ("chat", "general_chat"):
        return WORKFLOW_GENERAL_ANSWER

    if output_mode == "finance_answer":
        return WORKFLOW_GENERAL_ANSWER

    if output_mode == "company_report":
        return WORKFLOW_DEEP_RESEARCH if use_deep else WORKFLOW_COMPANY_REPORT_FAST

    if output_mode == "trade_plan":
        return WORKFLOW_TRADE_ANALYSIS

    if output_mode == "document":
        return WORKFLOW_DOCUMENT_REPORT

    if output_mode == "html_artifact":
        return WORKFLOW_HTML_ARTIFACT

    if output_mode == "market_snapshot":
        return WORKFLOW_MARKET_SNAPSHOT

    return WORKFLOW_GENERAL_ANSWER


def select_renderer_type(output_mode: str, workflow: str) -> str:
    """
    Map output_mode to renderer type.

    Invariants:
      - trade_plan  → trade_cards    (ONLY mode that may use trade cards)
      - company_report → paper_report (NEVER trade_cards)
      - document    → document
      - html_artifact → html_artifact
      - everything else → chat_bubble
    """
    if output_mode == "trade_plan":
        return RENDERER_TRADE_CARDS
    if output_mode == "company_report":
        return RENDERER_PAPER_REPORT
    if output_mode == "document":
        return RENDERER_DOCUMENT
    if output_mode == "html_artifact":
        return RENDERER_HTML
    return RENDERER_CHAT_BUBBLE


def plan_request(
    raw_query: str,
    request_controls: Optional[dict] = None,
) -> PipelinePlan:
    """
    Central pipeline planner. Returns a PipelinePlan describing every decision for a request.

    Only raw_query is used for intent routing; request_controls are optional overrides.
    This is the single source of truth for: output_mode, workflow, deep_research, renderer.

    Example outputs:
      "Give me everything on BlackRock"
        → output_mode=company_report, workflow=company_report_fast, renderer=paper_report,
          use_deep_research=False

      "Do deep research on BlackRock"
        → output_mode=company_report, workflow=deep_research, renderer=paper_report,
          use_deep_research=True

      "Give me a TSLA trade setup"
        → output_mode=trade_plan, workflow=trade_analysis, renderer=trade_cards

      "How do I make apple pie?"
        → output_mode=chat, workflow=general_answer, renderer=chat_bubble,
          use_deep_research=False

      "Make a PDF report on Microsoft"
        → output_mode=document, workflow=document_report, renderer=document
    """
    rc = request_controls or {}

    # 1. Intent routing — raw query only
    intent = _get_intent(raw_query)

    # 2. Output mode — intent + raw query, optional override
    output_mode = select_output_mode(raw_query, intent, rc)

    # 3. Deep research flag — explicit opt-in only
    use_deep = should_use_deep_research(raw_query, output_mode, rc)

    # 4. Workflow
    workflow = select_workflow(raw_query, intent, output_mode, rc)

    # 5. Renderer
    renderer_type = select_renderer_type(output_mode, workflow)

    # 6. Tools and persistence
    required_tools = list(_WORKFLOW_TOOLS.get(workflow, []))
    persistence_target = _WORKFLOW_PERSISTENCE.get(workflow, "chat_log")

    # 7. Skill mapping — output_mode → skill_name (never loads instructions here)
    skill_name = ""
    try:
        from omega_skill_registry import get_skill_for_output_mode as _gsfom
        skill_name = _gsfom(output_mode) or ""
    except Exception:
        pass

    # 8. Human-readable reason
    reason = (
        f"intent={intent}, output_mode={output_mode}, workflow={workflow}, "
        f"use_deep_research={use_deep}, renderer={renderer_type}"
    )

    return PipelinePlan(
        route=intent,
        output_mode=output_mode,
        workflow=workflow,
        use_deep_research=use_deep,
        required_tools=required_tools,
        renderer_type=renderer_type,
        persistence_target=persistence_target,
        reason=reason,
        skill_name=skill_name,
    )
