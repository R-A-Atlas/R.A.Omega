"""
dashboard_server.py - ATLAS Live Dashboard Server

Research-first: serves deep reports and manual tracking only — no broker orders or automated trading.

Runs a lightweight HTTP server at http://localhost:8765
No npm, no node_modules, no build step. Pure Python stdlib.

Background thread refreshes dashboard_state.json every 30 seconds by
polling live ATLAS modules (regime, tracker, memory, tuner) and building
manual portfolio values from positions_cache.json (no broker API).

Usage:
    python dashboard_server.py              # start server + open browser
    python dashboard_server.py --no-browser # headless / remote machine

Access from phone (same wifi):
    http://<your-PC-local-IP>:8765

ATLAS Financial Intelligence UI (v4 when present, else v2):
    http://localhost:8765/v2
    http://localhost:8765/atlas_dashboard_v2.html — legacy v2 only
    Requires python api_server.py on port 8000 for /omega queries.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import date, datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dashboard")

PORT       = 8765
STATE_FILE = Path(__file__).parent / "dashboard_state.json"
HTML_FILE  = Path(__file__).parent / "dashboard.html"
ATLAS_V2_HTML = Path(__file__).resolve().parent / "atlas_dashboard_v2.html"
ATLAS_V4_HTML = Path(__file__).resolve().parent / "atlas_dashboard_v4.html"
REFRESH_S  = 30   # seconds between state updates


def _atlas_intel_html_path() -> Path:
    return ATLAS_V4_HTML if ATLAS_V4_HTML.is_file() else ATLAS_V2_HTML


# ─────────────────────────────────────────────────────────────────────────────
# State builder - pulls from all live ATLAS modules
# ─────────────────────────────────────────────────────────────────────────────

def _safe(fn, default=None):
    """Call fn(), return default on any exception."""
    try:
        return fn()
    except Exception as e:
        log.debug("safe-call failed: %s", e)
        return default


SCRIPT_DIR = Path(__file__).resolve().parent


def _load_positions_cache_raw() -> dict:
    p = SCRIPT_DIR / "positions_cache.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _match_option_expiry(user_exp: str, available) -> str | None:
    """Pick the yfinance options expiration string that matches what the user saved."""
    if not available:
        return None
    exps = tuple(available)
    u = (user_exp or "").strip()
    if not u:
        return None
    if u in exps:
        return u
    u_flat = u.replace("/", "-")
    for e in exps:
        if u_flat in e or e[:10] == u_flat[:10]:
            return e
    from datetime import datetime

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            d = datetime.strptime(u[:10], fmt).date()
            iso = d.isoformat()
            for e in exps:
                if e.startswith(iso):
                    return e
        except ValueError:
            continue
    return None


def _yfinance_option_premium_per_share(
    under: str,
    strike: float,
    opt_type: str,
    expiry_raw: str,
) -> float | None:
    """Last / mid mark for one leg (per-share premium), or None."""
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        tk = yf.Ticker((under or "").upper().strip())
        exps = tk.options
        if not exps:
            return None
        exp = _match_option_expiry(expiry_raw, exps)
        if not exp:
            return None
        chain = tk.option_chain(exp)
        df = chain.calls if (opt_type or "call").lower() == "call" else chain.puts
        if df is None or getattr(df, "empty", True):
            return None
        i = (df["strike"] - s).abs().idxmin()
        row = df.loc[i]
        last = row.get("lastPrice")
        if last is not None and float(last) > 0:
            return round(float(last), 4)
        bid = row.get("bid")
        ask = row.get("ask")
        try:
            b = float(bid) if bid is not None else None
            a = float(ask) if ask is not None else None
        except (TypeError, ValueError):
            b = a = None
        if b is not None and a is not None and b > 0 and a > 0:
            return round((b + a) / 2, 4)
        if a is not None and float(a) > 0:
            return round(float(a), 4)
        if b is not None and float(b) > 0:
            return round(float(b), 4)
    except Exception:
        log.debug("option quote failed for %s", under, exc_info=True)
    return None


def _enrich_positions_cache_live(cache: dict) -> dict:
    """
    Fill current_price for manual stocks + options using yfinance (each dashboard refresh).
    Does not write back to positions_cache.json — only affects live /state payload.
    """
    if not cache or not isinstance(cache, dict):
        return cache
    try:
        import yfinance as yf
    except Exception:
        return cache

    stocks = []
    for s in cache.get("stocks") or []:
        if not isinstance(s, dict):
            stocks.append(s)
            continue
        s2 = dict(s)
        t = (s2.get("ticker") or "").strip().upper()
        if t:
            try:
                fi = getattr(yf.Ticker(t), "fast_info", {}) or {}
                last = fi.get("last_price") or fi.get("regular_market_price")
                if last is not None:
                    px = float(last)
                    s2["current_price"] = px
                    try:
                        sh = float(s2.get("shares") or 0)
                        s2["market_value"] = round(sh * px, 2)
                    except (TypeError, ValueError):
                        pass
            except Exception:
                pass
        stocks.append(s2)

    options = []
    for o in cache.get("options") or []:
        if not isinstance(o, dict):
            options.append(o)
            continue
        o2 = dict(o)
        t = (o2.get("ticker") or "").strip().upper()
        try:
            strike = float(o2.get("strike") or 0)
        except (TypeError, ValueError):
            strike = 0.0
        typ = (o2.get("option_type") or "call").lower()
        exp = o2.get("expiry") or ""
        if t and strike > 0 and exp:
            mark = _yfinance_option_premium_per_share(t, strike, typ, str(exp))
            if mark is not None:
                o2["current_price"] = mark
        options.append(o2)

    return {
        **cache,
        "stocks": stocks,
        "options": options,
    }


def _sector_data_map(sectors: list) -> dict[str, dict]:
    sd: dict[str, dict] = {}
    for s in sectors or []:
        sym = (s.get("ticker") or "").strip().upper()
        if not sym:
            continue
        t5 = s.get("change_5d")
        if t5 is None:
            t5 = s.get("change_pct")
        try:
            t5f = float(t5) if t5 is not None else 0.0
        except (TypeError, ValueError):
            t5f = 0.0
        sd[sym] = {
            "trend_5d": t5f,
            "signal":   s.get("signal") or "—",
        }
    return sd


def _congress_sample(limit: int = 48) -> list[dict]:
    cf = SCRIPT_DIR / "congress_cache" / "all_trades.json"
    if not cf.exists():
        return []
    try:
        all_t = json.loads(cf.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(all_t, list):
        return []
    out: list[dict] = []
    for t in all_t[:limit]:
        if not isinstance(t, dict):
            continue
        party_raw = (t.get("party") or "").lower()
        if "democrat" in party_raw:
            p_letter = "D"
        elif "republican" in party_raw:
            p_letter = "R"
        else:
            p_letter = "I"
        out.append({
            "politician":  t.get("name") or "?",
            "party":       p_letter,
            "transaction": (t.get("tx_type") or "?").upper(),
            "amount":      t.get("amount") or "—",
            "ticker":      t.get("ticker") or "?",
            "trade_date":  t.get("tx_date") or t.get("trade_date") or "?",
        })
    return out


def _volume_profile_bundle(ticker: str) -> dict:
    if not ticker:
        return {}
    try:
        import volume_profile as vp

        d = vp.calculate_volume_profile(ticker, lookback_days=30)
        if not isinstance(d, dict) or d.get("error") or d.get("poc") is None:
            return {}
        d = dict(d)
        d.setdefault("ticker", ticker.upper())
        return d
    except Exception:
        return {}


def _watcher_meta(cache: dict) -> tuple[bool, dict]:
    p = SCRIPT_DIR / "positions_cache.json"
    watcher_last: dict = {}
    if cache:
        snap = cache.get("snapshots") or []
        last_snap = snap[-1] if snap else {}
        watcher_last = {
            "timestamp": cache.get("last_seen"),
            "page":      (last_snap.get("page_type") if isinstance(last_snap, dict) else None) or "—",
            "extracted": len(cache.get("options") or []),
        }
    active = False
    try:
        if p.exists():
            active = (time.time() - p.stat().st_mtime) < 300.0
    except OSError:
        pass
    return active, watcher_last


def _list_reports() -> list[str]:
    rd = SCRIPT_DIR / "reports"
    if not rd.is_dir():
        return []
    return sorted(
        f.name for f in rd.iterdir()
        if f.is_file() and f.suffix.lower() in (".html", ".htm")
    )


RESEARCH_HISTORY_FILE = SCRIPT_DIR / "research_history.json"
PENDING_DEEP_FILE     = SCRIPT_DIR / "atlas_pending_deep.json"
TRACKING_STATE_FILE   = SCRIPT_DIR / "atlas_tracking_state.json"
WEEKLY_INSIGHT_FILE    = SCRIPT_DIR / "weekly_insight.json"
PENDING_WEEKLY_FILE    = SCRIPT_DIR / "atlas_pending_weekly.json"
WEEKLY_REPORT_HREF     = "/deep_reports/WEEKLY_INSIGHT.html"
WEEKLY_REPORTS_INDEX   = SCRIPT_DIR / "weekly_reports_index.json"


def _read_pending_weekly() -> dict | None:
    if not PENDING_WEEKLY_FILE.is_file():
        return None
    try:
        data = json.loads(PENDING_WEEKLY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _blocking_pending_weekly(max_age_s: float = 7200.0) -> dict | None:
    if not PENDING_WEEKLY_FILE.is_file():
        return None
    try:
        age = time.time() - PENDING_WEEKLY_FILE.stat().st_mtime
        if age > max_age_s:
            log.warning("Clearing stale weekly-insight pending flag (age %.0fs)", age)
            _clear_pending_weekly()
            return None
        data = json.loads(PENDING_WEEKLY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        _clear_pending_weekly()
        return None


def _set_pending_weekly(theme: str) -> None:
    PENDING_WEEKLY_FILE.write_text(
        json.dumps({
            "theme":      (theme or "")[:500],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status":     "running",
        }, indent=2),
        encoding="utf-8",
    )


def _clear_pending_weekly() -> None:
    try:
        if PENDING_WEEKLY_FILE.is_file():
            PENDING_WEEKLY_FILE.unlink()
    except OSError:
        pass


def _load_weekly_insight_ui() -> dict:
    base: dict = {
        "status":       "idle",
        "message":      "",
        "updated_at":   None,
        "theme":        "",
        "budget":       None,
        "tickers":      [],
        "report_href":  WEEKLY_REPORT_HREF,
        "archive_href": "",
        "pending":      None,
    }
    if WEEKLY_INSIGHT_FILE.is_file():
        try:
            disk = json.loads(WEEKLY_INSIGHT_FILE.read_text(encoding="utf-8"))
            if isinstance(disk, dict):
                base.update(disk)
        except Exception:
            pass
    pend = _read_pending_weekly()
    base["pending"] = pend
    if pend:
        base["status"] = "running"
        base["message"] = (
            "Market scan is running — several minutes. Each ticker gets full deep research; "
            "combined + archived reports appear under Weekly reports."
        )
    return base


def _save_weekly_insight_meta(
    theme: str,
    budget: float,
    results: list,
    source_report: str,
    *,
    archive_href: str = "",
) -> None:
    tickers: list[dict] = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        syn = r.get("synthesis") or {}
        t = (syn.get("ticker") or r.get("ticker") or "").upper().strip()
        if not t:
            continue
        tp = syn.get("trade_plan") or {}
        tickers.append({
            "ticker":      t,
            "rating":      syn.get("overall_rating"),
            "confidence":  syn.get("confidence"),
            "action":      tp.get("action"),
        })
    payload = {
        "status":        "ready" if tickers else "empty",
        "message":       (f"{len(tickers)} names in this scan — open the combined report, then each full deep report.")
        if tickers
        else "Discovery returned no candidates — try a different theme or check API quota.",
        "updated_at":    datetime.now(timezone.utc).isoformat(),
        "theme":         theme,
        "budget":        budget,
        "tickers":       tickers,
        "report_href":   WEEKLY_REPORT_HREF,
        "archive_href":  archive_href or "",
        "source_file":   source_report,
    }
    WEEKLY_INSIGHT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_weekly_reports_archive(limit: int = 50) -> list[dict]:
    if not WEEKLY_REPORTS_INDEX.is_file():
        return []
    try:
        data = json.loads(WEEKLY_REPORTS_INDEX.read_text(encoding="utf-8"))
        ent = data.get("entries") if isinstance(data, dict) else []
        if not isinstance(ent, list):
            return []
        ent = [e for e in ent if isinstance(e, dict)]
        ent.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return ent[:limit]
    except Exception:
        return []


def _append_weekly_reports_archive(
    theme: str,
    budget: float,
    tickers_syms: list[str],
    archive_href: str,
    latest_href: str,
    source_file: str,
) -> None:
    entries: list = []
    if WEEKLY_REPORTS_INDEX.is_file():
        try:
            raw = json.loads(WEEKLY_REPORTS_INDEX.read_text(encoding="utf-8"))
            entries = list(raw.get("entries") or []) if isinstance(raw, dict) else []
        except Exception:
            entries = []
    now_iso = datetime.now(timezone.utc).isoformat()
    title = (theme or "Market scan").strip()
    if len(title) > 140:
        title = title[:137] + "…"
    entries.insert(0, {
        "created_at":    now_iso,
        "title":         title,
        "theme":         (theme or "")[:800],
        "budget":        budget,
        "tickers":       [t.upper().strip() for t in tickers_syms if (t or "").strip()][:32],
        "ticker_count":  len([t for t in tickers_syms if (t or "").strip()]),
        "archive_href":  archive_href,
        "latest_href":   latest_href,
        "source_file":   source_file,
    })
    entries = entries[:120]
    WEEKLY_REPORTS_INDEX.write_text(json.dumps({"entries": entries}, indent=2), encoding="utf-8")


def _load_research_history(limit: int = 80) -> list[dict]:
    if not RESEARCH_HISTORY_FILE.is_file():
        return []
    try:
        data = json.loads(RESEARCH_HISTORY_FILE.read_text(encoding="utf-8"))
        ent = data.get("entries") if isinstance(data, dict) else []
        if not isinstance(ent, list):
            return []
        ent = [e for e in ent if isinstance(e, dict)]
        ent.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
        return ent[:limit]
    except Exception:
        return []


def _append_research_history(ticker: str, rel_path: str, kind: str) -> None:
    tick = (ticker or "").upper().strip()
    rel = (rel_path or "").replace("\\", "/").strip()
    if not tick or not rel:
        return
    entries: list = []
    if RESEARCH_HISTORY_FILE.is_file():
        try:
            raw = json.loads(RESEARCH_HISTORY_FILE.read_text(encoding="utf-8"))
            entries = list(raw.get("entries") or []) if isinstance(raw, dict) else []
        except Exception:
            entries = []
    entries.append({
        "ticker":      tick,
        "kind":        kind,
        "path":        rel,
        "created_at":  datetime.now(timezone.utc).isoformat(),
    })
    entries = entries[-300:]
    RESEARCH_HISTORY_FILE.write_text(
        json.dumps({"entries": entries}, indent=2),
        encoding="utf-8",
    )


def _upsert_research_history(ticker: str, rel_path: str, kind: str) -> None:
    """Single catalog row per (ticker, kind) so repeat runs do not spam history."""
    tick = (ticker or "").upper().strip()
    rel = (rel_path or "").replace("\\", "/").strip()
    if not tick or not rel:
        return
    entries: list = []
    if RESEARCH_HISTORY_FILE.is_file():
        try:
            raw = json.loads(RESEARCH_HISTORY_FILE.read_text(encoding="utf-8"))
            entries = list(raw.get("entries") or []) if isinstance(raw, dict) else []
        except Exception:
            entries = []
    now_iso = datetime.now(timezone.utc).isoformat()
    entries = [
        e for e in entries
        if isinstance(e, dict) and not (e.get("ticker") == tick and e.get("kind") == kind)
    ]
    entries.append({
        "ticker":     tick,
        "kind":       kind,
        "path":       rel,
        "created_at": now_iso,
        "updated_at": now_iso,
    })
    entries = entries[-300:]
    RESEARCH_HISTORY_FILE.write_text(
        json.dumps({"entries": entries}, indent=2),
        encoding="utf-8",
    )


def _safe_public_href(stored_path: str) -> str:
    """Turn stored relative path into dashboard URL path."""
    p = (stored_path or "").replace("\\", "/").strip().lstrip("/")
    if p.lower().startswith("deep_reports/"):
        return "/" + p
    if p.lower().startswith("reports/"):
        return "/" + p
    return "/reports/" + Path(p).name


def _read_pending_deep() -> dict | None:
    if not PENDING_DEEP_FILE.is_file():
        return None
    try:
        data = json.loads(PENDING_DEEP_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _set_pending_deep(ticker: str) -> None:
    PENDING_DEEP_FILE.write_text(
        json.dumps({
            "ticker":     ticker.upper().strip(),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status":     "running",
        }, indent=2),
        encoding="utf-8",
    )


def _clear_pending_deep() -> None:
    try:
        if PENDING_DEEP_FILE.is_file():
            PENDING_DEEP_FILE.unlink()
    except OSError:
        pass


def _blocking_pending_deep(max_age_s: float = 7200.0) -> dict | None:
    """Return pending deep-research payload if a run is active; clear stale lock files."""
    if not PENDING_DEEP_FILE.is_file():
        return None
    try:
        age = time.time() - PENDING_DEEP_FILE.stat().st_mtime
        if age > max_age_s:
            log.warning("Clearing stale pending deep-research flag (age %.0fs)", age)
            _clear_pending_deep()
            return None
        data = json.loads(PENDING_DEEP_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        _clear_pending_deep()
        return None


def _report_catalog_for_ui() -> list[dict]:
    """User-facing report index (no raw filenames in labels)."""
    dr = SCRIPT_DIR / "deep_reports"
    if not dr.is_dir():
        return []
    by_ticker: dict[str, dict] = {}
    for html in dr.glob("*_deep.html"):
        if not html.is_file() or html.name.upper().startswith("DISCOVERY"):
            continue
        stem = html.stem
        if not stem.endswith("_deep"):
            continue
        t = stem[:-5].upper()
        try:
            mt = html.stat().st_mtime
        except OSError:
            continue
        by_ticker[t] = {
            "ticker":        t,
            "href":          f"/deep_reports/{html.name}",
            "title":         f"{t} research",
            "updated_at":    datetime.fromtimestamp(mt, tz=timezone.utc).isoformat(),
            "sessions_note": None,
        }
    for logf in dr.glob("*_research_log.json"):
        t = logf.name.replace("_research_log.json", "").upper()
        try:
            raw = json.loads(logf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(raw, list) or not raw:
            continue
        latest = raw[0] if isinstance(raw[0], dict) else {}
        at = latest.get("at") or latest.get("at_display")
        if t not in by_ticker:
            by_ticker[t] = {
                "ticker":        t,
                "href":          f"/deep_reports/{t}_deep.html",
                "title":         f"{t} research",
                "updated_at":    datetime.now(timezone.utc).isoformat(),
                "sessions_note": None,
            }
        note = latest.get("source") or "session"
        by_ticker[t]["last_session_at"] = at
        by_ticker[t]["sessions_note"] = f"Last activity: {note}"
    return sorted(by_ticker.values(), key=lambda x: x.get("updated_at") or "", reverse=True)


def _load_atlas_tracking() -> dict:
    base = {"last_watchlist_deep": {}, "last_position_pulse": {}}
    if not TRACKING_STATE_FILE.is_file():
        return dict(base)
    try:
        data = json.loads(TRACKING_STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(base)
        data.setdefault("last_watchlist_deep", {})
        data.setdefault("last_position_pulse", {})
        return data
    except Exception:
        return dict(base)


def _save_atlas_tracking(data: dict) -> None:
    TRACKING_STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _watchlist_tickers_raw() -> list[str]:
    wl = SCRIPT_DIR / "watchlist.json"
    if not wl.is_file():
        return []
    try:
        data = json.loads(wl.read_text(encoding="utf-8"))
        return [
            str(x).upper().strip()
            for x in (data.get("tickers") or [])
            if str(x).strip()
        ]
    except Exception:
        return []


def _position_underlyings_from_cache() -> set[str]:
    out: set[str] = set()
    cache = _load_positions_cache_raw()
    for s in cache.get("stocks") or []:
        if not isinstance(s, dict):
            continue
        t = (s.get("ticker") or "").upper().strip()
        if t:
            out.add(t)
    for o in cache.get("options") or []:
        if not isinstance(o, dict):
            continue
        t = (o.get("ticker") or "").upper().strip()
        if t:
            out.add(t)
    return out


def _research_scheduler_tick() -> None:
    """Daily watchlist deep research; faster delta+note pulses for open positions."""
    now = time.time()
    tr = _load_atlas_tracking()
    day_s   = 86400.0
    pulse_s = 3 * 3600.0

    for t in _watchlist_tickers_raw():
        last = float(tr["last_watchlist_deep"].get(t, 0))
        if now - last < day_s:
            continue
        if _blocking_pending_deep() is not None:
            log.debug("[scheduler] defer daily deep for %s — research already in progress", t)
            continue
        tr["last_watchlist_deep"][t] = now
        _save_atlas_tracking(tr)
        log.info("[scheduler] daily deep research queued: %s", t)

        def _run_deep(tk: str = t) -> None:
            try:
                _set_pending_deep(tk)
                import deep_research as dr

                res = dr.research_ticker(tk, budget=100.0)
                if res:
                    outp = dr.write_report(res, budget=100.0)
                    rel = outp.relative_to(SCRIPT_DIR).as_posix()
                    _upsert_research_history(tk, rel, "deep_research")
            except Exception as e:
                log.error("[scheduler] deep %s: %s", tk, e)
            finally:
                _clear_pending_deep()
            try:
                _write_state(build_state())
            except Exception:
                pass

        threading.Thread(target=_run_deep, daemon=True).start()

    for t in _position_underlyings_from_cache():
        last = float(tr["last_position_pulse"].get(t, 0))
        if now - last < pulse_s:
            continue
        tr["last_position_pulse"][t] = now
        _save_atlas_tracking(tr)
        log.info("[scheduler] position tracking pulse: %s", t)

        def _run_pulse(tk: str = t) -> None:
            try:
                import web_scraper
                import delta_reporter
                from deep_research import append_research_log_note

                scrape = web_scraper.gather_all(tk)
                delta_reporter.scan_ticker(tk, scrape)
                append_research_log_note(
                    tk,
                    "Automated intraday refresh: news and technical data were rescanned. "
                    "Review the timeline in your living report.",
                    source="intraday_tracking",
                )
            except Exception as e:
                log.error("[scheduler] pulse %s: %s", tk, e)
            try:
                _write_state(build_state())
            except Exception:
                pass

        threading.Thread(target=_run_pulse, daemon=True).start()


def _research_scheduler_loop() -> None:
    time.sleep(60)
    while True:
        try:
            _research_scheduler_tick()
        except Exception as e:
            log.error("research_scheduler: %s", e)
        time.sleep(600)



def _manual_stocks_from_cache(cache: dict) -> list[dict]:
    out: list[dict] = []
    for s in cache.get("stocks") or []:
        if not isinstance(s, dict):
            continue
        t = (s.get("ticker") or "").strip().upper()
        if not t:
            continue
        out.append({
            "ticker":           t,
            "shares":           s.get("shares"),
            "avg_buy_price":    s.get("avg_buy_price"),
            "current_price":    s.get("current_price"),
            "market_value":     s.get("market_value"),
        })
    return out


def _options_from_cache(cache: dict) -> list[dict]:
    out: list[dict] = []
    for o in cache.get("options") or []:
        if not isinstance(o, dict):
            continue
        cp = o.get("current_price")
        out.append({
            "ticker":        o.get("ticker"),
            "type":          (o.get("option_type") or o.get("type") or "call").lower(),
            "strike":        o.get("strike"),
            "expiry":        o.get("expiry"),
            "qty":           o.get("contracts") or o.get("qty") or 1,
            "avg_premium":   o.get("avg_premium"),
            "current_value": cp,
            "current_price": cp,
        })
    return out


def _watchlist_cards() -> list[dict]:
    wl_path = SCRIPT_DIR / "watchlist.json"
    if not wl_path.is_file():
        return []
    try:
        wl = json.loads(wl_path.read_text(encoding="utf-8"))
        tickers = wl.get("tickers") or []
    except Exception:
        return []
    out: list[dict] = []
    for raw in tickers:
        t = str(raw or "").strip().upper()
        if not t:
            continue
        row: dict = {
            "ticker":      t,
            "name":        "",
            "last":        None,
            "change_pct":  None,
            "headline":    None,
        }

        try:
            import yfinance as yf

            tk = yf.Ticker(t)
            fi = getattr(tk, "fast_info", {}) or {}
            last = fi.get("last_price") or fi.get("regular_market_price")
            prev = fi.get("previous_close")
            if last is not None and prev:
                try:
                    row["change_pct"] = (float(last) - float(prev)) / float(prev) * 100.0
                except (TypeError, ValueError, ZeroDivisionError):
                    pass
            row["last"] = float(last) if last is not None else None
            try:
                info = tk.info or {}
                row["name"] = (info.get("shortName") or info.get("longName") or "")[:48]
            except Exception:
                pass
            news = getattr(tk, "news", None) or []
            if news and isinstance(news, list):
                first = news[0] if isinstance(news[0], dict) else {}
                row["headline"] = (first.get("title") or "")[:140]
        except Exception:
            pass
        out.append(row)
    return out


def _recent_alerts_feed(limit: int = 5) -> list[dict]:
    out: list[dict] = []
    log_p = SCRIPT_DIR / "atlas_alerts.log"
    if log_p.is_file():
        try:
            lines = [
                ln.strip()
                for ln in log_p.read_text(encoding="utf-8", errors="ignore").splitlines()
                if ln.strip()
            ]
            for ln in lines[-limit:]:
                text = ln.split("] ", 1)[-1] if "] " in ln else ln
                out.append({"text": text, "source": "log"})
        except Exception:
            pass
    if len(out) < limit:
        need = limit - len(out)
        aj = SCRIPT_DIR / "atlas_alerts.json"
        if aj.is_file():
            try:
                data = json.loads(aj.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    items = [x for x in data if isinstance(x, dict)]
                    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
                    for item in items:
                        msg = (item.get("message") or "").strip()
                        if not msg:
                            continue
                        tick = item.get("ticker") or ""
                        plain = f"{tick}: {msg}" if tick else msg
                        out.append({
                            "text":   plain,
                            "source": "alert",
                            "at":     item.get("created_at"),
                        })
                        need -= 1
                        if need <= 0:
                            break
            except Exception:
                pass
    return out[:limit]


def _startup_check_dict() -> dict:
    gk = os.environ.get("GOOGLE_API_KEY") or ""
    google_key = bool(gk.strip()) and "your_key" not in gk.lower()
    tradier = bool((os.environ.get("TRADIER_TOKEN") or "").strip())
    cache = _load_positions_cache_raw()
    null_exp = sum(
        1 for o in (cache.get("options") or [])
        if isinstance(o, dict) and not o.get("expiry")
    )
    chromadb_ok = False
    try:
        import chromadb  # noqa: F401

        chromadb_ok = True
    except ImportError:
        pass
    return {
        "google_key": google_key,
        "tradier":    tradier,
        "chromadb":   chromadb_ok,
        "positions_null_expiry": null_exp,
    }


def _compute_manual_portfolio(cache: dict) -> dict:
    """Total market value and cost basis from manual positions only (no broker API)."""
    total = 0.0
    cost = 0.0
    for s in cache.get("stocks") or []:
        if not isinstance(s, dict):
            continue
        try:
            sh = float(s.get("shares") or 0)
            avg = float(s.get("avg_buy_price") or 0)
        except (TypeError, ValueError):
            continue
        cur = s.get("current_price")
        try:
            cur_f = float(cur) if cur is not None else avg
        except (TypeError, ValueError):
            cur_f = avg
        cost += sh * avg
        total += sh * cur_f
    for o in cache.get("options") or []:
        if not isinstance(o, dict):
            continue
        try:
            contracts = int(o.get("contracts") or 1)
            prem = float(o.get("avg_premium") or 0)
        except (TypeError, ValueError):
            continue
        cur = o.get("current_price")
        try:
            cur_f = float(cur) if cur is not None else prem
        except (TypeError, ValueError):
            cur_f = prem
        mult = 100.0 * float(contracts)
        cost += prem * mult
        total += cur_f * mult
    unreal = total - cost
    plpct = (unreal / cost) if cost > 0 else 0.0
    return {
        "portfolio_value": round(total, 2),
        "cost_basis":      round(cost, 2),
        "unrealized_pl":   round(unreal, 2),
        "unrealized_plpc": plpct,
    }


def _latest_idea_for_ui(catalog: list[dict], watchlist_tickers: list[str]) -> dict:
    """Most recent research (catalog is sorted by updated_at desc) else last watchlist add."""
    if catalog:
        c0 = catalog[0]
        tick = (c0.get("ticker") or "").strip().upper()
        if tick:
            return {"ticker": tick, "subtitle": "Living report", "source": "research"}
    if watchlist_tickers:
        t = (watchlist_tickers[-1] or "").strip().upper()
        if t:
            return {"ticker": t, "subtitle": "On watchlist", "source": "watchlist"}
    return {"ticker": None, "subtitle": None, "source": None}


def build_state() -> dict:
    """Aggregate all live data into a single state dict."""
    now = datetime.now(timezone.utc).isoformat()

    # ── Market Regime (VIX, SPY, DXY) ────────────────────────────────────────
    try:
        import market_scanner as ms
        regime = ms.detect_market_regime()
    except Exception as e:
        log.warning("Regime unavailable: %s", e)
        regime = {}

    # ── Auto-tuner weights ────────────────────────────────────────────────────
    try:
        import auto_tuner
        tuner_weights = auto_tuner.load_weights()
    except Exception:
        tuner_weights = {}

    # ── Win-rate tracker ──────────────────────────────────────────────────────
    try:
        import tracker
        winrate_str = _safe(tracker.winrate_summary, "No outcomes graded yet.")
        recent_recs = _safe(lambda: tracker.recent_recommendations(50), [])
        _safe(tracker.auto_grade_pending)
    except Exception:
        winrate_str = "Tracker unavailable"
        recent_recs = []

    # ── Memory stats ──────────────────────────────────────────────────────────
    try:
        import memory
        mem_stats = _safe(memory.memory_stats, {})
    except Exception:
        mem_stats = {}

    cache_pc          = _load_positions_cache_raw()
    cache_pc          = _enrich_positions_cache_live(cache_pc)
    manual_pf         = _compute_manual_portfolio(cache_pc)
    manual_stocks     = _manual_stocks_from_cache(cache_pc)
    options_positions = _options_from_cache(cache_pc)
    watchlist_cards   = _watchlist_cards()
    recent_alerts     = _recent_alerts_feed(5)
    account = {
        "equity":            manual_pf["portfolio_value"],
        "portfolio_value":   manual_pf["portfolio_value"],
        "cost_basis":        manual_pf["cost_basis"],
        "cash":              0.0,
        "buying_power":      0.0,
        "unrealized_pl":     manual_pf["unrealized_pl"],
        "unrealized_plpc":   manual_pf["unrealized_plpc"],
        "manual_only":       True,
    }
    positions: list = []
    orders: list = []
    research_catalog = _report_catalog_for_ui()
    wl_raw = _watchlist_tickers_raw()
    latest_idea = _latest_idea_for_ui(research_catalog, wl_raw)

    return {
        "timestamp":             now,
        "account":               account,
        "positions":             positions,
        "orders":                orders,
        "regime":                regime,
        "tuner_weights":         tuner_weights,
        "winrate":               winrate_str,
        "recent_recs":           recent_recs or [],
        "mem_stats":             mem_stats or {},
        "sectors":               [],
        "paper_trades":          {},
        "manual_stocks":         manual_stocks,
        "options_positions":     options_positions,
        "watchlist_cards":       watchlist_cards,
        "recent_alerts":         recent_alerts,
        "sector_data":           {},
        "congress_trades":       [],
        "watcher_active":        False,
        "watcher_last":          {},
        "volume_profile":        {},
        "startup_check":         _startup_check_dict(),
        "reports":               [],
        "research_catalog":      research_catalog,
        "research_history":      [],
        "pending_deep_research": _read_pending_deep(),
        "latest_idea":           latest_idea,
        "weekly_insight":        _load_weekly_insight_ui(),
        "weekly_reports":        _load_weekly_reports_archive(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Background refresh loop
# ─────────────────────────────────────────────────────────────────────────────

_state_lock = threading.Lock()
_cached_state: dict = {}


def _write_state(state: dict) -> None:
    with _state_lock:
        _cached_state.clear()
        _cached_state.update(state)
        STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _bump_state_cache() -> None:
    """Rebuild cached JSON for GET /state after any POST that changes disk or DB."""
    try:
        _write_state(build_state())
    except Exception as e:
        log.warning("State cache bump failed: %s", e)


def _refresh_loop() -> None:
    while True:
        log.info("Refreshing dashboard state...")
        try:
            state = build_state()
            _write_state(state)
            acct = state.get("account", {})
            val  = acct.get("portfolio_value")
            pos  = len(state.get("manual_stocks", []) or [])
            pos += len(state.get("options_positions", []) or [])
            reg  = state.get("regime", {}).get("regime", "?")
            log.info(
                "State updated | Portfolio: $%s | %d positions | Regime: %s",
                f"{val:,.2f}" if val else "?", pos, reg
            )
        except Exception as e:
            log.error("State refresh failed: %s", e)
        time.sleep(REFRESH_S)


def _normalize_expiry_day(exp: str | None) -> str:
    """Normalize option expiry to YYYY-MM-DD for comparisons with stored legs."""
    if exp is None:
        return ""
    s = str(exp).strip()
    if not s:
        return ""
    if "T" in s:
        s = s.split("T", 1)[0].strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            date.fromisoformat(s[:10])
            return s[:10]
        except ValueError:
            pass
    for sep in ("/", "."):
        if sep in s:
            parts = [p for p in s.replace(" ", "").split(sep) if p.strip()]
            if len(parts) >= 3:
                try:
                    mm, dd = int(parts[0]), int(parts[1])
                    yy = int(str(parts[2])[:4])
                    if yy < 100:
                        yy += 2000
                    return date(yy, mm, dd).isoformat()
                except (ValueError, OverflowError):
                    pass
            break
    return s[:10] if len(s) >= 10 else s


def _option_leg_core_match(
    row: dict,
    ticker_u: str,
    strike: float,
    opt_type: str,
) -> bool:
    if (row.get("ticker") or "").upper().strip() != ticker_u:
        return False
    try:
        rs = float(row.get("strike"))
    except (TypeError, ValueError):
        return False
    if abs(rs - strike) > 1e-6:
        return False
    ot = (row.get("option_type") or row.get("type") or "call").lower()
    if ot not in ("call", "put"):
        ot = "call"
    return ot == opt_type.lower()


def _options_equivalent(
    row: dict,
    ticker_u: str,
    strike: float,
    opt_type: str,
    expiry_day: str,
) -> bool:
    if (row.get("ticker") or "").upper().strip() != ticker_u:
        return False
    try:
        rs = float(row.get("strike"))
    except (TypeError, ValueError):
        return False
    if abs(rs - strike) > 1e-6:
        return False
    ot = (row.get("option_type") or row.get("type") or "call").lower()
    if ot not in ("call", "put"):
        ot = "call"
    if ot != opt_type.lower():
        return False
    return _normalize_expiry_day(row.get("expiry")) == expiry_day


def _unlink_all_files_under(root: Path) -> int:
    """Delete every file under root (deepest first); remove now-empty subdirs. Returns file count."""
    if not root.is_dir():
        return 0
    n = 0
    for p in sorted(root.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.is_file():
            try:
                p.unlink()
                n += 1
            except OSError:
                pass
    for p in sorted(root.rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.is_dir() and p.resolve() != root.resolve():
            try:
                p.rmdir()
            except OSError:
                pass
    return n


def _reset_local_workspace() -> dict[str, int]:
    """Factory reset: no tickers, no report HTML, no SQLite/RAG memory (local only)."""
    detail: dict[str, int] = {
        "deep_reports_dir_files_removed": 0,
        "reports_dir_files_removed":      0,
        "congress_cache_files_removed":   0,
        "delta_snapshots_removed":        0,
        "tracker_db_removed":             0,
        "atlas_memory_db_removed":        0,
        "atlas_rag_files_removed":        0,
        "tuner_state_files_removed":      0,
    }

    empty_pc = {"stocks": [], "options": []}
    (SCRIPT_DIR / "positions_cache.json").write_text(
        json.dumps(empty_pc, indent=2), encoding="utf-8"
    )

    (SCRIPT_DIR / "watchlist.json").write_text(
        json.dumps({"tickers": []}, indent=2), encoding="utf-8"
    )

    if PENDING_DEEP_FILE.is_file():
        try:
            PENDING_DEEP_FILE.unlink()
        except OSError:
            pass

    TRACKING_STATE_FILE.write_text(
        json.dumps({"last_watchlist_deep": {}, "last_position_pulse": {}}, indent=2),
        encoding="utf-8",
    )

    (SCRIPT_DIR / "atlas_alerts.json").write_text("[]", encoding="utf-8")
    log_p = SCRIPT_DIR / "atlas_alerts.log"
    if log_p.is_file():
        try:
            log_p.write_text("", encoding="utf-8")
        except OSError:
            pass

    (SCRIPT_DIR / "research_history.json").write_text(
        json.dumps({"entries": []}, indent=2), encoding="utf-8"
    )

    for _wk in (WEEKLY_REPORTS_INDEX, WEEKLY_INSIGHT_FILE, PENDING_WEEKLY_FILE):
        if _wk.is_file():
            try:
                _wk.unlink()
            except OSError:
                pass

    pt = SCRIPT_DIR / "paper_trades.json"
    if pt.is_file():
        pt.write_text("[]", encoding="utf-8")

    dr = SCRIPT_DIR / "deep_reports"
    if dr.is_dir():
        detail["deep_reports_dir_files_removed"] = _unlink_all_files_under(dr)

    rd = SCRIPT_DIR / "reports"
    if rd.is_dir():
        detail["reports_dir_files_removed"] = _unlink_all_files_under(rd)

    cc = SCRIPT_DIR / "congress_cache"
    if cc.is_dir():
        detail["congress_cache_files_removed"] = _unlink_all_files_under(cc)

    ds = SCRIPT_DIR / "delta_snapshots"
    if ds.is_dir():
        detail["delta_snapshots_removed"] = _unlink_all_files_under(ds)

    tdb = SCRIPT_DIR / "atlas_tracker.db"
    if tdb.is_file():
        try:
            tdb.unlink()
            detail["tracker_db_removed"] = 1
        except OSError:
            log.warning("Could not remove atlas_tracker.db (in use?) — restart the dashboard and run reset again.")

    mem = SCRIPT_DIR / "atlas_memory.db"
    if mem.is_file():
        try:
            mem.unlink()
            detail["atlas_memory_db_removed"] = 1
        except OSError:
            log.warning("Could not remove atlas_memory.db (SQLite busy) — restart the dashboard and run reset again.")

    rag_dir = SCRIPT_DIR / "atlas_rag"
    if rag_dir.is_dir():
        detail["atlas_rag_files_removed"] = _unlink_all_files_under(rag_dir)

    for name in (
        "atlas_tuned_weights.json",
        "atlas_tuned_thresholds.json",
        "atlas_tuning_log.json",
        "atlas_paper_conviction.json",
    ):
        p = SCRIPT_DIR / name
        if p.is_file():
            try:
                p.unlink()
                detail["tuner_state_files_removed"] += 1
            except OSError:
                pass

    try:
        import rag_engine as _rag

        _rag.reset_client_cache()
    except Exception:
        pass

    return detail


def _purge_research_artifacts_for_ticker(ticker: str) -> dict[str, int]:
    """Remove deep report files + research_history.json rows for one symbol."""
    t = "".join(c for c in (ticker or "").upper() if c.isalnum())
    detail = {"files_removed": 0, "history_entries_removed": 0}
    if not t or len(t) > 12:
        return detail
    dr = SCRIPT_DIR / "deep_reports"
    prefix = f"{t}_"
    if dr.is_dir():
        for p in dr.iterdir():
            if not p.is_file():
                continue
            name_u = p.name.upper()
            if name_u.startswith(prefix):
                try:
                    p.unlink()
                    detail["files_removed"] += 1
                except OSError:
                    pass
    if not RESEARCH_HISTORY_FILE.is_file():
        return detail
    try:
        raw = json.loads(RESEARCH_HISTORY_FILE.read_text(encoding="utf-8"))
        entries = [e for e in (raw.get("entries") or []) if isinstance(e, dict)]
        kept = [e for e in entries if (e.get("ticker") or "").upper().strip() != t]
        detail["history_entries_removed"] = len(entries) - len(kept)
        RESEARCH_HISTORY_FILE.write_text(
            json.dumps({"entries": kept}, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning("purge research history for %s: %s", t, e)
    return detail


# ─────────────────────────────────────────────────────────────────────────────
# HTTP handler
# ─────────────────────────────────────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):  # silence default request logs
        if "/state" not in (args[0] if args else ""):
            log.debug("HTTP %s", fmt % args)

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        """Allow dashboard HTML opened from file:// to call the API (CORS preflight)."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0]
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        BASE_DIR = SCRIPT_DIR

        if path == "/add_position":
            # body: { ticker, type ("stock"|"call"|"put"),
            #         qty, avg_price, strike (options only),
            #         expiry (options only), premium (options only) }
            try:
                cache_path = BASE_DIR / "positions_cache.json"
                cache = json.loads(cache_path.read_text()) if cache_path.exists() else {"stocks": [], "options": []}

                ticker = body.get("ticker", "").upper().strip()
                pos_type = body.get("type", "stock")

                if pos_type == "stock":
                    # Remove existing entry for same ticker then add fresh
                    cache["stocks"] = [s for s in cache.get("stocks", []) if s.get("ticker") != ticker]
                    cache["stocks"].append({
                        "ticker": ticker,
                        "shares": float(body.get("qty", 0)),
                        "avg_buy_price": float(body.get("avg_price", 0)),
                        "current_price": None,
                        "market_value": None,
                        "last_updated": datetime.now(timezone.utc).isoformat()
                    })
                else:
                    cache["options"] = [o for o in cache.get("options", []) if not (o.get("ticker") == ticker and str(o.get("strike")) == str(body.get("strike")))]
                    cache["options"].append({
                        "ticker": ticker,
                        "option_type": pos_type,
                        "strike": float(body.get("strike", 0)),
                        "expiry": body.get("expiry", ""),
                        "contracts": int(body.get("qty", 1)),
                        "avg_premium": float(body.get("premium", 0)),
                        "current_price": None,
                        "market_value": None,
                        "last_updated": datetime.now(timezone.utc).isoformat()
                    })

                cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
                _bump_state_cache()
                self._send(200, "application/json", json.dumps({"ok": True}).encode())
            except Exception as e:
                self._send(500, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())

        elif path == "/remove_position":
            # body: Remove ONE leg only (never stock + options together).
            #  - { "kind": "stock", "ticker": "ABC" }
            #  - { "kind": "option", "ticker": "SOUN", "strike": 14, "option_type": "call", "expiry": "2026-06-18" }
            #  - Legacy: { "ticker": "ABC" } → stock row only (same as kind stock).
            try:
                cache_path = BASE_DIR / "positions_cache.json"
                if not cache_path.is_file():
                    self._send(200, "application/json", json.dumps({"ok": True}).encode())
                    return
                cache = json.loads(cache_path.read_text(encoding="utf-8"))
                kind = (body.get("kind") or "stock").lower().strip()
                ticker = (body.get("ticker") or "").upper().strip()
                if not ticker:
                    self._send(400, "application/json", json.dumps({"ok": False, "error": "ticker required"}).encode())
                    return

                if kind == "option":
                    strike_raw = body.get("strike")
                    try:
                        strike_f = float(strike_raw)
                    except (TypeError, ValueError):
                        self._send(400, "application/json", json.dumps({"ok": False, "error": "strike required for option"}).encode())
                        return
                    opt_type = (body.get("option_type") or body.get("type") or "call").lower().strip()
                    if opt_type not in ("call", "put"):
                        opt_type = "call"
                    exp_raw = body.get("expiry")
                    exp_provided = exp_raw not in (None, "")
                    exp_day = _normalize_expiry_day(exp_raw) if exp_provided else ""
                    opts_list = [o for o in (cache.get("options") or []) if isinstance(o, dict)]
                    before = len(opts_list)

                    if exp_day:
                        cache["options"] = [
                            o for o in opts_list
                            if not _options_equivalent(o, ticker, strike_f, opt_type, exp_day)
                        ]
                    else:
                        same = [o for o in opts_list if _option_leg_core_match(o, ticker, strike_f, opt_type)]
                        if not same:
                            self._send(404, "application/json", json.dumps({"ok": False, "error": "no matching option leg"}).encode())
                            return
                        if len(same) > 1:
                            self._send(
                                400,
                                "application/json",
                                json.dumps({
                                    "ok": False,
                                    "error": "Several legs match that strike/type — add expiry (YYYY-MM-DD) to remove the right one.",
                                }).encode(),
                            )
                            return
                        expn = _normalize_expiry_day(same[0].get("expiry"))
                        cache["options"] = [
                            o for o in opts_list
                            if not _options_equivalent(o, ticker, strike_f, opt_type, expn)
                        ]
                    if len(cache.get("options") or []) == before:
                        self._send(404, "application/json", json.dumps({"ok": False, "error": "no matching option leg"}).encode())
                        return
                else:
                    # stock (default): drop manual stock row for this ticker only
                    before_s = len(cache.get("stocks") or [])
                    cache["stocks"] = [
                        s for s in (cache.get("stocks") or [])
                        if not isinstance(s, dict) or (s.get("ticker") or "").upper().strip() != ticker
                    ]
                    if len(cache.get("stocks") or []) == before_s:
                        self._send(404, "application/json", json.dumps({"ok": False, "error": "no stock row for ticker"}).encode())
                        return

                cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
                _bump_state_cache()
                self._send(200, "application/json", json.dumps({"ok": True}).encode())
            except json.JSONDecodeError:
                self._send(500, "application/json", json.dumps({"ok": False, "error": "invalid cache file"}).encode())
            except Exception as e:
                self._send(500, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())

        elif path == "/add_watchlist":
            # body: { ticker }
            # Store a simple watchlist.json next to positions_cache
            try:
                wl_path = BASE_DIR / "watchlist.json"
                wl = json.loads(wl_path.read_text(encoding="utf-8")) if wl_path.exists() else {"tickers": []}
                ticker = body.get("ticker", "").upper().strip()
                if ticker and ticker not in wl["tickers"]:
                    wl["tickers"].append(ticker)
                wl_path.write_text(json.dumps(wl, indent=2), encoding="utf-8")
                _bump_state_cache()
                self._send(200, "application/json", json.dumps({"ok": True}).encode())
            except Exception as e:
                self._send(500, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())

        elif path == "/remove_watchlist":
            try:
                wl_path = BASE_DIR / "watchlist.json"
                if not wl_path.is_file():
                    self._send(200, "application/json", json.dumps({"ok": True}).encode())
                    return
                wl = json.loads(wl_path.read_text(encoding="utf-8"))
                tick = body.get("ticker", "").upper().strip()
                wl["tickers"] = [t for t in (wl.get("tickers") or []) if str(t).upper().strip() != tick]
                wl_path.write_text(json.dumps(wl, indent=2), encoding="utf-8")
                _bump_state_cache()
                self._send(200, "application/json", json.dumps({"ok": True}).encode())
            except Exception as e:
                self._send(500, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())

        elif path == "/remove_tracker_row":
            try:
                import tracker as tr

                rid = int(body.get("id") or 0)
                if rid <= 0:
                    self._send(400, "application/json", json.dumps({"ok": False, "error": "id required"}).encode())
                    return
                if not tr.delete_recommendation(rid):
                    self._send(404, "application/json", json.dumps({"ok": False, "error": "no recommendation with that id"}).encode())
                    return
                _bump_state_cache()
                self._send(200, "application/json", json.dumps({"ok": True}).encode())
            except Exception as e:
                self._send(500, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())

        elif path == "/clear_tracker":
            try:
                import tracker as tr

                n = tr.clear_all_recommendations()
                _bump_state_cache()
                self._send(200, "application/json", json.dumps({"ok": True, "removed": n}).encode())
            except Exception as e:
                self._send(500, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())

        elif path == "/delete_research_report":
            try:
                tick = (body.get("ticker") or "").upper().strip()
                if not tick:
                    self._send(400, "application/json", json.dumps({"ok": False, "error": "ticker required"}).encode())
                    return
                detail = _purge_research_artifacts_for_ticker(tick)
                _bump_state_cache()
                self._send(200, "application/json", json.dumps({"ok": True, "detail": detail}).encode())
            except Exception as e:
                self._send(500, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())

        elif path == "/run_weekly_discovery":
            bw = _blocking_pending_weekly()
            if bw is not None:
                self._send(
                    409,
                    "application/json",
                    json.dumps({
                        "ok": False,
                        "error": "A market scan is already running. Wait for it to finish.",
                    }).encode(),
                )
                return
            bd = _blocking_pending_deep()
            if bd is not None:
                self._send(
                    409,
                    "application/json",
                    json.dumps({
                        "ok": False,
                        "error": (
                            f"Single-symbol deep research is already running ({bd.get('ticker', '?')}). "
                            "Wait for it to finish before starting a market scan."
                        ),
                    }).encode(),
                )
                return
            raw_theme = (body.get("theme") or "").strip()
            theme = raw_theme or (
                "US-listed stocks for portfolio growth: combine (1) actionable setups for roughly the next 2–6 weeks, "
                "(2) 1–3 month tactical ideas, and (3) at least one or two longer-term quality names with clear fundamentals; "
                "include liquid lower-priced / small-cap ideas where real volume exists, alongside steadier growers. "
                "No leveraged ETFs; emphasize realistic catalysts and defined risk."
            )
            try:
                budget = float(body.get("budget") or 150)
            except (TypeError, ValueError):
                budget = 150.0
            try:
                max_n = int(body.get("max") or 5)
            except (TypeError, ValueError):
                max_n = 5
            max_n = max(1, min(max_n, 10))

            _set_pending_weekly(theme)

            def _run_weekly() -> None:
                try:
                    import deep_research as dr

                    results = dr.discover_stocks(theme, budget=budget, max_results=max_n)
                    disc_path = dr.write_discovery_report(theme, results or [])
                    weekly_dir = SCRIPT_DIR / "deep_reports" / "weekly"
                    weekly_dir.mkdir(parents=True, exist_ok=True)
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    arch_fname = f"MARKET_SCAN_{stamp}.html"
                    arch_path = weekly_dir / arch_fname
                    combined_html = disc_path.read_bytes()
                    arch_path.write_bytes(combined_html)
                    weekly_p = SCRIPT_DIR / "deep_reports" / "WEEKLY_INSIGHT.html"
                    weekly_p.write_bytes(combined_html)
                    archive_href = f"/deep_reports/weekly/{arch_fname}"
                    tk_syms: list[str] = []
                    for r in results or []:
                        if not isinstance(r, dict):
                            continue
                        syn = r.get("synthesis") or {}
                        t = (syn.get("ticker") or r.get("ticker") or "").upper().strip()
                        if t:
                            tk_syms.append(t)
                    _save_weekly_insight_meta(
                        theme, budget, results or [], disc_path.name, archive_href=archive_href
                    )
                    _append_weekly_reports_archive(
                        theme=theme,
                        budget=budget,
                        tickers_syms=tk_syms,
                        archive_href=archive_href,
                        latest_href=WEEKLY_REPORT_HREF,
                        source_file=disc_path.name,
                    )
                except Exception as e:
                    log.error("[weekly_insight] %s", e)
                    try:
                        WEEKLY_INSIGHT_FILE.write_text(
                            json.dumps(
                                {
                                    "status":       "error",
                                    "message":      str(e)[:400],
                                    "updated_at":   datetime.now(timezone.utc).isoformat(),
                                    "theme":        theme,
                                    "budget":       budget,
                                    "tickers":      [],
                                    "report_href":  WEEKLY_REPORT_HREF,
                                    "archive_href": "",
                                    "source_file":  "",
                                },
                                indent=2,
                            ),
                            encoding="utf-8",
                        )
                    except OSError:
                        pass
                finally:
                    _clear_pending_weekly()
                try:
                    _bump_state_cache()
                except Exception:
                    pass

            threading.Thread(target=_run_weekly, daemon=True).start()
            self._send(
                200,
                "application/json",
                json.dumps(
                    {
                        "ok":      True,
                        "message": "Market scan started — check Research → Weekly reports in a few minutes.",
                    }
                ).encode(),
            )

        elif path == "/reset_workspace":
            phrase = (body.get("phrase") or "").strip().upper()
            if phrase != "RESET ALL":
                self._send(
                    400,
                    "application/json",
                    json.dumps({
                        "ok": False,
                        "error": 'Confirmation required: type RESET ALL in the box (capital letters).',
                    }).encode(),
                )
                return
            try:
                detail = _reset_local_workspace()
                state = build_state()
                _write_state(state)
                log.info(
                    "Workspace reset | deep=%s reports=%s memory_db=%s rag_files=%s tracker=%s",
                    detail.get("deep_reports_dir_files_removed", 0),
                    detail.get("reports_dir_files_removed", 0),
                    detail.get("atlas_memory_db_removed", 0),
                    detail.get("atlas_rag_files_removed", 0),
                    detail.get("tracker_db_removed", 0),
                )
                self._send(
                    200,
                    "application/json",
                    json.dumps({"ok": True, "detail": detail}, default=str).encode(),
                )
            except Exception as e:
                log.error("reset_workspace failed: %s", e)
                self._send(500, "application/json", json.dumps({"ok": False, "error": str(e)}).encode())

        elif path == "/run_deep_research":
            ticker  = body.get("ticker", "").upper().strip()
            budget  = float(body.get("budget") or 100)
            if not ticker:
                self._send(400, "application/json", b'{"ok":false,"error":"ticker required"}')
                return

            blk = _blocking_pending_deep()
            if blk is not None:
                other = (blk.get("ticker") or "?").strip()
                self._send(
                    409,
                    "application/json",
                    json.dumps({
                        "ok": False,
                        "error": (
                            f"Deep research is already running ({other}). "
                            "Wait for it to finish before starting another."
                        ),
                    }).encode(),
                )
                return

            _set_pending_deep(ticker)

            def _run() -> None:
                try:
                    import deep_research as dr

                    res = dr.research_ticker(ticker, budget=budget)
                    if res:
                        outp = dr.write_report(res, budget=budget)
                        rel = outp.relative_to(SCRIPT_DIR).as_posix()
                        _upsert_research_history(ticker, rel, "deep_research")
                except Exception as e:
                    log.error("[run_deep_research] %s", e)
                finally:
                    _clear_pending_deep()
                try:
                    _write_state(build_state())
                except Exception:
                    pass

            threading.Thread(target=_run, daemon=True).start()
            self._send(
                200,
                "application/json",
                json.dumps({
                    "ok":      True,
                    "ticker":  ticker,
                    "message": "Deep research running — open Research → Report history in ~1–3 min.",
                }).encode(),
            )

        elif path == "/run_volume_profile":
            ticker = body.get("ticker", "").upper().strip()
            days   = int(body.get("lookback_days") or 30)
            if not ticker:
                self._send(400, "application/json", b'{"ok":false,"error":"ticker required"}')
                return

            def _run() -> None:
                try:
                    import volume_profile as vp

                    d    = vp.calculate_volume_profile(ticker, lookback_days=days)
                    html = vp.to_html(d)
                    rd   = SCRIPT_DIR / "reports"
                    rd.mkdir(exist_ok=True)
                    out  = rd / f"{ticker}_volume_profile.html"
                    doc  = (
                        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                        f"<title>{ticker} volume profile</title>"
                        "<style>body{margin:0;background:#0d1117;color:#e6edf3;font-family:system-ui,sans-serif}</style>"
                        f"</head><body>{html}</body></html>"
                    )
                    out.write_text(doc, encoding="utf-8")
                    _append_research_history(ticker, f"reports/{out.name}", "volume_profile")
                except Exception as e:
                    log.error("[run_volume_profile] %s", e)
                try:
                    _write_state(build_state())
                except Exception:
                    pass

            threading.Thread(target=_run, daemon=True).start()
            self._send(200, "application/json", json.dumps({"ok": True, "ticker": ticker}).encode())

        elif path == "/run_options_simulator":
            ticker = body.get("ticker", "").upper().strip()
            if not ticker:
                self._send(400, "application/json", b'{"ok":false,"error":"ticker required"}')
                return

            strike  = float(body.get("strike") or 0)
            expiry  = str(body.get("expiry") or "").strip()
            ask     = float(body.get("ask") or body.get("premium") or 0)
            opt_typ = str(body.get("option_type") or "call").lower()
            if opt_typ not in ("call", "put"):
                opt_typ = "call"
            budget = float(body.get("budget") or 100)
            spot   = body.get("spot")

            if strike <= 0 or not expiry or ask <= 0:
                self._send(
                    400,
                    "application/json",
                    json.dumps({"ok": False, "error": "strike, expiry, and ask/premium required"}).encode(),
                )
                return

            def _run() -> None:
                try:
                    import html as html_mod
                    import yfinance as yf
                    import options_simulator as osim

                    cur = spot
                    if cur is None:
                        tk  = yf.Ticker(ticker)
                        fi  = getattr(tk, "fast_info", {}) or {}
                        cur = fi.get("last_price") or fi.get("regular_market_price")
                    cur = float(cur or 0)
                    if cur <= 0:
                        raise ValueError("Could not resolve stock price for simulator")

                    res = osim.simulate(
                        ticker=ticker,
                        strike=strike,
                        expiry=expiry,
                        ask=ask,
                        current_price=cur,
                        option_type=opt_typ,
                        budget=budget,
                    )
                    chart = res.get("html_chart") or ""
                    rd    = SCRIPT_DIR / "reports"
                    rd.mkdir(exist_ok=True)
                    out   = rd / f"{ticker}_options_sim.html"
                    summ  = html_mod.escape(str(res.get("summary") or ""))
                    doc   = (
                        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                        f"<title>{ticker} options sim</title>"
                        "<style>body{margin:16px;background:#0d1117;color:#e6edf3;"
                        "font-family:system-ui,sans-serif}</style></head><body>"
                        f"<pre style=\"white-space:pre-wrap;color:#8b949e\">{summ}</pre>"
                        f"{chart}</body></html>"
                    )
                    out.write_text(doc, encoding="utf-8")
                    _append_research_history(ticker, f"reports/{out.name}", "options_simulator")
                except Exception as e:
                    log.error("[run_options_simulator] %s", e)
                try:
                    _write_state(build_state())
                except Exception:
                    pass

            threading.Thread(target=_run, daemon=True).start()
            self._send(200, "application/json", json.dumps({"ok": True, "ticker": ticker}).encode())

        elif path == "/run_intraday_cycle":
            def _run() -> None:
                try:
                    subprocess.run(
                        [sys.executable, str(SCRIPT_DIR / "auto_bot.py"), "--once-intraday"],
                        cwd=str(SCRIPT_DIR),
                        timeout=7200,
                    )
                except Exception as e:
                    log.error("[run_intraday_cycle] %s", e)
                try:
                    _write_state(build_state())
                except Exception:
                    pass

            threading.Thread(target=_run, daemon=True).start()
            self._send(
                200,
                "application/json",
                json.dumps({"ok": True, "message": "Intraday cycle started (runs auto_bot --once-intraday)."}).encode(),
            )

        elif path == "/run_tradier_chain":
            ticker = body.get("ticker", "").upper().strip()
            if not ticker:
                self._send(400, "application/json", b'{"ok":false,"error":"ticker required"}')
                return

            def _run() -> None:
                try:
                    cp = subprocess.run(
                        [sys.executable, str(SCRIPT_DIR / "auto_bot.py"), "--tradier-chain", ticker],
                        cwd=str(SCRIPT_DIR),
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    rd = SCRIPT_DIR / "reports"
                    rd.mkdir(exist_ok=True)
                    out = rd / f"{ticker}_tradier_chain.txt"
                    out.write_text(
                        (cp.stdout or "") + ("\n" + cp.stderr if cp.stderr else ""),
                        encoding="utf-8",
                        errors="ignore",
                    )
                    _append_research_history(ticker, f"reports/{out.name}", "tradier_chain")
                except Exception as e:
                    log.error("[run_tradier_chain] %s", e)
                try:
                    _write_state(build_state())
                except Exception:
                    pass

            threading.Thread(target=_run, daemon=True).start()
            self._send(200, "application/json", json.dumps({"ok": True, "ticker": ticker}).encode())

        else:
            self._send(
                404,
                "application/json",
                json.dumps({"ok": False, "error": f"Unknown POST path: {path}"}).encode(),
            )

    def do_GET(self):
        path = self.path.split("?")[0]
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        if path in ("/", "/index.html"):
            if HTML_FILE.exists():
                body = HTML_FILE.read_bytes()
                self._send(200, "text/html; charset=utf-8", body)
            else:
                self._send(404, "text/plain", b"dashboard.html not found")

        elif path in ("/v2", "/app"):
            p = _atlas_intel_html_path()
            if p.is_file():
                body = p.read_bytes()
                self._send(200, "text/html; charset=utf-8", body)
            else:
                self._send(404, "text/plain", b"atlas_dashboard_v4/v2 not found")

        elif path in ("/v4", "/atlas_dashboard_v4.html"):
            if ATLAS_V4_HTML.is_file():
                body = ATLAS_V4_HTML.read_bytes()
                self._send(200, "text/html; charset=utf-8", body)
            else:
                self._send(404, "text/plain", b"atlas_dashboard_v4.html not found")

        elif path == "/atlas_dashboard_v2.html":
            if ATLAS_V2_HTML.is_file():
                body = ATLAS_V2_HTML.read_bytes()
                self._send(200, "text/html; charset=utf-8", body)
            else:
                self._send(404, "text/plain", b"atlas_dashboard_v2.html not found")

        elif path == "/state":
            with _state_lock:
                body = json.dumps(_cached_state, default=str).encode()
            self._send(200, "application/json", body)

        elif path == "/refresh":
            # Manual force-refresh trigger
            try:
                state = build_state()
                _write_state(state)
                self._send(200, "application/json", b'{"ok":true}')
            except Exception as e:
                err = json.dumps({"ok": False, "error": str(e)}).encode()
                self._send(500, "application/json", err)

        elif path == "/research":
            # GET /research?ticker=SOUN
            from urllib.parse import urlparse, parse_qs

            qs = parse_qs(urlparse(self.path).query)
            ticker = qs.get("ticker", [""])[0].upper().strip()
            if not ticker:
                self._send(400, "application/json", b'{"ok":false,"error":"no ticker"}')
                return

            # Run the research in a background thread so the request returns immediately
            def _run():
                try:
                    import web_scraper, delta_reporter

                    log.info("[research] Starting scan for %s...", ticker)
                    scrape = web_scraper.gather_all(ticker)
                    delta_reporter.scan_ticker(ticker, scrape)
                    log.info("[research] Done — reports/ATLAS_DELTA_%s.html", ticker)
                except Exception as e:
                    log.error("[research] Failed for %s: %s", ticker, e)
                try:
                    _write_state(build_state())
                except Exception:
                    pass

            threading.Thread(target=_run, daemon=True).start()

            resp = json.dumps({
                "ok":       True,
                "ticker":   ticker,
                "report":   f"reports/ATLAS_DELTA_{ticker}.html",
                "message":  f"Scanning {ticker}… open /reports/ATLAS_DELTA_{ticker}.html in ~60s",
            }).encode()
            self._send(200, "application/json", resp)

        elif path.startswith("/reports/"):
            rel = unquote(path[len("/reports/") :]).strip()
            # no traversal
            if not rel or rel.startswith("/") or ".." in rel.replace("\\", "/"):
                self._send(400, "text/plain", b"Bad path")
                return
            fname = Path(rel).name
            fp = SCRIPT_DIR / "reports" / fname
            if fp.is_file() and fp.suffix.lower() in (".html", ".htm", ".txt"):
                if fp.suffix.lower() == ".txt":
                    self._send(200, "text/plain; charset=utf-8", fp.read_bytes())
                else:
                    self._send(200, "text/html; charset=utf-8", fp.read_bytes())
            else:
                self._send(404, "text/plain", b"Report not found")

        elif path.startswith("/deep_reports/"):
            rel = unquote(path[len("/deep_reports/") :]).strip()
            if not rel or rel.startswith("/") or ".." in rel.replace("\\", "/"):
                self._send(400, "text/plain", b"Bad path")
                return
            base_dir = (SCRIPT_DIR / "deep_reports").resolve()
            try:
                fp = (base_dir / rel).resolve()
            except OSError:
                self._send(400, "text/plain", b"Bad path")
                return
            try:
                fp.relative_to(base_dir)
            except ValueError:
                self._send(403, "text/plain", b"Forbidden")
                return
            if fp.is_file() and fp.suffix.lower() in (".html", ".htm"):
                self._send(200, "text/html; charset=utf-8", fp.read_bytes())
            else:
                self._send(404, "text/plain", b"Report not found")

        else:
            self._send(404, "text/plain", b"Not found")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    open_browser = "--no-browser" not in sys.argv

    # Initial state build (blocking, so first page load is ready)
    log.info("Building initial state...")
    try:
        state = build_state()
        _write_state(state)
        log.info("Initial state ready.")
    except Exception as e:
        log.warning("Initial state build failed: %s  (will retry in background)", e)

    # Start background refresh thread
    t = threading.Thread(target=_refresh_loop, daemon=True, name="state-refresh")
    t.start()

    threading.Thread(target=_research_scheduler_loop, daemon=True, name="research-scheduler").start()

    # Start HTTP server
    server = HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    url    = f"http://localhost:{PORT}"
    log.info("ATLAS Dashboard running at %s", url)
    log.info(
        "ATLAS Financial UI: %s/v2 → %s  (API: python api_server.py :8000)",
        url,
        ATLAS_V4_HTML.name if ATLAS_V4_HTML.is_file() else ATLAS_V2_HTML.name,
    )
    log.info("Phone access: http://<your-local-IP>:%d", PORT)
    log.info("Press Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Dashboard server stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
