# Skill: ATLAS scraper → data_cache JSON template

**ID:** SK-13  
**Created:** 2026-05-09  
**Proven:** 2+ (crypto pipeline + shared `agent_utils`; pattern replicated across repo scrapers)

---

## [D] Direction

**What this skill does:** Standard pattern for **no-LLM** fetchers that write **stable `*_latest.json`** plus a **timestamped copy** under `data_cache/`, using shared HTTP retries and JSON helpers.

**When to use it:** Adding a new market or macro snapshot that Omega or other agents read from disk; replacing ad-hoc `requests` scripts.

**Step-by-step workflow**

1. **Placement** — Put the script under `atlas_agents/<domain>/` (or another clear package path). Compute `REPO_ROOT` via `Path(__file__).resolve().parents[...]` and insert `REPO_ROOT` on `sys.path` if you import `atlas_core`.
2. **Constants** — Define `DATA_CACHE_DIR = REPO_ROOT / "data_cache"`, `OUTPUT_STABLE_NAME = "<topic>_latest.json"`, and a `stamped_prefix` for dated files (e.g. `crypto_top50_`).
3. **HTTP** — Use `requests_get_json` or `requests_get_text` from `atlas_core.utils.agent_utils` (timeouts, retries, decode recovery).
4. **Build payload** — Top-level **dict** with `generated_at` (ISO UTC), human `merge_policy` / `sources`, and typed rows (lists of dicts).
5. **Write** — Call `write_cache_json_pair(DATA_CACHE_DIR, payload, stable_filename=..., stamped_prefix=...)`; do not hand-roll two writes unless you have a strong reason.
6. **CLI** — Expose `main(argv) -> int` with `argparse`; `if __name__ == "__main__": raise SystemExit(main(sys.argv[1:]))`.
7. **Omega hook** — If Omega should consume it, add intent + filename + compactor per `omega-internal-knowledge-data-cache`.

**Rules and guardrails**

- Stable filename must stay **constant** so `*_latest.json` is a predictable contract.
- Respect rate limits: sequential pacing or bounded `ThreadPoolExecutor` (see `crypto_scraper.py`).
- Never write API keys into JSON output; no PII in cache blobs intended for models.

---

## [B] Blueprints

**Read before using**

- Reference: `atlas_agents/crypto/crypto_scraper.py` — merge policy, `scrape()`, `write_outputs()`, CLI
- Shared utils: `atlas_core/utils/agent_utils.py` — `requests_get_json`, `write_cache_json_pair`, `REQUEST_TIMEOUT_S`
- Validation skill: `atlas_vault/02-Wiki/Skills/data-validator/SKILL.md` (optional schema checks)
- Omega: `omega-internal-knowledge-data-cache` for filename alignment

**Good output**

```text
Wrote ...\data_cache\crypto_top50_latest.json
Wrote ...\data_cache\crypto_top50_2026-05-09T12-00-00Z.json
```

**Bad output to avoid**

- Raw `requests.get` without backoff while scraping dozens of endpoints.
- Single filename that changes daily (breaks Omega `intent_files`).
- Non-dict JSON root (Omega `_load_internal_knowledge_payload` rejects it).

---

## [S] Solutions

**Compile and help**

```powershell
cd "C:\Users\crist\OneDrive\Desktop\trading platform overview"
python -m py_compile atlas_core\utils\agent_utils.py
python -m py_compile atlas_agents\crypto\crypto_scraper.py
python atlas_agents\crypto\crypto_scraper.py --help
```

**Minimal write pattern**

```python
from pathlib import Path
from atlas_core.utils.agent_utils import write_cache_json_pair

DATA_CACHE_DIR = Path(__file__).resolve().parents[2] / "data_cache"

def write_outputs(payload: dict) -> None:
    write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename="my_topic_latest.json",
        stamped_prefix="my_topic_",
    )
```

**Validation**

- Run evals in `evals.json` after changes to shared utils or reference scraper.
