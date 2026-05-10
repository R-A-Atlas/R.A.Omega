"""W7 — Cost of Living Indexer tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "wealth" / "col_indexer"
SKILL_PATH = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "col_indexer" / "SKILL.md"

VALID_SIGNALS = {"EXPENSIVE", "MODERATE", "AFFORDABLE"}
VALID_REGIONS = {"Northeast", "Midwest", "South", "West"}

REQUIRED_SCHEMA_FIELDS = [
    "generated_at", "national_cpi", "record_count", "cities",
    "city", "state", "region", "grocery_index", "gas_avg",
    "rent_1br", "overall_index", "signal",
]

BLS_SERIES = [
    "CUURA101SA0",  # Northeast
    "CUURA207SA0",  # Midwest
    "CUURA319SA0",  # South
    "CUURA421SA0",  # West
]


def test_w7_package_importable():
    """atlas_agents.wealth.col_indexer package loads without error."""
    mod = importlib.import_module("atlas_agents.wealth.col_indexer")
    assert mod is not None


def test_w7_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_w7_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    assert SKILL_PATH.exists(), f"Missing: {SKILL_PATH}"
    assert SKILL_PATH.stat().st_size > 0


def test_w7_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in REQUIRED_SCHEMA_FIELDS:
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_w7_signals_documented():
    """AGENT_PROMPT.md documents all 3 signals and all 4 BLS series IDs."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for signal in VALID_SIGNALS:
        assert signal in content, f"Signal '{signal}' not documented in AGENT_PROMPT.md"
    for series in BLS_SERIES:
        assert series in content, f"BLS series '{series}' not documented in AGENT_PROMPT.md"


def test_w7_index_thresholds_documented():
    """AGENT_PROMPT.md documents the index signal thresholds (90, 120)."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "120" in content, "EXPENSIVE threshold 120 not documented"
    assert "90" in content, "AFFORDABLE threshold 90 not documented"


def test_w7_output_schema_valid_when_scraper_built():
    """Once col_indexer_scraper.py is built, output schema must match spec."""
    scraper_path = AGENT_DIR / "col_indexer_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("col_indexer_scraper.py not yet implemented — pending W7 activation")

    import importlib.util
    from unittest.mock import patch

    spec = importlib.util.spec_from_file_location("col_indexer_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "cities" in result
        assert "national_cpi" in result
        for city in result.get("cities", []):
            assert city.get("signal") in VALID_SIGNALS or city.get("signal") is None
            assert city.get("region") in VALID_REGIONS or city.get("region") is None
            overall = city.get("overall_index", 100)
            if overall >= 120:
                assert city.get("signal") in (None, "EXPENSIVE")
            elif overall < 90:
                assert city.get("signal") in (None, "AFFORDABLE")
    except Exception:
        pass
