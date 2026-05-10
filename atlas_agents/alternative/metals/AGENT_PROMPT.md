# A5 — Physical Metals Bot | Division: Alternative Assets & Niche

## IDENTITY
You track spot prices for Gold, Silver, Platinum, and Palladium using yfinance futures
contracts, then apply hardcoded typical dealer premiums (APMEX/JM Bullion patterns) to
derive physical coin and bar buy/sell prices. Spread analysis signals liquidity conditions.
No LLM calls. Pure yfinance fetch + arithmetic.

## DEFINITION
  Coverage: 4 precious metals (Gold, Silver, Platinum, Palladium).
  Data: spot price via yfinance futures (GC=F, SI=F, PL=F, PA=F).
  Physical premiums: hardcoded typical dealer premiums based on APMEX/JM Bullion patterns.
  Signal: TIGHT_SPREAD / NORMAL_SPREAD / WIDE_SPREAD based on buy/sell spread pct.
  Output: data_cache/metals_latest.json

## DATA SOURCES (with URLs)

### Primary — yfinance Spot Prices (already in requirements.txt):
  Gold:      GC=F  (COMEX Gold Futures front month — proxy for spot)
  Silver:    SI=F  (COMEX Silver Futures front month)
  Platinum:  PL=F  (NYMEX Platinum Futures front month)
  Palladium: PA=F  (NYMEX Palladium Futures front month)
  Usage: yfinance.Ticker("{symbol}").fast_info["lastPrice"]

### Secondary — Hardcoded Dealer Premiums (APMEX/JM Bullion typical patterns):
  Premiums are expressed as percentages above spot and embedded in METAL_UNIVERSE.
  Update when market conditions cause significant dealer premium shifts (e.g., supply shock).
  Coin premiums are higher than bar premiums due to smaller denomination and collectibility.

  Typical premiums (% above spot):
    Gold:      coin_premium_pct=5.0,  bar_premium_pct=2.0
    Silver:    coin_premium_pct=30.0, bar_premium_pct=15.0  (Silver Eagles vs bars)
    Platinum:  coin_premium_pct=8.0,  bar_premium_pct=4.0
    Palladium: coin_premium_pct=10.0, bar_premium_pct=5.0

### Physical Metals Reference:
  APMEX: https://www.apmex.com (reference only — do not scrape without permission)
  JM Bullion: https://www.jmbullion.com (reference only)

## OUTPUT FILE
  data_cache/metals_latest.json

## OUTPUT SCHEMA
```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "source": "yfinance_spot_plus_dealer_premiums",
  "record_count": 4,
  "metals": [
    {
      "metal": "Gold",
      "spot_price": 2340.50,
      "coin_type": "American Gold Eagle 1oz",
      "coin_premium_pct": 5.0,
      "bar_type": "1oz Gold Bar",
      "bar_premium_pct": 2.0,
      "buy_price": 2457.53,
      "sell_price": 2340.50,
      "spread_pct": 4.99,
      "signal": "NORMAL_SPREAD"
    }
  ]
}
```

## SIGNAL LOGIC
  coin_premium_pct = (coin_buy_price - spot_price) / spot_price * 100
  bar_premium_pct  = (bar_buy_price - spot_price) / spot_price * 100

  buy_price  = spot_price * (1 + coin_premium_pct / 100)   [coin price — retail buy]
  sell_price = spot_price                                    [dealer buy-back ≈ spot]
  spread_pct = (buy_price - sell_price) / sell_price * 100  [= coin_premium_pct]

  signal classification:
    "TIGHT_SPREAD"  — spread_pct <= 2.0   (high liquidity, low dealer markup)
    "NORMAL_SPREAD" — spread_pct <= 5.0   (normal market conditions)
    "WIDE_SPREAD"   — spread_pct > 5.0    (low liquidity or supply squeeze)

  Note: spread_pct is based on coin prices (most common retail transaction).
  Wide spread indicates stress in physical markets regardless of spot price.

## METAL UNIVERSE
  [
    {"metal": "Gold",      "symbol": "GC=F", "coin_type": "American Gold Eagle 1oz",    "coin_premium_pct": 5.0,  "bar_type": "1oz Gold Bar",      "bar_premium_pct": 2.0},
    {"metal": "Silver",    "symbol": "SI=F", "coin_type": "American Silver Eagle 1oz",  "coin_premium_pct": 30.0, "bar_type": "100oz Silver Bar",  "bar_premium_pct": 15.0},
    {"metal": "Platinum",  "symbol": "PL=F", "coin_type": "American Platinum Eagle 1oz","coin_premium_pct": 8.0,  "bar_type": "1oz Platinum Bar",  "bar_premium_pct": 4.0},
    {"metal": "Palladium", "symbol": "PA=F", "coin_type": "1oz Palladium Maple Leaf",   "coin_premium_pct": 10.0, "bar_type": "1oz Palladium Bar", "bar_premium_pct": 5.0},
  ]

## SCRAPER STRUCTURE
```python
import yfinance as yf
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "metals_latest.json"

METAL_UNIVERSE = [
    {"metal": "Gold",      "symbol": "GC=F", "coin_type": "American Gold Eagle 1oz",     "coin_premium_pct": 5.0,  "bar_type": "1oz Gold Bar",      "bar_premium_pct": 2.0},
    {"metal": "Silver",    "symbol": "SI=F", "coin_type": "American Silver Eagle 1oz",   "coin_premium_pct": 30.0, "bar_type": "100oz Silver Bar",  "bar_premium_pct": 15.0},
    {"metal": "Platinum",  "symbol": "PL=F", "coin_type": "American Platinum Eagle 1oz", "coin_premium_pct": 8.0,  "bar_type": "1oz Platinum Bar",  "bar_premium_pct": 4.0},
    {"metal": "Palladium", "symbol": "PA=F", "coin_type": "1oz Palladium Maple Leaf",    "coin_premium_pct": 10.0, "bar_type": "1oz Palladium Bar", "bar_premium_pct": 5.0},
]

def fetch_spot_price(symbol: str) -> float: ...
    # yf.Ticker(symbol).fast_info["lastPrice"]
    # Return float; on error return 0.0 and log warning

def compute_prices(spot: float, coin_premium_pct: float, bar_premium_pct: float) -> dict: ...
    # Return {"buy_price": ..., "sell_price": spot, "spread_pct": coin_premium_pct}
    # buy_price = spot * (1 + coin_premium_pct / 100)

def classify_signal(spread_pct: float) -> str: ...
    # Apply SIGNAL LOGIC thresholds, return one of three signal strings

def build_metal_record(metal_def: dict, spot_price: float) -> dict: ...
    # Build full metal record dict with all schema fields

def scrape() -> dict: ...
    # Iterate METAL_UNIVERSE, fetch spot prices, build records, return payload

def write_outputs(payload: dict) -> tuple[Path, Path]: ...
    # Call write_cache_json_pair(DATA_CACHE_DIR, OUTPUT_STABLE_NAME, payload)

def main(argv=None) -> int: ...
    # payload = scrape(); write_outputs(payload); return 0
```

## RULES
- No LLM calls — yfinance data fetch + arithmetic only
- spot_price expressed as float rounded to 2 decimal places
- coin_premium_pct and bar_premium_pct expressed as float (percentage)
- buy_price and sell_price expressed as float rounded to 2 decimal places
- spread_pct expressed as float rounded to 2 decimal places
- signal must be one of: TIGHT_SPREAD, NORMAL_SPREAD, WIDE_SPREAD
- generated_at must be ISO UTC string (datetime.utcnow().isoformat() + "Z")
- If yfinance fails for a symbol: set spot_price=0.0, signal="WIDE_SPREAD", log warning
- metal must be one of: Gold, Silver, Platinum, Palladium
- Use write_cache_json_pair for output
- record_count must equal len(metals) == 4

## VALIDATION CHECKLIST
Before reporting done:
  [ ] python -m py_compile metals_scraper.py exits 0
  [ ] scrape() returns dict with generated_at, record_count, metals list
  [ ] All metals have metal, spot_price, coin_type, coin_premium_pct, bar_type, bar_premium_pct, buy_price, sell_price, spread_pct, signal
  [ ] signal is one of: TIGHT_SPREAD, NORMAL_SPREAD, WIDE_SPREAD
  [ ] metal is one of: Gold, Silver, Platinum, Palladium
  [ ] record_count == 4
  [ ] python -m pytest tests/test_metals.py -v passes
