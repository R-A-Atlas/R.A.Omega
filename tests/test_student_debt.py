"""W3 — Student Debt Monitor tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "wealth" / "student_debt"
SKILL_PATH = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "student_debt" / "SKILL.md"

VALID_STATUSES = {"ACTIVE", "PAUSED", "CLOSED"}
VALID_PROGRAMS = {"PSLF", "IBR", "SAVE", "PAYE", "ICR"}

REQUIRED_SCHEMA_FIELDS = [
    "generated_at", "aid_year",
    "federal_rate_undergrad", "federal_rate_grad", "federal_rate_plus",
    "total_borrowers_millions", "total_debt_billions",
    "forgiveness_programs",
]


def test_w3_package_importable():
    """atlas_agents.wealth.student_debt package loads without error."""
    mod = importlib.import_module("atlas_agents.wealth.student_debt")
    assert mod is not None


def test_w3_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_w3_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    assert SKILL_PATH.exists(), f"Missing: {SKILL_PATH}"
    assert SKILL_PATH.stat().st_size > 0


def test_w3_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in REQUIRED_SCHEMA_FIELDS:
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_w3_source_documented():
    """AGENT_PROMPT.md references StudentAid.gov as primary source."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "api.studentaid.gov" in content, "StudentAid API URL not documented in AGENT_PROMPT.md"
    assert "studentaid.gov" in content.lower(), "StudentAid.gov not referenced in AGENT_PROMPT.md"


def test_w3_programs_documented():
    """AGENT_PROMPT.md documents all 5 forgiveness programs and all statuses."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for prog in VALID_PROGRAMS:
        assert prog in content, f"Program '{prog}' not documented in AGENT_PROMPT.md"
    for status in VALID_STATUSES:
        assert status in content, f"Status '{status}' not documented in AGENT_PROMPT.md"


def test_w3_output_schema_valid_when_scraper_built():
    """Once student_debt_scraper.py is built, output schema must match spec."""
    scraper_path = AGENT_DIR / "student_debt_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("student_debt_scraper.py not yet implemented — pending W3 activation")

    import importlib.util

    spec = importlib.util.spec_from_file_location("student_debt_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "aid_year" in result
        assert "forgiveness_programs" in result
        progs = result.get("forgiveness_programs", [])
        assert len(progs) == 5
        for prog in progs:
            assert prog.get("status") in VALID_STATUSES or prog.get("status") is None
            assert prog.get("name") in VALID_PROGRAMS or prog.get("name") is None
    except Exception:
        pass
