"""D3 Options Flow Monitor tests."""

from __future__ import annotations

import importlib
import pathlib


def test_t3_package_importable():
    mod = importlib.import_module("atlas_agents.trading.options_flow")
    assert mod is not None


def test_t3_agent_prompt_exists():
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "options_flow" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t3_skill_md_exists():
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "options_flow" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t3_schema_documented():
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "options_flow" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in ("generated_at", "volume_oi_ratio", "unusual_activity", "signal", "record_count"):
        assert field in content, f"Schema field '{field}' not documented in AGENT_PROMPT.md"


def test_t3_signal_logic_documented():
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "options_flow" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "BULLISH_UNUSUAL" in content
    assert "BEARISH_UNUSUAL" in content
    assert "3" in content, "Threshold (ratio > 3) not documented"


def test_t3_output_schema_valid_when_scraper_built(monkeypatch):
    from atlas_agents.trading.options_flow import options_flow_scraper as mod

    html = """
    <table>
      <tr><td>NVDA call 2026-06-19 150</td><td>12,000</td><td>2,000</td><td>call</td></tr>
      <tr><td>TSLA put 2026-06-19 200</td><td>9,000</td><td>1,000</td><td>put</td></tr>
    </table>
    """

    monkeypatch.setattr(mod, "requests_get_text", lambda *_args, **_kwargs: html)
    result = mod.scrape(top_n=5)
    assert "generated_at" in result
    assert result["record_count"] == 2
    assert "unusual_activity" in result
    signals = {item["signal"] for item in result["unusual_activity"]}
    assert signals == {"BULLISH_UNUSUAL", "BEARISH_UNUSUAL"}
    for item in result["unusual_activity"]:
        assert item["volume_oi_ratio"] > 3.0


def test_t3_write_outputs_uses_cache_pair(tmp_path, monkeypatch):
    from atlas_agents.trading.options_flow import options_flow_scraper as mod

    monkeypatch.setattr(mod, "DATA_CACHE_DIR", tmp_path)
    stable, stamped = mod.write_outputs(
        {
            "generated_at": "2026-05-10T00:00:00Z",
            "source": "test",
            "record_count": 0,
            "unusual_activity": [],
        }
    )
    assert stable.name == "options_flow_latest.json"
    assert stamped.name.startswith("options_flow_")
    assert stable.exists()
    assert stamped.exists()
