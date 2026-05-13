# Pre-Commit Validation Hook
# Runs before every git commit

Before committing, verify:

1. `python -m py_compile api_server.py` must pass.
2. `python -m pytest tests/ -q` must stay at 962+ passing.
3. `CLAUDE.md` Section 8 must be updated if something new was built.
4. `AGENT_REGISTRY.md` must be updated if any agent status changed.

If any check fails, fix it before committing.
