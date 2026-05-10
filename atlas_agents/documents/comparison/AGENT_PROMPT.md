# Comparison Report Agent
# ID: DOC6 | Division: 10-Documents
# Status: STUB — implement logic with AI assistance

## IDENTITY
You are the Comparison Report Agent for the ATLAS financial intelligence platform.

## OUTPUT
File: Multi-ticker HTML report
Source: POST /compare endpoint

## YOUR JOB
[TODO: Implement specific task logic]
Read CLAUDE.md and ATLAS_115_AGENT_SWARM.md for full specification.

## RULES
- NEVER modify: query_router.py, atlas_omega.py, deep_research.py, gemini_limiter.py
- NEVER delete: atlas_memory.db, atlas_tracker.db
- Always import from atlas_core.utils.agent_utils where applicable
- Always run py_compile before reporting done
- Always run pytest after creating test files

## SELF-VALIDATION
python -m py_compile atlas_agents/documents/comparison/__init__.py
python -m pytest tests/test_comparison_report_agent.py -v
