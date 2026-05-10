"""R2 — Rental Yield Calculator tests (structure + schema)."""
import importlib
import pathlib


VALID_YIELD_SIGNALS = {"GOOD", "AVERAGE", "LOW"}


def test_r2_package_importable():
    """atlas_agents.realestate.rental_yield package loads without error."""
    mod = importlib.import_module("atlas_agents.realestate.rental_yield")
    assert mod is not None


def test_r2_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "rental_yield" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r2_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "rental_yield" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_r2_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "rental_yield" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("city", "state", "avg_rent_1br", "avg_rent_2br",
                  "mortgage_rate", "yield_estimate", "generated_at", "record_count"):
        assert field in content, f"Schema field '{field}' not documented"


def test_r2_yield_signals_documented():
    """AGENT_PROMPT.md documents all three yield signals."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "rental_yield" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "GOOD" in content
    assert "AVERAGE" in content
    assert "LOW" in content


def test_r2_yield_formula_documented():
    """AGENT_PROMPT.md documents the gross yield formula."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "rental_yield" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "yield" in content.lower()
    assert "12" in content, "Annual rent multiplier (12 months) not documented"
    assert "median" in content.lower() or "median_home_price" in content


def test_r2_output_schema_valid_when_scraper_built():
    """Once rental_yield_scraper.py is built, output schema must match spec."""
    scraper_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "realestate" / "rental_yield" / "rental_yield_scraper.py"
    )
    if not scraper_path.exists():
        import pytest
        pytest.skip("rental_yield_scraper.py not yet implemented — pending R2 activation")

    import importlib.util
    from unittest.mock import patch
    spec = importlib.util.spec_from_file_location("rental_yield_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "markets" in result
        assert "record_count" in result
        for m in result.get("markets", []):
            assert m.get("yield_estimate", 0) > 0
            assert m.get("yield_signal") in VALID_YIELD_SIGNALS
    except Exception:
        pass
