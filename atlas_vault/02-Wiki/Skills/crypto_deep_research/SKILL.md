# Skill: Crypto Deep Research (Omega + cached snapshot)

## [D] Direction

**Purpose:** Define the contract between the **pure-Python crypto snapshot** ([`atlas_agents/crypto/crypto_scraper.py`](../../../../atlas_agents/crypto/crypto_scraper.py)) and **OmegaAgent** (or successor swarm agents) when generating crypto-sector narratives — including **Min / Mid / Max** scenario framing and **non-negotiable legal disclaimers**.

**When to invoke:** Crypto sector questions, “top meme vs utility flows,” breadth scans that should not invoke the expensive 10-loop equity engine, or any workflow that should ground answers in **`data_cache/crypto_top50_latest.json`**.

**Workflow**

1. **Refresh or trust cache** — If the JSON is stale (see cadence below), run the scraper (`Solutions`). Otherwise read the canonical file once and keep it in-context.
2. **Grounding** — Omega must cite aggregates from `coins[]` (e.g. meme share, median volume, leaders by `market_cap_usd`) and must not invent tickers absent from cache unless labeled as hypothetical.
3. **Outcomes framing** — Present **three scenarios** anchored to observable inputs:
   - **Min** — Liquidity dries up, risk-off / regulatory shock, meme basket drawdown heuristic.
   - **Mid** — Base case using current rankings, volume persistence, breadth of trending names.
   - **Max** — Upside liquidity / reflexivity case; still bounded by disclaimers below.
   All numeric paths are illustrative ranges, not forecasts, unless sourced elsewhere.
4. **Disclosures** — Every user-facing Omega response that uses this file must prepend or append **mandatory disclaimers** (Blueprint — exact block).
5. **No scrape in hot path** — The scraper is **offline/batch**. Do not call external HTTP from Omega for this snapshot during a chat turn unless intentionally re-running automation.
6. **API wiring (ATLAS)** — `POST /omega` and `POST /query` accept optional **`crypto_snapshot: true`** on the JSON body (`QueryRequest`). When set, **`data_cache_intent`** is **`CRYPTO_MARKET_SCAN`** so Omega loads and compacts `crypto_top50_latest.json` (`atlas_omega._load_internal_knowledge_payload`). Regex-based detection via `query_router.classify_sector_cache_intent()` still applies when `crypto_snapshot` is omitted (`false`).

### Canonical artifact

- **Path (repo-relative):** `data_cache/crypto_top50_latest.json` (repository root adjacent to [`api_server.py`](../../../../api_server.py)).
- **Companion:** timestamped sibling `crypto_top50_<generated_at>.json` (colon-free filename) emitted each run.

### Payload (summary)

Top-level keys: `generated_at`, `category_fetch_workers`, `category_request_gap_s` (non-null when sequential / default workers=1), `merge_policy`, `sources`, `coin_count`, `coins`.

Per coin (typical):

- Identifiers: `id`, `symbol`, `name`
- Liquidity/size: `market_cap_usd`, `volume_24h_usd`, `price_usd`, `price_change_24h_pct`
- **Sector:** `sector_category` — `"meme"` \| `"utility"` \| `"unknown"` (heuristic: CoinGecko `categories` substring match on `"meme"`)
- `categories` — raw strings from CoinGecko (Omega may nuance wording but not reverse the scrape)
- `trending`, `trending_rank`
- Optional: `binance_quote_volume_24h_usdt` when Binance cross-check enabled
- Optional: `category_warnings` if category fetch degraded

Merge policy documented in-field: trending-first union with volume leaderboard fill up to requested count (`--top`, default **50**).

### Mandatory Omega disclaimer block (adapt names to product)

Omega must communicate that:

- Output is **educational and informational**, **not personalized investment, tax, or legal advice**, and **not an offer or solicitation**.
- Cryptocurrencies are **volatile and high-risk**, including risk of total loss.
- **`sector_category`** is API/heuristic-derived and **not** a suitability or compliance classification.
- **Past or current ranking, volume, or popularity does not imply future performance.**
- User is solely responsible for compliance with laws in **their jurisdiction** (including securities, AML, reporting, licensing where applicable).

The model may shorten **only non-substantive wording** — not remove concepts above.

### Min / Mid / Max template (conceptual)

- **Inputs:** meme vs utility mix, dispersion of volume, trending concentration, extremes in `price_change_24h_pct`.
- **Min:** Stress case — correlate illiquidity, drawdown narratives, meme-heavy concentration risk when `sector_category == "meme"` dominates trending.
- **Mid:** Status-quo extrapolation bounded by snapshots (no fabricated catalysts unless clearly labeled external).
- **Max:** Liquidity-surplus reflexivity framing without promising returns; cite that scenario requires explicit assumptions Omega labels as hypothetical.

## [S] Solutions

**Run scraper (from repo root):**

```powershell
cd "C:\Users\crist\OneDrive\Desktop\trading platform overview"
python atlas_agents\crypto\crypto_scraper.py
```

**OPTIONS**

- `--top N` — number of coins (1–250; default **50**).
- `--no-binance` — omit Binance correlation field.
- `--category-workers N` — parallelism for CoinGecko `/coins/{id}` calls (`1` default: **sequential** with gap; `2–8` enables a bounded thread pool, may trigger more 429s on anonymous tiers).

**Refresh cadence (guidance)**

- Operational default: **≤ 24h** TTL for discretionary chat; intraday desks may rerun hourly if rate limits permit.
- If `generated_at` is missing or malformed, rerun scraper before synthesis.

**Rate limits**

- CoinGecko public API and Binance anonymous endpoints impose soft limits — keep batch windows conservative; scrape is **scheduled**, not conversational.

**Consumers (future swarm)**

Data agent → **`crypto_top50_latest.json`** → Omega textual synthesis (Min/Mid/Max + disclaimers) → optional downstream report renderer.

See [`evals.json`](evals.json) for mechanical binary checks aligned with repo hygiene.
