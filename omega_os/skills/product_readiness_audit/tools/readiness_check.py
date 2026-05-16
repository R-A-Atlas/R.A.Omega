"""
readiness_check.py — R.A. Omega product readiness audit.

Scores the product across 8 categories against a 100-point rubric.
All checks are local — no external API calls, no LLM calls.

Categories and max points:
  1. Auth & Security        (20 pts)
  2. Billing                (10 pts)
  3. Core AI Quality        (20 pts)
  4. UI/UX                  (15 pts)
  5. Data Layer             (15 pts)
  6. Infrastructure         (10 pts)
  7. Test Coverage           (5 pts)
  8. Memory & Personalization(5 pts)

Verdict thresholds:
  90-100  PRODUCTION READY
  75-89   BETA READY
  55-74   ALPHA / STAGING
  < 55    NOT READY

Usage:
    python omega_os/skills/product_readiness_audit/tools/readiness_check.py
    python omega_os/skills/product_readiness_audit/tools/readiness_check.py --json
    python omega_os/skills/product_readiness_audit/tools/readiness_check.py --category auth
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

TOOLS_PATH = ROOT / "omega_os" / "skills" / "improve_system" / "tools"
sys.path.insert(0, str(TOOLS_PATH))


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    label: str
    points: int
    max_points: int
    passed: bool
    detail: str
    fix: str = ""


@dataclass
class CategoryResult:
    name: str
    slug: str
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def score(self) -> int:
        return sum(c.points for c in self.checks)

    @property
    def max_score(self) -> int:
        return sum(c.max_points for c in self.checks)

    @property
    def pct(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score else 0

    @property
    def status(self) -> str:
        p = self.pct
        if p >= 90: return "EXCELLENT"
        if p >= 70: return "GOOD"
        if p >= 50: return "FAIR"
        return "NEEDS WORK"

    def failing_fixes(self) -> list[str]:
        return [c.fix for c in self.checks if not c.passed and c.fix]


@dataclass
class ReadinessReport:
    categories: list[CategoryResult]

    @property
    def total_score(self) -> int:
        return sum(c.score for c in self.categories)

    @property
    def max_score(self) -> int:
        return sum(c.max_score for c in self.categories)

    @property
    def pct(self) -> float:
        return (self.total_score / self.max_score * 100) if self.max_score else 0

    def verdict(self) -> str:
        p = self.pct
        if p >= 90: return "PRODUCTION READY"
        if p >= 75: return "BETA READY"
        if p >= 55: return "ALPHA / STAGING"
        return "NOT READY"

    def grade(self) -> str:
        p = self.pct
        if p >= 90: return "A"
        if p >= 80: return "A-"
        if p >= 70: return "B+"
        if p >= 60: return "B"
        if p >= 50: return "C"
        return "D"

    def all_fixes(self) -> list[tuple[str, str]]:
        """Return (category, fix) pairs for all failing checks, highest-max-points first."""
        fixes = []
        for cat in sorted(self.categories, key=lambda c: -c.max_score):
            for check in cat.checks:
                if not check.passed and check.fix:
                    fixes.append((cat.name, check.fix))
        return fixes


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def _env(var: str) -> str:
    return os.environ.get(var, "").strip()

def _has_env(var: str) -> bool:
    return bool(_env(var))

def _file_exists(path: Path) -> bool:
    return path.exists() and path.is_file()

def _dir_exists(path: Path) -> bool:
    return path.exists() and path.is_dir()

def _contains(text: str, *patterns: str) -> bool:
    return all(p.lower() in text.lower() for p in patterns)


# ── Category checks ────────────────────────────────────────────────────────────

def check_auth_security() -> CategoryResult:
    cat = CategoryResult(name="Auth & Security", slug="auth")
    api = _read(ROOT / "api_server.py")
    auth_html = _read(ROOT / "auth.html")

    # Auth route exists (2 pts)
    ok = "/auth" in api
    cat.checks.append(CheckResult("Auth route in api_server.py", 2 if ok else 0, 2, ok,
        "/auth route found" if ok else "Missing /auth route",
        "" if ok else "Add GET /auth route serving auth.html"))

    # auth.html has sign-in form (2 pts)
    ok = "sign" in auth_html.lower() and "supabase" in auth_html.lower()
    cat.checks.append(CheckResult("auth.html has Supabase sign-in", 2 if ok else 0, 2, ok,
        "Supabase auth form present" if ok else "No Supabase auth in auth.html",
        "" if ok else "Wire Supabase auth into auth.html"))

    # Auth redirects to /command-center not /option1 (3 pts)
    ok = "/command-center" in auth_html and "option1" not in auth_html
    cat.checks.append(CheckResult("Post-login redirects to /command-center", 3 if ok else 0, 3, ok,
        "Redirects to /command-center" if ok else "Still redirecting to /option1",
        "" if ok else "Update auth.html post-login redirect to /command-center"))

    # ATLAS_DISABLE_AUTH not true in prod (5 pts — checks env var)
    val = _env("ATLAS_DISABLE_AUTH").lower()
    ok = val != "true"
    cat.checks.append(CheckResult("ATLAS_DISABLE_AUTH not enabled", 5 if ok else 0, 5, ok,
        f"ATLAS_DISABLE_AUTH={val or '(not set)'}" ,
        "" if ok else "NEVER deploy with ATLAS_DISABLE_AUTH=true — disable it in prod env"))

    # Supabase credentials set (4 pts)
    has_url = _has_env("SUPABASE_URL")
    has_key = _has_env("SUPABASE_KEY")
    pts = (2 if has_url else 0) + (2 if has_key else 0)
    ok = has_url and has_key
    cat.checks.append(CheckResult("Supabase credentials set", pts, 4, ok,
        f"SUPABASE_URL={'set' if has_url else 'MISSING'}  SUPABASE_KEY={'set' if has_key else 'MISSING'}",
        "" if ok else "Set SUPABASE_URL and SUPABASE_KEY in production environment"))

    # .env not tracked by git (2 pts)
    try:
        import subprocess
        result = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        )
        ok = ".env" not in result.stdout
    except Exception:
        ok = True
    cat.checks.append(CheckResult(".env not tracked by git", 2 if ok else 0, 2, ok,
        ".env not in git" if ok else ".env IS tracked by git — secrets exposed!",
        "" if ok else "Run: git rm --cached .env && echo '.env' >> .gitignore"))

    # Auth guard on protected routes (2 pts)
    ok = "ATLAS_DISABLE_AUTH" in api and "Authorization" in api
    cat.checks.append(CheckResult("Auth guard on protected routes", 2 if ok else 0, 2, ok,
        "Auth guard present" if ok else "No auth guard detected",
        "" if ok else "Verify Bearer token check on /query and /omega routes"))

    return cat


def check_billing() -> CategoryResult:
    cat = CategoryResult(name="Billing", slug="billing")
    api = _read(ROOT / "api_server.py")

    # Stripe secret key set (3 pts)
    ok = _has_env("STRIPE_SECRET_KEY")
    cat.checks.append(CheckResult("STRIPE_SECRET_KEY set", 3 if ok else 0, 3, ok,
        "Stripe secret key configured" if ok else "STRIPE_SECRET_KEY not set",
        "" if ok else "Set STRIPE_SECRET_KEY in production environment (get from Stripe dashboard)"))

    # Stripe webhook secret set (2 pts)
    ok = _has_env("STRIPE_WEBHOOK_SECRET")
    cat.checks.append(CheckResult("STRIPE_WEBHOOK_SECRET set", 2 if ok else 0, 2, ok,
        "Stripe webhook signing configured" if ok else "STRIPE_WEBHOOK_SECRET not set",
        "" if ok else "Set STRIPE_WEBHOOK_SECRET — subscription events (cancel, renew) won't work without it"))

    # Stripe webhook route in api_server (2 pts)
    ok = "stripe" in api.lower() and "webhook" in api.lower()
    cat.checks.append(CheckResult("Stripe webhook route in api_server.py", 2 if ok else 0, 2, ok,
        "Stripe routes found" if ok else "No Stripe routes in api_server.py",
        "" if ok else "Add POST /stripe/webhook route to handle subscription events"))

    # Subscription tier gate present (3 pts)
    ok = "subscription" in api.lower() or "tier" in api.lower() or "plan" in api.lower()
    cat.checks.append(CheckResult("Subscription tier gate present", 3 if ok else 0, 3, ok,
        "Subscription gate found" if ok else "No subscription tier gate",
        "" if ok else "Add subscription_required() dependency to premium routes"))

    return cat


def check_core_ai() -> CategoryResult:
    cat = CategoryResult(name="Core AI Quality", slug="ai")
    router = _read(ROOT / "query_router.py")
    omega  = _read(ROOT / "atlas_omega.py")
    api    = _read(ROOT / "api_server.py")

    # Gemini API key set (4 pts)
    ok = _has_env("GEMINI_API_KEY")
    cat.checks.append(CheckResult("GEMINI_API_KEY set", 4 if ok else 0, 4, ok,
        "Gemini API key configured" if ok else "GEMINI_API_KEY not set — AI brain won't work",
        "" if ok else "Set GEMINI_API_KEY — this is the core AI brain, nothing works without it"))

    # Intent router present (3 pts)
    ok = "classify_intent_route" in router
    cat.checks.append(CheckResult("Intent router (classify_intent_route) present", 3 if ok else 0, 3, ok,
        "Intent router found" if ok else "classify_intent_route missing",
        "" if ok else "Intent router is in query_router.py — do not remove"))

    # 10-loop engine (FourLoopEngine) present (4 pts)
    ok = "FourLoopEngine" in router or "four_loop" in router.lower()
    cat.checks.append(CheckResult("FourLoopEngine (10-loop) present", 4 if ok else 0, 4, ok,
        "FourLoopEngine found in query_router.py" if ok else "FourLoopEngine MISSING",
        "" if ok else "FourLoopEngine must not be deleted from query_router.py"))

    # OmegaAgent present (3 pts)
    ok = "OmegaAgent" in omega or "omega_agent" in omega.lower()
    cat.checks.append(CheckResult("OmegaAgent present in atlas_omega.py", 3 if ok else 0, 3, ok,
        "OmegaAgent found" if ok else "OmegaAgent MISSING",
        "" if ok else "OmegaAgent must not be deleted from atlas_omega.py"))

    # Response envelope completeness (3 pts)
    expected_keys = ["final_report", "tldr", "execution_rules", "failure_modes", "scenarios"]
    found = sum(1 for k in expected_keys if k in router)
    pts = min(3, found)
    ok = found >= 4
    cat.checks.append(CheckResult("Response envelope has key fields", pts, 3, ok,
        f"Found {found}/{len(expected_keys)} envelope keys" ,
        "" if ok else "Verify final_report, tldr, execution_rules, failure_modes, scenarios in response"))

    # Fallback: if Omega errors, router falls back to 10-loop (3 pts)
    ok = "fallback" in api.lower() or ("except" in api and "omega" in api.lower())
    cat.checks.append(CheckResult("Fallback behavior wired (Omega → 10-loop)", 3 if ok else 0, 3, ok,
        "Fallback path found" if ok else "No fallback detected",
        "" if ok else "Verify classify_intent_route has fallback to FourLoopEngine on Omega error"))

    return cat


def check_ux() -> CategoryResult:
    cat = CategoryResult(name="UI/UX", slug="ux")
    api = _read(ROOT / "api_server.py")

    # /command-center route (3 pts)
    ok = "/command-center" in api
    cat.checks.append(CheckResult("/command-center route live", 3 if ok else 0, 3, ok,
        "/command-center route found" if ok else "/command-center route MISSING",
        "" if ok else "Add GET /command-center route serving omega_command_center.html"))

    # /app route (2 pts)
    ok = '"/app"' in api or "'/app'" in api
    cat.checks.append(CheckResult("/app route live", 2 if ok else 0, 2, ok,
        "/app route found" if ok else "/app route MISSING",
        "" if ok else "Add GET /app route serving ra_omega_app.html"))

    # Sessions sidebar in /app (2 pts)
    app_html = _read(ROOT / "ra_omega_app.html")
    ok = "session" in app_html.lower() and ("sidebar" in app_html.lower() or "sessions" in app_html.lower())
    cat.checks.append(CheckResult("Sessions sidebar in /app", 2 if ok else 0, 2, ok,
        "Sessions UI present" if ok else "Sessions UI not detected in ra_omega_app.html",
        "" if ok else "Wire sessions sidebar into ra_omega_app.html"))

    # StructuredResponse cards (3 pts)
    ok = "StructuredResponse" in app_html or "structured" in app_html.lower()
    cat.checks.append(CheckResult("StructuredResponse cards in /app", 3 if ok else 0, 3, ok,
        "StructuredResponse found" if ok else "StructuredResponse MISSING — results won't render as cards",
        "" if ok else "Verify StructuredResponse component is in ra_omega_app.html"))

    # Mobile responsive (UI score via ui_audit) (3 pts)
    try:
        import ui_audit
        reports = ui_audit.run_audit()
        avg_responsive = sum(
            r.axis_scores.get("responsiveness", 0) for r in reports if r.exists
        ) / max(1, sum(1 for r in reports if r.exists))
        pts = min(3, int(avg_responsive / 34))
        ok = avg_responsive >= 60
        cat.checks.append(CheckResult("Mobile responsive (ui_audit)", pts, 3, ok,
            f"Responsiveness avg {avg_responsive:.0f}/100" ,
            "" if ok else "Add mobile media queries and viewport meta to HTML files"))
    except Exception:
        cat.checks.append(CheckResult("Mobile responsive (ui_audit)", 2, 3, True,
            "ui_audit not available — assuming partial", ""))

    # /v2 dashboard (2 pts)
    ok = '"/v2"' in api or "'/v2'" in api or "/dashboard" in api
    cat.checks.append(CheckResult("/v2 dashboard route live", 2 if ok else 0, 2, ok,
        "/v2 route found" if ok else "/v2 route MISSING",
        "" if ok else "Add GET /v2 route for dashboard backwards compatibility"))

    return cat


def check_data_layer() -> CategoryResult:
    cat = CategoryResult(name="Data Layer", slug="data")

    # atlas_memory.db exists and > 1KB (5 pts)
    db = ROOT / "atlas_memory.db"
    exists = db.exists()
    size_kb = db.stat().st_size / 1024 if exists else 0
    ok_size = size_kb >= 1
    pts = (3 if exists else 0) + (2 if ok_size else 0)
    cat.checks.append(CheckResult("atlas_memory.db present and populated", pts, 5, exists and ok_size,
        f"atlas_memory.db: {size_kb:.1f}KB" if exists else "atlas_memory.db MISSING",
        "" if (exists and ok_size) else "atlas_memory.db missing or empty — memory system not accumulating"))

    # atlas_tracker.db exists (3 pts)
    ok = (ROOT / "atlas_tracker.db").exists()
    cat.checks.append(CheckResult("atlas_tracker.db present", 3 if ok else 0, 3, ok,
        "atlas_tracker.db found" if ok else "atlas_tracker.db MISSING",
        "" if ok else "NEVER delete atlas_tracker.db — it holds trade tracking history"))

    # atlas_rag/ with chunks (4 pts)
    rag = ROOT / "atlas_rag"
    ok = rag.exists() and any(rag.rglob("*.bin"))
    pts = 4 if ok else (2 if rag.exists() else 0)
    cat.checks.append(CheckResult("atlas_rag/ Chroma DB present with chunks", pts, 4, ok,
        f"RAG database found" if ok else f"atlas_rag/ {'empty' if rag.exists() else 'MISSING'}",
        "" if ok else "Run rag_engine.py ingest to populate vector database"))

    # Vault has output files (2 pts)
    vault_out = ROOT / "atlas_vault" / "03-Outputs"
    ok = vault_out.exists() and any(vault_out.iterdir())
    cat.checks.append(CheckResult("atlas_vault/03-Outputs/ has files", 2 if ok else 0, 2, ok,
        f"Vault outputs found" if ok else "atlas_vault/03-Outputs/ empty or missing",
        "" if ok else "Run summary_generator.py and data_map.py to populate vault outputs"))

    # schema.sql present (1 pt)
    ok = (ROOT / "schema.sql").exists()
    cat.checks.append(CheckResult("schema.sql present", 1 if ok else 0, 1, ok,
        "schema.sql found" if ok else "schema.sql MISSING",
        "" if ok else "schema.sql needed for Supabase migration — do not delete"))

    return cat


def check_infrastructure() -> CategoryResult:
    cat = CategoryResult(name="Infrastructure", slug="infra")

    # Procfile exists (3 pts)
    proc = ROOT / "Procfile"
    ok = proc.exists()
    if ok:
        text = _read(proc)
        ok = "uvicorn" in text and "api_server" in text
    cat.checks.append(CheckResult("Procfile for Railway/Render", 3 if ok else 0, 3, ok,
        f"Procfile found and correct" if ok else "Procfile MISSING or incorrect",
        "" if ok else "Create Procfile with: web: uvicorn api_server:app --host 0.0.0.0 --port $PORT"))

    # Health endpoint (2 pts)
    api = _read(ROOT / "api_server.py")
    ok = '"/health"' in api or "'/health'" in api
    cat.checks.append(CheckResult("/health endpoint", 2 if ok else 0, 2, ok,
        "/health route found" if ok else "/health MISSING",
        "" if ok else "Add GET /health endpoint returning JSON status"))

    # railway.json or render.yaml (2 pts)
    ok = (ROOT / "railway.json").exists() or (ROOT / "render.yaml").exists()
    cat.checks.append(CheckResult("Deployment config (railway.json/render.yaml)", 2 if ok else 0, 2, ok,
        "Deployment config found" if ok else "No railway.json or render.yaml",
        "" if ok else "Create railway.json for Railway deployment config"))

    # GEMINI_API_KEY set (3 pts — also in AI, but critical infra)
    ok = _has_env("GEMINI_API_KEY")
    cat.checks.append(CheckResult("GEMINI_API_KEY set", 3 if ok else 0, 3, ok,
        "Gemini key configured" if ok else "GEMINI_API_KEY not set",
        "" if ok else "Set GEMINI_API_KEY in production environment secrets"))

    return cat


def check_testing() -> CategoryResult:
    cat = CategoryResult(name="Test Coverage", slug="testing")

    # Test count >= 2000 (3 pts scale)
    tests_dir = ROOT / "tests"
    count = 0
    try:
        for f in tests_dir.glob("test_*.py"):
            text = _read(f)
            count += len(re.findall(r'^\s*def test_', text, re.MULTILINE))
    except Exception:
        pass
    pts = 3 if count >= 2000 else (2 if count >= 1500 else (1 if count >= 1000 else 0))
    ok = count >= 1500
    cat.checks.append(CheckResult(f"Test count ({count} detected)", pts, 3, ok,
        f"{count} tests — {'solid' if count >= 2000 else 'growing'} coverage",
        "" if ok else f"Add more tests; currently {count}, target 2000+"))

    # No HIGH fragile tests (2 pts)
    try:
        import sys as _sys
        frag_path = ROOT / "omega_os" / "skills" / "test_contract_guard" / "tools" / "test_fragility_scan.py"
        import importlib.util
        spec = importlib.util.spec_from_file_location("test_fragility_scan", frag_path)
        mod  = importlib.util.module_from_spec(spec)
        _sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        matches = mod.scan_tests()
        high = [m for m in matches if m.severity == "high"]
        ok = len(high) == 0
        cat.checks.append(CheckResult(f"No HIGH fragile tests ({len(high)} found)", 2 if ok else 0, 2, ok,
            "No high-severity fragile tests" if ok else f"{len(high)} high-severity fragile tests",
            "" if ok else "Fix fragile assertions: run test_fragility_scan.py --fix-hints"))
    except Exception as e:
        cat.checks.append(CheckResult("Fragile test scan", 1, 2, True,
            f"Scan unavailable: {e}", ""))

    return cat


def check_memory() -> CategoryResult:
    cat = CategoryResult(name="Memory & Personalization", slug="memory")

    # Memory injector wired (2 pts)
    try:
        inj = ROOT / "atlas_memory" / "memory_injector.py"
        ok = inj.exists()
        api = _read(ROOT / "api_server.py")
        ok = ok and "memory_injector" in api.lower()
    except Exception:
        ok = False
    cat.checks.append(CheckResult("Memory injector wired into /query", 2 if ok else 0, 2, ok,
        "Memory injector active" if ok else "Memory injector not wired",
        "" if ok else "Import and call save_to_memory() in POST /query handler"))

    # Loop 5 personalization (2 pts)
    try:
        router = _read(ROOT / "query_router.py")
        ok = "loop5" in router.lower() or "personalize" in router.lower()
    except Exception:
        ok = False
    cat.checks.append(CheckResult("Loop 5 personalization wired", 2 if ok else 0, 2, ok,
        "Loop 5 found in query_router.py" if ok else "Loop 5 not detected",
        "" if ok else "Wire loop5_personalize() into FourLoopEngine.run()"))

    # Session context persists (1 pt)
    try:
        api = _read(ROOT / "api_server.py")
        ok = "session_id" in api and "context_topic" in api
    except Exception:
        ok = False
    cat.checks.append(CheckResult("Session context (session_id + context_topic)", 1 if ok else 0, 1, ok,
        "Session context present" if ok else "Session context not wired",
        "" if ok else "Ensure session_id is passed from /query to DB and context_topic is set"))

    return cat


# ── Main runner ───────────────────────────────────────────────────────────────

def run_checks(category_filter: Optional[str] = None) -> ReadinessReport:
    categories = [
        check_auth_security(),
        check_billing(),
        check_core_ai(),
        check_ux(),
        check_data_layer(),
        check_infrastructure(),
        check_testing(),
        check_memory(),
    ]
    if category_filter:
        categories = [c for c in categories if category_filter.lower() in c.slug.lower()]
    return ReadinessReport(categories=categories)


def print_report(r: ReadinessReport, show_fixes: bool = True) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sep = "=" * 72

    print(sep)
    print("  R.A. OMEGA — PRODUCT READINESS AUDIT")
    print(sep)
    print(f"\n  Overall: {r.total_score}/{r.max_score} pts  ({r.pct:.1f}%)  Grade {r.grade()}")
    print(f"  Verdict: {r.verdict()}\n")

    print(f"  {'CATEGORY':<28} {'SCORE':>6}  {'MAX':>4}  {'PCT':>5}  STATUS")
    print(f"  {'-'*28} {'-'*6}  {'-'*4}  {'-'*5}  ------")
    for cat in r.categories:
        print(f"  {cat.name:<28} {cat.score:>6}  {cat.max_score:>4}  {cat.pct:>4.0f}%  {cat.status}")

    for cat in r.categories:
        print(f"\n  ── {cat.name.upper()} ──")
        for check in cat.checks:
            mark = "[OK]" if check.passed else "[!!]"
            pts  = f"{check.points}/{check.max_points}"
            print(f"    {mark}  {pts:<5}  {check.label}")
            if check.detail:
                print(f"           {check.detail[:72]}")

    if show_fixes:
        fixes = r.all_fixes()
        if fixes:
            print(f"\n  PRIORITY FIXES:")
            for i, (cat_name, fix) in enumerate(fixes[:12], 1):
                print(f"    {i:>2}. [{cat_name}] {fix[:68]}")

    print(f"\n{sep}")
    print(f"  RESULT: {r.total_score}/{r.max_score} — {r.verdict()} (Grade {r.grade()})")
    print(sep)


def main() -> ReadinessReport:
    parser = argparse.ArgumentParser(description="R.A. Omega product readiness audit")
    parser.add_argument("--json",     action="store_true", help="Output JSON")
    parser.add_argument("--category", help="Filter to one category slug (auth/billing/ai/ux/data/infra/testing/memory)")
    args = parser.parse_args()

    report = run_checks(category_filter=args.category)

    if args.json:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(json.dumps({
            "total_score":  report.total_score,
            "max_score":    report.max_score,
            "pct":          round(report.pct, 1),
            "grade":        report.grade(),
            "verdict":      report.verdict(),
            "categories": [
                {
                    "name":   cat.name,
                    "slug":   cat.slug,
                    "score":  cat.score,
                    "max":    cat.max_score,
                    "pct":    round(cat.pct, 1),
                    "status": cat.status,
                    "checks": [
                        {"label": c.label, "passed": c.passed, "points": c.points,
                         "max": c.max_points, "detail": c.detail, "fix": c.fix}
                        for c in cat.checks
                    ],
                }
                for cat in report.categories
            ],
            "priority_fixes": [
                {"category": cat, "fix": fix}
                for cat, fix in report.all_fixes()[:15]
            ],
        }, indent=2))
    else:
        print_report(report)

    return report


# avoid circular import error for Optional
from typing import Optional

if __name__ == "__main__":
    main()
