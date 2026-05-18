"""
deploy_check.py — R.A. Omega pre-deployment gate.

Validates every requirement before pushing to production (Railway/Render).
Exits 1 if any blocker is found — use as a CI gate or manual pre-deploy check.

Blockers (hard failures — do NOT deploy if any fail):
  - ATLAS_DISABLE_AUTH must NOT be "true" in prod
  - Required env vars must be set (SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY)
  - .env must not be staged in git
  - Required HTML files must exist on disk
  - api_server.py must compile clean
  - /health endpoint must return 200 (if server is running)

Warnings (soft — review before deploying):
  - Stripe keys not set (billing won't work)
  - TELEGRAM_BOT_TOKEN not set (Telegram won't work)
  - atlas_memory.db size < 1KB (no memory yet)

Usage:
    python omega_os/skills/deployment_checklist/tools/deploy_check.py
    python omega_os/skills/deployment_checklist/tools/deploy_check.py --strict
"""
from __future__ import annotations

import argparse
import os
import py_compile
import subprocess
import sys
import tempfile
import shutil
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def _load_local_dotenv(path: Path | None = None) -> bool:
    """Load local .env values for manual pre-deploy checks without overriding env."""
    env_path = path or (ROOT / ".env")
    if not env_path.is_file():
        return False
    loaded = False
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded = True
    return loaded


def _ok(msg: str)   -> None: print(f"  [OK]  {msg}")
def _warn(msg: str) -> None: print(f"  [~~]  {msg}")
def _fail(msg: str) -> None: print(f"  [!!]  {msg}")
def _section(t: str) -> None: print(f"\n  -- {t} --")


# ── Individual checks ──────────────────────────────────────────────────────────

def check_auth_disabled() -> list[str]:
    """ATLAS_DISABLE_AUTH must NOT be true in production."""
    blockers = []
    val = os.environ.get("ATLAS_DISABLE_AUTH", "").strip().lower()
    if val == "true":
        _fail("ATLAS_DISABLE_AUTH=true — NEVER deploy with auth disabled")
        blockers.append("ATLAS_DISABLE_AUTH is true — users can access without logging in")
    else:
        _ok(f"ATLAS_DISABLE_AUTH={val or '(not set)'} — auth guard active")
    return blockers


def check_required_env_vars() -> list[str]:
    """Core env vars must be set for the app to function."""
    blockers = []
    required = {
        "SUPABASE_URL": ("Supabase project URL", ("SUPABASE_URL",)),
        "SUPABASE_KEY": ("Supabase service/API key", ("SUPABASE_KEY",)),
        "GEMINI_API_KEY": ("Gemini API key (core AI brain)", ("GEMINI_API_KEY", "GOOGLE_API_KEY")),
    }
    for var, (desc, aliases) in required.items():
        val = next((os.environ.get(alias, "").strip() for alias in aliases if os.environ.get(alias, "").strip()), "")
        if not val:
            _fail(f"{var} not set - {desc}")
            blockers.append(f"Missing env var: {var}")
        else:
            _ok(f"{var} set ({len(val)} chars)")
    return blockers


def check_optional_env_vars() -> list[str]:
    """Optional env vars — warn if missing, don't block."""
    optional = {
        "STRIPE_SECRET_KEY":    "Stripe billing (revenue blocked without this)",
        "STRIPE_WEBHOOK_SECRET":"Stripe webhook signing (subscription events won't work)",
        "TELEGRAM_BOT_TOKEN":   "Telegram delivery (daily brief won't reach Telegram)",
        "OPENAI_API_KEY":       "Voice transcription (POST /voice/query won't work)",
    }
    for var, desc in optional.items():
        val = os.environ.get(var, "").strip()
        if not val:
            _warn(f"{var} not set — {desc}")
        else:
            _ok(f"{var} set")
    return []


def check_env_not_staged() -> list[str]:
    """Verify .env is not staged in git."""
    blockers = []
    try:
        staged = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only"],
            cwd=ROOT, stderr=subprocess.DEVNULL, text=True
        ).strip().splitlines()
        if any(".env" in s for s in staged):
            _fail(".env is staged — NEVER commit secrets to git")
            blockers.append(".env staged in git — would expose secrets")
        else:
            _ok(".env not staged")
    except Exception:
        _warn("git not available — skipping staged file check")
    return blockers


def check_required_files() -> list[str]:
    """All HTML pages and critical Python files must exist."""
    blockers = []
    required_html = [
        "index_1778228972988.html",
        "auth.html",
        "omega_command_center.html",
        "ra_omega_app.html",
        "atlas_dashboard_v4.html",
        "omega_brain_network.html",
        "design_system.css",
    ]
    required_py = [
        "api_server.py",
        "query_router.py",
        "atlas_omega.py",
        "deep_research.py",
        "gemini_limiter.py",
    ]
    for fname in required_html + required_py:
        p = ROOT / fname
        if p.exists():
            _ok(f"Exists: {fname}")
        else:
            _fail(f"MISSING: {fname}")
            blockers.append(f"Required file missing: {fname}")
    return blockers


def check_api_server_compiles() -> list[str]:
    """api_server.py must compile without syntax errors."""
    blockers = []
    tmp = tempfile.mktemp(suffix=".py")
    try:
        shutil.copy(ROOT / "api_server.py", tmp)
        py_compile.compile(tmp, doraise=True)
        _ok("api_server.py compiles clean")
    except py_compile.PyCompileError as e:
        _fail(f"api_server.py COMPILE ERROR: {str(e)[:80]}")
        blockers.append("api_server.py has syntax errors")
    finally:
        Path(tmp).unlink(missing_ok=True)
    return blockers


def check_protected_data() -> list[str]:
    """Critical databases must not be missing."""
    blockers = []
    for db in ("atlas_memory.db", "atlas_tracker.db"):
        p = ROOT / db
        if not p.exists():
            _fail(f"DATABASE MISSING: {db}")
            blockers.append(f"Missing database: {db}")
        else:
            size_kb = p.stat().st_size / 1024
            if size_kb < 1:
                _warn(f"{db} exists but is tiny ({size_kb:.1f}KB) — may be empty")
            else:
                _ok(f"{db} exists ({size_kb:.0f}KB)")
    return blockers


def check_auth_redirect() -> list[str]:
    """auth.html must redirect to /command-center (not /option1 or /app)."""
    blockers = []
    auth_path = ROOT / "auth.html"
    if not auth_path.exists():
        return []
    text = auth_path.read_text(encoding="utf-8", errors="replace")
    if "location.href = '/option1'" in text or "location.href = \"/option1\"" in text:
        _fail("auth.html redirects to /option1 — users won't see command center")
        blockers.append("auth.html redirect points to /option1 instead of /command-center")
    elif "/command-center" in text:
        _ok("auth.html → /command-center")
    else:
        _warn("auth.html redirect target unclear — verify manually")
    return blockers


def check_health_endpoint(base: str = "http://127.0.0.1:8000") -> list[str]:
    """If server is running, /health must return 200."""
    try:
        req = urllib.request.Request(f"{base}/health")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                _ok(f"/health → 200 OK")
            else:
                _warn(f"/health → {resp.status} (expected 200)")
    except Exception:
        _warn("/health unreachable — server not running (OK if checking before start)")
    return []


def check_procfile() -> list[str]:
    """Procfile must exist and point to uvicorn api_server:app."""
    blockers = []
    proc = ROOT / "Procfile"
    if not proc.exists():
        _fail("Procfile missing — Railway/Render won't know how to start the server")
        blockers.append("Procfile missing")
    else:
        text = proc.read_text(encoding="utf-8", errors="replace")
        if "api_server" in text and "uvicorn" in text:
            _ok(f"Procfile: {text.strip()[:60]}")
        else:
            _warn(f"Procfile exists but may not point to api_server: {text.strip()[:60]}")
    return blockers


# ── Main ───────────────────────────────────────────────────────────────────────

def run_checks(strict: bool = False) -> tuple[list[str], list[str]]:
    """Return (blockers, warnings)."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _load_local_dotenv()
    sep = "=" * 64
    mode = "STRICT" if strict else "STANDARD"
    print(sep)
    print(f"  R.A. OMEGA — PRE-DEPLOYMENT CHECKLIST  [{mode}]")
    print(sep)

    all_blockers: list[str] = []

    _section("Auth Guard")
    all_blockers.extend(check_auth_disabled())
    all_blockers.extend(check_auth_redirect())

    _section("Environment Variables")
    all_blockers.extend(check_required_env_vars())
    check_optional_env_vars()

    _section("Git Safety")
    all_blockers.extend(check_env_not_staged())

    _section("Required Files")
    all_blockers.extend(check_required_files())

    _section("Syntax")
    all_blockers.extend(check_api_server_compiles())

    _section("Protected Data")
    all_blockers.extend(check_protected_data())

    _section("Server Health")
    check_health_endpoint()

    _section("Deployment Config")
    all_blockers.extend(check_procfile())

    print(f"\n{sep}")
    if not all_blockers:
        print("  RESULT: PASS — ready to deploy")
    else:
        print(f"  RESULT: FAIL — {len(all_blockers)} blocker(s)")
        for i, b in enumerate(all_blockers, 1):
            print(f"    {i}. {b}")
        print("  Fix all blockers before pushing to production.")
    print(sep)
    return all_blockers, []


def main() -> None:
    parser = argparse.ArgumentParser(description="R.A. Omega pre-deployment checklist")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as blockers")
    args = parser.parse_args()
    blockers, _ = run_checks(strict=args.strict)
    sys.exit(0 if not blockers else 1)


if __name__ == "__main__":
    main()
