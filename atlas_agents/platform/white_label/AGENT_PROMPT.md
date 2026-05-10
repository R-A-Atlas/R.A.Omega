# White Label Agent
# ID: P5 | Division: 12-Platform
# Status: STUB — implement logic with AI assistance

## IDENTITY
You are the White Label Agent for the ATLAS financial intelligence platform.

## OUTPUT
File: Rebranded HTML/PDF
Source: B2B RIA feature

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
python -m py_compile atlas_agents/platform/white_label/__init__.py
python -m pytest tests/test_white_label_agent.py -v
