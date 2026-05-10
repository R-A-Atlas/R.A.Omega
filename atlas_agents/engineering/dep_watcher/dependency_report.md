# Dependency Report
Date: 2026-05-09
Agent: E9 Dependency Watcher
Scan: pip list --outdated against requirements.txt pins

**Session tooling:** `pip-audit` installed in dev interpreter (not listed in requirements.txt — run `pip install pip-audit` on fresh machines).

**pip-audit (2026-05-09):** `python -m pip_audit -r requirements.txt`. **No known vulnerabilities** (empty `fixes`, all dependency `vulns: []`). **E1 Debugger:** nothing to escalate for this run — re-run quarterly or whenever floors change materially.

---

## Direct Dependencies (pinned in requirements.txt)

| Package          | Pinned (>=) | Installed | Latest  | Bump Type    | Status             | Action  |
|------------------|-------------|-----------|---------|--------------|-------------------|---------|
| yfinance         | 0.2.40      | 0.2.65    | 1.3.0   | MAJOR (0→1)  | HOLD ⚠️           | Skip    |
| pandas           | 2.0.0       | 2.3.2     | 3.0.2   | MAJOR (2→3)  | HOLD ⚠️           | Skip    |
| beautifulsoup4   | 4.14.3      | 4.14.3    | 4.14.3  | floors raised| OK                | batch1  |
| google-genai     | 1.0.0       | 1.68.0    | 2.0.1   | MAJOR (1→2)  | HOLD ⚠️ CRITICAL  | Skip    |
| pydantic         | 2.7.0       | 2.12.5    | 2.13.4  | minor        | SAFE              | Monitor |
| requests         | 2.31.0      | 2.32.5    | 2.33.1  | minor        | SAFE              | Monitor |
| Pillow           | 10.0.0      | 11.3.0    | 12.2.0  | MAJOR (11→12)| HOLD ⚠️           | Skip    |
| playwright       | 1.40.0      | installed | latest  | —            | Not outdated      | —       |
| alpaca-py        | 0.13.0      | installed | latest  | —            | Not outdated      | —       |
| chromadb         | 0.4.0       | installed | latest  | —            | Not outdated      | —       |
| pypdf            | 6.11.0      | 6.11.0    | 6.11.0  | floors raised| OK                | batch1  |
| fastapi          | 0.111.0     | installed | latest  | —            | Not outdated      | —       |
| uvicorn          | 0.29.0      | installed | latest  | —            | Not outdated      | —       |
| supabase         | 2.4.0       | installed | latest  | —            | Not outdated      | —       |
| pytest           | 8.0.0       | 8.4.2     | 9.0.3   | MAJOR (8→9)  | HOLD ⚠️           | Skip    |
| mss              | 10.2.0      | 10.2.0    | 10.2.0  | floors raised| OK                | batch1  |

---

## Key Transitive Dependencies (not in requirements.txt — informational)

| Package                     | Installed | Latest  | Bump     | Note                                      |
|-----------------------------|-----------|---------|----------|-------------------------------------------|
| google-ai-generativelanguage| 0.6.15    | 0.11.0  | minor    | Transitive; watch alongside google-genai  |
| cryptography                | 46.0.5    | 48.0.0  | MAJOR    | TLS/auth layer — wait for supabase update |
| protobuf                    | 5.29.6    | 7.34.1  | MAJOR    | Transitive gRPC dep — do not force        |
| numpy                       | 2.3.3     | 2.4.4   | minor    | SAFE but test with pandas before updating |
| urllib3                     | 2.5.0     | 2.7.0   | minor    | SAFE                                      |
| certifi                     | 2025.8.3  | 2026.4.22| patch   | SAFE — security cert bundle update        |
| aiohttp                     | 3.13.3    | 3.13.5  | patch    | SAFE                                      |
| streamlit                   | 1.49.1    | 1.57.0  | minor    | SAFE — not used in prod API path          |

---

## HOLD Details (requires human review before updating)

### yfinance 0.2.65 → 1.3.0 (CRITICAL HOLD)
**Risk:** The equities scraper (`atlas_agents/equities/equities_scraper.py`) depends
heavily on yfinance screener API shape. Version 1.x introduced breaking changes to
the `yfin.screen()` call signature and response format. Updating without migrating
the scraper will break `GET /equities` data and Loop 5 personalization.
**Action:** Pin to `yfinance>=0.2.40,<1.0.0` in requirements.txt when ready to lock.

### google-genai 1.68.0 → 2.0.1 (CRITICAL HOLD)
**Risk:** The 10-loop engine (query_router.py) and OmegaAgent (atlas_omega.py) use
`google.genai` for all Gemini calls. Version 2.x changed the client initialization
API and streaming interface. Updating blindly will break every ATLAS query.
**Action:** Do NOT update until Anthropic/Google confirms backwards compat or a
migration guide is followed. Test on a feature branch first.

### pandas 2.3.2 → 3.0.2 (HOLD)
**Risk:** Pandas 3 removes `DataFrame.append()`, changes `groupby` behavior, and
introduces Copy-on-Write by default. The equities scraper uses pandas for CSV parsing.
**Action:** Review equities_scraper.py for deprecated APIs before upgrading.

### pytest 8.4.2 → 9.0.3 (HOLD)
**Risk:** pytest 9 may drop legacy plugins or change fixture scoping behavior.
The current suite has 29+ tests — run full suite after upgrade before committing.
**Action:** Upgrade in isolation, run full test suite, revert if any failures.

### Pillow 11.3.0 → 12.2.0 (HOLD)
**Risk:** Used by screen_watcher (mss captures). PIL API changes occasionally break
image mode handling. Low production risk (screen watcher is not in API path).
**Action:** Safe to upgrade in a dev environment first; test screen capture.

---

## Vulnerabilities
| Source | Finding |
|--------|---------|
| `pip list --outdated` | No CVE intelligence (version-only). |
| `python -m pip_audit -r requirements.txt` | **None** reported for resolver output (OsV). |

**Next:** rerun `pip-audit` quarterly or after any major floor change. If OsV/pysec ever reports issues, escalate to **E1 Debugger** with package + CVE id.

---

## Session batch 2026-05-09 (changelog skim, max 3)
Raised floors in `requirements.txt` and reinstalled (`pip install -r requirements.txt`): **beautifulsoup4≥4.14.3**, **mss≥10.2.0**, **pypdf≥6.11.0**. PyPI/release notes indicate minor/patch maintenance (no removals of ATLAS-critical APIs surfaced in skim).

**Regression gate:** `python -m pytest tests/ -q --tb=short` — **834 passed**, 56 skipped (2026-05-09).

---

## Human review backlog — HOLD majors (scheduled)
Human ownership required before merging any of these bumps (see HOLD Details below).

| Priority | Package | Current example | Target | Checkpoint |
|---------|---------|-----------------|--------|------------|
| P0 | google-genai | 1.x | 2.x | Feature branch only; Gemini client API migration; Omega + router smoke |
| P0 | yfinance | 0.2.x | 1.x | Equities scraper / `screen` API migration; pin `<1` until migrated |
| P1 | pandas | 2.x | 3.x | Deprecations (`append`, groupby defaults); equities path |
| P1 | Pillow | 11.x | 12.x | screen_watcher PIL modes |
| P2 | pytest | 8.x | 9.x | Full suite + plugin compatibility |

Suggested cadence: review **google-genai** and **yfinance** first (production query path); **pytest** ahead of widening dev-only upgrades.

---

## Recommended Next Actions (for human review)
1. Pin yfinance upper bound: `yfinance>=0.2.40,<1.0.0` until 1.x migration is complete
2. Watch **google-genai** 2.x release notes — migration guide before bumping floors
3. Keep running `pip-audit -r requirements.txt` quarterly
4. When upgrading pytest 8→9: full suite first; rollback on first failure cluster
5. Next SAFE batch candidates (stay ≤3/session): pydantic/request/tzdata class — check changelogs first
