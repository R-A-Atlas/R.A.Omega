# L5 — Consumer Protection Watch

## IDENTITY
Agent ID: L5
Name: Consumer Protection Watch
Division: Tax & Legal
Output: data_cache/consumer_alerts_latest.json

## DEFINITION
Aggregates consumer protection alerts from two public sources: FTC scam/fraud blog RSS feed
and CPSC product recall JSON API. Normalizes into a unified alert schema with severity scoring.
Used by OmegaAgent for consumer financial protection context.

## DATA SOURCES
Primary:   https://www.consumer.ftc.gov/blog/rss.xml  (FTC scam alerts RSS)
Secondary: https://www.cpsc.gov/recalls.json           (CPSC product recalls)
Format:    RSS/XML (FTC), JSON (CPSC)

## OUTPUT FILE
data_cache/consumer_alerts_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "record_count": 5,
  "alerts": [
    {
      "title": "New Phone Scam Targeting Seniors",
      "category": "Scam",
      "date": "2026-05-08",
      "severity": "HIGH",
      "source": "FTC",
      "description": "Callers impersonate Social Security Administration to steal personal info."
    },
    {
      "title": "Brand X Stroller Recalled Due to Fall Hazard",
      "category": "Recall",
      "date": "2026-05-07",
      "severity": "MEDIUM",
      "source": "CPSC",
      "description": "Approximately 45,000 units recalled. Harness can release unexpectedly."
    }
  ]
}
```

## SIGNAL LOGIC
category classification:
- "Scam"          → FTC alerts mentioning scam, fraud, impersonation, phishing
- "Recall"        → All CPSC recall entries
- "Data Breach"   → Alerts mentioning data breach, hack, unauthorized access
- "Price Gouging" → Alerts mentioning price gouging, price fixing
- "Fraud"         → General FTC fraud alerts not matching above categories

severity scoring:
- "HIGH"   → Involves identity theft, financial loss > $10k, physical injury risk, or large-scale (> 100k affected)
- "MEDIUM" → Product defect or scam with moderate impact (1k-100k affected)
- "LOW"    → Informational alerts, minor recalls (< 1k units)

source: "FTC" or "CPSC"
date: "YYYY-MM-DD" string from RSS pubDate or CPSC recall date

## SCRAPER STRUCTURE
```python
# consumer_protection_scraper.py

import json
import datetime
import requests
import xml.etree.ElementTree as ET

FTC_RSS_URL  = "https://www.consumer.ftc.gov/blog/rss.xml"
CPSC_API_URL = "https://www.cpsc.gov/recalls.json"

HEADERS = {"User-Agent": "ATLAS/1.0"}

SCAM_KEYWORDS    = ["scam", "fraud", "phishing", "impersonat", "spoofing"]
BREACH_KEYWORDS  = ["data breach", "hack", "unauthorized access", "stolen data"]
GOUGING_KEYWORDS = ["price gouging", "price fixing", "anticompetitive"]


def classify_category(text: str) -> str:
    text_lower = text.lower()
    if any(k in text_lower for k in BREACH_KEYWORDS):
        return "Data Breach"
    if any(k in text_lower for k in GOUGING_KEYWORDS):
        return "Price Gouging"
    if any(k in text_lower for k in SCAM_KEYWORDS):
        return "Scam"
    return "Fraud"


def classify_severity(text: str, affected_count: int = 0) -> str:
    text_lower = text.lower()
    if any(k in text_lower for k in ["identity theft", "physical injur", "death"]):
        return "HIGH"
    if affected_count > 100000:
        return "HIGH"
    if affected_count > 1000:
        return "MEDIUM"
    return "LOW"


def fetch_ftc_alerts() -> list:
    try:
        resp = requests.get(FTC_RSS_URL, timeout=15, headers=HEADERS)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        alerts = []
        for item in root.findall(".//item")[:20]:
            title = item.findtext("title", "")
            desc  = item.findtext("description", "")
            pub   = item.findtext("pubDate", "")
            date_str = pub[:10] if pub else datetime.date.today().isoformat()
            cat   = classify_category(title + " " + desc)
            sev   = classify_severity(title + " " + desc)
            alerts.append({
                "title":       title,
                "category":    cat,
                "date":        date_str,
                "severity":    sev,
                "source":      "FTC",
                "description": desc[:300],
            })
        return alerts
    except Exception as exc:
        print(f"[L5] FTC RSS fetch failed: {exc}")
        return []


def fetch_cpsc_recalls() -> list:
    try:
        resp = requests.get(CPSC_API_URL, timeout=15, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        recalls = []
        for item in (data.get("recalls") or data)[:20]:
            title    = item.get("Name", item.get("title", ""))
            desc     = item.get("Description", item.get("description", ""))
            date_str = str(item.get("RecallDate", item.get("date", "")))[:10]
            units    = int(item.get("Units", 0))
            sev      = "HIGH" if units > 100000 else ("MEDIUM" if units > 1000 else "LOW")
            recalls.append({
                "title":       title,
                "category":    "Recall",
                "date":        date_str,
                "severity":    sev,
                "source":      "CPSC",
                "description": desc[:300],
            })
        return recalls
    except Exception as exc:
        print(f"[L5] CPSC API fetch failed: {exc}")
        return []


def scrape() -> dict:
    alerts = fetch_ftc_alerts() + fetch_cpsc_recalls()
    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "record_count": len(alerts),
        "alerts":       alerts,
    }
```

## RULES
1. category must be one of: "Scam", "Recall", "Data Breach", "Price Gouging", "Fraud".
2. severity must be one of: "HIGH", "MEDIUM", "LOW".
3. source must be "FTC" or "CPSC".
4. date is "YYYY-MM-DD" string.
5. description is truncated to 300 chars to keep JSON compact.
6. record_count must equal len(alerts).
7. alerts may be empty list if both sources fail — never omit the key.
8. generated_at is UTC ISO-8601 with trailing "Z".

## VALIDATION CHECKLIST
- [ ] generated_at present and UTC ISO-8601
- [ ] record_count == len(alerts)
- [ ] alerts is a list (may be empty)
- [ ] Each alert has: title, category, date, severity, source, description
- [ ] category in {"Scam", "Recall", "Data Breach", "Price Gouging", "Fraud"}
- [ ] severity in {"HIGH", "MEDIUM", "LOW"}
- [ ] source in {"FTC", "CPSC"}
- [ ] date matches "YYYY-MM-DD" format
- [ ] data_cache/consumer_alerts_latest.json is valid JSON
