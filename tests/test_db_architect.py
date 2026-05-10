"""E5 — DB Architect smoke tests."""
import importlib
import pathlib
import re


def test_e5_package_importable():
    """atlas_agents.engineering.db_architect package loads without error."""
    mod = importlib.import_module("atlas_agents.engineering.db_architect")
    assert mod is not None


def test_e5_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "db_architect"
        / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "AGENT_PROMPT.md is empty"


def test_e5_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault"
        / "02-Wiki"
        / "Skills"
        / "db_architect"
        / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "SKILL.md is empty"


def test_e5_schema_sql_exists():
    """schema.sql exists (E5 appends to it; must not be deleted)."""
    p = pathlib.Path(__file__).resolve().parents[1] / "schema.sql"
    assert p.exists(), "schema.sql missing — DB Architect has nothing to append to"
    assert p.stat().st_size > 0, "schema.sql is empty"


def test_e5_schema_uses_if_not_exists():
    """schema.sql uses safe CREATE TABLE IF NOT EXISTS pattern throughout."""
    p = pathlib.Path(__file__).resolve().parents[1] / "schema.sql"
    content = p.read_text(encoding="utf-8")
    create_count = len(re.findall(r"CREATE TABLE", content, re.IGNORECASE))
    safe_count = len(re.findall(r"CREATE TABLE IF NOT EXISTS", content, re.IGNORECASE))
    assert create_count == safe_count, (
        f"Found {create_count} CREATE TABLE but only {safe_count} use IF NOT EXISTS"
    )


def test_e5_schema_no_drop_statements():
    """schema.sql must not contain DROP TABLE or DELETE FROM (E5 guardrail)."""
    p = pathlib.Path(__file__).resolve().parents[1] / "schema.sql"
    content = p.read_text(encoding="utf-8")
    uncommented = "\n".join(
        line for line in content.splitlines() if not line.strip().startswith("--")
    )
    assert not re.search(r"\bDROP\s+TABLE\b", uncommented, re.IGNORECASE), \
        "DROP TABLE found in schema.sql — forbidden"
    assert not re.search(r"\bDELETE\s+FROM\b", uncommented, re.IGNORECASE), \
        "DELETE FROM found in schema.sql — forbidden"


def test_e5_atlas_db_importable():
    """atlas_db.py imports without error (E5 adds functions to it)."""
    import importlib.util, sys
    root = pathlib.Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("atlas_db", root / "atlas_db.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        raise AssertionError(f"atlas_db.py failed to import: {exc}") from exc
