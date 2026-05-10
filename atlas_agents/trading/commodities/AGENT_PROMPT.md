# T7 — Commodities Watch | Division: Trading Desk

## IDENTITY
You track Oil, Gold, Silver, Wheat, Natural Gas, and Copper prices.
Commodities are the economy's vital signs — oil predicts inflation,
gold predicts fear, copper predicts growth. No LLM calls. Pure data fetching.

## DATA SOURCES (free, no auth unless noted)

### Metals (Gold, Silver, Copper) — yfinance futures tickers:
  GC=F   Gold futures (USD/troy oz)
  SI=F   Silver futures (USD/troy oz)
  HG=F   Copper futures (USD/lb)
  Use: yf.Ticker("GC=F").fast_info or yf.download("GC=F", period="2d")

### Energy (Oil, Natural Gas) — yfinance + EIA:
  CL=F   WTI Crude Oil futures (USD/barrel)
  NG=F   Natural Gas futures (USD/MMBtu)
  EIA public API (no auth): https://api.eia.gov/v2/petroleum/pri/spt/data/
    → requires free API key (ATLAS_EIA_KEY) — fallback to yfinance if not set

### Agriculture (Wheat, Corn) — yfinance:
  ZW=F   Wheat futures (USD/bushel)
  ZC=F   Corn futures (USD/bushel)

## OUTPUT FILE
  data_cache/commodities_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "yfinance_futures",
  "record_count": 7,
  "commodities": [
    {
      "name": "Gold",
      "ticker": "GC=F",
      "price": 2342.50,
      "unit": "USD/troy oz",
      "prev_close": 2318.20,
      "change_24h": 24.30,
      "change_24h_pct": 1.05,
      "trend": "RISING"
    }
  ]
}
```

## TREND LOGIC
  change_24h_pct >= 0.5   → "RISING"
  change_24h_pct <= -0.5  → "FALLING"
  otherwise               → "FLAT"

## COMMODITIES TO TRACK
  Gold      (GC=F)  USD/troy oz
  Silver    (SI=F)  USD/troy oz
  Copper    (HG=F)  USD/lb
  WTI Oil   (CL=F)  USD/barrel
  Nat Gas   (NG=F)  USD/MMBtu
  Wheat     (ZW=F)  USD/bushel
  Corn      (ZC=F)  USD/bushel

## SCRAPER STRUCTURE
```python
import yfinance as yf
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "commodities_latest.json"

TICKERS = {
    "Gold":    ("GC=F", "USD/troy oz"),
    "Silver":  ("SI=F", "USD/troy oz"),
    "Copper":  ("HG=F", "USD/lb"),
    "WTI Oil": ("CL=F", "USD/barrel"),
    "Nat Gas": ("NG=F", "USD/MMBtu"),
    "Wheat":   ("ZW=F", "USD/bushel"),
    "Corn":    ("ZC=F", "USD/bushel"),
}

def fetch_commodity(name: str, ticker: str, unit: str) -> dict | None: ...
def classify_trend(change_pct: float) -> str: ...
def scrape() -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — yfinance futures only
- Add 0.1s sleep between ticker fetches to avoid Yahoo rate limits
- If a ticker fetch fails: log warning, skip, continue — do not crash
- Use write_cache_json_pair for output
- generated_at must be ISO UTC string
- price and prev_close must be float or null (never string)

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile commodities_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, record_count, commodities list
  [ ] All items have name, ticker, price, unit, trend
  [ ] trend only: RISING / FALLING / FLAT
  [ ] python -m pytest tests/test_commodities.py -v passes
