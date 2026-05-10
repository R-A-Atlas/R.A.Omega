# R4 — Commercial Property Bot | Division: Real Estate & Property

## IDENTITY
You track commercial real estate market conditions — office, industrial,
retail, and multifamily segments. Average lease rates, vacancy rates, and
trend direction per segment per market. CoStar/CBRE publish free quarterly
reports; FRED tracks CRE price indices. No LLM calls. Data fetch + classify.

## DEFINITION
  CRE segments: Office, Industrial, Retail, Multifamily
  avg_lease_rate: annual rent per sq ft (USD/sqft/year)
  vacancy_rate: percentage of available space (e.g., 18.5 = 18.5%)
  trend: direction of vacancy over trailing 12 months

  Trend classification:
    TIGHTENING: vacancy_rate decreased >= 1.0% YoY (landlord market)
    STABLE:     |vacancy_rate change| < 1.0% YoY
    SOFTENING:  vacancy_rate increased >= 1.0% YoY (tenant market)

## DATA SOURCES (free, no auth)

### Primary — FRED CRE Indices (no auth required):
  Moody's/RCA CPPI (Commercial Property Price Index):
    https://fred.stlouisfed.org/series/RCPIATOT  (all property types)
    https://fred.stlouisfed.org/series/RCPIAINTR (industrial)
    https://fred.stlouisfed.org/series/RCPIAOFC  (office)
  Note: FRED free API (api_key optional for low volume — omit for public access)

### Secondary — CBRE/JLL Quarterly Market Reports (public PDFs):
  Published quarterly at: https://www.cbre.com/insights/figures/cap-rate-survey
  Parse headline figures from HTML summary pages (not PDF — scrape HTML tables)

### Tertiary — BLS PPI for construction (proxy for industrial rents):
  https://data.bls.gov/api/v2/timeseries/data/PCU236220236220
  No auth required for single series

### Hardcoded baseline (fallback):
  Maintain static snapshot of Q1 2026 market data as fallback when APIs fail.
  Update quarterly.

## OUTPUT FILE
  data_cache/commercial_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "fred_cre_indices",
  "record_count": 12,
  "segments": [
    {
      "type": "Office",
      "market": "National",
      "avg_lease_rate": 34.50,
      "vacancy_rate": 18.5,
      "yoy_vacancy_change": 2.1,
      "trend": "SOFTENING"
    },
    {
      "type": "Industrial",
      "market": "National",
      "avg_lease_rate": 9.80,
      "vacancy_rate": 5.2,
      "yoy_vacancy_change": -0.8,
      "trend": "STABLE"
    }
  ]
}
```

## TREND LOGIC
  yoy_vacancy_change = vacancy_rate_now - vacancy_rate_12m_ago
  yoy_vacancy_change <= -1.0  → "TIGHTENING"
  -1.0 < yoy_vacancy_change < 1.0  → "STABLE"
  yoy_vacancy_change >= 1.0   → "SOFTENING"

## SCRAPER STRUCTURE
```python
import requests
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "commercial_latest.json"

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

CRE_SERIES = {
    "All Property": "RCPIATOT",
    "Industrial":   "RCPIAINTR",
    "Office":       "RCPIAOFC",
}

FALLBACK_SNAPSHOT = [
    {"type": "Office",      "market": "National", "avg_lease_rate": 34.50, "vacancy_rate": 18.5, "yoy_vacancy_change": 2.1},
    {"type": "Industrial",  "market": "National", "avg_lease_rate": 9.80,  "vacancy_rate": 5.2,  "yoy_vacancy_change": -0.8},
    {"type": "Retail",      "market": "National", "avg_lease_rate": 21.00, "vacancy_rate": 4.1,  "yoy_vacancy_change": -0.3},
    {"type": "Multifamily", "market": "National", "avg_lease_rate": 18.50, "vacancy_rate": 6.8,  "yoy_vacancy_change": 0.4},
]

def fetch_fred_series(series_id: str) -> list[dict]: ...  # FRED observations
def classify_trend(yoy_change: float) -> str: ...
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — fetch + classify only
- avg_lease_rate expressed as float USD/sqft/year
- vacancy_rate expressed as float percentage (e.g., 18.5 not 0.185)
- yoy_vacancy_change expressed as float percentage points
- trend must be exactly: "TIGHTENING", "STABLE", or "SOFTENING"
- generated_at must be ISO UTC string
- If FRED unavailable: use FALLBACK_SNAPSHOT with source = "fallback_snapshot"
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile commercial_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, segments list, record_count
  [ ] All segments have type, market, avg_lease_rate, vacancy_rate, trend
  [ ] trend in {"TIGHTENING", "STABLE", "SOFTENING"}
  [ ] python -m pytest tests/test_commercial.py -v passes
