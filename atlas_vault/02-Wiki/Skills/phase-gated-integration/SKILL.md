# Skill: Phase-Gated Integration (ATLAS)

## [D] Direction

**Purpose:** Execute multi-step integration work (migrations, new auth plumbing, cross-layer changes) without context drift, silent scope creep, or broken runtime.

**When to invoke:** User names a target (e.g. “Loop 5 Supabase positions”) and asks for this skill. Assume production stakes: one wrong move breaks `api_server` or tenant isolation.

**Workflow (mandatory order):**

1. **Dependency scan** — List all readers/writers: HTTP routes, background jobs, direct file readers (`grep`), and downstream loops. Flag `test_user_local` / `ATLAS_DISABLE_AUTH` behavior.
2. **Execution plan** — Written artifact: in-scope files, out-of-scope files, risks, approval gate, self-validation commands, explicit **stop** before the next layer (e.g. “do not touch Loop 6 in this phase”).
3. **User approval** — No production code until the user approves the plan (unless they explicitly waive).
4. **Execute one phase** — Smallest diff; no drive-by refactors.
5. **Self-validation** — Run checks from plan (e.g. `py_compile`, `import api_server`). Fix failures before reporting done.
6. **Handoff** — Summarize what changed, what is deferred, and what to run in Supabase or the next session.

**Guardrails:**

- Never expand scope mid-phase without a new mini-plan and approval.
- If two layers are tightly coupled, say so and recommend one context window vs sub-agents (`claude_os_core.md`).
- Persist outcomes into `atlas_vault/02-Wiki/` or approved project docs when the user requests memory sync.

## [B] Blueprints

**Plan template (sections):**

- Objective & stop condition  
- In-scope paths / modules  
- Out-of-scope / forbidden paths  
- Dependency table (consumer → contract)  
- `test_user_local` & Supabase edge cases  
- Self-validation checklist  
- Rollback note (if applicable)  

**Audit table columns:** Consumer | Access type (HTTP / import / file) | Notes  

## [S] Solutions

**Mechanical checks (examples):**

```bash
python -m py_compile path/to/file.py
python -c "import api_server"
```

**Discovery:**

```bash
rg "pattern" --glob "*.py"
```

**Quality gate:** After substantive edits, run `evals.json` assertions for this skill (manual or scripted).

**Version:** Align with `evals.json` `version` field when updating this skill.
