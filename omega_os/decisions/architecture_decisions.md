# Architecture Decisions

## AD-001: FastAPI (not Flask or Django)
**Date:** 2026-05
**Decision:** FastAPI for all API routes.
**Rationale:** Async support for parallel data fetching, Pydantic validation, OpenAPI docs auto-generated, faster than Flask for I/O-bound finance data workloads.
**Status:** Active

## AD-002: Supabase (not custom auth)
**Date:** 2026-05
**Decision:** Supabase for auth + database.
**Rationale:** JWT auth out of the box, RLS policies for multi-tenancy, Postgres for complex queries, real-time subscriptions available for future use.
**Status:** Active

## AD-003: BASE_DIR not SCRIPT_DIR
**Date:** 2026-05
**Decision:** All file paths in api_server.py use BASE_DIR.
**Rationale:** SCRIPT_DIR breaks when the server is started from a different working directory (e.g., Railway, systemd). BASE_DIR is always the project root.
**Status:** Active — enforced in CLAUDE.md

## AD-004: Output Contracts (not ad-hoc prompting)
**Date:** 2026-05
**Decision:** Each output mode has an OutputContract with required_sections and forbidden_phrases.
**Rationale:** Prevents trade template contamination. Makes quality checking deterministic instead of relying on LLM self-assessment.
**Status:** Active — output_contracts.py

## AD-005: Progressive Context Loading
**Date:** 2026-05
**Decision:** omega_os_loader loads only relevant context per query, not all context files.
**Rationale:** Dumping all context into every prompt wastes tokens, increases cost, and dilutes prompt quality. Level 1 → Level 2 → Level 3 only when needed.
**Status:** Active — omega_os_loader.py

## AD-006: Summary-First Data Layer
**Date:** 2026-05
**Decision:** OmegaAgent loads data_cache/ summaries first, then enriches with company data.
**Rationale:** 64 cached summaries cover most common data needs without live API calls. Token-efficient for simple questions. Live enrichment only when the query demands it.
**Status:** Active — atlas_core/summaries/summary_generator.py

## AD-007: One Repair Loop Maximum
**Date:** 2026-05
**Decision:** Quality firewall triggers at most one repair synthesis call.
**Rationale:** Two repair loops would double Gemini cost on failures. One loop is sufficient to catch and fix common contract violations. Subsequent failures degrade gracefully (original synthesis returned).
**Status:** Active — deep_research.py

## AD-008: DBS Skill Framework
**Date:** 2026-05
**Decision:** All skills follow Direction (skill.md) + Blueprints (examples) + Solutions (scripts) structure.
**Rationale:** Skills without blueprints produce inconsistent output. Skills without solutions rely on LLM reasoning for deterministic tasks. DBS produces reliable, reusable workflows.
**Status:** Active — omega_os/skills/
