# M5 — Geopolitical Tariff Tracker Agent

## IDENTITY
Agent ID: M5  
Name: Geopolitical Tariff Tracker Agent  
Division: Macro Risk & Geopolitics  
Codename: TARIFFS  
Output File: data_cache/tariffs_latest.json  

---

## DEFINITION
Tracks active U.S. trade tariffs from USTR enforcement actions, WTO dispute tracker, and hardcoded authoritative data for major active tariffs (2026). Monitors tariff status changes, new escalations, and trade policy shifts to feed ATLAS geopolitical risk scoring and sector-level supply chain exposure analysis.

---

## DATA SOURCES

| Source | URL | Auth | Notes |
|--------|-----|------|-------|
| USTR Section 301 | https://ustr.gov/issue-areas/enforcement/section-301-investigations | None | Scrape public enforcement pages |
| USTR Federal Register | https://www.federalregister.gov/api/v1/documents?conditions[agencies][]=ustr | None | JSON API for USTR notices |
| WTO Dispute Tracker | https://www.wto.org/english/tratop_e/dispu_e/dispu_status_e.htm | None | Scrape dispute status table |
| Federal Register API | https://www.federalregister.gov/api/v1/ | None | Free JSON API for FR documents |

Primary Source URL: https://ustr.gov/issue-areas/enforcement/section-301-investigations

### Hardcoded Active Tariffs (2026 baseline — override if live data disagrees)
| Category | Rate | Authority | Partner | Status |
|----------|------|-----------|---------|--------|
| Electronics (China) | 25% | Section 301 | China | ACTIVE |
| Consumer Goods (China) | 7.5% | Section 301 | China | ACTIVE |
| Steel | 25% | Section 232 | Global | ACTIVE |
| Aluminum | 10% | Section 232 | Global | ACTIVE |

---

## OUTPUT FILE
`data_cache/tariffs_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "record_count": 4,
  "active_count": 3,
  "escalating_count": 1,
  "active_tariffs": [
    {
      "product_category": "Electronics",
      "rate_pct": 25.0,
      "effective_date": "2018-07-06",
      "trading_partner": "China",
      "authority": "Section 301",
      "status": "ACTIVE"
    },
    {
      "product_category": "Consumer Goods",
      "rate_pct": 7.5,
      "effective_date": "2020-02-14",
      "trading_partner": "China",
      "authority": "Section 301",
      "status": "ACTIVE"
    },
    {
      "product_category": "Steel",
      "rate_pct": 25.0,
      "effective_date": "2018-03-23",
      "trading_partner": "Global",
      "authority": "Section 232",
      "status": "ACTIVE"
    },
    {
      "product_category": "Aluminum",
      "rate_pct": 10.0,
      "effective_date": "2018-03-23",
      "trading_partner": "Global",
      "authority": "Section 232",
      "status": "ESCALATING"
    }
  ]
}
```

### Field Definitions
- `generated_at`: ISO-8601 UTC timestamp of data fetch
- `record_count`: total number of tariff entries
- `active_count`: count of entries with status == "ACTIVE"
- `escalating_count`: count of entries with status == "ESCALATING"
- `active_tariffs[].product_category`: product/sector description (string)
- `active_tariffs[].rate_pct`: tariff rate as percentage (float)
- `active_tariffs[].effective_date`: ISO-8601 date tariff took effect
- `active_tariffs[].trading_partner`: country or "Global" (string)
- `active_tariffs[].authority`: Section 301, Section 232, Section 201, or IEEPA
- `active_tariffs[].status`: ACTIVE, SUSPENDED, UNDER_REVIEW, or ESCALATING

### Status Definitions
- ACTIVE: Currently in force, no pending changes
- SUSPENDED: Temporarily halted (bilateral negotiation or court order)
- UNDER_REVIEW: USTR or Commerce Dept formal review initiated
- ESCALATING: Rate increase announced or additional products added

### Authority Definitions
- Section 301: Unfair trade practices (IP theft, forced tech transfer)
- Section 232: National security (steel, aluminum)
- Section 201: Safeguard tariffs (serious injury to domestic industry)
- IEEPA: International Emergency Economic Powers Act (emergency declarations)

---

## SIGNAL LOGIC

```
geopolitical_risk_score:
    base_score = sum(rate_pct for all ACTIVE tariffs) / count(ACTIVE tariffs)
    escalation_multiplier = 1.0 + (0.25 * escalating_count)
    risk_score = base_score * escalation_multiplier

sector_exposure:
    Electronics (Section 301, China) → AAPL, NVDA, QCOM, TSM supply chains at risk
    Steel/Aluminum (Section 232)      → automotive, construction, defense cost pressure
    Consumer Goods (Section 301)      → retail margins compressed

macro_signal:
    escalating_count >= 2  → TRADE_WAR_RISK → reduce EM exposure, add USD
    active_count >= 5       → HIGH_FRICTION → monitor supply chain agents M2
    all SUSPENDED           → RELIEF → positive for global trade equities
```

---

## SCRAPER STRUCTURE

```python
# tariffs_scraper.py — stub

import json
import datetime
import requests
from bs4 import BeautifulSoup

USTR_URL = "https://ustr.gov/issue-areas/enforcement/section-301-investigations"
WTO_URL = "https://www.wto.org/english/tratop_e/dispu_e/dispu_status_e.htm"
FR_API_URL = "https://www.federalregister.gov/api/v1/documents"
OUTPUT_PATH = "data_cache/tariffs_latest.json"

VALID_AUTHORITIES = {"Section 301", "Section 232", "Section 201", "IEEPA"}
VALID_STATUSES = {"ACTIVE", "SUSPENDED", "UNDER_REVIEW", "ESCALATING"}

# Authoritative 2026 baseline — always included even if live scrape fails
HARDCODED_TARIFFS = [
    {
        "product_category": "Electronics",
        "rate_pct": 25.0,
        "effective_date": "2018-07-06",
        "trading_partner": "China",
        "authority": "Section 301",
        "status": "ACTIVE"
    },
    {
        "product_category": "Consumer Goods",
        "rate_pct": 7.5,
        "effective_date": "2020-02-14",
        "trading_partner": "China",
        "authority": "Section 301",
        "status": "ACTIVE"
    },
    {
        "product_category": "Steel",
        "rate_pct": 25.0,
        "effective_date": "2018-03-23",
        "trading_partner": "Global",
        "authority": "Section 232",
        "status": "ACTIVE"
    },
    {
        "product_category": "Aluminum",
        "rate_pct": 10.0,
        "effective_date": "2018-03-23",
        "trading_partner": "Global",
        "authority": "Section 232",
        "status": "ACTIVE"
    }
]


def fetch_ustr_updates() -> list:
    """Scrape USTR enforcement page for status changes."""
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(USTR_URL, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    # TODO: parse enforcement action paragraphs for new tariff announcements
    raise NotImplementedError("Implement USTR page parser")


def fetch_federal_register_tariffs() -> list:
    """Fetch recent USTR tariff notices from Federal Register API."""
    params = {
        "conditions[agencies][]": "office-of-the-united-states-trade-representative",
        "conditions[term]": "tariff",
        "per_page": 20,
        "order": "newest"
    }
    resp = requests.get(FR_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("results", [])


def merge_with_baseline(live_tariffs: list) -> list:
    """Merge live data with hardcoded baseline. Live data overrides baseline."""
    merged = {t["product_category"]: t for t in HARDCODED_TARIFFS}
    for t in live_tariffs:
        cat = t.get("product_category", "")
        if cat:
            merged[cat] = t
    return list(merged.values())


def build_output(active_tariffs: list) -> dict:
    """Assemble output envelope."""
    active_count = sum(1 for t in active_tariffs if t["status"] == "ACTIVE")
    escalating_count = sum(1 for t in active_tariffs if t["status"] == "ESCALATING")
    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "record_count": len(active_tariffs),
        "active_count": active_count,
        "escalating_count": escalating_count,
        "active_tariffs": active_tariffs
    }


def scrape() -> dict:
    """Main entry point. Always returns at minimum the hardcoded baseline."""
    try:
        live_tariffs = fetch_federal_register_tariffs()
        parsed_live = []  # TODO: parse FR notices into tariff dicts
        active_tariffs = merge_with_baseline(parsed_live)
    except Exception:
        active_tariffs = HARDCODED_TARIFFS.copy()

    result = build_output(active_tariffs)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    data = scrape()
    print(json.dumps(data, indent=2))
```

---

## RULES
1. Hardcoded baseline MUST always be present in output — it represents confirmed active tariffs
2. Live scrape data overrides baseline for matching product_category keys
3. Never remove a tariff from output without confirmation from USTR or Federal Register
4. All `authority` values must be in: Section 301, Section 232, Section 201, IEEPA
5. All `status` values must be in: ACTIVE, SUSPENDED, UNDER_REVIEW, ESCALATING
6. Cache for 4 hours — tariff changes are significant policy events, not tick-by-tick
7. `active_count` + `escalating_count` must be <= `record_count`

---

## VALIDATION CHECKLIST
- [ ] `generated_at` is valid ISO-8601 UTC
- [ ] `record_count` equals `len(active_tariffs)`
- [ ] All `authority` values in: Section 301, Section 232, Section 201, IEEPA
- [ ] All `status` values in: ACTIVE, SUSPENDED, UNDER_REVIEW, ESCALATING
- [ ] Hardcoded baseline tariffs present (Electronics, Consumer Goods, Steel, Aluminum)
- [ ] `active_count` equals count of status == "ACTIVE" entries
- [ ] `escalating_count` equals count of status == "ESCALATING" entries
- [ ] Output file written to `data_cache/tariffs_latest.json`
