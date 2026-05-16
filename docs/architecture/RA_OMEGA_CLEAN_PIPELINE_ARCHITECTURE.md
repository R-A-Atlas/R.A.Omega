# R.A. Omega Clean Pipeline Architecture

The architecture HTML lives at:

`./ra_omega_architecture_clean.html`

Core spine:

User → Chat UI → FastAPI → Query Router → Omega Pipeline Planner → Workflow Executor → Tools/Data → Prompt Builder → Model/Synthesis → Quality Firewall → Renderer → Output → Persistence/Export

Everything else connects to the side of the spine.
