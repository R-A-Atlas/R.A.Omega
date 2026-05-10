"""E2 — Refactorer smoke tests."""
import importlib
import pathlib


def test_e2_package_importable():
    """atlas_agents.engineering.refactorer package loads without error."""
    mod = importlib.import_module("atlas_agents.engineering.refactorer")
    assert mod is not None


def test_e2_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "refactorer"
        / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "AGENT_PROMPT.md is empty"


def test_e2_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault"
        / "02-Wiki"
        / "Skills"
        / "refactorer"
        / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "SKILL.md is empty"


def test_e2_protected_files_untouched():
    """Confirm the four protected core files still exist (refactorer must never delete them)."""
    root = pathlib.Path(__file__).resolve().parents[1]
    for fname in ("query_router.py", "atlas_omega.py", "deep_research.py", "gemini_limiter.py"):
        assert (root / fname).exists(), f"Protected file missing: {fname}"


def test_agent_utils_has_required_exports():
    """agent_utils.py exposes the three canonical shared helpers."""
    from atlas_core.utils import agent_utils
    assert hasattr(agent_utils, "requests_get_json"), "Missing requests_get_json"
    assert hasattr(agent_utils, "write_cache_json_pair"), "Missing write_cache_json_pair"
    assert hasattr(agent_utils, "sleep_backoff"), "Missing sleep_backoff"
