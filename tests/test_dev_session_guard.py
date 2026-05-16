"""
tests/test_dev_session_guard.py

Binary evals for the dev_session_guard skill.
All checks are True/False (DBS eval standard).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SKILL_DIR = ROOT / "omega_os" / "skills" / "dev_session_guard"
TOOLS_DIR = SKILL_DIR / "tools"
RUN_PREFLIGHT     = TOOLS_DIR / "run_preflight.py"
SESSION_BRIEFING  = TOOLS_DIR / "session_briefing.py"
SKILL_MD          = SKILL_DIR / "SKILL.md"
CONTRACT_JSON     = SKILL_DIR / "contract.json"
EVALS_JSON        = SKILL_DIR / "evals.json"


# ── File existence ─────────────────────────────────────────────────────────

def test_skill_md_exists():
    assert SKILL_MD.is_file()

def test_contract_json_exists():
    assert CONTRACT_JSON.is_file()

def test_evals_json_exists():
    assert EVALS_JSON.is_file()

def test_run_preflight_exists():
    assert RUN_PREFLIGHT.is_file()

def test_session_briefing_exists():
    assert SESSION_BRIEFING.is_file()


# ── SKILL.md content ───────────────────────────────────────────────────────

def test_skill_md_has_guardrails():
    assert "guardrails" in SKILL_MD.read_text(encoding="utf-8")

def test_skill_md_has_commands():
    assert "run_preflight.py" in SKILL_MD.read_text(encoding="utf-8")

def test_skill_md_mentions_protected_files():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "deep_research.py" in text
    assert "gemini_limiter.py" in text


# ── contract.json content ─────────────────────────────────────────────────

def test_contract_json_is_valid():
    data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    assert "protected_files" in data
    assert "core_files_to_compile" in data

def test_contract_json_protected_files():
    data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    assert "deep_research.py" in data["protected_files"]
    assert "gemini_limiter.py" in data["protected_files"]

def test_contract_json_never_commit_env():
    data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    assert data["safety"]["never_commit_env"] is True


# ── evals.json content ────────────────────────────────────────────────────

def test_evals_json_is_valid_list():
    data = json.loads(EVALS_JSON.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) >= 6

def test_evals_json_has_ids():
    data = json.loads(EVALS_JSON.read_text(encoding="utf-8"))
    assert all("id" in e for e in data)


# ── Python compile ─────────────────────────────────────────────────────────

def test_run_preflight_compiles():
    import py_compile, tempfile, shutil
    tmp = tempfile.mktemp(suffix=".py")
    shutil.copy(RUN_PREFLIGHT, tmp)
    try:
        py_compile.compile(tmp, doraise=True)
    finally:
        Path(tmp).unlink(missing_ok=True)

def test_session_briefing_compiles():
    import py_compile, tempfile, shutil
    tmp = tempfile.mktemp(suffix=".py")
    shutil.copy(SESSION_BRIEFING, tmp)
    try:
        py_compile.compile(tmp, doraise=True)
    finally:
        Path(tmp).unlink(missing_ok=True)


# ── Runtime: protected-only (fast, no network) ────────────────────────────

def test_preflight_protected_only_exits_zero():
    result = subprocess.run(
        [sys.executable, str(RUN_PREFLIGHT), "--protected-only"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

def test_preflight_protected_only_prints_pass():
    result = subprocess.run(
        [sys.executable, str(RUN_PREFLIGHT), "--protected-only"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert "PASS" in result.stdout

def test_preflight_protected_only_checks_deep_research():
    result = subprocess.run(
        [sys.executable, str(RUN_PREFLIGHT), "--protected-only"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert "deep_research.py" in result.stdout

def test_preflight_protected_only_checks_databases():
    result = subprocess.run(
        [sys.executable, str(RUN_PREFLIGHT), "--protected-only"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert "atlas_memory.db" in result.stdout


# ── Runtime: session briefing ─────────────────────────────────────────────

def test_session_briefing_exits_zero():
    result = subprocess.run(
        [sys.executable, str(SESSION_BRIEFING)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

def test_session_briefing_prints_branch():
    result = subprocess.run(
        [sys.executable, str(SESSION_BRIEFING)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert "Branch" in result.stdout

def test_session_briefing_prints_health():
    result = subprocess.run(
        [sys.executable, str(SESSION_BRIEFING)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert "Health" in result.stdout

def test_session_briefing_prints_next_priority():
    result = subprocess.run(
        [sys.executable, str(SESSION_BRIEFING)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert "priority" in result.stdout.lower() or "PRIORITY" in result.stdout

def test_session_briefing_prints_recent_commits():
    result = subprocess.run(
        [sys.executable, str(SESSION_BRIEFING)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert "commits" in result.stdout.lower() or "Recent" in result.stdout

def test_session_brief_fits_one_screen():
    result = subprocess.run(
        [sys.executable, str(SESSION_BRIEFING)],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    lines = result.stdout.splitlines()
    assert len(lines) <= 40, f"Brief is {len(lines)} lines — must fit in one screen (<=40)"
