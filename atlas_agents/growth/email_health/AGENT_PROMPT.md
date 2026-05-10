# G7 — Email Deliverability Monitor | Division: Business Growth & Ops

## IDENTITY
You check email infrastructure health for a domain — SPF, DKIM, DMARC, MX records,
and blacklist status. Computes a 0–100 deliverability score and letter grade.
No LLM calls. DNS lookup + scoring.

## DEFINITION
  SPF:  Sender Policy Framework record (TXT record in DNS)
  DKIM: DomainKeys Identified Mail (TXT record at _domainkey subdomain)
  DMARC: Domain-based Message Authentication (TXT at _dmarc subdomain)
  MX:   Mail exchanger record
  deliverability_score = 25*(SPF PASS) + 25*(DKIM PASS) + 25*(DMARC PASS) + 25*(MX PASS) - 10*(blacklist_count)

## DATA SOURCES
  dnspython library (pip install dnspython):
    import dns.resolver
    dns.resolver.resolve(domain, "TXT")   # SPF, DMARC
    dns.resolver.resolve(domain, "MX")    # MX
  MXToolbox API (public, no auth for basic):
    https://mxtoolbox.com/api/v1/lookup/blacklist/{domain}
  Note: MXTOOLBOX_API_KEY in .env optional — falls back to DNS-only check

## OUTPUT FILE
  data_cache/email_health_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "domain": "example.com",
  "spf_status": "PASS",
  "dkim_status": "MISSING",
  "dmarc_status": "PASS",
  "mx_status": "PASS",
  "blacklist_hits": 0,
  "blacklist_count": 0,
  "deliverability_score": 75,
  "grade": "B"
}
```

## SCORING LOGIC
  deliverability_score = (
      25 if spf_status == "PASS" else 0
    + 25 if dkim_status == "PASS" else 0
    + 25 if dmarc_status == "PASS" else 0
    + 25 if mx_status == "PASS" else 0
    - 10 * blacklist_count
  )
  Clamp to [0, 100]
  grade: A (>=90), B (>=75), C (>=60), F (<60)

## SCRAPER STRUCTURE
```python
import dns.resolver
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "email_health_latest.json"

def check_spf(domain: str) -> str: ...     # returns PASS/FAIL/MISSING
def check_dmarc(domain: str) -> str: ...   # returns PASS/FAIL/MISSING
def check_mx(domain: str) -> str: ...      # returns PASS/FAIL/MISSING
def check_dkim(domain: str, selector: str = "default") -> str: ...
def check_blacklists(domain: str) -> int: ...  # count of blacklist hits
def compute_score(statuses: dict, blacklist_count: int) -> tuple[int, str]: ...
def scrape(domain: str = "example.com") -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — DNS lookup + scoring only
- deliverability_score clamped to [0, 100]
- grade: "A" (>=90), "B" (>=75), "C" (>=60), "F" (<60)
- status values: exactly "PASS", "FAIL", or "MISSING"
- generated_at must be ISO UTC string
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
  [ ] python -m py_compile email_health_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, domain, deliverability_score, grade
  [ ] 0 <= deliverability_score <= 100
  [ ] grade in {"A", "B", "C", "F"}
  [ ] python -m pytest tests/test_email_health.py -v passes
