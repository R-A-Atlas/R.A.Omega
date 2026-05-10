# M1 — Fed Rate Probability Agent

## IDENTITY
Agent ID: M1  
Name: FedWatch Rate Probability Agent  
Division: Macro Risk & Geopolitics  
Codename: FED_WATCH  
Output File: data_cache/fed_watch_latest.json  

---

## DEFINITION
Fetches real-time Federal Reserve rate decision probabilities from CME FedWatch and Fed Funds futures (ZQ=F series via yfinance). Synthesizes the market's implied probability distribution across rate actions for the next FOMC meeting. Enables ATLAS to contextualize equity risk, bond duration sensitivity, and macro regime shifts driven by Fed policy.

---

## DATA SOURCES

| Source | URL | Auth | Notes |
|--------|-----|------|-------|
| CME FedWatch Tool | https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html | None | Scrape public HTML table |
| CME FedWatch JSON API | https://www.cmegroup.com/CmeWS/mvc/ProductCalendar/V2/FedWatch/Probabilities | None | JSON endpoint (may require browser headers) |
| yfinance ZQ=F series | yfinance Python package — ticker ZQ=F | None | Fed Funds futures implied rate |
| FRED API (fallback) | https://fred.stlouisfed.org/series/FEDFUNDS | None | Historical effective rate |

---

## OUTPUT FILE
`data_cache/fed_watch_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "current_rate": 5.33,
  "next_meeting_date": "2026-06-11",
  "dominant_action": "HOLD",
  "dominant_probability_pct": 68.4,
  "record_count": 5,
  "probabilities": [
    {
      "action": "CUT_50BPS",
      "probability_pct": 2.1
    },
    {
      "action": "CUT_25BPS",
      "probability_pct": 18.3
    },
    {
      "action": "HOLD",
      "probability_pct": 68.4
    },
    {
      "action": "HIKE_25BPS",
      "probability_pct": 9.7
    },
    {
      "action": "HIKE_50BPS",
      "probability_pct": 1.5
    }
  ]
}
```

### Field Definitions
- `generated_at`: ISO-8601 UTC timestamp of data fetch
- `current_rate`: Current Fed Funds effective rate (float, percent)
- `next_meeting_date`: ISO-8601 date of the next scheduled FOMC meeting
- `dominant_action`: action enum with the highest probability_pct
- `dominant_probability_pct`: probability of dominant_action (float)
- `record_count`: number of probability buckets returned (must equal 5)
- `probabilities[].action`: one of CUT_50BPS, CUT_25BPS, HOLD, HIKE_25BPS, HIKE_50BPS
- `probabilities[].probability_pct`: market-implied probability (float, 0-100)

### Invariants
- Sum of all `probability_pct` values MUST equal 100 (±0.5 rounding tolerance)
- `record_count` MUST equal `len(probabilities)`
- `dominant_action` MUST match the action with the highest `probability_pct`

---

## SIGNAL LOGIC

```
dominant_action = argmax(probability_pct over all actions)

if dominant_action in ["CUT_50BPS", "CUT_25BPS"]:
    macro_signal = "DOVISH"
elif dominant_action == "HOLD":
    macro_signal = "NEUTRAL"
elif dominant_action in ["HIKE_25BPS", "HIKE_50BPS"]:
    macro_signal = "HAWKISH"

risk_implication:
    DOVISH  → equity positive, bond duration positive, USD negative
    NEUTRAL → wait-and-see, watch next CPI/PCE print
    HAWKISH → equity headwinds, short duration, USD positive
```

---

## SCRAPER STRUCTURE

```python
# fed_watch_scraper.py — stub

import json
import datetime
import yfinance as yf
import requests
from bs4 import BeautifulSoup

CME_FEDWATCH_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
CME_JSON_URL = "https://www.cmegroup.com/CmeWS/mvc/ProductCalendar/V2/FedWatch/Probabilities"
OUTPUT_PATH = "data_cache/fed_watch_latest.json"
ACTION_KEYS = ["CUT_50BPS", "CUT_25BPS", "HOLD", "HIKE_25BPS", "HIKE_50BPS"]


def fetch_cme_json() -> dict:
    """Attempt CME JSON API first (fastest path)."""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    resp = requests.get(CME_JSON_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_cme_html() -> dict:
    """Fallback: scrape CME FedWatch HTML table."""
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(CME_FEDWATCH_URL, headers=headers, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    # Parse probability table rows
    # Returns dict {action: probability_pct}
    raise NotImplementedError("HTML scrape fallback — implement table parsing")


def fetch_current_rate() -> float:
    """Get current Fed Funds rate from yfinance ZQ=F or FRED."""
    ticker = yf.Ticker("ZQ=F")
    hist = ticker.history(period="5d")
    if not hist.empty:
        implied = 100 - hist["Close"].iloc[-1]
        return round(implied, 4)
    # FRED fallback
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"
    df_text = requests.get(url, timeout=10).text
    lines = [l for l in df_text.strip().split("\n") if l and not l.startswith("DATE")]
    last = lines[-1].split(",")
    return float(last[1])


def build_output(probabilities: list, current_rate: float, next_meeting: str) -> dict:
    """Assemble and validate output envelope."""
    total = sum(p["probability_pct"] for p in probabilities)
    assert abs(total - 100) <= 0.5, f"Probabilities sum to {total}, expected 100"
    dominant = max(probabilities, key=lambda x: x["probability_pct"])
    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "current_rate": current_rate,
        "next_meeting_date": next_meeting,
        "dominant_action": dominant["action"],
        "dominant_probability_pct": dominant["probability_pct"],
        "record_count": len(probabilities),
        "probabilities": probabilities
    }


def scrape() -> dict:
    """Main entry point. Returns output dict and writes to OUTPUT_PATH."""
    try:
        raw = fetch_cme_json()
        # TODO: parse raw into probabilities list
        probabilities = []  # placeholder
    except Exception:
        raw = fetch_cme_html()
        probabilities = []  # placeholder

    current_rate = fetch_current_rate()
    next_meeting = "2026-06-11"  # TODO: parse from CME calendar
    result = build_output(probabilities, current_rate, next_meeting)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    data = scrape()
    print(json.dumps(data, indent=2))
```

---

## RULES
1. Always validate that probabilities sum to 100 (±0.5 tolerance) before writing output
2. If CME JSON endpoint fails, fall back to HTML scrape
3. If both CME sources fail, fall back to yfinance ZQ=F implied rate only — write partial output with null probabilities and log warning
4. Never hardcode probabilities — always fetch live
5. Write output atomically (write to temp file, rename)
6. Log data age: if cached file is < 15 minutes old, skip fetch and return cached
7. Next meeting date must come from CME calendar, not hardcoded permanently

---

## VALIDATION CHECKLIST
- [ ] `generated_at` is valid ISO-8601 UTC
- [ ] `current_rate` is a float between 0 and 10
- [ ] `record_count` equals 5
- [ ] All 5 action keys present: CUT_50BPS, CUT_25BPS, HOLD, HIKE_25BPS, HIKE_50BPS
- [ ] Sum of `probability_pct` values equals 100 (±0.5)
- [ ] `dominant_action` matches action with max `probability_pct`
- [ ] `next_meeting_date` is a valid future ISO-8601 date
- [ ] Output file written to `data_cache/fed_watch_latest.json`
