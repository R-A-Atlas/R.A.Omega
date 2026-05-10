# L3 — Bankruptcy Parser

## IDENTITY
Agent ID: L3
Name: Bankruptcy Parser
Division: Tax & Legal
Output: data_cache/bankruptcy_latest.json

## DEFINITION
Scrapes US Courts public bankruptcy filing statistics to track chapter-level filings
(Ch.7, Ch.11, Ch.13), compute year-over-year change, classify trend, and surface
top distressed sectors. Used by OmegaAgent for macro credit cycle analysis.

## DATA SOURCES
Primary:   https://www.uscourts.gov/statistics-reports/caseload-statistics-data-tables
Stats:     https://www.uscourts.gov/statistics/table/f/bankruptcy-filings/2024/12/31
Fallback:  Hardcoded 2024 annual totals (Ch.7: 387,721 | Ch.11: 6,067 | Ch.13: 132,282)
Format:    HTML tables (scraped), fallback to hardcoded data

## OUTPUT FILE
data_cache/bankruptcy_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "period": "2024-12",
  "ch7_filings": 387721,
  "ch11_filings": 6067,
  "ch13_filings": 132282,
  "total_filings": 526070,
  "yoy_change_pct": 12.5,
  "trend_signal": "RISING",
  "top_sectors": ["Retail", "Healthcare", "Real Estate"]
}
```

## SIGNAL LOGIC
Compute yoy_change_pct = ((current_total - prior_year_total) / prior_year_total) * 100

trend_signal classification:
- "SURGING"  → yoy_change_pct >= 20.0
- "RISING"   → yoy_change_pct >= 5.0
- "STABLE"   → -5.0 <= yoy_change_pct < 5.0
- "DECLINING"→ yoy_change_pct <= -5.0

top_sectors: hardcoded list of historically distressed sectors for context.
If live data is unavailable, use period = "2024-12" and hardcoded totals.
yoy_change_pct is rounded to 2 decimal places.

## SCRAPER STRUCTURE
```python
# bankruptcy_scraper.py

import json
import datetime
import requests
from bs4 import BeautifulSoup

US_COURTS_URL = "https://www.uscourts.gov/statistics-reports/caseload-statistics-data-tables"
STATS_URL     = "https://www.uscourts.gov/statistics/table/f/bankruptcy-filings/2024/12/31"

HARDCODED = {
    "period": "2024-12",
    "ch7_filings":   387721,
    "ch11_filings":    6067,
    "ch13_filings":  132282,
    "prior_year_total": 467737,
}
DEFAULT_TOP_SECTORS = ["Retail", "Healthcare", "Real Estate"]


def classify_trend(yoy: float) -> str:
    if yoy >= 20.0:
        return "SURGING"
    elif yoy >= 5.0:
        return "RISING"
    elif yoy <= -5.0:
        return "DECLINING"
    return "STABLE"


def scrape() -> dict:
    """Return bankruptcy filing stats with trend signal."""
    try:
        resp = requests.get(STATS_URL, timeout=15, headers={"User-Agent": "ATLAS/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # ... parse ch7_filings, ch11_filings, ch13_filings from table
        # Fall through to fallback on any parse failure
    except Exception as exc:
        print(f"[L3] US Courts page unavailable ({exc}), using hardcoded fallback")

    ch7  = HARDCODED["ch7_filings"]
    ch11 = HARDCODED["ch11_filings"]
    ch13 = HARDCODED["ch13_filings"]
    total = ch7 + ch11 + ch13
    prior = HARDCODED["prior_year_total"]
    yoy = round(((total - prior) / prior) * 100, 2) if prior else 0.0

    return {
        "generated_at":   datetime.datetime.utcnow().isoformat() + "Z",
        "period":         HARDCODED["period"],
        "ch7_filings":    ch7,
        "ch11_filings":   ch11,
        "ch13_filings":   ch13,
        "total_filings":  total,
        "yoy_change_pct": yoy,
        "trend_signal":   classify_trend(yoy),
        "top_sectors":    DEFAULT_TOP_SECTORS,
    }
```

## RULES
1. total_filings must equal ch7_filings + ch11_filings + ch13_filings.
2. trend_signal must be one of: "SURGING", "RISING", "STABLE", "DECLINING".
3. yoy_change_pct is a float rounded to 2 decimal places.
4. top_sectors is always a non-empty list of strings.
5. period is a "YYYY-MM" string.
6. generated_at is UTC ISO-8601 with trailing "Z".
7. Never omit fields — all 9 schema keys must be present.

## VALIDATION CHECKLIST
- [ ] generated_at present and UTC ISO-8601
- [ ] period present as "YYYY-MM" string
- [ ] ch7_filings, ch11_filings, ch13_filings are positive integers
- [ ] total_filings == ch7_filings + ch11_filings + ch13_filings
- [ ] yoy_change_pct is a float
- [ ] trend_signal in {"SURGING", "RISING", "STABLE", "DECLINING"}
- [ ] top_sectors is a non-empty list
- [ ] data_cache/bankruptcy_latest.json is valid JSON
