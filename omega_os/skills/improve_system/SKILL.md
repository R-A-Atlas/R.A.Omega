# skill: improve_system

## name
improve_system

## description
Analyze system behavior, identify improvement opportunities, and produce actionable recommendations for the R.A. Omega platform.

## when_to_use
- User asks "why is X broken?", "can you improve Y?", "what should we fix next?"
- Internal audit or self-improvement request
- Quality firewall triggers improvement review

## when_not_to_use
- User wants a finance answer (use company_report or general_chat)
- This is a normal user query, not a system improvement request

## inputs_required
- Description of the issue or area to improve
- Optional: recent logs, test output, or failure examples

## steps
1. Understand the issue or area to improve
2. Review relevant files, logs, or test output
3. Identify root cause or improvement opportunity
4. Produce specific, actionable recommendations
5. Flag any destructive changes and require user confirmation

## outputs
- renderer_type: chat_bubble
- Format: structured recommendation list
- Tone: engineering, specific, actionable
- Destructive changes: always flagged and require confirmation

## safety_rules
- Do not modify production files without explicit user approval
- Never delete data files (atlas_memory.db, atlas_tracker.db)
- All recommendations must be reversible or explicitly flagged as destructive

## quality_checks
- Each recommendation is specific and actionable (not vague)
- Destructive changes are flagged
- No production files modified without user approval

## examples
Input: "The quality firewall is rejecting too many valid company reports"
Output: Analysis of firewall rules + specific rule changes to make + test cases to add

## repair_strategy
If the improvement analysis is inconclusive, request more context (logs, test output).

## related_files
- omega_os/skills/source_verification/skill.md
- omega_os/skills/capture_triage/skill.md
