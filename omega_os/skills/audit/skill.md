# Skill: audit

## name
audit

## description
Run the Four C audit on the current Omega OS state and generate a scored report with
strengths, gaps, and the next 5 best implementation steps.

## when_to_use
- Weekly — every Monday morning as part of weekly product review
- When the user asks "what is our Omega OS score?" or "run an audit"
- Before starting a new sprint to establish baseline
- After completing a sprint to measure progress

## inputs_required
- None required — reads omega_os/ folder structure automatically
- Optional: previous audit result for delta comparison

## steps
1. Import and run omega_audit.run_audit()
2. Display Four C scores: Context / Connections / Capabilities / Cadence (0–25 each)
3. Show total score (0–100) and phase label (Foundation / Development / Operations / Command Center)
4. List strengths (what is already working)
5. List gaps (what is missing or incomplete)
6. List missing connections (planned but not yet active)
7. List missing skills (planned but not yet created)
8. List missing cadence jobs (planned but not yet scheduled)
9. Output next 5 best implementation steps in priority order
10. Append result to omega_os/audits/four_c_audits.md via omega_os_loader.append_audit_result()

## outputs
- Four C score card (Context / Connections / Capabilities / Cadence / Total)
- Strengths list
- Gaps list
- Next 5 implementation steps
- Appended audit entry in omega_os/audits/four_c_audits.md

## safety_rules
- Do not modify any files except four_c_audits.md during the audit
- Do not delete any omega_os files during the audit
- Do not expose file system paths or internal configs to end users

## related_files
- omega_audit.py — Four C scoring engine
- omega_os_loader.py — append_audit_result()
- omega_os/audits/four_c_audits.md — audit history

## quality_checks
- [ ] All four C scores are between 0 and 25
- [ ] Total score is between 0 and 100
- [ ] Next 5 steps are specific and actionable (not vague)
- [ ] Audit result appended to four_c_audits.md
- [ ] No file modifications other than four_c_audits.md
