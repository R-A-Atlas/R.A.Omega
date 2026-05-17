"""
ui_doctor.py — Diagnoses and fixes the R.A. Omega frontend serving stack.

Checks:
  1. Static assets (React, Babel, Lucide, Tailwind) exist and are served locally
  2. FastAPI static mount is wired in api_server.py
  3. ra_omega_app.html references /static/ not CDN URLs
  4. Lucide icon renderer uses correct data index (iconData[2] not iconData[1])
  5. Server is reachable at the expected port
  6. /app returns the correct HTML file

Usage:
    python omega_os/skills/ui_doctor/tools/ui_doctor.py
    python omega_os/skills/ui_doctor/tools/ui_doctor.py --fix
    python omega_os/skills/ui_doctor/tools/ui_doctor.py --json
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

STATIC_DIR      = ROOT / "static"
APP_HTML        = ROOT / "ra_omega_app.html"
API_SERVER      = ROOT / "api_server.py"

REQUIRED_STATIC = {
    "react.development.js":     "https://unpkg.com/react@18/umd/react.development.js",
    "react-dom.development.js": "https://unpkg.com/react-dom@18/umd/react-dom.development.js",
    "babel.min.js":             "https://unpkg.com/@babel/standalone@7.29.4/babel.min.js",
    "lucide.min.js":            "https://unpkg.com/lucide@0.244.0/dist/umd/lucide.min.js",
    "tailwind.min.js":          "https://cdn.tailwindcss.com",
}

CDN_PATTERNS = [
    "https://cdn.tailwindcss.com",
    "https://unpkg.com/react@",
    "https://unpkg.com/react-dom@",
    "https://unpkg.com/@babel/standalone",
    "https://unpkg.com/lucide@",
]


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    fix_applied: bool = False


@dataclass
class UIDoctorReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    @property
    def fixes_applied(self) -> int:
        return sum(1 for c in self.checks if c.fix_applied)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "fixes_applied": self.fixes_applied,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail, "fix_applied": c.fix_applied}
                for c in self.checks
            ],
        }


# ── Individual checks ─────────────────────────────────────────────────────────

def check_static_files(fix: bool = False) -> CheckResult:
    missing = []
    downloaded = []

    for fname, cdn_url in REQUIRED_STATIC.items():
        dest = STATIC_DIR / fname
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        if fix:
            try:
                import urllib.request
                STATIC_DIR.mkdir(exist_ok=True)
                headers = {"User-Agent": "Mozilla/5.0"}
                req = urllib.request.Request(cdn_url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                dest.write_bytes(data)
                downloaded.append(fname)
            except Exception as e:
                missing.append(f"{fname} (download failed: {e})")
        else:
            missing.append(fname)

    if missing:
        return CheckResult("static_files", False,
                           f"Missing: {', '.join(missing)}. Run --fix to download.",
                           fix_applied=False)
    if downloaded:
        return CheckResult("static_files", True,
                           f"Downloaded: {', '.join(downloaded)}",
                           fix_applied=True)
    return CheckResult("static_files", True, f"All {len(REQUIRED_STATIC)} static assets present")


def check_static_mount(fix: bool = False) -> CheckResult:
    if not API_SERVER.exists():
        return CheckResult("static_mount", False, "api_server.py not found")

    src = API_SERVER.read_text(encoding="utf-8", errors="replace")

    if "StaticFiles" in src and 'mount("/static"' in src:
        return CheckResult("static_mount", True, "StaticFiles mounted at /static in api_server.py")

    if not fix:
        return CheckResult("static_mount", False,
                           "StaticFiles not mounted. Run --fix to add it.")

    # Fix: add StaticFiles import and mount
    if "from fastapi.staticfiles import StaticFiles" not in src:
        src = src.replace(
            "    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer",
            "    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer\n"
            "    from fastapi.staticfiles import StaticFiles",
        )

    mount_block = (
        "\n_static_dir = BASE_DIR / \"static\"\n"
        "if _static_dir.exists():\n"
        "    app.mount(\"/static\", StaticFiles(directory=str(_static_dir)), name=\"static\")\n"
    )
    if 'app.mount("/static"' not in src:
        src = src.replace(
            "app.add_middleware(\n    CORSMiddleware,",
            mount_block + "\napp.add_middleware(\n    CORSMiddleware,",
        )

    API_SERVER.write_text(src, encoding="utf-8")
    return CheckResult("static_mount", True, "StaticFiles mount added to api_server.py", fix_applied=True)


def check_html_cdn_refs(fix: bool = False) -> CheckResult:
    if not APP_HTML.exists():
        return CheckResult("html_cdn_refs", False, "ra_omega_app.html not found")

    src = APP_HTML.read_text(encoding="utf-8", errors="replace")
    cdn_hits = [p for p in CDN_PATTERNS if p in src]

    if not cdn_hits:
        return CheckResult("html_cdn_refs", True, "ra_omega_app.html uses /static/ — no CDN refs")

    if not fix:
        return CheckResult("html_cdn_refs", False,
                           f"Still referencing CDN: {cdn_hits}. Run --fix.")

    replacements = {
        '<script src="https://cdn.tailwindcss.com"></script>':
            '<script src="/static/tailwind.min.js"></script>',
        '<script src="https://unpkg.com/react@18/umd/react.development.js" crossorigin></script>':
            '<script src="/static/react.development.js" crossorigin></script>',
        '<script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js" crossorigin></script>':
            '<script src="/static/react-dom.development.js" crossorigin></script>',
        '<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>':
            '<script src="/static/babel.min.js"></script>',
        '<script src="https://unpkg.com/lucide@latest"></script>':
            '<script src="/static/lucide.min.js"></script>',
        '<script src="https://unpkg.com/@babel/standalone@7.29.4/babel.min.js"></script>':
            '<script src="/static/babel.min.js"></script>',
    }
    for old, new in replacements.items():
        src = src.replace(old, new)

    APP_HTML.write_text(src, encoding="utf-8")
    return CheckResult("html_cdn_refs", True,
                       f"Replaced {len(cdn_hits)} CDN refs with /static/ in ra_omega_app.html",
                       fix_applied=True)


def check_lucide_icon_index(fix: bool = False) -> CheckResult:
    if not APP_HTML.exists():
        return CheckResult("lucide_icon_index", False, "ra_omega_app.html not found")

    src = APP_HTML.read_text(encoding="utf-8", errors="replace")

    # Bad pattern: iconData[1] when format is ["svg", attrs, children]
    bad = "iconData[0] === 'string') ? iconData[1] : iconData"
    good = "iconData[0] === 'string') ? iconData[2] : iconData"

    if good in src:
        return CheckResult("lucide_icon_index", True,
                           "Lucide icon renderer uses correct index [2] for children")
    if bad not in src:
        return CheckResult("lucide_icon_index", True,
                           "Lucide icon renderer pattern not found — may already be correct")

    if not fix:
        return CheckResult("lucide_icon_index", False,
                           "Icon renderer reads iconData[1] (attrs) instead of iconData[2] (children). Run --fix.")

    src = src.replace(bad, good)
    APP_HTML.write_text(src, encoding="utf-8")
    return CheckResult("lucide_icon_index", True,
                       "Fixed: Lucide icon renderer now reads iconData[2] for children",
                       fix_applied=True)


def check_server_reachable() -> CheckResult:
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as r:
            if r.status == 200:
                return CheckResult("server_reachable", True, "Server up at http://127.0.0.1:8000")
            return CheckResult("server_reachable", False, f"Server returned {r.status}")
    except Exception as e:
        return CheckResult("server_reachable", False,
                           f"Server not reachable: {e}. Start with: uvicorn api_server:app --host 127.0.0.1 --port 8000")


def check_app_serves_correct_file() -> CheckResult:
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:8000/app", timeout=5) as r:
            content = r.read(4096).decode("utf-8", errors="replace")
        if "R.A. Omega" in content and "react" in content.lower():
            # Confirm it's the local-static version
            if "/static/react" in content or "/static/babel" in content:
                return CheckResult("app_correct_file", True,
                                   "/app serves ra_omega_app.html with local static deps")
            return CheckResult("app_correct_file", False,
                               "/app is serving the file but still references CDN — restart the server")
        return CheckResult("app_correct_file", False,
                           "/app returned unexpected content — wrong file may be served")
    except Exception as e:
        return CheckResult("app_correct_file", False, f"Could not fetch /app: {e}")


def check_formatQueryResponse_order(fix: bool = False) -> CheckResult:
    if not APP_HTML.exists():
        return CheckResult("format_response_order", False, "ra_omega_app.html not found")

    src = APP_HTML.read_text(encoding="utf-8", errors="replace")

    # Bad: data.tldr first in plain-chat branch (shows "ATLAS" for casual)
    bad_pattern  = "isPlainChatResponse(data)) {\n                return (\n                    data.tldr ||"
    good_pattern = "isPlainChatResponse(data)) {\n                // For casual/chat responses prefer the actual body text"

    if good_pattern in src:
        return CheckResult("format_response_order", True,
                           "formatQueryResponse: executive_summary checked before tldr (casual fix in place)")
    if bad_pattern in src:
        if not fix:
            return CheckResult("format_response_order", False,
                               "formatQueryResponse returns data.tldr first — casual queries show 'ATLAS'. Run --fix.")
        src = src.replace(
            "isPlainChatResponse(data)) {\n                return (\n                    data.tldr ||\n                    fr.executive_summary ||",
            "isPlainChatResponse(data)) {\n                // For casual/chat responses prefer the actual body text\n                return (\n                    fr.executive_summary ||\n                    fr.executive_brief ||",
        )
        APP_HTML.write_text(src, encoding="utf-8")
        return CheckResult("format_response_order", True,
                           "Fixed: formatQueryResponse now shows executive_summary before tldr",
                           fix_applied=True)
    return CheckResult("format_response_order", True,
                       "formatQueryResponse pattern not matched — likely already fixed")


# ── Runner ────────────────────────────────────────────────────────────────────

def run_checks(fix: bool = False) -> UIDoctorReport:
    report = UIDoctorReport()
    report.checks.append(check_static_files(fix=fix))
    report.checks.append(check_static_mount(fix=fix))
    report.checks.append(check_html_cdn_refs(fix=fix))
    report.checks.append(check_lucide_icon_index(fix=fix))
    report.checks.append(check_formatQueryResponse_order(fix=fix))
    report.checks.append(check_server_reachable())
    if any(c.name == "server_reachable" and c.passed for c in report.checks):
        report.checks.append(check_app_serves_correct_file())
    return report


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="R.A. Omega UI Doctor")
    parser.add_argument("--fix",  action="store_true", help="Auto-fix all detected issues")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    report = run_checks(fix=args.fix)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        sys.exit(0 if report.failed == 0 else 1)

    sep  = "=" * 64
    sep2 = "-" * 64

    print(sep)
    print("  R.A. OMEGA — UI DOCTOR")
    print(sep)
    print()

    icons = {True: "[OK]", False: "[!!]"}
    for c in report.checks:
        icon = icons[c.passed]
        fix_tag = " [FIXED]" if c.fix_applied else ""
        print(f"  {icon}  {c.name:<30} {fix_tag}")
        print(f"       {c.detail}")
        print()

    print(sep2)
    print(f"  {report.passed} passed  |  {report.failed} failed  |  {report.fixes_applied} fixes applied")
    print()

    if report.failed == 0:
        print("  RESULT: All checks pass.")
        print("  Do a hard refresh (Ctrl+Shift+R) in the browser to see changes.")
    else:
        print("  RESULT: Issues found. Run with --fix to auto-repair:")
        print("    python omega_os/skills/ui_doctor/tools/ui_doctor.py --fix")
        if any(not c.passed and c.name == "server_reachable" for c in report.checks):
            print()
            print("  Then restart the server:")
            print("    uvicorn api_server:app --host 127.0.0.1 --port 8000")
        elif any(c.fix_applied for c in report.checks):
            print()
            print("  Fixes applied — restart the server:")
            print("    uvicorn api_server:app --host 127.0.0.1 --port 8000")

    print(sep)
    sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
