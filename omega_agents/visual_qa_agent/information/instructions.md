# visual_qa_agent — Instructions

## What This Worker Does
Reviews screenshots, UI notes, and visual artifacts to produce structured visual QA
findings. Identifies regressions, layout issues, missing elements, and UX problems
in the R.A. Omega UI.

## When to Run
- After any UI change to ra_omega_app.html, auth.html, or index_*.html
- After a server restart and manual test session
- Weekly visual regression check

## Skills Used
- `visual_qa` — answer questions about charts, UI screenshots, and visual artifacts

## Input Sources (read-only, safe)
- Screenshots saved to `atlas_vault/01-Raw/Screenshots/`
- UI notes in `atlas_vault/01-Raw/` or provided inline
- `ra_omega_app.html`, `auth.html`, `index_*.html` (read-only)

## Output
- A markdown QA report with:
  - PASS/FAIL for each UI element checked
  - Screenshots referenced by filename
  - Issues found with severity (Critical / High / Medium / Low)
  - Recommended fixes

## Error Recording
On any failure, append to `past_errors.md` with timestamp, screenshot name, and issue.

## How to Improve
After each QA run, append findings summary to `memory.md`.
Update `plan.md` if new UI elements need systematic coverage.
