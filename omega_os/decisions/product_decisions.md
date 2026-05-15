# Product Decisions

## PD-001: Two-Path Architecture (FourLoopEngine vs OmegaAgent)
**Date:** 2026-05
**Decision:** Keep two separate execution paths rather than merging into one.
**Rationale:** FourLoopEngine is optimized for deep equity/options (10 loops, structured trade output). OmegaAgent is optimized for cross-domain speed (debt, cars, mortgages, macro). Merging would compromise both.
**Status:** Active

## PD-002: Routing Purity
**Date:** 2026-05
**Decision:** classify_intent_route() receives ONLY the user's raw plain-text query.
**Rationale:** Prepending memory, session data, or request controls caused routing pollution — wrong intents were being selected. Clean routing means deterministic, testable behavior.
**Status:** Active — rule is enforced in CLAUDE.md

## PD-003: Trade Template Quarantine
**Date:** 2026-05
**Decision:** Trade plan sections (Entry, Stop Loss, Take Profit, Execution Rules, Risk/Reward) only appear when output_mode == trade_plan.
**Rationale:** The system was outputting trade plan format for company research and casual questions. OUTPUT_CONTRACTS enforce forbidden phrases per mode.
**Status:** Active

## PD-004: Gemini Flash for Simple, Pro for Deep
**Date:** 2026-05
**Decision:** Use Gemini Flash for chat/simple queries, Gemini Pro for deep research, company_report, and trade_plan.
**Rationale:** Cost optimization. Flash is ~17x cheaper than Pro. Only deep synthesis justifies Pro cost.
**Status:** Active

## PD-005: Atlas Memory as Switching Cost Moat
**Date:** 2026-05
**Decision:** atlas_memory.db is never deleted and grows with every query.
**Rationale:** The system getting smarter with usage is the primary retention and moat mechanism. Losing this DB would reset the personalization layer.
**Status:** Active — NEVER DELETE rule enforced in CLAUDE.md

## PD-006: Interactive HTML Reports as Conversion Hook
**Date:** 2026-05
**Decision:** Standalone HTML report is the primary conversion hook for beta users.
**Rationale:** "Power BI for retail traders" — editable, dark-themed, exportable reports are a unique differentiator vs Bloomberg/Seeking Alpha.
**Status:** Active
