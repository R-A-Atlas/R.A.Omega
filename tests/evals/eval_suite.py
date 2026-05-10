"""
E10 — Eval Scorer | ATLAS Quality Benchmark
============================================
Runs 4 test queries against the live ATLAS server and scores each
response against a 7-assertion rubric. Saves a JSON report per run with UTC stamp filename.

Usage:
  python tests/evals/eval_suite.py
  python tests/evals/eval_suite.py --query "Analyze TSLA setup"
  python tests/evals/eval_suite.py --dry-run   (schema check only, no live calls)

Requires:
  - ATLAS server running at 127.0.0.1:8000
  - ATLAS_EVAL_TOKEN env var set to a valid JWT (or ATLAS_DISABLE_AUTH=true)
  - Optional: ATLAS_EVAL_INTER_QUERY_SLEEP — seconds to wait between queries (e.g. 65) to reduce 429s
  - Optional: ATLAS_EVAL_429_RETRY_SLEEP — seconds to wait before retrying a single query after HTTP 429 (default 65)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:8000"
QUERY_TIMEOUT_S = 360
EVALS_DIR = Path(__file__).resolve().parent
REPORT_PREFIX = "eval_report_"

DEFAULT_QUERIES = [
    "Analyze NVDA — current setup and trade plan",
    "What is the options play for AAPL next earnings?",
    "Should I buy or rent in Miami right now?",
    "What are the top crypto movers today?",
]

ASSERTION_IDS = (
    "tldr_populated",
    "overall_rating_valid",
    "execution_rules_count_5",
    "scenarios_count_3",
    "scenarios_probability_sum",
    "failure_modes_count_3",
    "api_time_under_300s",
)

VALID_RATINGS = frozenset({"buy", "sell", "hold", "strong_buy"})
PROB_SUM_LO = 0.95
PROB_SUM_HI = 1.05


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth_headers() -> dict[str, str]:
    token = os.environ.get("ATLAS_EVAL_TOKEN", "")
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _server_alive() -> bool:
    try:
        r = requests.get(BASE_URL + "/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _429_retry_sleep_s() -> float:
    return max(0.0, _env_float("ATLAS_EVAL_429_RETRY_SLEEP", 65.0))


def _assertions_for_http_error(
    resp: requests.Response,
    client_elapsed_s: float,
) -> tuple[dict[str, bool], str | None]:
    """
    Non-OK responses: default all assertions False.
    For HTTP 429 (rate limit), set error_class rate_limit and evaluate api_time_under_300s
    from JSON _api_time_s when present, else client elapsed.
    """
    assertions: dict[str, bool] = {k: False for k in ASSERTION_IDS}
    error_class: str | None = None
    if resp.status_code != 429:
        return assertions, error_class
    error_class = "rate_limit"
    time_s = float(client_elapsed_s)
    try:
        body = resp.json()
        api_t = body.get("_api_time_s")
        if api_t is not None:
            time_s = float(api_t)
    except Exception:
        pass
    try:
        assertions["api_time_under_300s"] = float(time_s) < 300.0
    except (TypeError, ValueError):
        assertions["api_time_under_300s"] = float(client_elapsed_s) < 300.0
    return assertions, error_class


def _result_dict_for_http_error(
    query: str,
    resp: requests.Response,
    client_elapsed_s: float,
) -> dict[str, Any]:
    assertions, error_class = _assertions_for_http_error(resp, client_elapsed_s)
    failed = [k for k in ASSERTION_IDS if not assertions[k]]
    out: dict[str, Any] = {
        "query": query,
        "label": "",
        "score": sum(assertions.values()),
        "max_score": 7,
        "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
        "response_time_s": round(client_elapsed_s, 2),
        "assertions": assertions,
        "failed_assertions": failed,
        "intent_route": None,
    }
    if error_class:
        out["error_class"] = error_class
    return out


def _normalize_overall_rating(raw: Any) -> str:
    s = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    if s in ("strongbuy", "strong_buy") or s.endswith("strong_buy"):
        return "strong_buy"
    return s


def _scenarios_probability_sum_ok(scenarios: Any) -> bool:
    if not isinstance(scenarios, list) or len(scenarios) != 3:
        return False
    total = 0.0
    for s in scenarios:
        if not isinstance(s, dict):
            return False
        p = s.get("probability")
        try:
            if p is None or p == "":
                return False
            total += float(p)
        except (TypeError, ValueError):
            return False
    return PROB_SUM_LO <= total <= PROB_SUM_HI


def _score_response(
    data: dict[str, Any],
    *,
    client_elapsed_s: float,
) -> dict[str, Any]:
    """Apply 7-assertion rubric to a POST /query response dict."""
    tldr = data.get("tldr")
    tldr_ok = tldr is not None and str(tldr).strip() != ""

    fr = data.get("final_report") if isinstance(data.get("final_report"), dict) else {}
    rating_norm = _normalize_overall_rating(fr.get("overall_rating"))
    rating_ok = rating_norm in VALID_RATINGS

    er = data.get("execution_rules")
    er_ok = isinstance(er, list) and len(er) == 5

    sc = data.get("scenarios")
    sc_count_ok = isinstance(sc, list) and len(sc) == 3
    sc_prob_ok = _scenarios_probability_sum_ok(sc)

    fm = data.get("failure_modes")
    fm_ok = isinstance(fm, list) and len(fm) == 3

    api_t = data.get("_api_time_s")
    try:
        time_s = float(api_t) if api_t is not None else float(client_elapsed_s)
    except (TypeError, ValueError):
        time_s = float(client_elapsed_s)
    time_ok = time_s < 300.0

    assertions: dict[str, bool] = {
        "tldr_populated": tldr_ok,
        "overall_rating_valid": rating_ok,
        "execution_rules_count_5": er_ok,
        "scenarios_count_3": sc_count_ok,
        "scenarios_probability_sum": sc_prob_ok,
        "failure_modes_count_3": fm_ok,
        "api_time_under_300s": time_ok,
    }

    score = sum(assertions.values())
    failed = [k for k, v in assertions.items() if not v]

    return {
        "score": score,
        "max_score": 7,
        "assertions": assertions,
        "failed_assertions": failed,
        "response_time_s": round(client_elapsed_s, 2),
        "_api_time_s": api_t,
        "time_used_s": round(time_s, 2),
        "intent_route": (data.get("parsed_query") or {}).get("intent_route"),
    }


def run_eval(query: str) -> dict[str, Any]:
    """Run one query, score it, return result dict.

    On HTTP 429, sleeps ATLAS_EVAL_429_RETRY_SLEEP seconds (default 65) and retries once.
    """
    max_attempts = 2
    print(f"  >> Running: {query[:60]}...")
    data: dict[str, Any] | None = None
    elapsed = 0.0
    resp: requests.Response | None = None
    for attempt in range(1, max_attempts + 1):
        t0 = time.monotonic()
        try:
            resp = requests.post(
                BASE_URL + "/query",
                json={"query": query},
                headers=_auth_headers(),
                timeout=QUERY_TIMEOUT_S,
            )
            elapsed = time.monotonic() - t0
            if resp.ok:
                data = resp.json()
                break
            if resp.status_code == 429 and attempt < max_attempts:
                sleep_s = _429_retry_sleep_s()
                print(
                    f"     HTTP 429 — sleeping {sleep_s}s then retry "
                    f"({attempt + 1}/{max_attempts})..."
                )
                time.sleep(sleep_s)
                continue
            return _result_dict_for_http_error(query, resp, elapsed)
        except Exception as exc:
            elapsed = time.monotonic() - t0
            return {
                "query": query,
                "label": "",
                "score": 0,
                "max_score": 7,
                "error": str(exc),
                "response_time_s": round(elapsed, 2),
                "assertions": {k: False for k in ASSERTION_IDS},
                "failed_assertions": list(ASSERTION_IDS),
                "intent_route": None,
            }

    assert data is not None

    scored = _score_response(data, client_elapsed_s=elapsed)
    result = {
        "query": query,
        "label": "",
        "score": scored["score"],
        "max_score": 7,
        "assertions": scored["assertions"],
        "failed_assertions": scored["failed_assertions"],
        "response_time_s": scored["response_time_s"],
        "_api_time_s": scored.get("_api_time_s"),
        "time_used_s": scored.get("time_used_s"),
        "intent_route": scored.get("intent_route"),
    }
    print(
        f"     Score: {result['score']}/7  ({result['response_time_s']}s client, "
        f"_api_time_s={result.get('_api_time_s')})"
    )
    if result["failed_assertions"]:
        print(f"     Failed: {', '.join(result['failed_assertions'])}")
    return result


def _overall_status_pct(pct: float) -> str:
    if pct > 85.0:
        return "GREEN"
    if pct >= 70.0:
        return "YELLOW"
    return "RED"


def _latest_report_path(*, exclude: Path | None = None) -> Path | None:
    reports = sorted(
        EVALS_DIR.glob(f"{REPORT_PREFIX}*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    excl = exclude.resolve() if exclude is not None else None
    for p in reports:
        if excl is not None and p.resolve() == excl:
            continue
        return p
    return None


def assertion_regressions(
    prev_queries: list[dict[str, Any]],
    curr_queries: list[dict[str, Any]],
) -> list[str]:
    """List assertions that were True in prev and are False now (by index)."""
    out: list[str] = []
    for i, cur in enumerate(curr_queries):
        if i >= len(prev_queries):
            break
        p_as = prev_queries[i].get("assertions") or {}
        c_as = cur.get("assertions") or {}
        for key in ASSERTION_IDS:
            if p_as.get(key) is True and c_as.get(key) is False:
                out.append(f"Q{i + 1}:{key}")
    return out


def save_report(
    results: list[dict[str, Any]],
    *,
    iso_timestamp: str,
    labels: list[str],
    report_file_stamp: str,
) -> Path:
    """Write eval report JSON (UTC stamp in filename) and return its path."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = EVALS_DIR / f"{REPORT_PREFIX}{report_file_stamp}.json"

    for r, lbl in zip(results, labels):
        r["label"] = lbl

    total = sum(r.get("score", 0) for r in results)
    max_total = 7 * len(results)
    pct = round(100 * total / max_total, 1) if max_total else 0.0
    status = _overall_status_pct(pct)
    e1 = len(results) > 0 and results[0].get("score", 0) < 5

    prev_path = _latest_report_path(exclude=report_path)
    regressions: list[str] = []
    if prev_path and prev_path.exists():
        try:
            prev_data = json.loads(prev_path.read_text(encoding="utf-8"))
            regressions = assertion_regressions(
                prev_data.get("queries") or [],
                results,
            )
            if total < int(prev_data.get("total_score", 0)):
                regressions.append(
                    f"total_score {prev_data.get('total_score')}->{total} ({prev_path.name})"
                )
        except Exception:
            pass

    report = {
        "timestamp_utc": iso_timestamp,
        "date": date_str,
        "report_file": report_path.name,
        "atlas_version": "Phase2",
        "server": BASE_URL,
        "queries": results,
        "total_score": total,
        "max_total_score": max_total,
        "overall_pct": pct,
        "status": status,
        "e1_escalation": e1,
        "regressions": regressions,
        "previous_report": str(prev_path) if prev_path else None,
    }

    EVALS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path


def print_banner_report(
    iso_timestamp: str,
    results: list[dict[str, Any]],
    labels: list[str],
    total: int,
    max_total: int,
    pct: float,
    status: str,
    regressions: list[str],
    e1: bool,
    report_path: Path | None = None,
) -> None:
    line = "=" * 28
    print(line)
    print(f"EVAL REPORT - {iso_timestamp}")
    print(line)
    for i, (r, lbl) in enumerate(zip(results, labels)):
        failed = r.get("failed_assertions") or []
        fail_txt = f" [{', '.join(failed)}]" if failed else ""
        print(f"{lbl}:    [{r.get('score', 0)}/7]{fail_txt}")
    print(line)
    print(f"OVERALL: {total}/{max_total} ({pct}%)")
    tag = "[GREEN]" if status == "GREEN" else "[YELLOW]" if status == "YELLOW" else "[RED]"
    print(f"STATUS: {tag} {status} (>85% GREEN / 70-85% YELLOW / <70% RED)")
    if e1:
        print("E1 ESCALATION: Query 1 (NVDA) scored below 5/7 - investigate 10-loop / response path.")
    if regressions:
        print(f"REGRESSIONS: {', '.join(regressions)}")
    else:
        print("REGRESSIONS: (none vs prior report)")
    save_disp = report_path if report_path is not None else EVALS_DIR / f"{REPORT_PREFIX}<stamp>.json"
    print(f"SAVE TO: {save_disp}")
    print(line)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ATLAS Eval Scorer (E10)")
    p.add_argument("--query", help="Run a single custom query instead of the default suite")
    p.add_argument("--dry-run", action="store_true", help="Schema check only - no live API calls")
    args = p.parse_args(argv)

    queries = [args.query] if args.query else DEFAULT_QUERIES
    labels = (
        ["Single query"]
        if args.query
        else [
            "Query 1 (NVDA)",
            "Query 2 (AAPL)",
            "Query 3 (Miami)",
            "Query 4 (Crypto)",
        ]
    )

    if args.dry_run:
        print("DRY RUN - validating eval_suite.py loads correctly")
        print(f"  Queries to run: {len(queries)}")
        print(f"  Rubric: 7 assertions ({', '.join(ASSERTION_IDS)})")
        print("  OK")
        return 0

    iso_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report_file_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")

    if not _server_alive():
        print("SERVER_UNAVAILABLE - ATLAS not running at", BASE_URL)
        print("Start with: uvicorn api_server:app --host 127.0.0.1 --port 8000")
        results = []
        for q, lbl in zip(queries, labels):
            results.append({
                "query": q,
                "label": lbl,
                "score": 0,
                "max_score": 7,
                "error": "SERVER_UNAVAILABLE",
                "response_time_s": 0,
                "assertions": {k: False for k in ASSERTION_IDS},
                "failed_assertions": list(ASSERTION_IDS),
                "intent_route": None,
            })
        report_path = save_report(
            results,
            iso_timestamp=iso_ts,
            labels=labels,
            report_file_stamp=report_file_stamp,
        )
        print(f"Skipped report saved: {report_path}")
        return 1

    print(f"ATLAS Eval Suite - {len(queries)} quer{'y' if len(queries) == 1 else 'ies'}")
    print(
        "Tip: full 4-query suites often hit Gemini quota — set ATLAS_EVAL_INTER_QUERY_SLEEP=65 "
        "between queries; on HTTP 429 each query auto-retries once after "
        "ATLAS_EVAL_429_RETRY_SLEEP seconds (default 65)."
    )
    print("-" * 60)

    try:
        inter_sleep = float(os.environ.get("ATLAS_EVAL_INTER_QUERY_SLEEP", "0") or "0")
    except ValueError:
        inter_sleep = 0.0

    results = []
    for i, query in enumerate(queries):
        if i and inter_sleep > 0:
            time.sleep(inter_sleep)
        results.append(run_eval(query))

    total = sum(r.get("score", 0) for r in results)
    max_total = 7 * len(results)
    pct = round(100 * total / max_total, 1) if max_total else 0.0
    status = _overall_status_pct(pct)
    e1 = len(results) > 0 and results[0].get("score", 0) < 5

    report_path = save_report(
        results,
        iso_timestamp=iso_ts,
        labels=labels,
        report_file_stamp=report_file_stamp,
    )
    try:
        report_disk = json.loads(report_path.read_text(encoding="utf-8"))
        regressions = report_disk.get("regressions") or []
    except Exception:
        regressions = []

    print("-" * 60)
    print_banner_report(
        iso_ts,
        results,
        labels,
        total,
        max_total,
        pct,
        status,
        regressions,
        e1,
        report_path=report_path,
    )
    print(f"Report: {report_path}")

    if status == "RED":
        return 1
    if status == "YELLOW":
        return 1
    if e1:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
