# R6 — REIT Screener | Division: Real Estate & Property

## IDENTITY
You screen the top US REITs by dividend yield, price, and sector classification.
REITs are the public market proxy for real estate — yield comparison against
bond rates is a core valuation signal. No LLM calls. yfinance fetch + classify.

## DEFINITION
  REIT: Real Estate Investment Trust — must distribute 90%+ of taxable income
  dividend_yield: trailing 12-month dividend / current price (as percentage)
  rating: yield-based attractiveness vs current 10y Treasury rate

  Rating thresholds (relative to 10y Treasury ~4.2%):
    STRONG_BUY:  dividend_yield >= 7.0%
    BUY:         dividend_yield >= 5.5%
    HOLD:        dividend_yield >= 4.0%
    UNDERPERFORM: dividend_yield < 4.0%

## REIT UNIVERSE (top 30 by market cap)
  Residential:  AMT, PLD, EQIX, CCI, WELL, DLR, PSA, EXR, AVB, EQR
  Commercial:   SPG, O, VICI, WPC, NNN, STORE, ADC, EPRT, IIPR, GTY
  Specialty:    IRM, SBAC, AMH, INVH, UDR, CPT, MAA, ESS, AIV, BRT

## DATA SOURCES (free, no auth)

### Primary — yfinance per-ticker info:
  yf.Ticker(ticker).info → dividendYield, currentPrice, longName,
                            sector, marketCap, trailingAnnualDividendYield
  Batch: yf.Tickers(" ".join(REIT_UNIVERSE)).tickers

### Secondary — SEC EDGAR company facts (XBRL):
  https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
  Fields: us-gaap/Dividends, us-gaap/RealEstateInvestmentPropertyNet
  Note: requires CIK lookup first via https://efts.sec.gov/LATEST/search-index?q={ticker}&dateRange=custom&startdt=2024-01-01

## OUTPUT FILE
  data_cache/reits_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "yfinance",
  "record_count": 30,
  "treasury_10y_rate": 4.20,
  "reits": [
    {
      "ticker": "O",
      "name": "Realty Income Corp",
      "sector": "Retail REIT",
      "price": 52.30,
      "dividend_yield": 5.92,
      "market_cap": 46800000000,
      "rating": "BUY"
    }
  ]
}
```

## RATING LOGIC
  dividend_yield >= 7.0  → "STRONG_BUY"
  dividend_yield >= 5.5  → "BUY"
  dividend_yield >= 4.0  → "HOLD"
  dividend_yield < 4.0   → "UNDERPERFORM"

## SCRAPER STRUCTURE
```python
import yfinance as yf
import time
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "reits_latest.json"

REIT_UNIVERSE = [
    "AMT", "PLD", "EQIX", "CCI", "WELL", "DLR", "PSA", "EXR", "AVB", "EQR",
    "SPG", "O", "VICI", "WPC", "NNN", "IRM", "SBAC", "AMH", "INVH", "UDR",
    "CPT", "MAA", "ESS", "ADC", "EPRT", "IIPR", "GTY", "STORE", "AIV", "BRT",
]

def fetch_reit_data(ticker: str) -> dict: ...    # yf.Ticker(ticker).info
def classify_rating(dividend_yield: float) -> str: ...
def scrape(*, top_n: int = 30) -> dict: ...
def write_outputs(payload: dict) -> tuple[Path, Path]: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — yfinance fetch + classify only
- dividend_yield expressed as float percentage (e.g., 5.92 not 0.0592)
- price expressed as float USD
- market_cap expressed as integer USD
- rating must be exactly: "STRONG_BUY", "BUY", "HOLD", or "UNDERPERFORM"
- Sleep 0.2s between per-ticker yfinance calls
- Skip tickers where yfinance returns None or missing dividendYield
- generated_at must be ISO UTC string
- Include treasury_10y_rate as context for yield comparison
- Use write_cache_json_pair for output

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile reit_screener_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, reits list, record_count
  [ ] dividend_yield > 0 for all included REITs
  [ ] rating in {"STRONG_BUY", "BUY", "HOLD", "UNDERPERFORM"}
  [ ] python -m pytest tests/test_reit_screener.py -v passes
