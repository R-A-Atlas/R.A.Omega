# M8 — Congressional Trade Watcher Agent

## IDENTITY
Agent ID: M8  
Name: Congressional Trade Watcher Agent  
Division: Macro Risk & Geopolitics  
Codename: CONGRESS_TRADES  
Output File: data_cache/congress_trades_latest.json  

---

## DEFINITION
Fetches U.S. Congressional stock trade disclosures from the HouseStockWatcher public API (House STOCK Act filings) and SEC EDGAR for Senate periodic transaction reports. Monitors for late disclosures, large trades, and sector patterns to surface potential information-advantage signals for ATLAS macro intelligence.

---

## DATA SOURCES

| Source | URL | Auth | Notes |
|--------|-----|------|-------|
| HouseStockWatcher API | https://housestockwatcher.com/api | None | JSON API, no auth required |
| HouseStockWatcher Trades | https://housestockwatcher.com/api/transactions | None | All House STOCK Act filings |
| HouseStockWatcher by Member | https://housestockwatcher.com/api/transactions/{member} | None | Filter by member name |
| SEC EDGAR Full-Text Search | https://efts.sec.gov/LATEST/search-index?q=%22periodic+transaction+report%22&forms=4 | None | Senate Form 4 analogues |
| Senate STOCK Act | https://efts.sec.gov/LATEST/search-index?q=%22periodic+transaction+report%22&forms=4 | None | Public disclosures |

Primary Source URL: https://housestockwatcher.com/api

---

## OUTPUT FILE
`data_cache/congress_trades_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T12:00:00Z",
  "record_count": 5,
  "late_disclosure_count": 2,
  "most_traded_ticker": "NVDA",
  "trades": [
    {
      "member": "Rep. Jane Smith",
      "chamber": "House",
      "party": "R",
      "state": "TX",
      "ticker": "NVDA",
      "transaction_type": "Purchase",
      "amount_range": "$50,001 - $100,000",
      "trade_date": "2026-04-15",
      "disclosed_date": "2026-04-28",
      "days_to_disclose": 13,
      "disclosure_signal": "ON_TIME"
    },
    {
      "member": "Sen. John Doe",
      "chamber": "Senate",
      "party": "D",
      "state": "CA",
      "ticker": "AAPL",
      "transaction_type": "Sale",
      "amount_range": "$100,001 - $250,000",
      "trade_date": "2026-03-01",
      "disclosed_date": "2026-04-20",
      "days_to_disclose": 50,
      "disclosure_signal": "LATE_DISCLOSURE"
    }
  ]
}
```

### Field Definitions
- `generated_at`: ISO-8601 UTC timestamp of data fetch
- `record_count`: total number of trade entries returned
- `late_disclosure_count`: count of trades with days_to_disclose > 45
- `most_traded_ticker`: ticker symbol appearing most frequently in the dataset (string)
- `trades[].member`: full name of the member of Congress (string)
- `trades[].chamber`: "House" or "Senate"
- `trades[].party`: "R", "D", or "I"
- `trades[].state`: two-letter state code
- `trades[].ticker`: stock ticker symbol (string, uppercase)
- `trades[].transaction_type`: Purchase, Sale, Sale (Full), or Exchange
- `trades[].amount_range`: dollar range of the transaction (see Amount Ranges)
- `trades[].trade_date`: ISO-8601 date of the transaction
- `trades[].disclosed_date`: ISO-8601 date of STOCK Act disclosure
- `trades[].days_to_disclose`: integer (disclosed_date - trade_date in calendar days)
- `trades[].disclosure_signal`: LATE_DISCLOSURE (> 45 days) or ON_TIME (<= 45 days)

### Amount Ranges (STOCK Act reporting brackets)
- "$1,001 - $15,000"
- "$15,001 - $50,000"
- "$50,001 - $100,000"
- "$100,001 - $250,000"
- "$250,001 - $500,000"
- "Over $1,000,000"

---

## SIGNAL LOGIC

```
disclosure_signal:
    LATE_DISCLOSURE  days_to_disclose > 45
    ON_TIME          days_to_disclose <= 45

STOCK Act requires disclosure within 45 days of transaction.

cluster_signal (aggregate analysis):
    if 3+ members bought same ticker within 30 days:
        → CLUSTER_BUY: potential information signal — escalate to ATLAS research
    if 3+ members sold same ticker within 30 days:
        → CLUSTER_SELL: potential distribution signal

sector_signal:
    Most traded sector → infer legislative attention or insider comfort
    Tech buys → AI policy favorable?
    Energy buys → energy subsidies or deregulation upcoming?
    Defense buys → defense appropriations or conflict escalation?

late_disclosure_flag:
    days_to_disclose > 45 → STOCK Act violation window
    days_to_disclose > 90 → egregious late — flag for media attention risk
```

---

## SCRAPER STRUCTURE

```python
# congress_trades_scraper.py — stub

import json
import datetime
import requests
from collections import Counter
from datetime import date

HSW_API_BASE = "https://housestockwatcher.com/api"
HSW_TRANSACTIONS_URL = f"{HSW_API_BASE}/transactions"
SEC_EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
OUTPUT_PATH = "data_cache/congress_trades_latest.json"

VALID_TRANSACTION_TYPES = {"Purchase", "Sale", "Sale (Full)", "Exchange"}
VALID_CHAMBERS = {"House", "Senate"}
VALID_PARTIES = {"R", "D", "I"}
AMOUNT_RANGES = [
    "$1,001 - $15,000",
    "$15,001 - $50,000",
    "$50,001 - $100,000",
    "$100,001 - $250,000",
    "$250,001 - $500,000",
    "Over $1,000,000"
]


def fetch_house_trades(limit: int = 100) -> list:
    """Fetch recent House member stock trades from HouseStockWatcher API."""
    headers = {"User-Agent": "ATLAS-MacroAgent/1.0"}
    resp = requests.get(HSW_TRANSACTIONS_URL, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    # API returns list directly or nested under key
    if isinstance(data, list):
        return data[:limit]
    return data.get("data", data.get("transactions", []))[:limit]


def fetch_senate_trades() -> list:
    """Fetch Senate periodic transaction reports from SEC EDGAR."""
    params = {
        "q": '"periodic transaction report"',
        "forms": "4",
        "dateRange": "custom",
        "startdt": (datetime.date.today() - datetime.timedelta(days=90)).isoformat(),
        "enddt": datetime.date.today().isoformat()
    }
    resp = requests.get(SEC_EFTS_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json().get("hits", {}).get("hits", [])


def compute_days_to_disclose(trade_date_str: str, disclosed_date_str: str) -> int:
    """Compute calendar days between trade and disclosure."""
    try:
        trade_dt = datetime.date.fromisoformat(trade_date_str)
        disclosed_dt = datetime.date.fromisoformat(disclosed_date_str)
        return (disclosed_dt - trade_dt).days
    except Exception:
        return -1


def classify_disclosure(days: int) -> str:
    """Classify disclosure timeliness."""
    if days > 45:
        return "LATE_DISCLOSURE"
    return "ON_TIME"


def normalize_house_trade(raw: dict) -> dict:
    """Normalize HouseStockWatcher API response to output schema."""
    trade_date = raw.get("transaction_date", raw.get("trade_date", ""))
    disclosed_date = raw.get("disclosure_date", raw.get("filed_date", ""))
    days = compute_days_to_disclose(trade_date, disclosed_date)
    return {
        "member": raw.get("representative", raw.get("name", "")),
        "chamber": "House",
        "party": raw.get("party", ""),
        "state": raw.get("state", ""),
        "ticker": raw.get("ticker", "").upper().strip("--"),
        "transaction_type": raw.get("type", raw.get("transaction_type", "Purchase")),
        "amount_range": raw.get("amount", ""),
        "trade_date": trade_date,
        "disclosed_date": disclosed_date,
        "days_to_disclose": days,
        "disclosure_signal": classify_disclosure(days)
    }


def compute_most_traded_ticker(trades: list) -> str:
    """Find the most frequently appearing ticker."""
    tickers = [t["ticker"] for t in trades if t.get("ticker") and t["ticker"] not in ("", "--")]
    if not tickers:
        return ""
    return Counter(tickers).most_common(1)[0][0]


def build_output(trades: list) -> dict:
    """Assemble output envelope."""
    late_count = sum(1 for t in trades if t.get("disclosure_signal") == "LATE_DISCLOSURE")
    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "record_count": len(trades),
        "late_disclosure_count": late_count,
        "most_traded_ticker": compute_most_traded_ticker(trades),
        "trades": trades
    }


def scrape() -> dict:
    """Main entry point."""
    raw_house = fetch_house_trades(limit=50)
    trades = [normalize_house_trade(r) for r in raw_house if r.get("ticker")]

    # Filter out non-stock entries (e.g., "--" tickers, real estate)
    trades = [t for t in trades if t["ticker"] and len(t["ticker"]) <= 5 and t["ticker"].isalpha()]

    result = build_output(trades)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    data = scrape()
    print(json.dumps(data, indent=2))
```

---

## RULES
1. HouseStockWatcher API is public and free — no auth required
2. Cache for 4 hours — new disclosures are filed continuously but not tick-by-tick
3. Filter out non-equity entries: "--" tickers, mutual funds, bonds
4. ticker field must be uppercase alphabetic (1-5 chars) after normalization
5. `days_to_disclose` must be computed, not taken from API (APIs may not provide it)
6. Never include personally identifiable information beyond what is in public STOCK Act filings
7. `late_disclosure_count` must equal count of trades where `disclosure_signal` == "LATE_DISCLOSURE"
8. If HouseStockWatcher API is down, try Senate EDGAR endpoint as fallback

---

## VALIDATION CHECKLIST
- [ ] `generated_at` is valid ISO-8601 UTC
- [ ] `record_count` equals `len(trades)`
- [ ] `late_disclosure_count` equals count of LATE_DISCLOSURE entries
- [ ] Each trade has: member, chamber, party, state, ticker, transaction_type, amount_range, trade_date, disclosed_date, days_to_disclose, disclosure_signal
- [ ] All `chamber` values are "House" or "Senate"
- [ ] All `disclosure_signal` values are "LATE_DISCLOSURE" or "ON_TIME"
- [ ] All `ticker` values are uppercase alphabetic (1-5 chars)
- [ ] `days_to_disclose` is a non-negative integer for valid dates
- [ ] Output file written to `data_cache/congress_trades_latest.json`
