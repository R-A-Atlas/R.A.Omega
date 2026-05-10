# ATLAS 115-Agent Swarm — Canonical Index

This file is the **stable entry point** for the full agent roster. Per-agent **executable specs** live in-repo as follows; keep this index short so tooling can cite one path.

## Authoritative roster

- **Table of all 115 agents (ID, name, directory, output, status):** [atlas_agents/AGENT_REGISTRY.md](atlas_agents/AGENT_REGISTRY.md)

## Full narrative blueprint (build order, roles, prompt templates)

- **Phase-by-phase setup and embedded AGENT_PROMPT text:** [ATLAS_AGENT_SWARM_SETUP.md](ATLAS_AGENT_SWARM_SETUP.md)

## Per-agent prompt on disk (what Swarm Builder ships)

- **Runtime spec for agent `<A>`:** `atlas_agents/<division>/<package>/AGENT_PROMPT.md` (path from registry **Directory** column)
- **DBS skill:** `atlas_vault/02-Wiki/Skills/<kebab-slug>/SKILL.md`

## Swarm Builder procedure

- **Operational copy:** [ATLAS_25_CURSOR_AGENTS.md](ATLAS_25_CURSOR_AGENTS.md) — section **AGENT B3 — SWARM BUILDER**

## If you need JSON schemas

Schemas referenced in skills and prompts are defined alongside each agent’s `AGENT_PROMPT.md` or in [ATLAS_AGENT_SWARM_SETUP.md](ATLAS_AGENT_SWARM_SETUP.md) until a separate schema bundle is added.

---

*Swarm Builder note: When adding a new agent, update `AGENT_REGISTRY.md` and keep this file as the single “read me first” pointer—do not duplicate long specs here.*
