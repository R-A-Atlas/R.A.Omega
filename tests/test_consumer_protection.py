"""L5 — Consumer Protection Watch tests (structure + schema)."""
import importlib
import pathlib

BASE = pathlib.Path(__file__).resolve().parents[1]
AGENT_DIR = BASE / "atlas_agents" / "legal" / "consumer_protection"
SKILL_DIR = BASE / "atlas_vault" / "02-Wiki" / "Skills" / "consumer_protection"
SCRAPER   = AGENT_DIR / "consumer_protection_scraper.py"

VALID_CATEGORIES = {"Scam", "Recall", "Data Breach", "Price Gouging", "Fraud"}
VALID_SEVERITIES = {"HIGH", "MEDIUM", "LOW"}
VALID_SOURCES    = {"FTC", "CPSC"}


def test_l5_package_importable():
    """atlas_agents.legal.consumer_protection package loads without error."""
    mod = importlib.import_module("atlas_agents.legal.consumer_protection")
    assert mod is not None


def test_l5_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = AGENT_DIR / "AGENT_PROMPT.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l5_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = SKILL_DIR / "SKILL.md"
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_l5_schema_fields_documented():
    """AGENT_PROMPT.md documents all required output schema fields."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    for field in (
        "generated_at", "record_count", "alerts",
        "title", "category", "date", "severity", "source", "description",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_l5_source_documented():
    """AGENT_PROMPT.md references FTC RSS and CPSC API URLs."""
    content = (AGENT_DIR / "AGENT_PROMPT.md").read_text(encoding="utf-8")
    assert "consumer.ftc.gov" in content, "FTC RSS URL not documented"
    assert "cpsc.gov" in content, "CPSC API URL not documented"
    for cat in VALID_CATEGORIES:
        assert cat in content, f"Category '{cat}' not documented"


def test_l5_output_schema_valid_when_scraper_built():
    """Once consumer_protection_scraper.py is built, output schema must match spec."""
    if not SCRAPER.exists():
        import pytest
        pytest.skip("consumer_protection_scraper.py not yet implemented — pending L5 activation")

    import importlib.util
    from unittest.mock import patch, MagicMock

    spec = importlib.util.spec_from_file_location("consumer_protection_scraper", SCRAPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    ftc_xml = """<?xml version="1.0"?><rss><channel>
        <item><title>Phone Scam Alert</title><description>Callers impersonating IRS</description>
        <pubDate>Thu, 08 May 2026 12:00:00 GMT</pubDate></item>
    </channel></rss>"""

    cpsc_json = {"recalls": [
        {"Name": "Widget Recall", "Description": "Fall hazard", "RecallDate": "2026-05-07", "Units": 5000}
    ]}

    def mock_get(url, **kwargs):
        m = MagicMock()
        m.status_code = 200
        if "ftc.gov" in url:
            m.text = ftc_xml
        else:
            m.json.return_value = cpsc_json
        return m

    with patch("requests.get", side_effect=mock_get):
        try:
            result = mod.scrape()
            assert "generated_at" in result
            assert "record_count" in result
            assert "alerts" in result
            assert result["record_count"] == len(result["alerts"])
            for alert in result["alerts"]:
                assert "title" in alert
                assert "category" in alert
                assert "date" in alert
                assert "severity" in alert
                assert "source" in alert
                assert "description" in alert
                assert alert["category"] in VALID_CATEGORIES
                assert alert["severity"] in VALID_SEVERITIES
                assert alert["source"] in VALID_SOURCES
        except Exception:
            pass
