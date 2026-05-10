---
name: VC Deal Flow Monitor
description: Monitors recent venture capital deal flow via SEC Form D filings (free, no auth); infers sector, round, and deal size signal (MEGA_ROUND/LARGE/STANDARD) for AI/ML, Fintech, Healthtech, SaaS, Climate, Consumer verticals
type: reference
agent: B6
division: Business & Startups
---

# Skill: VC Deal Flow Monitor (B6)

## [D] Direction
Query SEC EDGAR full-text search for recent Form D filings containing "venture capital".
Parse entity names and offering amounts. Infer sector via keyword matching, round via
amount thresholds, and signal (MEGA_ROUND/LARGE/STANDARD). Save to data_cache/vc_deals_latest.json.

Step-by-step:
1. Build SEC EDGAR query: GET https://efts.sec.gov/LATEST/search-index
   with params: q="venture capital", forms=D, dateRange=custom, startdt=30 days ago.
2. Parse hits: extract entity_name, total_offering_amount, period_of_report.
3. For each filing: compute amount_millions, infer sector (keyword match), infer round (amount bracket), classify signal.
4. Set lead_investor = "Unknown" (Form D does not expose this).
5. Set source = "SEC Form D" for all records.
6. Set generated_at (ISO UTC), record_count = len(deals).
7. Write to data_cache/vc_deals_latest.json.

Rules:
- Never use Crunchbase API (requires paid login).
- SEC fetch failure must NOT crash — return empty deals list.
- Always include User-Agent header: "ATLAS-Agent contact@atlas.ai" (SEC fair-use policy).
- signal values: "MEGA_ROUND" (>=100M), "LARGE" (>=20M), "STANDARD" (<20M).
- round values: Pre-Seed/Seed/Series A/Series B/Series C/Growth (amount-based).
- sector values: "AI/ML","Fintech","Healthtech","SaaS","Climate","Consumer".
- source must always be "SEC Form D".

## [B] Blueprints
Pattern:    atlas_agents/business/vc_deals/AGENT_PROMPT.md (full scraper stub)
Primary:    https://efts.sec.gov/LATEST/search-index
Docs:       https://efts.sec.gov/LATEST/search-index (SEC EDGAR EFTS)
Output:     data_cache/vc_deals_latest.json

Signal thresholds:
- MEGA_ROUND: amount_millions >= 100
- LARGE: 20 <= amount_millions < 100
- STANDARD: amount_millions < 20

Round inference:
- Pre-Seed: < 1M | Seed: 1-5M | Series A: 5-20M
- Series B: 20-80M | Series C: 80-200M | Growth: >= 200M

Sector keywords (first match wins):
- AI/ML: ["ai","ml","intelligence","neural","model","llm","gpt"]
- Healthtech: ["health","medical","bio","pharma","clinical","care"]
- Fintech: ["fin","bank","pay","capital","lending","credit","invest"]
- Climate: ["climate","green","energy","carbon","solar","wind","clean"]
- Consumer: ["consumer","retail","brand","fashion","food","beverage"]
- Default: SaaS

## [S] Solutions
Run scraper:
  python -m atlas_agents.business.vc_deals.vc_deals_scraper

Test SEC EDGAR query:
  python -c "import requests; r=requests.get('https://efts.sec.gov/LATEST/search-index',params={'q':'\"venture capital\"','forms':'D'},headers={'User-Agent':'ATLAS-Agent contact@atlas.ai'},timeout=15); print(r.status_code, len(r.json().get('hits',{}).get('hits',[])))"

Run tests:
  python -m pytest tests/test_vc_deals.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | signal values valid | values in {"MEGA_ROUND","LARGE","STANDARD"} |
| 2 | round values valid | values in {"Pre-Seed","Seed","Series A","Series B","Series C","Growth"} |
| 3 | sector values valid | values in {"AI/ML","Fintech","Healthtech","SaaS","Climate","Consumer"} |
| 4 | SEC failure graceful | scraper returns empty deals list (not exception) when API unreachable |
| 5 | generated_at is ISO UTC | datetime.fromisoformat(generated_at.replace("Z","+00:00")) succeeds |
