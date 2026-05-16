"""
prompt_builder.py — Clean structured prompt construction.
Stops random prompt concatenation and ensures synthesis prompts
carry intent, output_mode, required/forbidden sections cleanly.

Two entry points:
  build_synthesis_prompt() — returns the prompt string (backward-compatible)
  build_synthesis_prompt_meta() — returns (prompt, metadata_dict) with
    selected_skill and context_files_used for frontend/logging use
"""
from __future__ import annotations

from typing import Any
from output_contracts import OUTPUT_CONTRACTS

# Intent → context files that are relevant (mirrors omega_os_loader._INTENT_CONTEXT_MAP)
_INTENT_CONTEXT_MAP: dict[str, list[str]] = {
    "COMPANY_RESEARCH":    ["about_business.md", "brand_guidelines.md", "product_specs.md"],
    "MARKET_DEEP_DIVE":    ["about_business.md", "risk_profile.md", "portfolio_profile.md"],
    "GENERAL_FINANCE":     ["about_business.md", "preferences.md"],
    "DOCUMENT_GENERATION": ["brand_guidelines.md", "preferences.md"],
    "HTML_ARTIFACT":       ["brand_guidelines.md", "preferences.md"],
    "GENERAL_CHAT":        ["about_user.md", "preferences.md"],
    "CASUAL":              ["about_user.md"],
    "TRADING_ANALYSIS":    ["risk_profile.md", "portfolio_profile.md"],
}


def build_synthesis_prompt(
    *,
    raw_query: str,
    intent: str,
    output_mode: str,
    memory_context: str = "",
    live_data: str = "",
    request_controls: str = "",
    company_name: str | None = None,
    omega_os_context: str = "",
    sec_filing_context: str = "",
) -> str:
    """
    Build a structured synthesis prompt from components.
    Memory, live data, request controls, Omega OS context, and SEC filing context
    enter ONLY here — never before routing. classify_intent_route() receives only raw_query.
    """
    contract = OUTPUT_CONTRACTS.get(output_mode)

    required  = list(contract.required_sections) if contract else []
    forbidden = list(contract.forbidden_phrases)  if contract else []
    tone      = contract.tone if contract else "clear and helpful"

    chat_instruction = ""
    if output_mode in ("chat", "general_chat"):
        chat_instruction = "\n".join([
            "GENERAL CHAT MODE:",
            "The user is asking a normal question. Answer conversationally in plain text.",
            "Do NOT structure this as a finance report, trade plan, or trading document.",
            "Do NOT include any of the following sections or phrases:",
            "THE SETUP, YOUR RULES, WHAT BREAKS THIS, HOW THIS PLAYS OUT,",
            "Action: buy/sell/avoid/short, Rating: buy/sell/hold/avoid,",
            "Entry, Stop Loss, Take Profit, Options Play, Best Contract,",
            "Hedge Fund Brief, Intelligence Brief, Intelligence Memo,",
            "Hold Period, Position Size, Position Sizing, Tripwire, Trade Rating, Risk/Reward.",
            "Answer the user's actual question directly in conversational plain text.",
        ])

    company_instruction = ""
    if output_mode == "company_report":
        company_parts = [
            "COMPANY INTELLIGENCE REPORT MODE:",
            "You are writing a professional company intelligence report in clean markdown.",
            "This is not a trade plan. Do not write a trade plan.",
            "Do not include entries, exits, position sizing, trade ratings, tripwires, or execution rules.",
            "Do not use THE SETUP, YOUR RULES, WHAT BREAKS THIS, Entry, Stop Loss, Take Profit,",
            "Action: buy/sell/avoid, or Rating: buy/sell/hold as section headers.",
            "Use these sections: Title, Executive Summary, Company Overview, What They Do,",
            "Business Model, Financial Snapshot, Key Executives, Recent News / Catalysts,",
            "Competitive Position, Key Risks, Sources / Data Notes, Bottom Line.",
        ]
        if company_name:
            company_parts += [
                "",
                f"COMPANY: {company_name}",
                "Include: AUM / revenue / market cap when applicable, business model, key executives, recent news, risks, competitive position, and sources.",
            ]
        company_instruction = "\n".join(company_parts)

    required_block  = "\n".join(f"  - {s}" for s in required)  if required  else "None"
    forbidden_block = "\n".join(f"  - {p}" for p in forbidden) if forbidden else "None"

    parts = [
        "SYSTEM ROLE:",
        "You are R.A. Omega, a finance-specialized intelligence assistant.",
        "You behave like a general conversational AI when the user asks normal questions.",
        "You only use trading/trade-plan formatting when the user explicitly asks for trading analysis.",
        "",
        "RAW USER QUERY:",
        raw_query or "(empty)",
        "",
        f"INTENT: {intent}",
        f"OUTPUT MODE: {output_mode}",
        f"TONE: {tone}",
    ]

    if chat_instruction:
        parts += ["", chat_instruction]

    if company_instruction:
        parts += ["", company_instruction]

    if memory_context:
        parts += ["", "RELEVANT MEMORY:", memory_context]

    if live_data:
        parts += ["", "LIVE DATA / TOOL RESULTS:", live_data]

    if request_controls:
        parts += ["", "REQUEST CONTROLS:", request_controls]

    if omega_os_context:
        parts += ["", "OMEGA OS CONTEXT:", omega_os_context]

    if sec_filing_context and output_mode == "company_report":
        parts += ["", "SEC EDGAR FILINGS (official public record):", sec_filing_context]

    parts += [
        "",
        "REQUIRED SECTIONS:",
        required_block,
        "",
        "FORBIDDEN SECTIONS / PHRASES:",
        forbidden_block,
        "",
        "OUTPUT CONTRACT:",
        "- Answer the raw user query directly.",
        "- Match the output mode exactly.",
        "- Do not include forbidden sections.",
        "- Do not force finance framing on casual non-finance questions.",
        "- Do not force trading language unless output_mode is trade_plan.",
        "- If data is unavailable, say what is missing and what would be needed.",
    ]

    return "\n".join(parts)


def build_synthesis_prompt_meta(
    *,
    raw_query: str,
    intent: str,
    output_mode: str,
    memory_context: str = "",
    live_data: str = "",
    request_controls: str = "",
    company_name: str | None = None,
    include_omega_os: bool = False,
    include_sec_filings: bool = False,
) -> tuple[str, dict[str, Any]]:
    """
    Build a synthesis prompt and return it with metadata.
    Returns (prompt_str, metadata_dict) where metadata includes:
      - selected_skill: the Omega OS skill name matched, or ""
      - context_files_used: list of context file names loaded
      - output_mode: confirmed output mode
      - intent: routing intent
      - omega_os_loaded: bool
      - sec_filings_used: bool
      - latest_10k, latest_10q, latest_8k: filing dicts or None

    This never passes context into classify_intent_route() —
    only raw_query is used for routing. Context loading is synthesis-time only.
    SEC filings are only fetched when output_mode == "company_report" and include_sec_filings=True.
    """
    omega_os_context = ""
    selected_skill = ""
    context_files_used: list[str] = []

    if include_omega_os:
        try:
            from omega_os_loader import select_skill as _select, load_relevant_context as _load_ctx
            selected_skill = _select(raw_query, intent, output_mode)
            omega_os_context = _load_ctx(raw_query, intent, output_mode)
            context_files_used = _INTENT_CONTEXT_MAP.get(intent, ["preferences.md"])
            if selected_skill:
                context_files_used = list(context_files_used) + [f"skills/{selected_skill}/skill.md"]
        except Exception:
            pass  # omega_os unavailable — degrade gracefully

        # Fallback: load only the relevant skill's instructions via omega_skill_registry
        # Only fires when omega_os_loader produced no skill (or wasn't available).
        # Never loads all skills — only the one matched to output_mode.
        if not selected_skill:
            try:
                from omega_skill_registry import (
                    get_skill_for_output_mode as _gsfom,
                    load_skill_instructions as _lsi,
                )
                _matched_skill = _gsfom(output_mode)
                if _matched_skill:
                    selected_skill = _matched_skill
                    _instructions = _lsi(_matched_skill)
                    if _instructions:
                        if omega_os_context:
                            omega_os_context = omega_os_context + "\n\n" + _instructions
                        else:
                            omega_os_context = _instructions
                        context_files_used = list(context_files_used) + [
                            f"skills/{_matched_skill}/skill.md"
                        ]
            except Exception:
                pass  # registry unavailable — degrade gracefully

    # SEC filings — only for company_report, never for casual/chat queries
    sec_filing_context = ""
    sec_meta: dict[str, Any] = {
        "sec_filings_used": False,
        "latest_10k": None,
        "latest_10q": None,
        "latest_8k":  None,
    }
    if include_sec_filings and output_mode == "company_report" and company_name:
        try:
            from omega_sec_edgar import get_filing_summary, is_available
            if is_available():
                filing_data = get_filing_summary(company_name)
                sec_filing_context = filing_data.get("filing_context", "")
                sec_meta = {
                    "sec_filings_used": filing_data.get("sec_filings_used", False),
                    "latest_10k":       filing_data.get("latest_10k"),
                    "latest_10q":       filing_data.get("latest_10q"),
                    "latest_8k":        filing_data.get("latest_8k"),
                }
        except Exception:
            pass  # SEC EDGAR unavailable — degrade gracefully

    prompt = build_synthesis_prompt(
        raw_query=raw_query,
        intent=intent,
        output_mode=output_mode,
        memory_context=memory_context,
        live_data=live_data,
        request_controls=request_controls,
        company_name=company_name,
        omega_os_context=omega_os_context,
        sec_filing_context=sec_filing_context,
    )

    metadata: dict[str, Any] = {
        "selected_skill":     selected_skill,
        "context_files_used": context_files_used,
        "output_mode":        output_mode,
        "intent":             intent,
        "omega_os_loaded":    bool(omega_os_context),
        **sec_meta,
    }

    return prompt, metadata
