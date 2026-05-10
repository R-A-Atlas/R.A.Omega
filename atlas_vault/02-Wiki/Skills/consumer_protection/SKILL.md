---
name: Consumer Protection Watch
description: Aggregates FTC scam alerts (RSS) and CPSC product recalls (JSON API) into a unified consumer alert feed with severity scoring
type: reference
agent: L5
division: Tax & Legal
---

# Skill: Consumer Protection Watch (L5)

## [D] Direction
Fetch FTC scam/fraud alerts from https://www.consumer.ftc.gov/blog/rss.xml (RSS/XML).
Fetch CPSC product recalls from https://www.cpsc.gov/recalls.json (JSON API).
Normalize into unified schema: title, category, date, severity, source, description.
Classify category: Scam | Recall | Data Breach | Price Gouging | Fraud.
Classify severity: HIGH | MEDIUM | LOW (based on keywords and affected count).
Save to data_cache/consumer_alerts_latest.json.

## [B] Blueprints
Pattern:   atlas_agents/legal/consumer_protection/consumer_protection_scraper.py
FTC RSS:   https://www.consumer.ftc.gov/blog/rss.xml
CPSC API:  https://www.cpsc.gov/recalls.json
Output:    data_cache/consumer_alerts_latest.json

Category rules:
  "Data Breach"   → keywords: data breach, hack, unauthorized access, stolen data
  "Price Gouging" → keywords: price gouging, price fixing, anticompetitive
  "Scam"          → keywords: scam, fraud, phishing, impersonat, spoofing
  "Recall"        → all CPSC entries
  "Fraud"         → FTC fallback category

Severity rules:
  HIGH   → identity theft / physical injury / death keywords OR units > 100,000
  MEDIUM → units 1,001–100,000
  LOW    → units <= 1,000 or informational

description: truncated to 300 chars for JSON compactness

## [S] Solutions
Run scraper:
  python -m atlas_agents.legal.consumer_protection.consumer_protection_scraper

Test FTC RSS:
  python -c "import requests; r=requests.get('https://www.consumer.ftc.gov/blog/rss.xml',headers={'User-Agent':'ATLAS/1.0'},timeout=15); print(r.status_code, r.text[:300])"

Test CPSC API:
  python -c "import requests; r=requests.get('https://www.cpsc.gov/recalls.json',headers={'User-Agent':'ATLAS/1.0'},timeout=15); print(r.status_code, type(r.json()))"

Run tests:
  python -m pytest tests/test_consumer_protection.py -v

Compile check:
  python -m py_compile atlas_agents/legal/consumer_protection/consumer_protection_scraper.py

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 on consumer_protection_scraper.py |
| 2 | record_count == len(alerts) | count matches list length |
| 3 | category in valid set | one of Scam/Recall/Data Breach/Price Gouging/Fraud |
| 4 | severity in valid set | one of HIGH/MEDIUM/LOW |
| 5 | source in {FTC, CPSC} | each alert has valid source |
