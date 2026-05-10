# G2 — CRM Sync Agent | Division: Business Growth & Ops

## IDENTITY
You read leads from data_cache/leads_latest.json (G1 output) and POST each
lead to a CRM webhook (n8n/ManyChat) for pipeline entry. No scraping.
No LLM calls. Read + POST + report.

## DEFINITION
  CRM sync: reading G1 leads and pushing to configured webhook endpoint
  CRM_WEBHOOK_URL: env var pointing to n8n, ManyChat, or Zapier webhook
  Signal:
    SUCCESS: leads_failed == 0
    PARTIAL: 0 < leads_failed < leads_synced
    FAILED:  all leads failed

## DATA SOURCES
  Input:  data_cache/leads_latest.json (G1 — Lead Generation Scraper output)
  Output: POST to CRM_WEBHOOK_URL (from .env)
  Note: if CRM_WEBHOOK_URL not set, return status="SKIPPED"

## OUTPUT FILE
  data_cache/crm_sync_latest.json  (sync report, not leads)

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "webhook_url": "https://n8n.example.com/webhook/abc123",
  "leads_total": 20,
  "leads_synced": 18,
  "leads_failed": 2,
  "status": "PARTIAL",
  "errors": ["Lead #4: timeout", "Lead #17: 400 Bad Request"]
}
```

## SIGNAL LOGIC
  leads_failed == 0                              → status = "SUCCESS"
  0 < leads_failed < leads_total                 → status = "PARTIAL"
  leads_failed == leads_total AND leads_total > 0 → status = "FAILED"
  CRM_WEBHOOK_URL not set                        → status = "SKIPPED"

## SCRAPER STRUCTURE
```python
import requests
import json
import os
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "crm_sync_latest.json"
LEADS_FILE = DATA_CACHE_DIR / "leads_latest.json"

def load_leads() -> list[dict]: ...           # read leads_latest.json
def post_lead(lead: dict, url: str) -> bool: ...  # POST to webhook
def sync(webhook_url: str, leads: list) -> dict: ...
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — read + POST only
- If CRM_WEBHOOK_URL missing: log warning, return status="SKIPPED"
- If leads_latest.json missing: log warning, return status="FAILED"
- Use 5s timeout per POST request
- generated_at must be ISO UTC string
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
  [ ] python -m py_compile crm_sync_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, status, leads_synced, leads_failed
  [ ] status in {"SUCCESS", "PARTIAL", "FAILED", "SKIPPED"}
  [ ] python -m pytest tests/test_crm_sync.py -v passes
