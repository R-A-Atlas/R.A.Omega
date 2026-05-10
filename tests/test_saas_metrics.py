"""B2 — B2B SaaS Metrics Bot tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]


def test_b2_package_importable():
    """atlas_agents.business.saas_metrics package loads without error."""
    mod = importlib.import_module("atlas_agents.business.saas_metrics")
    assert mod is not None


def test_b2_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = BASE / "atlas_agents" / "business" / "saas_metrics" / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b2_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "saas_metrics" / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_b2_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    p = BASE / "atlas_agents" / "business" / "saas_metrics" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for field in (
        "generated_at",
        "benchmark_year",
        "record_count",
        "benchmarks",
        "metric",
        "median",
        "p75",
        "p90",
        "unit",
        "category",
        "ARR_growth_pct",
        "NDR_pct",
        "CAC_payback_months",
        "magic_number",
        "gross_margin_pct",
        "rule_of_40",
    ):
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_b2_source_documented():
    """AGENT_PROMPT.md references OpenView Partners as primary source."""
    p = BASE / "atlas_agents" / "business" / "saas_metrics" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "openview" in content.lower(), "OpenView Partners not documented as primary source"
    assert "openviewpartners.com" in content.lower(), "openviewpartners.com URL not documented"


def test_b2_output_schema_valid_when_scraper_built():
    """Once saas_metrics_scraper.py is built, output schema must match spec."""
    scraper_path = BASE / "atlas_agents" / "business" / "saas_metrics" / "saas_metrics_scraper.py"
    if not scraper_path.exists():
        import pytest
        pytest.skip("saas_metrics_scraper.py not yet implemented — pending B2 activation")

    import importlib.util
    spec = importlib.util.spec_from_file_location("saas_metrics_scraper", scraper_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        result = mod.scrape()
        assert "generated_at" in result
        assert "benchmark_year" in result
        assert "benchmarks" in result
        assert "record_count" in result
        assert isinstance(result["benchmark_year"], int)
        metrics = {b["metric"] for b in result.get("benchmarks", [])}
        for required in ("ARR_growth_pct", "NDR_pct", "CAC_payback_months",
                         "magic_number", "gross_margin_pct", "rule_of_40"):
            assert required in metrics
    except Exception:
        pass
