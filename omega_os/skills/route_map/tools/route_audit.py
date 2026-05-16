"""
route_audit.py — R.A. Omega route and HTML file audit tool.

Scans api_server.py for all routes, checks which HTML files exist,
and reports:
  - Every page route and what file it serves
  - Orphaned HTML files (not routed)
  - Dead file references (routed but file missing)
  - Auth redirect correctness

Usage:
    python omega_os/skills/route_map/tools/route_audit.py
    python omega_os/skills/route_map/tools/route_audit.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# HTML files intentionally kept but not served (per CLAUDE.md Section 5)
IGNORE_ORPHANS = {
    "atlas_dashboard_v2.html",
    "atlas_dashboard_v3.html",
    "dashboard.html",
    "ATLAS_OUTPUT_MAP.html",
    "ATLAS_OVERVIEW.html",
    "CANVAS_1_Roadmap.html",
    "CANVAS_3_ATLAS_vs_World.html",
    "CANVAS_4_Intelligence_Layers.html",
    "LIVE_SCRATCHPAD.html",
    "index_1778307874705.html",   # legacy landing — referenced by test_cursor_launch_kit.py, no route needed
}

# Files served via helper functions or via path outside root — scanner can't trace these
# auto-generated or sub-folder paths, or served via helper (_zenith_landing_response etc.)
EXPLICITLY_SERVED = {
    "index_1778228972988.html",   # GET /  via _zenith_landing_response
    "auth.html",                  # GET /auth
    "ra_omega_app.html",          # GET /app
    "atlas_dashboard_v4.html",    # GET /dashboard and /v2  via _dashboard_html_response
    "data_map.html",              # GET /data-map  (auto-generated, lives in atlas_vault/03-Outputs/)
}


@dataclass
class RouteEntry:
    method: str
    path: str
    serves: str        # filename, redirect target, or "(JSON/logic)"
    file_exists: bool


@dataclass
class AuditReport:
    routes: list[RouteEntry] = field(default_factory=list)
    orphaned_html: list[str] = field(default_factory=list)
    dead_references: list[str] = field(default_factory=list)
    auth_redirect_ok: bool = True
    auth_redirect_target: str = ""


# ── Route parsing ──────────────────────────────────────────────────────────────

def _extract_route_blocks(api_text: str) -> list[tuple[str, str, str]]:
    """
    Return list of (method, path, function_body) for every route handler.
    Handles stacked decorators like @app.get("/v2") / @app.get("/dashboard").
    """
    results = []
    # Split file into function-level chunks
    fn_pattern = re.compile(
        r'(@app\.[a-z]+\(["\'][^"\']+["\']\)(?:\s*\n\s*@app\.[a-z]+\(["\'][^"\']+["\']\))*)\s*\n'
        r'def (\w+)\([^)]*\).*?(?=\n@app\.|\Z)',
        re.DOTALL
    )
    for m in fn_pattern.finditer(api_text):
        decorators = m.group(1)
        body       = m.group(0)
        # Extract all (method, path) pairs from stacked decorators
        for dec_m in re.finditer(r'@app\.(\w+)\(["\']([^"\']+)["\']', decorators):
            results.append((dec_m.group(1).upper(), dec_m.group(2), body))
    return results


def _serves_from_body(body: str) -> tuple[str, bool]:
    """
    Return (serves_description, file_exists) by scanning the function body
    for .html filenames, redirects, and HTML responses.
    """
    # RedirectResponse
    rr = re.search(r'RedirectResponse\(url=["\']([^"\']+)["\']', body)
    if rr:
        return f"→ {rr.group(1)}", True

    # Pure HTML filenames (no spaces = real filenames, not error messages)
    html_m = re.findall(r'["\']([A-Za-z0-9_\-]+\.html)["\']', body)
    if html_m:
        fname = html_m[0]            # first match is the path assignment
        fpath = ROOT / fname
        if not fpath.is_file():
            fpath = ROOT / Path(fname).name
        return Path(fname).name, fpath.is_file()

    # Inline HTMLResponse (no file)
    if "HTMLResponse" in body and "FileResponse" not in body:
        return "(inline HTML)", True

    return "(JSON/logic)", True


def _parse_routes(api_text: str) -> list[RouteEntry]:
    entries: list[RouteEntry] = []
    seen: set[tuple[str, str]] = set()

    for method, path, body in _extract_route_blocks(api_text):
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        serves, file_exists = _serves_from_body(body)
        entries.append(RouteEntry(method=method, path=path, serves=serves, file_exists=file_exists))

    return entries


# ── Orphan detection ───────────────────────────────────────────────────────────

def _find_orphaned_html(routes: list[RouteEntry]) -> list[str]:
    """HTML files in root that are not referenced by any route."""
    served: set[str] = set(EXPLICITLY_SERVED)
    for r in routes:
        if r.serves and r.serves.endswith(".html"):
            served.add(Path(r.serves).name)

    orphaned = []
    for f in sorted(ROOT.glob("*.html")):
        if f.name in IGNORE_ORPHANS:
            continue
        if f.name not in served:
            orphaned.append(f.name)
    return orphaned


# ── Auth redirect check ────────────────────────────────────────────────────────

def _check_auth_redirect(auth_html_path: Path) -> tuple[bool, str]:
    """Return (is_correct, target) for the post-login redirect in auth.html."""
    if not auth_html_path.is_file():
        return False, "auth.html not found"
    text = auth_html_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", text)
    target = m.group(1) if m else "unknown"
    ok = target == "/command-center"
    return ok, target


# ── Main ───────────────────────────────────────────────────────────────────────

def run_audit() -> AuditReport:
    api_text = (ROOT / "api_server.py").read_text(encoding="utf-8", errors="replace")
    routes   = _parse_routes(api_text)

    orphaned  = _find_orphaned_html(routes)
    # data_map.html is auto-generated on demand — not a blocker if missing
    dead_refs = [r.path for r in routes
                 if not r.file_exists and r.serves.endswith(".html")
                 and r.serves not in {"data_map.html"}]
    auth_ok, auth_target = _check_auth_redirect(ROOT / "auth.html")

    return AuditReport(
        routes=routes,
        orphaned_html=orphaned,
        dead_references=dead_refs,
        auth_redirect_ok=auth_ok,
        auth_redirect_target=auth_target,
    )


def print_report(report: AuditReport) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    sep = "=" * 68
    print(sep)
    print("  R.A. OMEGA — ROUTE MAP AUDIT")
    print(sep)

    # ── Page routes ──────────────────────────────────────────────────────
    page_routes = [r for r in report.routes
                   if r.method == "GET" and r.serves != "(JSON/logic)"]
    if page_routes:
        print(f"\n  PAGE ROUTES  ({len(page_routes)} total)")
        print(f"  {'PATH':<30} {'SERVES':<36} STATUS")
        print(f"  {'-'*30} {'-'*36} ------")
        for r in sorted(page_routes, key=lambda x: x.path):
            status = "[OK]" if r.file_exists else "[!!] MISSING"
            print(f"  {r.path:<30} {r.serves:<36} {status}")

    # ── API routes ───────────────────────────────────────────────────────
    api_count = sum(1 for r in report.routes if r.serves == "(JSON/logic)")
    print(f"\n  API ENDPOINTS: {api_count} data/logic routes")

    # ── Auth redirect ────────────────────────────────────────────────────
    print("\n  AUTH REDIRECT")
    if report.auth_redirect_ok:
        print(f"  [OK]  auth.html → {report.auth_redirect_target}")
    else:
        print(f"  [!!]  auth.html → {report.auth_redirect_target}  ← should be /command-center")

    # ── Orphaned HTML ────────────────────────────────────────────────────
    print(f"\n  ORPHANED HTML FILES ({len(report.orphaned_html)})")
    if report.orphaned_html:
        for f in report.orphaned_html:
            print(f"  [~~]  {f}  ← no route serves this file")
    else:
        print("  [OK]  None")

    # ── Dead file refs ───────────────────────────────────────────────────
    print(f"\n  DEAD FILE REFERENCES ({len(report.dead_references)})")
    if report.dead_references:
        for r in report.dead_references:
            print(f"  [!!]  Route {r} references a missing HTML file")
    else:
        print("  [OK]  None")

    # ── Result ───────────────────────────────────────────────────────────
    blockers = len(report.dead_references) + (0 if report.auth_redirect_ok else 1)
    warnings = len(report.orphaned_html)
    print(f"\n{sep}")
    if blockers:
        print(f"  RESULT: FAIL — {blockers} blocker(s), {warnings} warning(s)")
    else:
        print(f"  RESULT: PASS — 0 blockers, {warnings} warning(s)")
    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(description="R.A. Omega route map audit")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    report = run_audit()

    if args.json:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(json.dumps({
            "page_routes": [
                {"method": r.method, "path": r.path, "serves": r.serves, "file_exists": r.file_exists}
                for r in report.routes if r.serves != "(JSON/logic)"
            ],
            "api_endpoint_count": sum(1 for r in report.routes if r.serves == "(JSON/logic)"),
            "orphaned_html": report.orphaned_html,
            "dead_references": report.dead_references,
            "auth_redirect_ok": report.auth_redirect_ok,
            "auth_redirect_target": report.auth_redirect_target,
        }, indent=2))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
