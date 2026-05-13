"""Repository audit for R.A. Omega production readiness.

Checks are intentionally static and deterministic so the audit can run locally,
in CI, or before deployment without calling external services.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEXT_EXTS = {".py", ".html", ".md", ".ps1", ".toml", ".txt", ".sql", ".yml", ".yaml"}
SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "reports",
    "data_cache",
    "congress_cache",
    "atlas_vault",
}
LOCAL_LINK_RE = re.compile(r"""(?:href|src)=["']([^"'#]+)["']""", re.IGNORECASE)
SECRET_PATTERNS = {
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "stripe_secret": re.compile(r"\bsk_(?:test|live)_[A-Za-z0-9]{20,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\b"),
}


@dataclass(frozen=True)
class Finding:
    severity: str
    area: str
    detail: str
    path: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "area": self.area,
            "path": self.path,
            "detail": self.detail,
        }


def _iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_EXTS:
            files.append(path)
    return sorted(files)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _env_example_keys() -> set[str]:
    path = ROOT / ".env.example"
    if not path.exists():
        return set()
    keys: set[str] = set()
    for line in _read(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0].strip())
    return keys


def _env_keys_from_python(path: Path) -> set[str]:
    keys: set[str] = set()
    try:
        tree = ast.parse(_read(path))
    except SyntaxError:
        return keys
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"get", "getenv"}:
                target = node.func.value
                is_env = (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "os"
                    and target.attr == "environ"
                ) or (isinstance(target, ast.Name) and target.id == "os")
                if is_env and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    keys.add(node.args[0].value)
            if isinstance(node.func, ast.Name) and node.func.id in {"env_text", "env_bool", "env_csv"}:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    keys.add(node.args[0].value)
        if isinstance(node, ast.Subscript):
            target = node.value
            is_environ = (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "os"
                and target.attr == "environ"
            )
            if is_environ and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                keys.add(node.slice.value)
    return keys


def _referenced_env_keys(files: list[Path]) -> set[str]:
    keys: set[str] = set()
    for path in files:
        if path.suffix == ".py":
            keys |= _env_keys_from_python(path)
    return keys


def _audit_env(files: list[Path]) -> tuple[list[Finding], dict[str, Any]]:
    example = _env_example_keys()
    referenced = _referenced_env_keys(files)
    ignore = {
        "ATLAS_DIR",
        "ATLAS_DASHBOARD_V2",
        "ATLAS_DASHBOARD_V4",
        "ATLAS_ZENITH_LANDING",
        "RA_OMEGA_APP",
        "GEMINI_HTTP_TIMEOUT_MS",
        "SEC_SEARCH_URL",
        "FRED_URL",
        "FRED_SERIES",
        "BLS_SERIES",
        "PYTEST_CURRENT_TEST",
    }
    missing_from_example = sorted(key for key in referenced - example - ignore if not key.endswith("_RE"))
    findings = [
        Finding("medium", "env", f"Referenced environment key is not documented in .env.example: {key}")
        for key in missing_from_example
    ]
    local_env_exists = (ROOT / ".env").exists()
    required_runtime = ["GOOGLE_API_KEY", "GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_ANON_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"]
    if not local_env_exists:
        findings.append(Finding("medium", "env", "Local .env file is absent in this workspace; runtime integrations will be disabled until configured."))
    if "STRIPE_SECRET_KEY" not in example or "STRIPE_WEBHOOK_SECRET" not in example:
        findings.append(Finding("high", "env", "Stripe production keys are used by billing routes but missing from .env.example."))
    return findings, {
        "env_example_keys": sorted(example),
        "referenced_env_keys": sorted(referenced),
        "missing_from_env_example": missing_from_example,
        "local_env_exists": local_env_exists,
        "required_runtime_keys": required_runtime,
    }


def _audit_links(files: list[Path]) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    checked = 0
    missing: list[str] = []
    for path in files:
        if path.suffix.lower() not in {".html", ".md"}:
            continue
        text = _read(path)
        for link in LOCAL_LINK_RE.findall(text):
            if link.startswith(("http://", "https://", "mailto:", "tel:", "data:", "#", "/", "javascript:")):
                continue
            target = (path.parent / link.split("#", 1)[0].split("?", 1)[0]).resolve()
            if not target.exists():
                rel = path.relative_to(ROOT).as_posix()
                missing.append(f"{rel} -> {link}")
                findings.append(Finding("low", "links", f"Local HTML asset/link target is missing: {link}", rel))
            checked += 1
    return findings, {"local_links_checked": checked, "missing_local_links": missing[:50]}


def _audit_branding(files: list[Path]) -> tuple[list[Finding], dict[str, Any]]:
    user_facing = [
        ROOT / "index_1778228972988.html",
        ROOT / "auth.html",
        ROOT / "ra_omega_app.html",
        ROOT / "atlas_dashboard_v4.html",
        ROOT / "api_server.py",
    ]
    allowed = {
        "ATLAS_DISABLE_AUTH",
        "ATLAS_DEV_API_KEY",
        "ATLAS_DEV_API_KEYS",
        "ATLAS_TEST_JWT",
        "ATLAS_CORS_ORIGINS",
        "ATLAS_DEFAULT_SUBSCRIPTION_TIER",
        "ATLAS_DATA_CACHE_DIR",
        "X-ATLAS-DEV-KEY",
        "__ATLAS_SB_CONFIG__",
        "ATLAS_API_DEFAULT",
        "ATLAS_QUERY_FETCH_MS",
        "ATLAS_REPORT_HISTORY_KEY",
        "ATLAS_REPORT_HISTORY_MAX",
        "ATLAS_FOLDER_FOLD_KEY",
        "ATLAS_ACTIVE_SESSION_KEY",
        "ATLAS_DIR",
        "ATLAS_DASHBOARD_V2",
        "ATLAS_DASHBOARD_V4",
        "ATLAS_ZENITH_LANDING",
        "atlas_dir",
    }
    leaks: list[str] = []
    for path in user_facing:
        if not path.exists():
            continue
        for idx, line in enumerate(_read(path).splitlines(), start=1):
            if "ATLAS" not in line:
                continue
            if any(token in line for token in allowed):
                continue
            leaks.append(f"{path.relative_to(ROOT).as_posix()}:{idx}:{line.strip()[:120]}")
    findings = [
        Finding("low", "branding", "Possible user-facing ATLAS legacy string remains.", leak.split(":", 2)[0])
        for leak in leaks
    ]
    return findings, {"legacy_branding_hits": leaks[:80]}


def _audit_secret_leaks(files: list[Path]) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    hits: list[str] = []
    ignored_names = {".env.example"}
    for path in files:
        if path.name in ignored_names:
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = _read(path)
        for idx, line in enumerate(text.splitlines(), start=1):
            if "=" in line and line.strip().endswith("="):
                continue
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    hit = f"{rel}:{idx}:{name}"
                    hits.append(hit)
                    findings.append(Finding("high", "secrets", f"Possible hardcoded secret detected: {name}", rel))
    return findings, {"secret_pattern_hits": hits[:80], "patterns_checked": sorted(SECRET_PATTERNS)}


def _audit_routes() -> tuple[list[Finding], dict[str, Any]]:
    text = _read(ROOT / "api_server.py")
    routes = sorted(set(re.findall(r"@app\.(?:get|post|patch|delete)\([\"']([^\"']+)[\"']", text)))
    required = ["/", "/auth", "/app", "/dashboard", "/health", "/query", "/agents/status", "/pricing"]
    missing = [route for route in required if route not in routes]
    findings = [Finding("high", "routes", f"Required route missing from api_server.py: {route}") for route in missing]
    return findings, {"route_count": len(routes), "routes": routes, "required_missing": missing}


def run_audit() -> dict[str, Any]:
    files = _iter_text_files()
    findings: list[Finding] = []
    details: dict[str, Any] = {"file_count_scanned": len(files)}

    for name, fn in {
        "env": _audit_env,
        "links": _audit_links,
        "branding": _audit_branding,
        "secrets": _audit_secret_leaks,
    }.items():
        fn_findings, fn_details = fn(files)
        findings.extend(fn_findings)
        details[name] = fn_details

    route_findings, route_details = _audit_routes()
    findings.extend(route_findings)
    details["routes"] = route_details

    try:
        from agent_audit import collect_agent_audit

        details["agents"] = collect_agent_audit()["summary"]
    except Exception as exc:
        findings.append(Finding("medium", "agents", f"Agent audit failed: {exc}"))

    by_severity: dict[str, int] = {}
    for finding in findings:
        by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1

    return {
        "ok": not any(f.severity == "high" for f in findings),
        "summary": {
            "findings": len(findings),
            "by_severity": by_severity,
        },
        "findings": [finding.as_dict() for finding in findings],
        "details": details,
    }


def main() -> int:
    report = run_audit()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if any(f["severity"] == "high" for f in report["findings"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
