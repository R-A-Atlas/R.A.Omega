# Skill: weekly_product_review

## name
weekly_product_review

## description
Weekly structured review of product metrics, architecture decisions, open issues, roadmap
progress, and next week's priorities. Combines Four C audit + level-up + roadmap check.

## when_to_use
- Every Monday morning (cadence job: weekly_product_review)
- User asks "run the weekly review" or "what's the status of the product?"
- Before planning a new sprint
- After completing a major feature or sprint

## inputs_required
- Current test count (python -m pytest --co -q | tail -1)
- Optional: queries run this week (GET /history/reports)
- Optional: any user feedback received
- Optional: current Four C audit score

## steps
1. Run system health check:
   a. python -m py_compile api_server.py query_router.py atlas_omega.py
   b. pytest count — confirm no regression
   c. Check server starts: uvicorn api_server:app --host 127.0.0.1 --port 8000
2. Run Four C audit (omega_audit.run_audit())
3. Run level-up analysis (omega_level_up.analyze())
4. Review project_roadmap.md — which items completed this week?
5. Review architecture_decisions.md — any new decisions made?
6. Review product_decisions.md — any pivots or reversals?
7. Check connection status: any planned connections now feasible?
8. Identify this week's top 3 wins
9. Identify this week's top 3 blockers
10. Set next week's top 3 priorities
11. Write session log entry: atlas_vault/04-Projects/ATLAS/Notes/session_log.md (PASS/FAIL/PARTIAL)
12. Update project_roadmap.md with completed items and new priorities

## outputs
- Weekly review report (wins, blockers, priorities)
- Four C audit score with delta from last week
- Top automation opportunity from level-up engine
- Updated session_log.md entry
- Updated project_roadmap.md

## safety_rules
- Do not edit deep_research.py, gemini_limiter.py, or atlas_memory.db during review
- Do not push to production without completing visual QA step first
- Do not mark items as complete if tests are failing
- Session log must be PASS only if all tests pass and server starts clean

## related_files
- omega_audit.py — Four C scoring
- omega_level_up.py — automation opportunities
- omega_os/context/project_roadmap.md — roadmap tracking
- omega_os/decisions/architecture_decisions.md
- omega_os/decisions/product_decisions.md
- atlas_vault/04-Projects/ATLAS/Notes/session_log.md

## quality_checks
- [ ] Test count confirmed (no regression from last week)
- [ ] Server starts clean (no import errors)
- [ ] Four C score computed and compared to last week
- [ ] Top 3 wins listed (specific, not vague)
- [ ] Top 3 blockers listed (specific, with proposed resolution)
- [ ] Next week's priorities set (3 items max, ordered)
- [ ] session_log.md updated
- [ ] project_roadmap.md updated with completed items
