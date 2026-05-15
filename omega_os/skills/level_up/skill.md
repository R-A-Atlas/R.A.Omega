# Skill: level_up

## name
level_up

## description
Analyze the current state of the system and user workflows to identify the highest-leverage
automation opportunities, recommend the next skill to build, and suggest the next connection
to add.

## when_to_use
- Weekly — every Friday as a retrospective
- When the user asks "what should I automate next?" or "what is the next skill to build?"
- After completing a sprint — what was manual and painful?
- When the Four C audit score stalls or drops

## inputs_required
- Optional: description of what the user did manually this week
- Optional: list of queries run in the past week (from GET /history/reports)
- Optional: current Four C audit scores

## steps
1. Run the Five Questions analysis (via omega_level_up.analyze()):
   a. What did the user do repeatedly this week?
   b. What felt manual, boring, or copy-paste?
   c. What could a smart intern do with clear instructions?
   d. What would break if 500 new users came tomorrow?
   e. What would create the most leverage if automated?
2. Score each opportunity: priority (1–10) + estimated leverage (low / medium / high / 10x)
3. Recommend the top automation opportunity
4. Recommend the next skill to build (from omega_os/skills/ gaps)
5. Recommend the next connection to add (from omega_os/connections/ planned list)
6. Output a structured level-up report

## outputs
- Five Questions analysis results
- Ranked automation opportunities with priority scores
- Recommended next skill to build
- Recommended next connection to add
- Estimated leverage score for top recommendation

## safety_rules
- Do not recommend automating anything that involves sending money or trades without human confirmation
- Do not recommend deleting or modifying core files (deep_research.py, gemini_limiter.py)
- Automation recommendations must have a safety_rules section — never propose unsafe automations

## related_files
- omega_level_up.py — Five Questions engine
- omega_audit.py — current Four C scores
- omega_os/skills/README.md — skill gap list
- omega_os/connections/connections.md — connection gap list

## quality_checks
- [ ] All five questions are answered
- [ ] At least 3 automation opportunities identified
- [ ] Priority scores are 1–10 (no ties for top spot)
- [ ] Recommended skill exists in planned skills list or is a new proposal
- [ ] Recommended connection exists in planned connections list or is a new proposal
- [ ] No unsafe automations recommended (trading, deletion, irreversible actions)
