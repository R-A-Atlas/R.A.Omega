from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_CACHE = ROOT / "data_cache"
SUMMARY_DIR = DATA_CACHE / "summaries"
CRITICAL_PATH_DIR = ROOT / "atlas_agents" / "cognitive" / "critical_paths"
OUTPUT_PATH = ROOT / "atlas_vault" / "03-Outputs" / "data_map.html"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": str(exc)}
    return payload if isinstance(payload, dict) else {"_error": "not_object"}


def cache_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(DATA_CACHE.glob("*_latest.json")):
        payload = read_json(path)
        stem = path.name.replace("_latest.json", "")
        summary = SUMMARY_DIR / f"{stem}_summary.json"
        rows.append(
            {
                "cache": path.name,
                "agent": stem.replace("_", " ").title(),
                "freshness": str(
                    payload.get("generated_at")
                    or payload.get("timestamp")
                    or payload.get("source_generated_at")
                    or "unknown"
                ),
                "records": str(
                    payload.get("record_count")
                    or payload.get("count")
                    or payload.get("total")
                    or ""
                ),
                "summary": "yes" if summary.is_file() else "missing",
                "status": "error" if payload.get("_error") else "ok",
            }
        )
    return rows


def summary_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(SUMMARY_DIR.glob("*_summary.json")):
        payload = read_json(path)
        rows.append(
            {
                "summary": path.name,
                "source": str(payload.get("source_cache") or payload.get("_source_cache") or ""),
                "signal": str(
                    payload.get("signal")
                    or payload.get("breadth_signal")
                    or payload.get("put_call_ratio_signal")
                    or payload.get("market_regime")
                    or ""
                ),
                "records": str(payload.get("record_count") or ""),
                "keys": ", ".join(list(payload.keys())[:8]),
                "status": "error" if payload.get("_error") else "ready",
            }
        )
    return rows


def critical_path_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(CRITICAL_PATH_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        trigger = ""
        for line in text.splitlines():
            if line.upper().startswith("TRIGGER:"):
                trigger = line.split(":", 1)[1].strip()
                break
        rows.append(
            {
                "path": path.name,
                "trigger": trigger,
                "steps": str(sum(1 for line in text.splitlines() if line.startswith("STEP "))),
                "status": "ready",
            }
        )
    return rows


def row_html(row: dict[str, str], cols: list[str]) -> str:
    return "<tr>" + "".join(f"<td>{escape(row.get(col, ''))}</td>" for col in cols) + "</tr>"


def table_html(title: str, subtitle: str, rows: list[dict[str, str]], cols: list[str]) -> str:
    body = "\n".join(row_html(row, cols) for row in rows)
    head = "".join(f"<th>{escape(col.replace('_', ' ').title())}</th>" for col in cols)
    return f"""
    <section>
      <div class="section-head">
        <h2>{escape(title)}</h2>
        <p>{escape(subtitle)}</p>
      </div>
      <table>
        <thead><tr>{head}</tr></thead>
        <tbody>{body}</tbody>
      </table>
    </section>
    """


def render_html() -> str:
    caches = cache_rows()
    summaries = summary_rows()
    paths = critical_path_rows()
    cache_names = {row["cache"].replace("_latest.json", "") for row in caches}
    summary_names = {row["summary"].replace("_summary.json", "") for row in summaries}
    missing_summaries = sorted(cache_names - summary_names)
    orphan_summaries = sorted(summary_names - cache_names)
    gap_rows = [
        {
            "gap": "Caches without summaries",
            "count": str(len(missing_summaries)),
            "items": ", ".join(missing_summaries[:20]) or "none",
        },
        {
            "gap": "Summaries without raw cache",
            "count": str(len(orphan_summaries)),
            "items": ", ".join(orphan_summaries[:20]) or "none",
        },
        {
            "gap": "Critical paths defined",
            "count": str(len(paths)),
            "items": ", ".join(row["path"] for row in paths) or "none",
        },
    ]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>R.A. Omega Data Map</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0B1020;
      --panel: #111827;
      --line: #263244;
      --text: #F8FAFC;
      --muted: #94A3B8;
      --teal: #18C6C8;
      --green: #2ED47A;
      --amber: #F5B84B;
    }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: Inter, Arial, sans-serif; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 40px 24px 72px; }}
    h1 {{ font-family: "Space Grotesk", Inter, sans-serif; font-size: 42px; margin: 0 0 8px; letter-spacing: 0; }}
    h2 {{ font-size: 18px; letter-spacing: .12em; text-transform: uppercase; margin: 0; }}
    p {{ color: var(--muted); margin: 8px 0 0; line-height: 1.5; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 28px 0; }}
    .metric {{ border: 1px solid var(--line); background: var(--panel); padding: 18px; border-radius: 8px; }}
    .metric strong {{ display: block; font-size: 28px; color: var(--teal); }}
    section {{ margin-top: 32px; border: 1px solid var(--line); background: rgba(17,24,39,.72); border-radius: 8px; overflow: hidden; }}
    .section-head {{ padding: 20px; border-bottom: 1px solid var(--line); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ text-align: left; padding: 11px 14px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ color: var(--teal); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; }}
    tr:last-child td {{ border-bottom: 0; }}
    td {{ color: #D7DEE9; }}
    @media (max-width: 760px) {{
      .metrics {{ grid-template-columns: 1fr; }}
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>R.A. Omega Data Map</h1>
    <p>Generated {escape(utc_now())}. This map shows the pantry, prep table, and plate for the active intelligence layer.</p>
    <div class="metrics">
      <div class="metric"><strong>{len(caches)}</strong><span>raw cache files</span></div>
      <div class="metric"><strong>{len(summaries)}</strong><span>summary files</span></div>
      <div class="metric"><strong>{len(paths)}</strong><span>critical paths</span></div>
    </div>
    {table_html("Pantry", "All data-cache inputs and freshness timestamps.", caches, ["cache", "agent", "freshness", "records", "summary", "status"])}
    {table_html("Prep Table", "Compact summary files used by Omega before raw cache fallback.", summaries, ["summary", "source", "signal", "records", "keys", "status"])}
    {table_html("Plate", "Deterministic workflows available to the agent layer.", paths, ["path", "trigger", "steps", "status"])}
    {table_html("Gap Analysis", "Missing or incomplete connective tissue.", gap_rows, ["gap", "count", "items"])}
  </main>
</body>
</html>
"""


def main() -> dict[str, Any]:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    html = render_html()
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    result = {
        "ok": True,
        "output": OUTPUT_PATH.as_posix(),
        "cache_files": len(cache_rows()),
        "summary_files": len(summary_rows()),
        "critical_paths": len(critical_path_rows()),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    main()
