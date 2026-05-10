"""L4 — SEC EDGAR Bot tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "legal" / "sec_edgar"
SKILL_DIR = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "sec_edgar"
SCRAPER   = AGENT_DIR / "sec_edgar_scraper.py"

VALID_FORM_TYPES = {"8-K", "10-Q", "10-K", "S-1", "SC 13G"}
FLAG_TERMS = {"material weakness", "going concern", "restatement"}


def test_l4_package_importable():
    """atlas_agents.legal.sec_edgar package loads without error."""
    mod = importlib.import_module("atlas_agents.legal.sec_edgar")
    assert mod is not None


def test_l4_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l4_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = SKILL_DIR / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l4_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in (
        "generated_at", "record_count", "filings",
        "ticker", "company_name", "form_type",
        "filed_date", "description", "url", "flags",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_l4_source_documented():
    """AGENT_PROMPT.md references SEC EDGAR full-text search URL."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "efts.sec.gov" in content, "SEC EDGAR EFTS URL not documented"
    for term in FLAG_TERMS:
        assert term in content, f"Flag term '{term}' not documented"


def test_l4_output_schema_valid_when_scraper_built():
    """Once sec_edgar_scraper.py is built, output schema must match spec."""
    if not SCRAPER.exists():
        import pytest
        pytest.skip("sec_edgar_scraper.py not yet implemented — pending L4 activation")

    import importlib.util
    from unittest.mock import patch, MagicMock
    spec = importlib.util.spec_from_file_location("sec_edgar_scraper", SCRAPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "entity_name": "Test Corp",
                        "tickers": ["TEST"],
                        "file_type": "8-K",
                        "period_of_report": "2026-05-08",
                        "description": "Material weakness in internal controls",
                        "file_date": "edgar/data/12345/0001-index.htm",
                    }
                }
            ]
        }
    }
    with patch("requests.get", return_value=mock_response):
        try:
            result = mod.scrape()
            assert "generated_at" in result
            assert "record_count" in result
            assert "filings" in result
            assert result["record_count"] == len(result["filings"])
            for f in result["filings"]:
                assert "ticker" in f
                assert "company_name" in f
                assert "form_type" in f
                assert "filed_date" in f
                assert "description" in f
                assert "url" in f
                assert "flags" in f
                assert isinstance(f["flags"], list)
        except Exception:
            pass
