#!/usr/bin/env python3
"""ATLAS query JSON → institutional PDF (nine primary sections).

Reads a dict shaped like POST /query. Writes by default to
atlas_vault/03-Outputs/Reports/<ticker>_YYYY-MM-DD.pdf .

  pip install weasyprint

Windows: install GTK/Cairo per WeasyPrint documentation.
See: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html

Examples:
  python tools/atlas_pdf_weasyprint.py report.json
  type report.json | python tools/atlas_pdf_weasyprint.py -
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "atlas_vault" / "03-Outputs" / "Reports"


def _esc(x: Any) -> str:
    return html_lib.escape("" if x is None else str(x), quote=False)


def _ticker(envelope: dict[str, Any]) -> str:
    pq = envelope.get("parsed_query") or {}
    if isinstance(pq, dict):
        t = pq.get("tickers")
        if isinstance(t, Iterable) and not isinstance(t, (str, bytes)):
            lst = list(t)
            if lst:
                return str(lst[0])
    fr = envelope.get("final_report") or {}
    if isinstance(fr, dict) and fr.get("ticker"):
        return str(fr["ticker"])
    return "ATLAS"


def _cats(val: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(val, list):
        for c in val:
            if isinstance(c, str) and c.strip():
                rows.append({"date": "", "event": c.strip(), "meta": ""})
            elif isinstance(c, dict):
                d = str(c.get("date") or c.get("when") or "")
                e = str(c.get("event") or c.get("label") or c.get("title") or "")
                m = " · ".join(str(x) for x in (c.get("impact"), c.get("direction")) if x not in (None, ""))
                rows.append({"date": d, "event": e, "meta": m})
        return rows
    if isinstance(val, str) and val.strip():
        try:
            j = json.loads(val)
            if isinstance(j, list):
                return _cats(j)
        except json.JSONDecodeError:
            pass
        for line in val.splitlines():
            t = re.sub(r"^[-*•\d.)]+\s*", "", line).strip()
            if t:
                rows.append({"date": "", "event": t, "meta": ""})
    return rows


def _trade_plan(fr: dict[str, Any]) -> tuple[list[str], list[str]]:
    tp = fr.get("trade_plan")
    labs = ["Entry", "Stop Loss", "Target 1", "Target 2"]
    if isinstance(tp, str):
        return labs, [_esc(tp.strip()), "—", "—", "—"]
    if not isinstance(tp, dict):
        return ["Detail"], [_esc(json.dumps(tp, indent=2)[:4400])]
    seq = [
        tp.get("entry_price", tp.get("entry", "")),
        tp.get("stop_loss", tp.get("stop", "")),
        tp.get("target_1", tp.get("target", "")),
        tp.get("target_2", ""),
    ]
    cells = [_esc(v) if v != "" else "—" for v in seq]
    return labs, cells


def _scenarios(env: dict[str, Any]) -> tuple[list[str], list[float], list[str], list[str]]:
    canon = ["Bull", "Base", "Bear"]
    colors = ["#238636", "#00AFFF", "#DA3633"]
    arr = env.get("scenarios")
    if not isinstance(arr, list) or not arr:
        return canon, [0.0, 0.0, 0.0], ["—", "—", "—"], colors

    pool: list[dict[str, Any]] = []
    for i, sc in enumerate(arr):
        if not isinstance(sc, dict):
            continue
        lab = sc.get("label") or sc.get("name") or sc.get("scenario") or "S" + str(i + 1)
        raw = float(sc.get("probability") or sc.get("prob") or 0)
        pct = raw if raw > 1 else raw * 100
        pool.append({"label": str(lab), "pct": pct, "u": False})

    def zone(lbl: str) -> int:
        low = lbl.lower()
        if re.search(r"\bbull\b", low):
            return 0
        if re.search(r"\bbear\b", low):
            return 2
        for token in ("base", "middle", "mid", "balanced", "neutral case", "central", "main", "consensus"):
            if token in low:
                return 1
        return -1

    slots: list[Any] = [None, None, None]
    for o in pool:
        z = zone(o["label"])
        if z >= 0 and slots[z] is None:
            slots[z] = o
            o["u"] = True
    left = [x for x in pool if not x["u"]]
    n = 0
    for idx in range(3):
        if slots[idx] is None:
            if n < len(left):
                slots[idx] = left[n]
                n += 1
            else:
                slots[idx] = {"ph": True, "label": canon[idx], "pct": 0.0}

    lbls: list[str] = []
    pcts: list[float] = []
    notes: list[str] = []
    for s in slots:
        if isinstance(s, dict) and s.get("ph"):
            lbls.append(str(s["label"]))
            pcts.append(0.0)
            notes.append("—")
            continue
        if isinstance(s, dict):
            lbls.append(str(s["label"]))
            pcts.append(float(s.get("pct", 0)))
            parts: list[str] = []
            for k in ("description", "summary", "outcome", "trigger"):
                if s.get(k):
                    parts.append(str(s[k]))
            if s.get("your_action"):
                parts.append("Your action: " + str(s["your_action"]))
            notes.append(" — ".join(parts) if parts else "—")
        else:
            lbls.append("—")
            pcts.append(0.0)
            notes.append("—")
    return lbls, pcts, notes, colors


def _fmk(rv: Any) -> str:
    u = str(rv or "").upper()
    if "CRIT" in u:
        return "CRITICAL"
    if "HIGH" in u:
        return "HIGH"
    if "MED" in u:
        return "MEDIUM"
    if "LOW" in u:
        return "LOW"
    return "HIGH"


_FM = {
    "CRITICAL": "background:rgba(218,54,51,.17);border:1px solid rgba(218,54,51,.5);color:#ffb4b0;",
    "HIGH": "background:rgba(234,88,12,.13);border:1px solid rgba(234,88,12,.4);color:#fdba74;",
    "MEDIUM": "background:rgba(210,153,34,.12);border:1px solid rgba(210,153,34,.39);color:#f0d078;",
    "LOW": "background:rgba(107,114,128,.1);border:1px solid rgba(156,163,175,.34);color:#d1d5db;",
}



def build_html(envelope: dict[str, Any]) -> str:
    raw_fr = envelope.get("final_report")
    fr = raw_fr if isinstance(raw_fr, dict) else {}

    tk = _ticker(envelope)
    pq_env = envelope.get("parsed_query") if isinstance(envelope.get("parsed_query"), dict) else {}
    tick_line = ""
    tick_arr = pq_env.get("tickers")
    if isinstance(tick_arr, list) and tick_arr:
        tick_line = ", ".join(_esc(str(x)) for x in tick_arr)

    tldr = envelope.get("tldr") or fr.get("primary_recommendation") or fr.get("overall_rating") or ""
    exec_txt = fr.get("executive_summary") or fr.get("executive_brief") or ""
    h_lab, h_val = _trade_plan(fr)

    lbl, pct, prose, clr = _scenarios(envelope)
    segments = []
    for i in range(3):
        width = max(0.0, min(float(pct[i]), 100.0))
        pct_show = max(0.0, min(float(pct[i]), 999.0))
        segments.append(
            "<div class='sc' style='border-top:5px solid "
            + clr[i]
            + "'><h3>"
            + _esc(lbl[i])
            + "</h3><p class='muted mono'>"
            + f"{pct_show:,.1f}"
            + "%</p><div class='meter'><span style='background:"
            + clr[i]
            + ";width:"
            + f"{width:.2f}"
            + "%'></span></div><p class='bod'>"
            + _esc(prose[i])
            + "</p></div>"
        )
    tri = "".join(segments)

    pl_obj = fr.get("price_levels")
    if isinstance(pl_obj, dict) and pl_obj:
        rows_html = "".join(
            "<tr><td>"
            + _esc(str(key)).replace("_", " ")
            + "</td><td class='tr mono'>"
            + _esc(val)
            + "</td></tr>"
            for key, val in pl_obj.items()
        )
        pl_block = "<table class='kv'>" + rows_html + "</table>"
    elif isinstance(pl_obj, str) and pl_obj.strip():
        pl_block = "<pre class='muted'>" + _esc(pl_obj) + "</pre>"
    else:
        pl_block = "<p class='muted'>—</p>"

    rules_parts = []
    er_list = envelope.get("execution_rules")
    if isinstance(er_list, list):
        for idx, ru in enumerate(er_list[:15], start=1):
            if isinstance(ru, str):
                line = ru
            elif isinstance(ru, dict):
                bits_r = []
                if ru.get("type"):
                    bits_r.append(f"[{ru['type']}]")
                if ru.get("ticker"):
                    bits_r.append(str(ru["ticker"]))
                if ru.get("trigger_price") not in (None, ""):
                    bits_r.append(f"@ {ru['trigger_price']}")
                if ru.get("action"):
                    bits_r.append(f"→ {ru['action']}")
                line = " ".join(bits_r) if bits_r else json.dumps(ru, ensure_ascii=False)[:340]
            else:
                line = json.dumps(ru, ensure_ascii=False)[:340]
            rules_parts.append(
                "<div class='rule'><span class='idx'>" + str(idx) + ".</span> " + _esc(line) + "</div>"
            )
    rules_dom = "".join(rules_parts) if rules_parts else "<p class='muted'>—</p>"

    fm_parts = []
    fm_list = envelope.get("failure_modes")
    if isinstance(fm_list, list):
        for item in fm_list[:10]:
            if isinstance(item, str):
                fm_parts.append(
                    "<div class='fm'><span class='tag' style='" + _FM["HIGH"] + "'>HIGH</span> " + _esc(item) + "</div>"
                )
                continue
            if not isinstance(item, dict):
                continue
            disp_sev = str(item.get("severity") or "RISK").upper()
            ky = _fmk(item.get("severity"))
            parts_f = []
            if item.get("mode"):
                parts_f.append(str(item["mode"]))
            if item.get("tripwire"):
                parts_f.append("Tripwire: " + str(item["tripwire"]))
            if item.get("response"):
                parts_f.append("Response: " + str(item["response"]))
            if item.get("probability") is not None:
                parts_f.append("P: " + str(item["probability"]))
            body_f = " — ".join(parts_f) if parts_f else json.dumps(item, ensure_ascii=False)[:420]
            badge_style = _FM.get(ky, _FM["HIGH"])
            fm_parts.append(
                "<div class='fm'><span class='tag' style='" + badge_style + "'>" + _esc(disp_sev) + "</span> "
                + _esc(body_f)
                + "</div>"
            )
    fm_dom = "".join(fm_parts) if fm_parts else "<p class='muted'>—</p>"

    cat_dom = "".join(
        "<div class='cat'><div class='muted'>" + (_esc(ent["date"]) or "TBD") + "</div><strong>"
        + _esc(ent["event"]) + "</strong><div class='muted'>" + _esc(ent["meta"]) + "</div></div>"
        for ent in _cats(fr.get("catalysts_timeline"))[:16]
    )

    memo_txt = envelope.get("trader_memo") or fr.get("trader_memo") or ""

    rating_lc = str(fr.get("overall_rating") or "").lower()
    hue = "#0044FF"
    if re.search(r"\bbull\b|strong buy|\bbuy\b", rating_lc):
        hue = "#238636"
    elif re.search(r"\bbear\b|\bsell\b|short", rating_lc):
        hue = "#DA3633"
    elif re.search(r"\bhold\b|\bneutral\b|\bwait\b", rating_lc):
        hue = "#D29922"

    thead_cells = "".join("<th>" + _esc(cell) + "</th>" for cell in h_lab)
    tbody_cells = "".join("<td>" + cell + "</td>" for cell in h_val)

    banner = ""
    if tldr:
        banner = (
            "<div class='card hero' style='border-left-color:"
            + hue
            + "'><span class='eyeb'>TLDR</span><div class='tldr'>" + _esc(tldr) + "</div></div>"
        )

    exec_block = (
        "<section class='card'><h2>Executive Summary</h2><div class='bod'>" + _esc(exec_txt) + "</div></section>"
        if exec_txt
        else ""
    )

    trade_section = (
        "<section class='card'><h2>Trade Plan</h2><table class='tp'><thead><tr>"
        + thead_cells
        + "</tr></thead><tbody><tr>"
        + tbody_cells
        + "</tr></tbody></table></section>"
    )

    scenarios_section = "<section class='card'><h2>Scenarios</h2><div class='tri'>" + tri + "</div></section>"
    level_section = "<section class='card'><h2>Price Levels</h2>" + pl_block + "</section>"
    rules_section = "<section class='card'><h2>Execution Rules</h2>" + rules_dom + "</section>"
    fm_section = "<section class='card'><h2>Failure Modes</h2>" + fm_dom + "</section>"
    cat_section = (
        "<section class='card'><h2>Catalyst Timeline</h2><div class='scroll'>" + cat_dom + "</div></section>"
        if cat_dom
        else ""
    )
    memo_section = (
        "<section class='memo'><span class='ey'>Trader Memo</span><div class='bod'>" + _esc(memo_txt) + "</div></section>"
        if memo_txt
        else ""
    )

    iso_day = html_lib.escape(date.today().isoformat(), quote=False)

    stylesheet = """@page { margin:14mm;
  @bottom-center {content:"Page " counter(page);font:bold 11px monospace;color:rgba(230,237,243,.52);}}
body{font-family:Inter,system-ui,sans-serif;margin:0;padding:42px;color:#E6EDF3;background:#0D1117;-webkit-print-color-adjust:exact;print-color-adjust:exact;font-size:15px;line-height:1.55;}
h2{font:bold 13px monospace;letter-spacing:.2em;color:#0044FF;margin:30px 0 18px;text-transform:uppercase;}
h3{font-size:17px;color:#E6EDF3;margin-top:4px;margin-bottom:8px;font-weight:600;}
.top{border-bottom:1px solid rgba(240,246,252,.13);margin-bottom:24px;padding-bottom:18px;}
.brand{font:bold 13px monospace;letter-spacing:.22em;color:#0044FF;}
.title{font-size:29px;font-weight:700;color:#E6EDF3;margin-top:6px;margin-bottom:6px;}
.tick{font:bold 13px monospace;color:#00AFFF;margin-bottom:12px;display:block;}
.card{background:rgba(255,255,255,.035);border:1px solid rgba(240,246,252,.12);padding:21px;margin-bottom:20px;border-radius:12px;}
.hero{border-left:12px solid #0044FF;padding-top:24px;margin-top:26px;padding-bottom:6px;padding-right:26px;padding-left:24px;border-radius:13px!important;}
.hero .eyeb{display:block;color:rgba(255,255,255,.45);font:bold 11px monospace;letter-spacing:.2em;margin-bottom:13px;text-transform:uppercase;}
.hero .tldr{font-size:30px;line-height:1.3;font-weight:700;margin:0;}
.tp{width:100%;border-collapse:collapse;}
.tp th{color:rgba(255,255,255,.43);padding:12px 8px;text-align:center;border-bottom:1px solid rgba(240,246,252,.13);font:bold 11px monospace;text-transform:uppercase;}
.tp td{font:14px JetBrains Mono,monospace;padding:16px;text-align:center;}
.tri{display:flex;flex-wrap:wrap;gap:15px;}
.sc{flex:1;min-width:170px;padding:18px;border-radius:13px;background:rgba(0,0,0,.16);border:1px solid rgba(240,246,252,.06);}
.meter{margin:13px 0;height:8px;background:rgba(255,255,255,.08);border-radius:999px;}
.meter>span{display:block;height:100%;border-radius:999px;}
.bod{font-size:14px;line-height:1.55;color:rgba(230,237,243,.93);}
.rule{margin-bottom:14px;display:flex;line-height:1.55;color:rgba(230,237,243,.9);}
.idx{font-weight:700;min-width:28px;display:inline-block;font-family:JetBrains Mono,monospace;color:rgba(255,255,255,.44);}
.mono{font-family:JetBrains Mono,monospace;}
.muted{color:rgba(255,255,255,.45);margin:9px 0;}
.fm{display:flex;margin-bottom:16px;line-height:1.55;color:rgba(230,237,243,.9);gap:12px;font-size:14px;}
.tag{padding:10px;font:bold 11px monospace;border-radius:9px;display:inline-flex;align-items:flex-start;line-height:1.35;}
.scroll{display:flex;flex-wrap:wrap;gap:13px;margin-top:6px;}
.cat{flex:0 1 164px;background:rgba(0,0,0,.2);padding:13px;border:1px solid rgba(240,246,252,.08);border-radius:12px;}
.cat strong{color:#E6EDF3;font-weight:640;font-size:15px;display:block;margin-bottom:7px;line-height:1.37;}
.memo{margin-top:6px;background:rgba(0,68,255,.11);padding:26px;font-style:italic;border-radius:12px;line-height:1.65;color:rgba(205,217,239,.93);border:1px solid rgba(0,68,255,.38);}
.memo .bod{margin-top:10px;color:rgba(206,217,239,.93);}
.memo .ey{color:#00AFFF;display:block;text-transform:uppercase;font:bold 11px monospace;letter-spacing:.19em;margin-bottom:4px;}
.kv{border-collapse:collapse;width:100%;}
.kv td{font-size:14px;padding:10px;border-bottom:1px solid rgba(240,246,252,.09);}
.tr{text-align:right;}
footer{margin-top:34px;margin-bottom:48px;color:rgba(230,237,243,.48);padding-top:16px;font:11px monospace;border-top:1px solid rgba(240,246,252,.08);}"""

    page = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'/>"
        "<title>ATLAS PDF — "
        + html_lib.escape(str(tk), quote=False)
        + "</title>"
        "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
        "&family=JetBrains+Mono:wght@400;600;700' rel='stylesheet'/>"
        "<style>"
        + stylesheet
        + "</style></head><body><div class='top'><span class='brand'>ATLAS_</span>"
        "<div class='title'>Institutional report · "
        + html_lib.escape(str(tk), quote=False)
        + "</div>"
        + ("<span class='tick'>" + tick_line + "</span>" if tick_line else "")
        + "<span class='muted mono'>"
        + iso_day
        + "</span></div>"
        + banner
        + exec_block
        + trade_section
        + scenarios_section
        + level_section
        + rules_section
        + fm_section
        + cat_section
        + memo_section
        + "<footer>ATLAS synthesis · informational only · not investment advice · "
        + iso_day
        + "</footer></body></html>"
    )
    return page


def main() -> int:
    parser = argparse.ArgumentParser(description="Render saved ATLAS envelope JSON to PDF.")
    parser.add_argument("path", nargs="?", default="", help='JSON path, or "-" reads stdin')
    parser.add_argument("-o", "--output", default="", dest="dest", help="Output PDF path")
    ns = parser.parse_args()
    if not ns.path.strip():
        parser.print_help(sys.stderr)
        return 2
    try:
        if ns.path.strip() == "-":
            blob = sys.stdin.read()
        else:
            jp = Path(ns.path)
            if not jp.exists():
                print("Not found:", jp, file=sys.stderr)
                return 2
            blob = jp.read_text(encoding="utf-8")
        env_doc = json.loads(blob)
        if not isinstance(env_doc, dict):
            raise ValueError("JSON root must be an object dict")
    except (json.JSONDecodeError, OSError, ValueError) as err:
        print("Bad input:", err, file=sys.stderr)
        return 2

    try:
        from weasyprint import HTML
    except ImportError:
        print("pip install weasyprint  (see GTK note in script header for Windows)", file=sys.stderr)
        return 1

    tick_slug = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in _ticker(env_doc)).strip("_")[:42]
    if not tick_slug:
        tick_slug = "report"
    out_dir = DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    target = Path(ns.dest) if ns.dest.strip() else out_dir / (tick_slug + "_" + date.today().strftime("%Y-%m-%d") + ".pdf")

    html_src = build_html(env_doc)
    try:
        HTML(string=html_src, base_url=str(ROOT.absolute())).write_pdf(str(target.resolve()))
    except Exception as exc:  # pylint: disable=broad-except
        print("WeasyPrint failed:", exc, file=sys.stderr)
        return 1

    print(str(target.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
