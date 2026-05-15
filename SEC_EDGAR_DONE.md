# SEC EDGAR Integration — DONE

**Date:** 2026-05-15
**Branch:** codex/chat-modes-settings
**Session goal:** Activate SEC EDGAR as the first live finance-grade connection in Omega OS.

---

## Files Changed

| File | Change |
|------|--------|
| `omega_sec_edgar.py` | Created — full SEC EDGAR integration module |
| `omega_connections.py` | Updated — SEC EDGAR status computed dynamically via `_sec_edgar_status()` |
| `prompt_builder.py` | Updated — `sec_filing_context` param + `include_sec_filings` param in `build_synthesis_prompt_meta()` |
| `api_server.py` | Updated — `GET /omega-os/sec-filings/{company}` endpoint added |
| `omega_os/skills/company_report/skill.md` | Updated — SEC filing steps added to company_report skill SOP |
| `.env.example` | Updated — `SEC_USER_AGENT` placeholder added |
| `tests/test_omega_sec_edgar.py` | Created — 58 unit tests, all passing |

---

## What Was Built

### omega_sec_edgar.py
- `search_company_cik(company_name_or_ticker)` — resolves CIK from name or ticker via `company_tickers.json`
- `get_company_submissions(cik)` — fetches full EDGAR submissions JSON
- `get_recent_filings(cik, forms, max_per_form)` — extracts 10-K / 10-Q / 8-K with URLs
- `get_filing_summary(company_name_or_ticker)` — high-level summary with `filing_context` string for prompt injection
- `is_available()` — True when `SEC_USER_AGENT` is non-placeholder
- `_normalize_cik()` — zero-pads CIK to 10 digits
- `_rate_limited_get()` — enforces 110ms between requests (10 req/sec EDGAR limit)
- `_load_company_tickers()` — `@lru_cache(maxsize=1)` to avoid repeat downloads
- `_cik_cache` — per-session dict for CIK lookup deduplication

### prompt_builder.py additions
- `build_synthesis_prompt()` now accepts `sec_filing_context: str = ""`
  - SEC context injected **only** when `output_mode == "company_report"`
  - Never injected for trade_plan, chat, or other modes
- `build_synthesis_prompt_meta()` now accepts `include_sec_filings: bool = False`
  - Fetches EDGAR data at synthesis time only (never before routing)
  - Returns metadata: `sec_filings_used`, `latest_10k`, `latest_10q`, `latest_8k`

### omega_connections.py change
- `_sec_edgar_status()` function computes live status from env:
  - `STATUS_ACTIVE` when `SEC_USER_AGENT` is set to a non-placeholder value
  - `STATUS_CONFIGURED` when placeholder (`contact@example.com`)

### API endpoint
```
GET /omega-os/sec-filings/{company}
```
- Returns `{"available": False, ...}` when `SEC_USER_AGENT` not configured
- Returns full `get_filing_summary()` result when configured

---

## Safety Rules Enforced

- SEC filing context never passed to `classify_intent_route()` — routing is raw-query-only
- `prompt_builder.py` does not import `query_router`
- SEC calls only happen at synthesis time (`include_sec_filings=True`)
- Filing context only injected into `company_report` output mode
- `can_write=False`, `is_destructive=False` on SEC EDGAR connection
- Rate limiting: 110ms between all EDGAR requests
- `SEC_USER_AGENT` identifies app + contact email per EDGAR terms of service

---

## Test Results

```
tests/test_omega_sec_edgar.py: 58 passed
Full suite (excluding live-server test_omega.py): 1378 passed, 0 failures
```

### Test coverage
- CIK normalization (4 cases)
- `is_available()` (4 cases: unset, placeholder, real, empty)
- `_get_user_agent()` (3 cases)
- `search_company_cik()` (8 cases: ticker, case-insensitive, name, partial, not-found, empty map, zero-padding, caching)
- `get_company_submissions()` (4 cases: success, None, non-dict, URL format)
- `get_recent_filings()` (8 cases: defaults, 10-K present, 10-Q multiple, max_per_form, URL format, failed submissions, custom forms, required keys)
- `get_filing_summary()` (8 cases: all keys, sec_filings_used, latest_10k, error, filing_context CIK, filing_context date, no-filings fallback, sec_filings_used false)
- prompt_builder integration (7 cases)
- Routing purity (3 cases)
- omega_connections status (4 cases)
- Module import + API registration (5 cases)

---

## py_compile Results

```
python -m py_compile omega_sec_edgar.py         # PASS
python -m py_compile omega_connections.py       # PASS
python -m py_compile prompt_builder.py          # PASS
python -m py_compile api_server.py              # PASS
python -m py_compile atlas_omega.py             # PASS
```

---

## Remaining / Next Steps

- `include_sec_filings=True` is not yet wired into `atlas_omega.py` or `api_server.py`'s company report path — the endpoint exists but the OmegaAgent call site must be updated to pass `include_sec_filings=True` when `output_mode == "company_report"`
- `GET /omega-os/sec-filings/{company}` is read-only and safe to expose — no auth required by EDGAR
- Set `SEC_USER_AGENT=YourApp your@email.com` in `.env` to activate (copy from `.env.example`)
