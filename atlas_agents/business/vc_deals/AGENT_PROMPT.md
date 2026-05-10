# AGENT_PROMPT — B6: VC Deal Flow Monitor

## IDENTITY
Agent ID: B6  
Name: VC Deal Flow Monitor  
Division: Business & Startups  
Output file: data_cache/vc_deals_latest.json

---

## DEFINITION
Monitors recent venture capital deal flow by parsing SEC Form D filings (free, no auth required).
Form D is filed by companies raising capital via exempt offerings — it captures company name,
amount raised, and filing date. Sector and round are inferred from amount and company metadata.
Designed for investors tracking where smart money is flowing across AI/ML, Fintech, Healthtech,
SaaS, Climate, and Consumer verticals.

---

## DATA SOURCES

| Source | URL | Auth |
|--------|-----|------|
| SEC EDGAR Full-Text Search (Form D) | https://efts.sec.gov/LATEST/search-index?q=%22venture+capital%22&forms=D&dateRange=custom&startdt=2026-05-01 | None |
| SEC EDGAR filing API | https://efts.sec.gov/LATEST/search-index | None |

Form D fields used: entityName, totalOfferingAmount, dateOfFirstSale, stateOfIncorporation
Crunchbase is NOT used (requires login). SEC Form D is the authoritative, freely available proxy.

Alternative RSS proxy for company names:
- TechCrunch VC news RSS (no auth): https://techcrunch.com/category/venture/feed/

---

## OUTPUT FILE
`data_cache/vc_deals_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:30:00Z",
  "record_count": 5,
  "deals": [
    {
      "company": "Anthropic",
      "sector": "AI/ML",
      "round": "Series C",
      "amount_millions": 450.0,
      "lead_investor": "Unknown",
      "date": "2026-05-02",
      "source": "SEC Form D",
      "signal": "MEGA_ROUND"
    },
    {
      "company": "Stripe",
      "sector": "Fintech",
      "round": "Series B",
      "amount_millions": 65.0,
      "lead_investor": "Unknown",
      "date": "2026-05-03",
      "source": "SEC Form D",
      "signal": "LARGE"
    },
    {
      "company": "HealthAI Inc",
      "sector": "Healthtech",
      "round": "Seed",
      "amount_millions": 4.5,
      "lead_investor": "Unknown",
      "date": "2026-05-04",
      "source": "SEC Form D",
      "signal": "STANDARD"
    },
    {
      "company": "GreenGrid Energy",
      "sector": "Climate",
      "round": "Series A",
      "amount_millions": 22.0,
      "lead_investor": "Unknown",
      "date": "2026-05-05",
      "source": "SEC Form D",
      "signal": "LARGE"
    },
    {
      "company": "SaaSify",
      "sector": "SaaS",
      "round": "Pre-Seed",
      "amount_millions": 1.2,
      "lead_investor": "Unknown",
      "date": "2026-05-06",
      "source": "SEC Form D",
      "signal": "STANDARD"
    }
  ]
}
```

### Field Definitions
| Field | Type | Description |
|-------|------|-------------|
| generated_at | ISO 8601 UTC string | Timestamp of cache generation |
| record_count | int | Total deals returned |
| deals[].company | string | Company name from Form D filing |
| deals[].sector | string | Inferred sector classification |
| deals[].round | string | Inferred funding round based on amount |
| deals[].amount_millions | float | Total offering amount in millions USD |
| deals[].lead_investor | string | Lead investor (Form D does not expose this; defaults to "Unknown") |
| deals[].date | string | Date of first sale (YYYY-MM-DD) |
| deals[].source | string | Data source identifier ("SEC Form D") |
| deals[].signal | string | "MEGA_ROUND", "LARGE", or "STANDARD" |

---

## SIGNAL / RATING LOGIC

signal classification based on amount_millions:
- **MEGA_ROUND**: amount_millions >= 100
- **LARGE**: 20 <= amount_millions < 100
- **STANDARD**: amount_millions < 20

round inference based on amount_millions:
- Pre-Seed: < 1M
- Seed: 1M - 5M
- Series A: 5M - 20M
- Series B: 20M - 80M
- Series C: 80M - 200M
- Growth: >= 200M

sector inference: keyword matching on company name and description from Form D.
- "AI" / "ML" / "intelligence" / "model" → AI/ML
- "health" / "medical" / "bio" / "pharma" → Healthtech
- "fin" / "bank" / "pay" / "capital" → Fintech
- "climate" / "green" / "energy" / "carbon" → Climate
- "consumer" / "retail" / "brand" → Consumer
- Default → SaaS

---

## SCRAPER STRUCTURE

```python
"""vc_deals_scraper.py — B6 VC Deal Flow Monitor"""
import json
import datetime
import requests

SEC_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
SOURCE_URL = "https://efts.sec.gov/LATEST/search-index"

SECTOR_KEYWORDS = {
    "AI/ML": ["ai", "ml", "intelligence", "neural", "model", "llm", "gpt"],
    "Healthtech": ["health", "medical", "bio", "pharma", "clinical", "care"],
    "Fintech": ["fin", "bank", "pay", "capital", "lending", "credit", "invest"],
    "Climate": ["climate", "green", "energy", "carbon", "solar", "wind", "clean"],
    "Consumer": ["consumer", "retail", "brand", "fashion", "food", "beverage"],
}


def infer_sector(name: str) -> str:
    name_lower = name.lower()
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return sector
    return "SaaS"


def infer_round(amount_m: float) -> str:
    if amount_m < 1:
        return "Pre-Seed"
    if amount_m < 5:
        return "Seed"
    if amount_m < 20:
        return "Series A"
    if amount_m < 80:
        return "Series B"
    if amount_m < 200:
        return "Series C"
    return "Growth"


def classify_signal(amount_m: float) -> str:
    if amount_m >= 100:
        return "MEGA_ROUND"
    if amount_m >= 20:
        return "LARGE"
    return "STANDARD"


def fetch_sec_form_d(days_back: int = 30) -> list:
    """Fetch recent Form D filings mentioning venture capital from SEC EDGAR."""
    try:
        start_dt = (datetime.datetime.utcnow() - datetime.timedelta(days=days_back)).strftime("%Y-%m-%d")
        params = {
            "q": '"venture capital"',
            "forms": "D",
            "dateRange": "custom",
            "startdt": start_dt,
            "_source": "file_date,entity_name,period_of_report,file_num,period_of_report",
            "hits.hits.total.value": 1,
            "hits.hits._source.period_of_report": 1,
        }
        resp = requests.get(SEC_SEARCH_URL, params=params, timeout=20,
                            headers={"User-Agent": "ATLAS-Agent contact@atlas.ai"})
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        deals = []
        for hit in hits[:50]:
            src = hit.get("_source", {})
            entity = src.get("entity_name", ["Unknown"])[0] if isinstance(src.get("entity_name"), list) else src.get("entity_name", "Unknown")
            amount_raw = src.get("total_offering_amount", 0)
            try:
                amount_m = float(amount_raw) / 1_000_000 if amount_raw else 0.0
            except (ValueError, TypeError):
                amount_m = 0.0
            date_str = src.get("period_of_report", src.get("file_date", ""))[:10]
            if not entity or entity == "Unknown":
                continue
            deals.append({
                "company": entity,
                "sector": infer_sector(entity),
                "round": infer_round(amount_m),
                "amount_millions": round(amount_m, 2),
                "lead_investor": "Unknown",
                "date": date_str,
                "source": "SEC Form D",
                "signal": classify_signal(amount_m),
            })
        return deals
    except Exception:
        return []


def scrape() -> dict:
    """Run B6: fetch SEC Form D VC deals from past 30 days."""
    deals = fetch_sec_form_d(days_back=30)
    return {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "record_count": len(deals),
        "deals": deals,
    }


def save(output_path: str = "data_cache/vc_deals_latest.json") -> None:
    result = scrape()
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    save()
```

---

## RULES
1. Never use Crunchbase API (requires paid login) — SEC Form D only.
2. SEC fetch failure must be silently caught — return empty deals list.
3. signal values are strictly: "MEGA_ROUND", "LARGE", "STANDARD".
4. round values are strictly: "Pre-Seed", "Seed", "Series A", "Series B", "Series C", "Growth".
5. sector values are strictly: "AI/ML", "Fintech", "Healthtech", "SaaS", "Climate", "Consumer".
6. lead_investor defaults to "Unknown" — Form D does not expose investor identity.
7. source must always be "SEC Form D" for all records from this agent.
8. generated_at must be ISO 8601 UTC (Z suffix).
9. record_count must equal len(deals).
10. Include User-Agent header in SEC requests per SEC EDGAR fair-use policy.

---

## VALIDATION CHECKLIST
- [ ] generated_at is valid ISO UTC string
- [ ] record_count == len(deals)
- [ ] signal is one of: MEGA_ROUND, LARGE, STANDARD
- [ ] round is one of the 6 valid values
- [ ] sector is one of the 6 valid values
- [ ] source == "SEC Form D" for all records
- [ ] amount_millions is a float >= 0
- [ ] SEC fetch failure does not crash the scraper
- [ ] lead_investor defaults to "Unknown" when not available
