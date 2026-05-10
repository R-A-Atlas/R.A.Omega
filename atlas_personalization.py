"""
atlas_personalization.py — Loop 5: user portfolio, paper trades, tracker performance.

When user_id is provided (POST /query): open stock/option rows come from Supabase via
atlas_db.fetch_positions_cache_shapes (except test_user_local → empty portfolio).
When user_id is None (e.g. CLI): legacy positions_cache.json.
Always loads paper_trades.json and atlas_tracker.db from disk where applicable.
Produces a structured context dict plus a narrative block for the batched LLM.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

import atlas_db

log = logging.getLogger(__name__)

# Heuristic tech / growth single-names for concentration callouts (expand as needed)
_TECH_TICKERS = frozenset({
    "AAPL", "MSFT", "GOOGL", "GOOG", "META", "NVDA", "AMD", "INTC", "AVGO", "CRM",
    "TSLA", "SOUN", "PLTR", "SNOW", "CRWD", "PANW", "NOW", "ADBE", "ORCL", "AMZN",
    "SHOP", "SQ", "COIN", "MSTR", "ARM", "RDDT",
})


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _notional_stock(s: dict) -> float:
    return _safe_float(s.get("shares")) * _safe_float(s.get("avg_buy_price"))


def _notional_option(o: dict) -> float:
    return _safe_float(o.get("contracts"), 1.0) * 100.0 * _safe_float(o.get("avg_premium"))


def _load_positions_cache(base: Path) -> tuple[list[dict], list[dict]]:
    stocks: list[dict] = []
    options: list[dict] = []
    pc = base / "positions_cache.json"
    if not pc.is_file():
        return stocks, options
    try:
        raw = json.loads(pc.read_text(encoding="utf-8"))
        stocks = list(raw.get("stocks") or [])
        options = list(raw.get("options") or [])
    except Exception as e:
        log.debug("[personalization] positions_cache read failed: %s", e)
    return stocks, options


def _load_paper_trades(base: Path) -> list[dict]:
    pt = base / "paper_trades.json"
    if not pt.is_file():
        return []
    try:
        raw = json.loads(pt.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception as e:
        log.debug("[personalization] paper_trades read failed: %s", e)
        return []


def _query_tracker_history(base: Path) -> tuple[list[dict], dict[str, Any]]:
    """Return row dicts and a numeric summary from atlas_tracker.db."""
    rows_out: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "db_present": False,
        "row_count": 0,
        "graded_count": 0,
        "win_rate_pct": None,
        "avg_pnl_pct": None,
        "best_ticker": None,
        "best_pnl_pct": None,
        "worst_ticker": None,
        "worst_pnl_pct": None,
        "options_wins": 0,
        "options_graded": 0,
    }
    db = base / "atlas_tracker.db"
    if not db.is_file():
        return rows_out, summary
    summary["db_present"] = True
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT r.ticker AS ticker,
                       r.atlas_rating AS atlas_rating,
                       r.atlas_conf AS atlas_conf,
                       r.recorded_at AS recorded_at,
                       r.setup_tags AS setup_tags,
                       o.pnl_pct AS pnl_pct,
                       o.options_pnl_pct AS options_pnl_pct,
                       o.outcome AS outcome,
                       o.graded_at AS graded_at
                FROM recommendations r
                LEFT JOIN outcomes o ON o.recommendation_id = r.id
                ORDER BY r.recorded_at DESC
                LIMIT 200
                """
            )
            fetched = cur.fetchall()
        except sqlite3.OperationalError:
            cur.execute(
                """
                SELECT ticker, atlas_rating, atlas_conf, recorded_at, setup_tags
                FROM recommendations
                ORDER BY recorded_at DESC
                LIMIT 100
                """
            )
            fetched = cur.fetchall()
            rows_out = [dict(r) for r in fetched]
            summary["row_count"] = len(rows_out)
            conn.close()
            return rows_out, summary

        rows_out = [dict(r) for r in fetched]
        summary["row_count"] = len(rows_out)

        pnls: list[tuple[str, float]] = []
        for row in rows_out:
            t = (row.get("ticker") or "?").upper()
            oc = (row.get("outcome") or "").upper() or None
            pnl = row.get("options_pnl_pct")
            if pnl is None:
                pnl = row.get("pnl_pct")
            if pnl is None:
                continue
            eff = float(pnl)
            if oc in ("WIN", "LOSS", "PARTIAL_WIN") or eff != 0:
                pnls.append((t, eff))

        outcomes_graded = [
            r
            for r in rows_out
            if r.get("outcome")
            and str(r["outcome"]).upper() in ("WIN", "LOSS", "PARTIAL_WIN")
        ]
        if outcomes_graded:
            hard_wins = sum(
                1
                for r in outcomes_graded
                if str(r.get("outcome") or "").upper() in ("WIN", "PARTIAL_WIN")
            )
            summary["graded_count"] = len(outcomes_graded)
            summary["win_rate_pct"] = round(hard_wins / len(outcomes_graded) * 100, 1)

        if pnls:
            summary["avg_pnl_pct"] = round(sum(p for _, p in pnls) / len(pnls), 2)
            best = max(pnls, key=lambda x: x[1])
            worst = min(pnls, key=lambda x: x[1])
            summary["best_ticker"], summary["best_pnl_pct"] = best[0], round(best[1], 2)
            summary["worst_ticker"], summary["worst_pnl_pct"] = worst[0], round(worst[1], 2)

        opt_rows = [r for r in rows_out if r.get("options_pnl_pct") is not None]
        if opt_rows:
            opt_out = [
                r
                for r in opt_rows
                if r.get("outcome")
                and str(r["outcome"]).upper() in ("WIN", "LOSS", "PARTIAL_WIN")
            ]
            summary["options_graded"] = len(opt_out)
            if opt_out:
                ow = sum(
                    1
                    for r in opt_out
                    if str(r.get("outcome") or "").upper() in ("WIN", "PARTIAL_WIN")
                )
                summary["options_win_rate_pct"] = round(
                    ow / len(opt_out) * 100, 1
                )
                op_vals = [float(r["options_pnl_pct"]) for r in opt_out]
                summary["options_avg_pnl_pct"] = round(
                    sum(op_vals) / len(op_vals), 2
                )
    except Exception as e:
        log.debug("[personalization] tracker query failed: %s", e)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    return rows_out, summary


def _allocation_pct(stocks: list[dict], options: list[dict]) -> dict[str, float]:
    notionals: dict[str, float] = {}
    for s in stocks:
        t = (s.get("ticker") or "").upper()
        if not t:
            continue
        notionals[t] = notionals.get(t, 0.0) + _notional_stock(s)
    for o in options:
        t = (o.get("ticker") or "").upper()
        if not t:
            continue
        notionals[t] = notionals.get(t, 0.0) + _notional_option(o)
    total = sum(notionals.values())
    if total <= 0:
        return {k: 0.0 for k in notionals}
    return {k: round(v / total * 100, 1) for k, v in sorted(notionals.items(), key=lambda x: -x[1])}


def _risk_flags(
    allocation: dict[str, float],
    stocks: list[dict],
    options: list[dict],
    tracker_summary: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    if allocation:
        top, pct = next(iter(allocation.items()))
        if pct >= 55:
            flags.append(f"Heavy single-name concentration: ~{pct}% notional in {top}.")
    opt_notional = sum(_notional_option(o) for o in options)
    stk_notional = sum(_notional_stock(s) for s in stocks)
    book = opt_notional + stk_notional
    if book > 0 and opt_notional / book >= 0.65:
        flags.append("Book is mostly options by notional — theta/IV risk dominant.")

    tech_n = stk_notional + sum(
        _notional_option(o) for o in options if (o.get("ticker") or "").upper() in _TECH_TICKERS
    )
    tech_s = sum(_notional_stock(s) for s in stocks if (s.get("ticker") or "").upper() in _TECH_TICKERS)
    tech_total = tech_n + tech_s
    if book > 0 and tech_total / book >= 0.5:
        flags.append("High tech/growth exposure in open book — watch sector correlation.")

    wr = tracker_summary.get("win_rate_pct")
    n = tracker_summary.get("graded_count") or 0
    if wr is not None and n >= 8 and wr < 42:
        flags.append(
            f"Historical ATLAS graded win rate is low ({wr}% over {n} outcomes) — favor tighter risk control."
        )
    owr = tracker_summary.get("options_win_rate_pct")
    og = tracker_summary.get("options_graded") or 0
    if owr is not None and og >= 6 and owr < 40:
        flags.append(
            f"Options outcomes in tracker skew weak ({owr}% wins on {og} grades) — prefer defined risk / smaller size."
        )
    return flags


def _format_prompt_block(
    user_state: str,
    stocks: list[dict],
    options: list[dict],
    paper: list[dict],
    tracker_summary: dict[str, Any],
    tracker_rows_sample: list[dict],
    allocation: dict[str, float],
    risk_flags: list[str],
) -> str:
    lines: list[str] = [
        "USER PORTFOLIO & RISK CONTEXT (local ATLAS data — use for personalization)",
        "=" * 60,
        f"User state: {user_state}",
        "",
        "OPEN POSITIONS (positions_cache.json):",
    ]
    if not stocks and not options:
        lines.append("  (none — treat as new or unlinked account; still deliver full analysis.)")
    else:
        for s in stocks:
            lines.append(
                f"  STOCK {s.get('ticker','?')}: {s.get('shares','?')} sh @ "
                f"${s.get('avg_buy_price','?')}  (notional ~${_notional_stock(s):,.0f})"
            )
        for o in options:
            lines.append(
                f"  OPTION {o.get('ticker','?')} {str(o.get('option_type','?')).upper()} "
                f"${o.get('strike','?')} exp {o.get('expiry','?')}: "
                f"{o.get('contracts',1)}× @ ${o.get('avg_premium','?')}/sh prem "
                f"(notional ~${_notional_option(o):,.0f})"
            )
    lines.append("")
    if allocation:
        lines.append("ALLOCATION (notional % by ticker):")
        for t, p in list(allocation.items())[:12]:
            lines.append(f"  {t}: {p}%")
        lines.append("")
    lines.append(f"PAPER / SIMULATED (paper_trades.json): {len(paper)} record(s)")
    open_paper = [t for t in paper if str(t.get("state", "")).upper() == "OPEN"][
        :8
    ]
    if open_paper:
        for t in open_paper:
            lines.append(
                f"  OPEN {t.get('ticker','?')}  state={t.get('state')}  "
                f"entry={t.get('entry_price','?')}"
            )
    lines.append("")
    lines.append("ATLAS TRACKER DB (recommendations + outcomes, recent sample):")
    if not tracker_summary.get("db_present"):
        lines.append("  (no atlas_tracker.db — no historical ATLAS grade stats)")
    else:
        lines.append(
            f"  Rows loaded: {tracker_summary.get('row_count', 0)} | "
            f"Graded outcomes: {tracker_summary.get('graded_count', 0)}"
        )
        if tracker_summary.get("win_rate_pct") is not None:
            lines.append(f"  Win rate (outcome-based): {tracker_summary['win_rate_pct']}%")
        if tracker_summary.get("avg_pnl_pct") is not None:
            lines.append(f"  Avg P&L (when numeric): {tracker_summary['avg_pnl_pct']}%")
        if tracker_summary.get("best_ticker"):
            lines.append(
                f"  Best: {tracker_summary['best_ticker']} {tracker_summary.get('best_pnl_pct')}%"
            )
        if tracker_summary.get("worst_ticker"):
            lines.append(
                f"  Worst: {tracker_summary['worst_ticker']} {tracker_summary.get('worst_pnl_pct')}%"
            )
        if tracker_summary.get("options_graded"):
            lines.append(
                f"  Options-graded count: {tracker_summary['options_graded']} | "
                f"options win rate: {tracker_summary.get('options_win_rate_pct', 'n/a')}%"
            )
    if tracker_rows_sample[:5]:
        lines.append("  Recent rows (abbrev):")
        for r in tracker_rows_sample[:5]:
            lines.append(
                f"    {r.get('ticker')} | {r.get('atlas_rating') or r.get('rating')} | "
                f"outcome={r.get('outcome')} | "
                f"pnl={r.get('pnl_pct')}% opt={r.get('options_pnl_pct')}%"
            )
    lines.append("")
    lines.append("RISK FLAGS (pre-computed hints — mention in memo/rules if relevant):")
    if not risk_flags:
        lines.append("  (none beyond normal single-name risk)")
    else:
        for f in risk_flags:
            lines.append(f"  • {f}")
    return "\n".join(lines)


def build_personalization_bundle(
    base_dir: Optional[Path] = None,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build Loop 5 payload: context for API/UI and a long-form prompt for the batched LLM.

    user_id:
      - None: legacy positions_cache.json + paper_trades (e.g. CLI).
      - atlas_db.TEST_USER_LOCAL: empty stocks/options/paper for auth-disabled dev.
      - else: Supabase positions; paper_trades still from disk.
    """
    base = base_dir or Path(__file__).resolve().parent
    if user_id == atlas_db.TEST_USER_LOCAL:
        stocks: list[dict] = []
        options: list[dict] = []
        paper: list[dict] = []
    elif user_id:
        stocks, options = atlas_db.fetch_positions_cache_shapes(user_id)
        paper = _load_paper_trades(base)
    else:
        stocks, options = _load_positions_cache(base)
        paper = _load_paper_trades(base)

    tracker_rows, tracker_summary = _query_tracker_history(base)

    positions_flat: list[dict[str, Any]] = (
        [{"_type": "stock", **s} for s in stocks]
        + [{"_type": "option", **o} for o in options]
    )
    allocation = _allocation_pct(stocks, options)
    risk_flags = _risk_flags(allocation, stocks, options, tracker_summary)

    has_book = bool(stocks or options or paper)
    user_state = "has_portfolio_data" if has_book else "new_user_no_local_positions"

    slim_tracker = []
    for r in tracker_rows[:40]:
        slim_tracker.append(
            {
                "ticker": r.get("ticker"),
                "atlas_rating": r.get("atlas_rating") or r.get("rating"),
                "atlas_conf": r.get("atlas_conf") or r.get("confidence"),
                "pnl_pct": r.get("pnl_pct"),
                "options_pnl_pct": r.get("options_pnl_pct"),
                "outcome": r.get("outcome"),
                "recorded_at": r.get("recorded_at"),
                "setup_tags": r.get("setup_tags"),
            }
        )

    win_rate = tracker_summary.get("win_rate_pct")
    report_personalization = {
        "user_state": user_state,
        "open_stocks": len(stocks),
        "open_options": len(options),
        "paper_trade_records": len(paper),
        "tracker_db": tracker_summary.get("db_present", False),
        "tracker_win_rate_pct": win_rate,
        "tracker_graded_n": tracker_summary.get("graded_count", 0),
        "concentration_top_ticker": next(iter(allocation.keys()), None) if allocation else None,
        "concentration_top_pct": next(iter(allocation.values()), None) if allocation else None,
    }

    portfolio_risk_prompt = _format_prompt_block(
        user_state,
        stocks,
        options,
        paper,
        tracker_summary,
        tracker_rows,
        allocation,
        risk_flags,
    )

    context = {
        "positions": positions_flat,
        "paper_trades": paper[:50],
        "tracker_patterns": slim_tracker,
        "tracker_summary": tracker_summary,
        "allocation_pct_by_ticker": allocation,
        "risk_flags": risk_flags,
    }

    return {
        "user_state": user_state,
        "stocks": stocks,
        "options": options,
        "context": context,
        "tracker_summary": tracker_summary,
        "portfolio_risk_prompt": portfolio_risk_prompt,
        "report_personalization_meta": report_personalization,
    }

