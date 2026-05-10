# Skill: Data Validator
# ID: E8 | Division: 0-Engineering
# DBS Framework

## [D] Direction
Data Validator — ATLAS 0-Engineering. Validates JSON under `data_cache/` for required
schema and consistency. Read [ATLAS_115_AGENT_SWARM.md](../../../../ATLAS_115_AGENT_SWARM.md);
full narrative in [ATLAS_AGENT_SWARM_SETUP.md](../../../../ATLAS_AGENT_SWARM_SETUP.md) (E8).
B2 implements `atlas_core.validation.data_validator`; this skill covers the agent stub + checks.

## [B] Blueprints
Reference snapshot pattern: atlas_agents/crypto/crypto_scraper.py  
Shared utilities (for scrapers; validator may reuse types only): atlas_core/utils/agent_utils.py  
Agent stub: atlas_agents/engineering/data_validator/

## [S] Solutions
Validate Swarm structure:
  python -m py_compile atlas_agents/engineering/data_validator/__init__.py
  python -m pytest tests/test_data_validator_agent.py -v

When implementation exists:
  python -m atlas_core.validation.data_validator
