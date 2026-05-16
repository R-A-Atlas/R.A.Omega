# Skill: smoke_tester

## Purpose
Hits every critical HTTP endpoint after a server start or code change and verifies
status codes and key content substrings. Catches broken routes before a full test
suite run or before marking a task done.

## Trigger
- After any `uvicorn` restart
- After changes to api_server.py or any HTML file
- Before marking a task done that touches routing

## Steps
1. Start the server: `uvicorn api_server:app --host 127.0.0.1 --port 8000`
2. Run: `python omega_os/skills/smoke_tester/tools/smoke_test.py`
3. All rows must show [OK]. Any [!!] row is a blocker.
4. For CI or scripting: use `--json` and check exit code (0 = all pass, 1 = failures)

## Endpoints covered

| Endpoint | Checks |
|---|---|
| / | 200 |
| /auth | 200 |
| /command-center | 200 + "R.A. Omega" in body |
| /app | 200 or 302 (auth redirect OK) |
| /v2 | 200 |
| /design_system.css | 200 + "--color-accent" in body |
| /omega-os/brain-network | 200 + "omega" in body |
| /health | 200 |
| /regime | 200 |
| /alerts | 200 |
| /watchlist | 200 |
| /sessions | 200 |
| /omega-os/dashboard | 200 |
| /omega-os/skills | 200 |
| /sandbox/agent-health | 200 |

## Guardrails
- Requires a running server — does not start one itself
- Only uses stdlib (urllib.request) — no external dependencies to install
- Does not authenticate — tests unauthenticated baseline only
- Do not add endpoints that require request bodies (POST-only routes won't smoke cleanly)

## Output
```
  /command-center                     200    42ms  [OK]
  /regime                             200    18ms  [OK]
  /broken-route                       404    12ms  [!!]  <- expected 200
...
RESULT: PASS — 15/15 endpoints OK
```
