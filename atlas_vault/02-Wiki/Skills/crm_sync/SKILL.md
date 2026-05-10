---
name: CRM Sync Agent
description: Reads G1 leads from data_cache/leads_latest.json and POSTs each to CRM_WEBHOOK_URL; reports SUCCESS/PARTIAL/FAILED/SKIPPED
type: reference
agent: G2
division: Business Growth & Ops
---

# Skill: CRM Sync Agent (G2)

## [D] Direction
Load leads_latest.json. POST each lead to CRM_WEBHOOK_URL (n8n/Zapier).
Report: leads_synced, leads_failed, status (SUCCESS/PARTIAL/FAILED/SKIPPED).
Save report to data_cache/crm_sync_latest.json.

## [B] Blueprints
Input:   data_cache/leads_latest.json (G1 output)
Webhook: CRM_WEBHOOK_URL env var
Utils:   atlas_core/utils/agent_utils.py (write_cache_json_pair)

## [S] Solutions
Run sync:
  python -m atlas_agents.growth.crm_sync.crm_sync_scraper

Run tests:
  python -m pytest tests/test_crm_sync.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | status in valid set | SUCCESS/PARTIAL/FAILED/SKIPPED |
| 3 | graceful when webhook absent | returns SKIPPED, no crash |
| 4 | graceful when leads file absent | returns FAILED, no crash |
| 5 | leads_synced + leads_failed == leads_total | arithmetic correct |
