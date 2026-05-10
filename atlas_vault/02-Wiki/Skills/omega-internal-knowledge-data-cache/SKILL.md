# Skill: Omega internal knowledge (data_cache)

**ID:** SK-11  
**Created:** 2026-05-09  
**Proven:** 2+ (crypto + macro cache paths exercised in production Omega flows; contract stable in `atlas_omega.py`)

---

## [D] Direction

**What this skill does:** Describes how OmegaAgent loads **precomputed JSON** from `data_cache/` when `data_cache_intent` is set, compacts it for the model, and surfaces metadata on the response.

**When to use it:** Adding a new cache file, wiring a new sector scan intent, debugging “missing_file” / empty internal knowledge, or confirming router → Omega handoff without touching the 10-loop engine.

**Step-by-step workflow**

1. **Source data** — Ensure a no-LLM scraper (see `atlas-scraper-data-cache-template`) writes a **`<stem>_latest.json`** file under repo `data_cache/` with a dict root (Omega rejects non-dict JSON).
2. **Intent constant** — Add or reuse a `DC_INTENT_*` string in `atlas_omega.py` and add it to `_load_internal_knowledge_payload` → `intent_files` (filename must match the scraper’s stable output name).
3. **Compactor** — Implement or extend `_compact_*` for that intent so the LLM sees a small structured blob, not the raw scrape.
4. **Router hook** — Only if needed: coarse routing in `query_router.py` (`classify_sector_cache_intent`) maps natural language to the same `DC_INTENT_*` string. Do **not** change the 10-loop body.
5. **API path** — `api_server` passes `data_cache_intent` into `OmegaAgent.query` (already patterned for `/omega` and Omega branch of `/query`).
6. **Validate** — Run `py_compile`, `import atlas_omega`, hit `/omega` with a query that triggers the intent; confirm `report._meta.data_cache` shows `"loaded": true` and expected `asset_rows` when the file exists.

**Rules and guardrails**

- Per `CLAUDE.md`: **minimal edits** to `atlas_omega.py`; `query_router.py` changes are **coarse routing / cache intent only** — never modify the 10-loop implementation block.
- Filename in `intent_files` must match on-disk **`data_cache/<stem>_latest.json`** (Omega resolves `data_cache` beside `atlas_omega.py`).
- New intent must have a compactor; unknown intent → `meta.error == "unknown_data_cache_intent"`.
- Never commit secrets; cache files are research snapshots only.

---

## [B] Blueprints

**Read before using**

- `atlas_omega.py` — `_data_cache_root`, `_load_internal_knowledge_payload`, `DC_INTENT_*`, `_compact_*`, `DATA_CACHE_MACRO_ONLY_INTENTS`, attachment to `report["_meta"]["data_cache"]`
- `query_router.py` — `classify_sector_cache_intent` (read-only unless extending mapping)
- `api_server.py` — where `classify_sector_cache_intent` feeds `data_cache_intent` into Omega
- Reference scraper: `atlas_agents/crypto/crypto_scraper.py` → `crypto_top50_latest.json`
- Tests: `tests/test_api_endpoints.py` — cache intent regex / exclusions

**Good outcome**

- New cache file present; Omega response includes compact internal knowledge and `_meta.data_cache` with `"loaded": true`, `"file": "<name>_latest.json"`.

**Bad outcome to avoid**

- Editing `deep_research.py`, `gemini_limiter.py`, or the 10-loop core for cache fixes.
- Pointing `intent_files` at a path outside `data_cache/` or a mismatched filename (silent `missing_file` in production).

---

## [S] Solutions

**Exact commands (repo root)**

```powershell
python -m py_compile atlas_omega.py
python -c "import atlas_omega"
```

**Snippet: intent → file (authoritative map in code)**

| `DC_INTENT_*` value | Expected `data_cache/` file |
|---------------------|-----------------------------|
| `CRYPTO_MARKET_SCAN` | `crypto_top50_latest.json` |
| `EQUITIES_MARKET_SCAN` | `equities_latest.json` |
| `OPTIONS_FLOW_MARKET_SCAN` | `options_flow_latest.json` |
| `INSIDER_TRADES_MARKET_SCAN` | `insider_trades_latest.json` |
| `TREASURY_YIELD_MARKET_SCAN` | `bond_yields_latest.json` |
| `CPI_INFLATION_MARKET_SCAN` | `cpi_latest.json` |
| `FED_WATCH_MARKET_SCAN` | `fed_watch_latest.json` |

**Validation**

1. Unknown intent returns `(None, meta)` with `meta["error"] == "unknown_data_cache_intent"`.
2. Missing file returns `meta["error"]` starting with `missing_file:`.
3. After wiring, run evals in `evals.json` for this skill.
