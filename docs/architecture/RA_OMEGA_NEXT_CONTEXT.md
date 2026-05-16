# R.A. Omega Architecture + Skills Handoff Brief

**Purpose:** This file is the single handoff note for Claude Code / Claude.ai before continuing the R.A. Omega build.

**Use:** Put this file in the project root as `RA_OMEGA_NEXT_CONTEXT.md` or in `docs/architecture/RA_OMEGA_NEXT_CONTEXT.md`, then tell Claude Code:

```txt
Read RA_OMEGA_NEXT_CONTEXT.md completely before touching any files. Follow the order exactly.
```

---

## 1. Project Vision

R.A. Omega is an AI finance intelligence operating system, not just a chatbot.

It is meant to become:

- AI chat interface
- Company intelligence report engine
- SEC EDGAR-powered research system
- Finance/market intelligence dashboard
- Omega OS memory/context layer
- Paper-style report/document generator
- Supabase-backed persistence system
- Obsidian knowledge vault
- Future Telegram + Whisper capture layer
- Future Hermes 24/7 operator layer
- Future Agentic OS scheduled workers
- Future Modal/local always-on automation system

The core product behavior should feel like ChatGPT/Gemini:

> The user asks naturally in chat.  
> R.A. Omega detects intent, chooses the right workflow/tools/output mode, and renders the right result automatically.

Users should **not** have to constantly switch buttons/toggles to get the right answer format.

---

## 2. Core Behavioral Rules

Correct examples:

```txt
“Give me everything on BlackRock”
→ company_report
→ company_report_fast
→ paper_report
→ no trade cards
→ no entry/stop/risk-reward/action plan
→ no deep research unless explicitly requested
```

```txt
“Do deep research on BlackRock”
→ company_report + deep_research
→ deeper research workflow allowed
→ paper-style research report
```

```txt
“Give me a TSLA trade setup”
→ trade_plan
→ trade_analysis
→ trade_cards
→ setup/entry/invalidation/risk allowed
```

```txt
“How do I make apple pie?”
→ general_chat
→ general_answer
→ simple chat bubble
→ no finance/report/trade format
```

```txt
“Make a PDF report on Microsoft”
→ document/report workflow
→ downloadable/report artifact
```

---

## 3. Current Priority

Do **not** jump to Telegram, Hermes, Modal, or new features yet.

Current order:

1. Finish/verify `COMPANY_REPORT_PAPER_RENDERER_DONE`
2. Run tests and manually test BlackRock / TSLA / apple pie
3. Run `PIPELINE_REFACTOR_DONE`
4. Run `OMEGA_SKILL_ARCHITECTURE_DONE`
5. Run `AGENTIC_OS_WORKERS_DONE`
6. Run `TELEGRAM_CAPTURE_DONE`
7. Set up actual Telegram BotFather credentials locally
8. Set up Hermes
9. Add Modal/local scheduled workers

---

## 4. Immediate Verification After Current Claude Code Step Finishes

When the stuck/current Claude Code run finishes, first run:

```powershell
dir *DONE*.md
git status
pytest --maxfail=1 --disable-warnings -q
```

If a live-server test fails, start the server in another terminal:

```powershell
uvicorn api_server:app --host 127.0.0.1 --port 8000
```

Then rerun tests.

Then manually test in the app:

```txt
Give me everything on BlackRock
```

Expected:

- paper-style company report
- no trade cards
- no `HOW THIS PLAYS OUT`
- no `ACTION`
- no `HOLD PERIOD`
- no `YOUR RULES`
- no `Entry`
- no `Stop Loss`
- no automatic deep research unless explicitly asked

Then test:

```txt
Give me a TSLA trade setup
```

Expected:

- trade plan
- trade cards allowed
- setup/entry/invalidation/risk allowed

Then test:

```txt
How do I make apple pie?
```

Expected:

- normal casual chat answer
- no finance/report/trade formatting

If any of those fail, fix that before moving forward.

---

## 5. Clean System Pipeline

Every request should flow through one predictable path:

```txt
Input
→ API
→ Intent Router
→ Pipeline Planner
→ Skill Registry
→ Workflow Executor
→ Tools/Data
→ Prompt Builder
→ Model/Synthesis
→ Output Contracts
→ Quality Firewall
→ Renderer
→ Persistence/Export
```

Main center spine:

```txt
User / R.A.
↓
R.A. Omega Chat UI /app
↓
FastAPI Server api_server.py
↓
Query Router query_router.py
↓
Omega Pipeline Planner omega_pipeline.py
↓
Skill Registry omega_skill_registry.py
↓
Workflow Executor atlas_omega.py / future omega_workflows.py
↓
Tools/Data Fetch
↓
Prompt Builder prompt_builder.py
↓
Model Layer Gemini / OpenAI / Claude-compatible
↓
Response Synthesis
↓
Output Contracts output_contracts.py
↓
Quality Firewall quality_firewall.py
↓
Response Judge response_judge.py
↓
Renderer ra_omega_app.html
↓
User Output
↓
Persistence / Export
```

Everything else should connect to the side of this spine:

- Omega OS
- Supabase
- Local JSON fallback
- Google Workspace export
- Dashboard
- Obsidian
- Hermes
- Telegram
- Whisper
- Agentic OS workers
- Modal/local scheduling
- Safety rules

---

## 6. Current Code Rules

Always preserve these:

- Do not touch `deep_research.py` unless explicitly told.
- Do not touch `gemini_limiter.py` unless explicitly told.
- Do not delete `atlas_memory.db`.
- Do not delete `atlas_tracker.db`.
- Do not hardcode API keys.
- Do not break tests.
- Keep routing raw-query-only.
- Buttons/toggles are optional overrides only.
- Trade cards only appear for explicit trade requests.
- Company reports render as paper-style reports.
- Deep research is opt-in only, not default.
- One quality repair pass max.
- Never let repair loops freeze the app.

---

## 7. Prompt 1 — Pipeline Refactor

Run this after `COMPANY_REPORT_PAPER_RENDERER_DONE` is complete and basic tests/manual tests are okay.

```txt
/goal Read COMPANY_REPORT_PAPER_RENDERER_DONE.md, CHAT_DRIVEN_OUTPUT_PLANNER_DONE.md, api_server.py, query_router.py, atlas_omega.py, prompt_builder.py, output_modes.py, output_contracts.py, quality_firewall.py, response_judge.py, progress_state.py, ra_omega_app.html, and tests completely.

Goal:
Create a clean central pipeline planner so every R.A. Omega request follows one predictable flow:
Input → API → Intent Router → Pipeline Planner → Workflow Executor → Tools/Data → Prompt Builder → Model/Synthesis → Quality Firewall → Renderer → Persistence/Export.

Rules:
- Do not touch deep_research.py or gemini_limiter.py.
- Do not delete atlas_memory.db or atlas_tracker.db.
- Do not hardcode API keys.
- Do not break tests.
- Keep routing raw-query-only.
- Buttons/toggles are optional overrides only.
- Trade cards only appear for explicit trade requests.
- Company reports render as paper-style reports.
- Deep research is opt-in only, not default.

Implement:
1. Create omega_pipeline.py.
2. Add:
   - plan_request(raw_query, request_controls=None)
   - select_output_mode(raw_query, route, request_controls=None)
   - select_workflow(raw_query, route, output_mode, request_controls=None)
   - should_use_deep_research(raw_query, output_mode, request_controls=None)
   - select_renderer_type(output_mode, workflow)
3. Pipeline plan must include:
   - route
   - output_mode
   - workflow
   - use_deep_research
   - required_tools
   - renderer_type
   - persistence_target
   - reason
4. Update api_server.py and atlas_omega.py to use omega_pipeline.py as the single source of truth for output_mode, workflow, deep research, and renderer decisions.
5. Remove duplicated/scattered output-mode decision logic where safe.
6. Enforce:
   - “Give me everything on BlackRock” → company_report, company_report_fast, paper_report, use_deep_research=false.
   - “Do deep research on BlackRock” → company_report, deep_research, paper_report, use_deep_research=true.
   - “Give me TSLA trade setup” → trade_plan, trade_analysis, trade_cards.
   - “How do I make apple pie?” → general_chat, general_answer, chat_bubble.
   - “Make a PDF report on Microsoft” → document/report workflow.
7. Ensure company_report cannot render trade_cards.
8. Ensure casual/general chat cannot trigger deep research.
9. Ensure Deep toggle only overrides when explicitly set.

Add tests:
- BlackRock normal query produces company_report, company_report_fast, paper_report, use_deep_research=false.
- Deep research BlackRock query uses deep research.
- TSLA trade setup produces trade_plan and trade_cards.
- Apple pie produces general_chat and chat_bubble.
- PDF report request produces document/report workflow.
- Buttons/toggles only override when explicitly set.
- No company_report returns trade_cards.
- No casual query triggers deep research.

Run:
python -m py_compile omega_pipeline.py api_server.py atlas_omega.py query_router.py prompt_builder.py output_modes.py output_contracts.py quality_firewall.py response_judge.py progress_state.py
pytest --maxfail=1 --disable-warnings -q

Goal met when:
- omega_pipeline.py exists
- request planning is centralized
- output_mode/workflow/renderer decisions are predictable
- BlackRock does not trigger deep research in normal mode
- company_report cannot render trade cards
- casual chat stays casual
- tests pass

Write PIPELINE_REFACTOR_DONE.md with files changed, diff summary, pipeline rules, tests, py_compile results, pytest results, and remaining issues.
```

---

## 8. Skill-Centric Architecture

The Claude Skills transcript adds a major design rule:

> Do not build more random agents/prompts. Build composable skills with tools.

The key concepts:

```txt
Agents = roles/reviewers/coordinators
Skills = reusable procedures
Tools/scripts = deterministic operations inside skills
Pipeline = decides what runs
```

Important principles:

- Prompt skills, not Claude.
- Skills are more than prompts.
- Good skills include description, instructions, tools/scripts, examples, contracts, tests, and changelog.
- Build composable skills, not one giant mega-skill.
- Save deterministic scripts inside skills.
- Use safety metadata to control who can invoke what.
- Update skills after failures/edge cases.
- Avoid skill debt.
- Start with a small set of actively maintained skills, not 100.

R.A. Omega should have two different skill systems:

### A. Claude Code skills / commands

These help build the project.

Likely locations:

```txt
.claude/commands/
.claude/agents/
.claude/settings.json
```

Examples:

```txt
/test-and-fix
/review-changes
/grill
/techdebt
/pipeline-audit
/report-qa
/quick-commit
```

Agents:

```txt
staff-reviewer
code-architect
output-contract-auditor
security-reviewer
ux-qa-reviewer
```

### B. R.A. Omega product skills

These are used by the actual app/model.

Location:

```txt
omega_os/skills/
```

Examples:

```txt
company_report
trade_plan
general_chat
document_generator
dashboard_generator
source_verification
report_export
capture_triage
visual_qa
improve_system
```

---

## 9. Prompt 2 — Omega Skill Architecture

Run this after `PIPELINE_REFACTOR_DONE`.

```txt
/goal Read PIPELINE_REFACTOR_DONE.md, omega_pipeline.py, api_server.py, atlas_omega.py, prompt_builder.py, output_modes.py, output_contracts.py, quality_firewall.py, omega_os_loader.py, omega_dashboard.py, and tests completely.

Goal:
Create a clean R.A. Omega Skill Architecture so repeated workflows are handled by composable skills with metadata, instructions, deterministic tools, examples, tests, and safety rules.

Rules:
- Do not touch deep_research.py or gemini_limiter.py.
- Do not delete atlas_memory.db or atlas_tracker.db.
- Do not hardcode API keys.
- Do not break tests.
- Do not create 100 skills.
- Start with a small maintainable core skill set.
- Skills must support the clean pipeline architecture.
- Skills are procedures/tools, not random prompts.
- Agents decide/review/coordinate; skills define how repeated tasks are done.

Implement:
1. Create docs/architecture/SKILLS_ARCHITECTURE.md explaining:
   - Agents = roles/reviewers/coordinators
   - Skills = reusable procedures
   - Tools/scripts = deterministic operations inside skills
   - Pipeline planner decides when skills are used
   - Keep active skills small to avoid skill debt
   - Update skills after failures/edge cases

2. Standardize omega_os/skills structure.
Each skill folder should support:
   - SKILL.md
   - examples.md
   - contract.json
   - tools/
   - tests/
   - CHANGELOG.md

3. Create or update these core skills only:
   - company_report
   - trade_plan
   - general_chat
   - document_generator
   - dashboard_generator
   - source_verification
   - report_export
   - capture_triage
   - visual_qa
   - improve_system

4. Each SKILL.md must include:
   - name
   - description
   - when_to_use
   - when_not_to_use
   - required_inputs
   - output_contract
   - safety_rules
   - examples
   - repair_strategy
   - related_skills

5. Add skill metadata loader:
Create omega_skill_registry.py with:
   - list_skills()
   - load_skill_metadata()
   - load_skill_instructions(skill_name)
   - get_skill_for_output_mode(output_mode)
   - get_related_skills(skill_name)
   - validate_skill_structure(skill_name)

Metadata should be light. Full SKILL.md loads only when needed.

6. Add deterministic tools:
For company_report:
   omega_os/skills/company_report/tools/verify_company_report.py
   It checks required sections and forbidden trade terms.

For trade_plan:
   omega_os/skills/trade_plan/tools/verify_trade_plan.py
   It checks setup/entry/invalidation/risk sections.

For report_export:
   omega_os/skills/report_export/tools/export_markdown_report.py

For improve_system:
   omega_os/skills/improve_system/tools/audit_skills.py

7. Integrate minimally:
- Pipeline planner can map output_mode to skill.
- Prompt builder can load relevant skill instructions only.
- Quality firewall can call deterministic verification tools where available.
- Do not dump all skills into every prompt.

8. Safety metadata:
Each skill must define:
   - auto_invocable true/false
   - user_invocable true/false
   - requires_confirmation true/false
   - destructive true/false

High-risk future skills like deploy, send_email, schema_migration, broker_action must be documented as requires_confirmation=true and auto_invocable=false if added later.

9. Add tests:
- skill registry lists the 10 core skills
- every skill has SKILL.md, examples.md, contract.json, CHANGELOG.md
- metadata loads without loading full instructions
- company_report maps to company_report skill
- trade_plan maps to trade_plan skill
- company_report verifier catches trade bleed
- trade_plan verifier catches missing sections
- no skill has destructive=true and auto_invocable=true
- prompt_builder loads only the relevant skill instructions
- quality_firewall can use verifier output

Run:
python -m py_compile omega_skill_registry.py omega_pipeline.py prompt_builder.py quality_firewall.py
pytest --maxfail=1 --disable-warnings -q

Goal met when:
- skills are structured, composable, and maintainable
- only 10 core skills exist
- deterministic verification tools exist for company_report and trade_plan
- pipeline/prompt/firewall can use skills without context bloat
- safety metadata prevents dangerous auto-invocation
- tests pass

Write OMEGA_SKILL_ARCHITECTURE_DONE.md with files changed, diff summary, skill list, safety rules, tests, py_compile results, pytest results, and remaining issues.
```

---

## 10. Agentic OS / Double AI Framework

The Agentic OS worker layer comes after skills.

The rule:

> Workers must use existing `omega_os/skills` instead of inventing their own procedures.

Double AI Framework:

```txt
information/
- instructions.md
- memory.md
- past_errors.md
- plan.md
- safety_rules.md

implementation/
- run_worker.py
```

Initial workers:

- Daily Build Brief Agent
- Visual QA Agent
- Report QA Agent
- Growth Content Agent
- Supabase Health Agent

Purpose:

- scheduled safe workers
- future Modal/local hosting
- future Hermes integration
- no dangerous automation yet

---

## 11. Prompt 3 — Agentic OS Workers

Run after `OMEGA_SKILL_ARCHITECTURE_DONE`.

```txt
/goal Read PIPELINE_REFACTOR_DONE.md, OMEGA_SKILL_ARCHITECTURE_DONE.md, omega_pipeline.py, omega_skill_registry.py, omega_os_loader.py, omega_cadence.py, omega_dashboard.py, omega_persistence.py, api_server.py, and tests completely.

Goal:
Add the Agentic OS worker structure using the Double AI Framework. Each always-on worker has an Information folder for instructions/memory/errors/plans and an Implementation folder for safe executable scripts. Workers must use existing omega_os/skills instead of inventing their own procedures.

Rules:
- Do not touch deep_research.py or gemini_limiter.py.
- Do not delete atlas_memory.db or atlas_tracker.db.
- Do not hardcode API keys.
- Do not break tests.
- Do not enable destructive actions.
- Do not enable broker trading.
- Do not send emails automatically.
- This is structure + safe stubs only.

Implement:
1. Create omega_agents/ with this structure:
   - omega_agents/README.md
   - omega_agents/daily_build_brief/information/
   - omega_agents/daily_build_brief/implementation/
   - omega_agents/visual_qa_agent/information/
   - omega_agents/visual_qa_agent/implementation/
   - omega_agents/report_qa_agent/information/
   - omega_agents/report_qa_agent/implementation/
   - omega_agents/growth_content_agent/information/
   - omega_agents/growth_content_agent/implementation/
   - omega_agents/supabase_health_agent/information/
   - omega_agents/supabase_health_agent/implementation/

2. Each information folder must contain:
   - instructions.md
   - memory.md
   - past_errors.md
   - plan.md
   - safety_rules.md

3. Each implementation folder must contain a safe stub Python script:
   - run_daily_build_brief.py
   - run_visual_qa.py
   - run_report_qa.py
   - run_growth_content.py
   - run_supabase_health.py

4. Add omega_agentic_os.py with:
   - list_agentic_workers()
   - load_worker_info(worker_name)
   - get_worker_status(worker_name)
   - run_worker_stub(worker_name)
   - append_worker_memory(worker_name, note)
   - append_worker_error(worker_name, error)

5. Add planned hosting notes:
   - docs/architecture/ALWAYS_ON_AGENT_HOSTING.md
   Include:
   - Local Windows Task Scheduler / Mac Agent Triggers for UI/screenshot workflows
   - Modal Cloud for API-driven scheduled workflows
   - When to use local vs cloud
   - Safety boundaries

6. Add dashboard-ready metadata for future:
   - agentic_workers_count
   - agentic_workers_available
   - always_on_hosting_status="planned"

7. Worker-to-skill mapping:
   - Daily Build Brief Agent uses improve_system
   - Visual QA Agent uses visual_qa
   - Report QA Agent uses company_report, source_verification, improve_system
   - Growth Content Agent uses future content skills, currently safe stub only
   - Supabase Health Agent uses persistence/dashboard health checks

8. Add tests:
   - omega_agents structure exists
   - every worker has information and implementation folders
   - every worker has required information files
   - omega_agentic_os lists workers
   - run_worker_stub does not perform destructive actions
   - worker docs reference existing skills
   - no secrets are hardcoded

Run:
python -m py_compile omega_agentic_os.py
pytest --maxfail=1 --disable-warnings -q

Goal met when:
- omega_agents structure exists
- Double AI Framework is documented
- safe worker stubs exist
- workers reference existing skills
- dashboard can see planned worker metadata
- tests pass

Write AGENTIC_OS_WORKERS_DONE.md with files changed, diff summary, tests, py_compile results, pytest results, and remaining issues.
```

---

## 12. Telegram + Whisper + Hermes Capture

Do this after Agentic OS workers.

Telegram is the remote control.  
Whisper is voice-to-text.  
Hermes is the operator/chief of staff.  
R.A. Omega is still the product.

Flow:

```txt
User → Telegram text/voice → Whisper if voice → Hermes → Capture Inbox → Obsidian / Claude Code prompt / R.A. Omega task
```

---

## 13. Prompt 4 — Telegram Capture

Run after `AGENTIC_OS_WORKERS_DONE`.

```txt
/goal Read PIPELINE_REFACTOR_DONE.md, OMEGA_SKILL_ARCHITECTURE_DONE.md, AGENTIC_OS_WORKERS_DONE.md, omega_pipeline.py, omega_skill_registry.py, omega_persistence.py, omega_connections.py, omega_dashboard.py, api_server.py, .env.example, and tests completely.

Goal:
Add safe Telegram + Whisper-ready capture integration for R.A. Omega, designed to work with Hermes as the 24/7 operator layer later.

Rules:
- Do not delete atlas_memory.db or atlas_tracker.db.
- Do not hardcode API keys.
- Use .env.example placeholders only.
- Do not paste secrets into prompts or logs.
- Do not enable broker trading.
- Do not allow Telegram to trigger destructive actions.
- Telegram must only accept messages from TELEGRAM_ALLOWED_USER_IDS.
- Voice transcription must fail safely if not configured.

Implement:
1. Create or update omega_capture.py:
   - save_capture(raw_text, source="telegram", metadata=None)
   - classify_capture(raw_text, source="telegram")
   - triage_capture(capture_id)
   - get_capture_inbox(limit=20)
   - get_capture_status()

2. Create or update omega_telegram.py:
   - is_telegram_configured()
   - get_telegram_status()
   - verify_allowed_user(user_id)
   - normalize_telegram_message(payload)
   - process_telegram_text_message(payload)
   - process_telegram_voice_message(payload)
   - process_telegram_voice_stub(payload)

3. Voice/Whisper:
   - If VOICE_TRANSCRIPTION_ENABLED=false, return status="voice_not_enabled".
   - If no Whisper/OpenAI key is configured, return status="not_configured".
   - Do not crash.
   - Text messages should work without voice.

4. Add env placeholders:
   TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
   TELEGRAM_ALLOWED_USER_IDS=YOUR_TELEGRAM_USER_ID
   TELEGRAM_WEBHOOK_SECRET=YOUR_TELEGRAM_WEBHOOK_SECRET
   VOICE_TRANSCRIPTION_ENABLED=false
   WHISPER_PROVIDER=openai

5. Add API endpoints:
   - GET /omega-os/capture/status
   - GET /omega-os/capture/inbox
   - POST /omega-os/capture
   - POST /omega-os/capture/{capture_id}/triage
   - GET /omega-os/telegram/status
   - POST /omega-os/telegram/webhook

6. Dashboard:
   Add capture/telegram fields to /omega-os/dashboard:
   - capture_inbox_count
   - latest_captures
   - telegram_status
   - voice_capture_status

7. Tests:
   - Telegram not_configured path works
   - unauthorized user is rejected
   - allowed user text capture saves
   - voice disabled path works
   - capture inbox works
   - triage returns structured recommendation
   - no secrets hardcoded
   - dashboard includes capture fields

Run:
python -m py_compile omega_capture.py omega_telegram.py omega_persistence.py omega_connections.py omega_dashboard.py api_server.py
pytest --maxfail=1 --disable-warnings -q

Write TELEGRAM_CAPTURE_DONE.md with files changed, diff summary, tests, py_compile results, pytest results, and remaining issues.
```

---

## 14. Hermes Rules

Hermes is not R.A. Omega.

Hermes is the future 24/7 operator/chief of staff around R.A. Omega.

Hermes can:

- read/write Obsidian inbox
- triage Telegram captures
- create Claude Code prompts
- review screenshots
- produce visual QA notes
- create daily build briefs
- create content drafts
- create GitHub issues/PR notes if allowed

Hermes must not:

- broker trades
- send emails automatically
- delete files automatically
- modify production DB schema without approval
- expose secrets
- deploy without confirmation

---

## 15. Always-On Hosting Layer

Use later, not now.

Local machine / Windows Task Scheduler / Mac Agent Triggers:

- best for UI/browser/screenshot workflows
- good for visual QA
- uses local session/IP
- useful for logged-in app testing

Modal Cloud:

- best for API-driven scheduled jobs
- daily briefs
- DB checks
- content generation
- health checks
- no screen rendering

---

## 16. Updated Diagram Prompt

Use this to create the updated architecture diagram.

```txt
Create a clean top-to-bottom system architecture diagram for my AI product: R.A. Omega.

I want a professional vertical pipeline map, not a messy network graph.

TITLE:
R.A. Omega Clean Pipeline Architecture

SUBTITLE:
Chat-driven finance intelligence OS with composable skills, optional Hermes operator layer, and future Agentic OS scheduled workers

STYLE:
- Dark background
- White bordered boxes
- Cyan/teal arrows for the main request pipeline
- Gold arrows/boxes for optional/future systems
- Red boxes for safety boundaries
- Top-to-bottom layout
- Grouped layers with section headers
- No spaghetti lines
- Main pipeline must stay visually centered
- Side systems should connect into the correct layer, not cross everywhere

CORE RULE:
Every normal user request flows through:
Input → API → Intent Router → Pipeline Planner → Skill Registry → Workflow Executor → Tools/Data → Prompt Builder → Model/Synthesis → Quality Firewall → Renderer → Persistence/Export.

MAIN CENTER SPINE:
User / R.A.
↓
R.A. Omega Chat UI /app
↓
FastAPI Server api_server.py
↓
Query Router query_router.py
↓
Omega Pipeline Planner omega_pipeline.py
↓
Skill Registry omega_skill_registry.py
↓
Workflow Executor atlas_omega.py / future omega_workflows.py
↓
Tools/Data Fetch
↓
Prompt Builder prompt_builder.py
↓
Model Layer Gemini / OpenAI / Claude-compatible
↓
Response Synthesis
↓
Output Contracts output_contracts.py
↓
Quality Firewall quality_firewall.py
↓
Response Judge response_judge.py
↓
Renderer ra_omega_app.html
↓
User Output
↓
Persistence / Export

SIDE LAYERS:
- Omega OS Memory / Control
- Supabase / Local JSON Fallback
- Google Workspace Export
- Command Center Dashboard
- Obsidian Brain Vault
- Hermes 24/7 Operator
- Telegram + Whisper Capture
- Agentic OS Workers
- Modal / Local Scheduled Hosting
- Safety Boundaries

IMPORTANT CONCEPT:
Agents use skills.
Skills use tools/scripts.
Pipeline controls when each runs.

SKILL LAYER:
Add a dedicated Skill Registry layer with:
- omega_skill_registry.py
- omega_os/skills/
- metadata loaded always
- SKILL.md loaded only when triggered
- tools/scripts run as needed
- examples/contracts used for QA
- CHANGELOG.md for improvements

Core skills:
- company_report
- trade_plan
- general_chat
- document_generator
- dashboard_generator
- source_verification
- report_export
- capture_triage
- visual_qa
- improve_system

Quality rule:
company_report → Paper Report View, not trade cards.
trade_plan → Trade Cards, only explicit trade requests.
general_chat → Simple Chat Bubble.
deep_research → Research Report / Paper Report, only explicit deep request.

HERMES LAYER:
Hermes connects to:
- Telegram Bot
- Whisper
- Capture Inbox
- Obsidian
- Claude Code / Cursor
- GitHub
- Visual QA
- Content Engine
- Daily Briefs
- R.A. Omega API optionally

AGENTIC OS WORKERS:
Show as future scheduled worker layer:
- Daily Build Brief Agent
- Visual QA Agent
- Report QA Agent
- Growth Content Agent
- Supabase Health Agent

Each worker uses Double AI Framework:
information/
- instructions.md
- memory.md
- past_errors.md
- plan.md
- safety_rules.md

implementation/
- run_worker.py

Hosting:
- Local Windows Task Scheduler / Mac Agent Triggers for UI/screenshot workflows
- Modal Cloud for API-driven scheduled workflows

SAFETY:
Show red safety boundary:
- No broker trades
- Draft-only email
- No destructive actions without confirmation
- No secrets in chat/logs
- Confirmation before deploy/schema changes
- Workers cannot modify production DB schema without approval

EXAMPLE CALLOUTS:
Company report:
“Give me everything on BlackRock”
→ COMPANY_RESEARCH
→ company_report skill
→ company_report_fast
→ SEC EDGAR + Web + Market Data
→ verify_company_report.py
→ Paper Report View
→ Save / Download

Trade setup:
“Give me TSLA trade setup”
→ TRADE_SETUP
→ trade_plan skill
→ Trade Analysis
→ Market + Options Data
→ verify_trade_plan.py
→ Trade Cards

Casual:
“How do I make apple pie?”
→ GENERAL_CHAT
→ general_chat skill
→ Simple Chat Bubble
→ no deep research

Deep research:
“Do deep research on BlackRock”
→ explicit deep
→ Deep Research Workflow
→ Research Report / Paper Report

Telegram/Hermes:
Telegram voice/text
→ Whisper if voice
→ Hermes
→ Capture Inbox
→ Obsidian / Claude Code Prompt / R.A. Omega Task

Scheduled worker:
Daily Build Brief Agent
→ uses improve_system skill
→ reads git/test/DONE files
→ writes brief to Obsidian
→ updates dashboard status
→ creates next Claude Code prompt

FINAL OUTPUT:
Create a clean vertical architecture diagram with all layers, arrows, grouped boxes, and concise labels. Keep the main pipeline centered. Put Hermes, Obsidian, Agentic OS Workers, Modal, Supabase, Google Export, and Safety as side/support layers. Avoid spaghetti.
```

---

## 17. One-Sentence Operating Principle

If confused, return to this:

```txt
Pipeline is the spine.
Skills are the reusable procedures.
Agents are specialists/reviewers.
Tools/scripts are deterministic hands.
Memory is the brain.
Hermes is the chief of staff.
Telegram is the remote control.
Modal/local schedules are the heartbeat.
```

---

## 18. What Not To Do Yet

Do not:

- add 100 skills
- add 117 independent active agents
- wire Telegram before the pipeline works
- wire Hermes before capture is safe
- wire Modal before workers are safe
- let company reports render trade cards
- let deep research run by default
- dump the entire Obsidian vault into every query
- give Hermes destructive permissions
- allow broker trades
- send emails automatically
