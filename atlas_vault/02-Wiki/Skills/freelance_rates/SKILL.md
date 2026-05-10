---
name: Freelance Rate Indexer
description: Indexes hourly freelance rates for 10 key roles using BLS OES API data + hardcoded 2025 Upwork annual report benchmarks; tracks demand trend and YoY rate change per role
type: reference
agent: B4
division: Business & Startups
---

# Skill: Freelance Rate Indexer (B4)

## [D] Direction
Combine BLS Occupational Employment Statistics API wage data with hardcoded 2025 Upwork
rate ranges to produce a comprehensive freelance rate index for 10 roles. BLS data refines
the hourly bounds when available; Upwork ranges serve as authoritative fallback.
Save result to data_cache/freelance_rates_latest.json.

Step-by-step:
1. Load ROLES_BASELINE list (10 roles with bls_series, hardcoded Upwork bounds).
2. For each role, POST to BLS API: https://api.bls.gov/publicAPI/v2/timeseries/data/
3. If BLS returns valid hourly wage, use it to anchor avg_hourly bounds.
4. If BLS fails, use hardcoded Upwork ranges unchanged.
5. Strip bls_series from output (internal metadata only).
6. Set generated_at (ISO UTC), record_count = 10.
7. Write to data_cache/freelance_rates_latest.json.

Rules:
- BLS API failure must NOT crash the scraper — use hardcoded fallback.
- demand_trend values: "HIGH_DEMAND", "MODERATE", "DECLINING" only.
- avg_hourly_low must always be < avg_hourly_high.
- yoy_rate_change_pct may be negative (rates declining).
- All 10 roles must always appear in output.
- bls_series must NOT appear in output JSON.

## [B] Blueprints
Pattern:    atlas_agents/business/freelance_rates/AGENT_PROMPT.md (full scraper stub)
Primary:    https://api.bls.gov/publicAPI/v2/timeseries/data/ (BLS OES API)
Secondary:  https://www.upwork.com/research/freelance-forward (hardcoded)
Landing:    https://www.bls.gov/oes/
Output:     data_cache/freelance_rates_latest.json

BLS OES series IDs:
- Software Engineer: OES151252
- Data Scientist: OES152051
- UI/UX Designer: OES271024
- Copywriter: OES273043
- Video Editor: OES274014
- SEO Specialist: OES131161
- Virtual Assistant: OES436014
- Accountant: OES132011
- Financial Analyst: OES132051
- DevOps Engineer: OES151244

2025 Upwork rate ranges (hardcoded baseline):
- Software Engineer: $75-175/hr, HIGH_DEMAND, +8.5% YoY
- Data Scientist: $85-200/hr, HIGH_DEMAND, +12.0% YoY
- DevOps Engineer: $80-185/hr, HIGH_DEMAND, +11.0% YoY

## [S] Solutions
Run scraper:
  python -m atlas_agents.business.freelance_rates.freelance_rates_scraper

Test BLS API:
  python -c "import requests; r=requests.post('https://api.bls.gov/publicAPI/v2/timeseries/data/',json={'seriesid':['OES151252'],'startyear':'2024','endyear':'2024'},timeout=10); print(r.status_code, r.json().get('Results',{}).get('series',[{}])[0].get('data',[{}])[0])"

Run tests:
  python -m pytest tests/test_freelance_rates.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | All 10 roles present | len(roles) == 10 |
| 2 | avg_hourly_low < avg_hourly_high | all roles satisfy constraint |
| 3 | demand_trend valid | values in {"HIGH_DEMAND","MODERATE","DECLINING"} |
| 4 | BLS failure graceful | scraper completes with hardcoded data when API unreachable |
| 5 | generated_at is ISO UTC | datetime.fromisoformat(generated_at.replace("Z","+00:00")) succeeds |
