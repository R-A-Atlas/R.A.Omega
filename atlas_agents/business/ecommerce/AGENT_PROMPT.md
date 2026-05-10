# AGENT_PROMPT — B3: Ecommerce Trends Bot

## IDENTITY
Agent ID: B3  
Name: Ecommerce Trends Bot  
Division: Business & Startups  
Output file: data_cache/ecommerce_latest.json

---

## DEFINITION
Tracks 8 ecommerce niches using Google Trends (via pytrends, no auth required).
Pulls relative search interest over the past 3 months, classifies each niche as
RISING / STABLE / DECLINING, and estimates competition level. Designed for dropshippers,
D2C founders, and ecommerce investors evaluating product-market timing.

---

## DATA SOURCES

| Source | URL | Auth | Library |
|--------|-----|------|---------|
| Google Trends (via pytrends) | https://trends.google.com/trends/ | None | pip install pytrends |

API call pattern:
```python
from pytrends.request import TrendReq
pytrends = TrendReq(hl='en-US', tz=360)
pytrends.build_payload(kw_list, timeframe="today 3-m", geo="US")
df = pytrends.interest_over_time()
```

pytrends documentation: https://github.com/GeneralMills/pytrends

---

## OUTPUT FILE
`data_cache/ecommerce_latest.json`

---

## OUTPUT SCHEMA

```json
{
  "generated_at": "2026-05-09T14:30:00Z",
  "record_count": 8,
  "trending_niches": [
    {
      "niche": "AI gadgets",
      "trend_score": 82,
      "trend_direction": "RISING",
      "avg_price_estimate": 89.99,
      "competition_level": "HIGH"
    },
    {
      "niche": "sustainable fashion",
      "trend_score": 55,
      "trend_direction": "STABLE",
      "avg_price_estimate": 65.00,
      "competition_level": "MEDIUM"
    },
    {
      "niche": "home gym equipment",
      "trend_score": 61,
      "trend_direction": "STABLE",
      "avg_price_estimate": 245.00,
      "competition_level": "HIGH"
    },
    {
      "niche": "pet tech",
      "trend_score": 74,
      "trend_direction": "RISING",
      "avg_price_estimate": 49.99,
      "competition_level": "MEDIUM"
    },
    {
      "niche": "meal prep",
      "trend_score": 58,
      "trend_direction": "STABLE",
      "avg_price_estimate": 34.99,
      "competition_level": "MEDIUM"
    },
    {
      "niche": "travel accessories",
      "trend_score": 67,
      "trend_direction": "STABLE",
      "avg_price_estimate": 42.00,
      "competition_level": "HIGH"
    },
    {
      "niche": "smart home",
      "trend_score": 71,
      "trend_direction": "RISING",
      "avg_price_estimate": 119.99,
      "competition_level": "HIGH"
    },
    {
      "niche": "vintage clothing",
      "trend_score": 63,
      "trend_direction": "STABLE",
      "avg_price_estimate": 38.00,
      "competition_level": "LOW"
    }
  ]
}
```

### Field Definitions
| Field | Type | Description |
|-------|------|-------------|
| generated_at | ISO 8601 UTC string | Timestamp of cache generation |
| record_count | int | Total niches tracked |
| trending_niches[].niche | string | Niche keyword (matches pytrends kw_list) |
| trending_niches[].trend_score | int | Google Trends relative interest 0-100 (avg over 3-month window) |
| trending_niches[].trend_direction | string | "RISING", "STABLE", or "DECLINING" |
| trending_niches[].avg_price_estimate | float | Hardcoded average selling price estimate in USD |
| trending_niches[].competition_level | string | "HIGH", "MEDIUM", or "LOW" |

---

## SIGNAL / RATING LOGIC

trend_direction thresholds (based on 3-month average Google Trends score):
- **RISING**: trend_score >= 70
- **STABLE**: 40 <= trend_score < 70
- **DECLINING**: trend_score < 40

competition_level (hardcoded by category knowledge — not scraped):
- "HIGH": AI gadgets, home gym equipment, travel accessories, smart home
- "MEDIUM": sustainable fashion, pet tech, meal prep
- "LOW": vintage clothing

avg_price_estimate is a hardcoded market-research estimate per niche. Not live-scraped.

---

## SCRAPER STRUCTURE

```python
"""ecommerce_scraper.py — B3 Ecommerce Trends Bot"""
import json
import datetime
import time

SOURCE_URL = "https://trends.google.com/trends/"

NICHES = [
    "AI gadgets",
    "sustainable fashion",
    "home gym equipment",
    "pet tech",
    "meal prep",
    "travel accessories",
    "smart home",
    "vintage clothing",
]

# Hardcoded avg price estimates (USD) and competition levels per niche
NICHE_META = {
    "AI gadgets":           {"avg_price_estimate": 89.99,  "competition_level": "HIGH"},
    "sustainable fashion":  {"avg_price_estimate": 65.00,  "competition_level": "MEDIUM"},
    "home gym equipment":   {"avg_price_estimate": 245.00, "competition_level": "HIGH"},
    "pet tech":             {"avg_price_estimate": 49.99,  "competition_level": "MEDIUM"},
    "meal prep":            {"avg_price_estimate": 34.99,  "competition_level": "MEDIUM"},
    "travel accessories":   {"avg_price_estimate": 42.00,  "competition_level": "HIGH"},
    "smart home":           {"avg_price_estimate": 119.99, "competition_level": "HIGH"},
    "vintage clothing":     {"avg_price_estimate": 38.00,  "competition_level": "LOW"},
}


def classify_direction(score: int) -> str:
    if score >= 70:
        return "RISING"
    if score >= 40:
        return "STABLE"
    return "DECLINING"


def fetch_trends_batch(kw_list: list, timeframe: str = "today 3-m") -> dict:
    """Return {keyword: avg_score} using pytrends. Batch by 5 (API limit)."""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=360)
        scores = {}
        for i in range(0, len(kw_list), 5):
            batch = kw_list[i:i+5]
            pytrends.build_payload(batch, timeframe=timeframe, geo="US")
            df = pytrends.interest_over_time()
            if df.empty:
                for kw in batch:
                    scores[kw] = 0
                continue
            for kw in batch:
                if kw in df.columns:
                    scores[kw] = int(df[kw].mean())
                else:
                    scores[kw] = 0
            time.sleep(1)  # rate-limit courtesy
        return scores
    except Exception:
        # Fallback: return zero scores so caller gets DECLINING signal
        return {kw: 0 for kw in kw_list}


def scrape() -> dict:
    """Run B3: fetch Google Trends for all 8 niches, classify and enrich."""
    scores = fetch_trends_batch(NICHES)
    niches_out = []
    for niche in NICHES:
        score = scores.get(niche, 0)
        meta = NICHE_META.get(niche, {"avg_price_estimate": 0.0, "competition_level": "MEDIUM"})
        niches_out.append({
            "niche": niche,
            "trend_score": score,
            "trend_direction": classify_direction(score),
            "avg_price_estimate": meta["avg_price_estimate"],
            "competition_level": meta["competition_level"],
        })
    return {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "record_count": len(niches_out),
        "trending_niches": niches_out,
    }


def save(output_path: str = "data_cache/ecommerce_latest.json") -> None:
    result = scrape()
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    save()
```

---

## RULES
1. Always track all 8 niches — never drop any from the list.
2. pytrends failure must be silently caught; return score=0 and DECLINING direction.
3. Batch pytrends calls to <=5 keywords per request (API restriction).
4. Sleep 1 second between pytrends batches to avoid rate limiting.
5. trend_direction thresholds are fixed: >=70 RISING, 40-69 STABLE, <40 DECLINING.
6. competition_level is hardcoded — never derived from live data.
7. avg_price_estimate is hardcoded — not scraped.
8. generated_at must be ISO 8601 UTC.
9. record_count must equal len(trending_niches).

---

## VALIDATION CHECKLIST
- [ ] All 8 niches present in output
- [ ] trend_score is int 0-100 for each niche
- [ ] trend_direction is one of: RISING, STABLE, DECLINING
- [ ] competition_level is one of: HIGH, MEDIUM, LOW
- [ ] avg_price_estimate > 0 for all niches
- [ ] record_count == 8
- [ ] generated_at is valid ISO UTC string
- [ ] pytrends import failure does not crash the scraper
