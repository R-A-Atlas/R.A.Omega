---
name: Email Deliverability Monitor
description: Checks SPF/DKIM/DMARC/MX via DNS + blacklist hits; scores 0-100 and grades A/B/C/F
type: reference
agent: G7
division: Business Growth & Ops
---

# Skill: Email Deliverability Monitor (G7)

## [D] Direction
Resolve SPF (TXT), DMARC (_dmarc TXT), MX records via dnspython.
Check blacklists via MXToolbox API (optional).
Score = 25*SPF + 25*DKIM + 25*DMARC + 25*MX - 10*blacklist_count. Clamp [0,100].
Grade: A>=90, B>=75, C>=60, F<60. Save to data_cache/email_health_latest.json.

## [B] Blueprints
Library: dnspython (pip install dnspython)
Utils:   atlas_core/utils/agent_utils.py

## [S] Solutions
Run scraper:
  python -m atlas_agents.growth.email_health.email_health_scraper example.com

Run tests:
  python -m pytest tests/test_email_health.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | 0 <= deliverability_score <= 100 | clamped range |
| 3 | grade in A/B/C/F | valid grades only |
| 4 | all statuses in PASS/FAIL/MISSING | no other values |
| 5 | blacklist_count >= 0 | non-negative |
