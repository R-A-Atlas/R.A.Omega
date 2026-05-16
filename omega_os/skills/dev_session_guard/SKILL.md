# Skill: dev_session_guard

## name
dev_session_guard

## description
Pre-flight and post-flight guard for every development session.
Runs one command at session start to give a full system state brief,
and one command before committing to block unsafe changes.
Prevents the most common R.A. Omega development mistakes.

## why_this_exists
Every session previously required manually:
  - Reading CLAUDE.md to find next priority
  - Running health_scorer to check architecture state
  - Running chain_mapper to find dead wires
  - Manually checking protected files weren't touched
  - Verifying test count hadn't dropped
  - Checking git status for forgotten files

This skill automates all of that into two commands:
  python run_preflight.py          → session START check
  python run_preflight.py --pre-commit → before git commit

## when_to_use
- START of every Claude Code session
- Before every git commit
- After any change to api_server.py, query_router.py, or atlas_omega.py
- When returning to the project after more than 24 hours
- When the test count drops unexpectedly

## commands

### Session start (run FIRST, every session)
```bash
python omega_os/skills/dev_session_guard/tools/run_preflight.py
```

### Pre-commit check (run BEFORE every git commit)
```bash
python omega_os/skills/dev_session_guard/tools/run_preflight.py --pre-commit
```

### Full state brief only (no checks)
```bash
python omega_os/skills/dev_session_guard/tools/session_briefing.py
```

### Quick protected-file check only
```bash
python omega_os/skills/dev_session_guard/tools/run_preflight.py --protected-only
```

## steps

### Session Start (run_preflight.py, default mode)
1. Check git branch — warn if not on expected feature branch
2. Scan for modifications to PROTECTED files (deep_research.py, gemini_limiter.py)
3. Run py_compile on all core files (api_server.py, query_router.py, atlas_omega.py, output_modes.py, alerts.py)
4. Count current test total — warn if below 2387 (last known good baseline)
5. Run health_scorer → show 5-axis score and rating
6. Run chain_mapper --wires → show any dead wires
7. Run upgrade_scanner --critical-only → show critical items only
8. Read CLAUDE.md Section 9 (PRIORITY BUILD LIST) → surface next priority
9. Read last 3 git commit messages → show recent context
10. Output structured "Session Brief" — everything in one screen

### Pre-commit mode (--pre-commit)
1. Steps 2-4 from above (protected files + compile + test count) — BLOCK on failure
2. Run ui_audit → warn if any file scores below 65
3. Check no .env file staged (git diff --cached)
4. Check no atlas_memory.db or atlas_tracker.db staged
5. Check api_server.py compiles clean
6. Run chain_mapper --wires → BLOCK if any broken chains
7. Output PASS or FAIL with specific blockers

## guardrails
- NEVER modify deep_research.py or gemini_limiter.py (enforced by check #2)
- NEVER delete atlas_memory.db, atlas_tracker.db, atlas_rag/ (file existence checks)
- NEVER commit .env (staged file scan)
- NEVER let test count drop below baseline (enforced by check #4)
- ALWAYS run tests after any change to routing files

## outputs
- Session Brief: branch, score, priority, recent commits, warnings (printed to stdout)
- Pre-commit report: PASS or FAIL with numbered blockers (exit code 1 on failure)
- Both outputs fit in one terminal screen

## related_files
- omega_os/skills/improve_system/tools/health_scorer.py
- omega_os/skills/improve_system/tools/chain_mapper.py
- omega_os/skills/improve_system/tools/upgrade_scanner.py
- omega_os/skills/improve_system/tools/ui_audit.py
- CLAUDE.md — source of truth for priorities and rules
- tests/ — test suite baseline

## evals
See evals.json — 8 binary assertions.

## quality_checks
- [ ] Protected file check catches modifications to deep_research.py
- [ ] Compile check catches syntax errors in api_server.py
- [ ] Test count check detects dropped tests
- [ ] Health scorer runs and returns a score
- [ ] Chain mapper runs and reports dead wires
- [ ] Pre-commit mode exits 1 on any blocker
- [ ] Session brief fits in one terminal screen (<40 lines)
- [ ] Run time under 30 seconds total
