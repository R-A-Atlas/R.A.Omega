"""D4 Insider Tracker tests."""

from __future__ import annotations

import importlib
import pathlib


def test_t4_package_importable():
    mod = importlib.import_module("atlas_agents.trading.insider_tracker")
    assert mod is not None


def test_t4_agent_prompt_exists():
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "insider_tracker" / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t4_skill_md_exists():
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault" / "02-Wiki" / "Skills" / "insider_tracker" / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0


def test_t4_schema_fields_documented():
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "insider_tracker" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    for field in (
        "ticker",
        "insider_name",
        "role",
        "transaction_type",
        "shares",
        "price",
        "date",
        "signal",
        "generated_at",
    ):
        assert field in content, f"Schema field '{field}' not documented"


def test_t4_signal_values_documented():
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "insider_tracker" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "BULLISH_INSIDER" in content
    assert "BEARISH_INSIDER" in content


def test_t4_sec_rate_limit_noted():
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents" / "trading" / "insider_tracker" / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "sleep" in content.lower() or "rate" in content.lower(), (
        "SEC rate limit / sleep not documented"
    )


def test_t4_output_schema_valid_when_scraper_built(monkeypatch):
    from atlas_agents.trading.insider_tracker import insider_tracker_scraper as mod

    atom = """
    <feed>
      <entry>
        <title>4 - Example Corp (EXM)</title>
        <link href="https://www.sec.gov/Archives/edgar/data/1/primary_doc.html" />
        <updated>2026-05-10T00:00:00Z</updated>
      </entry>
    </feed>
    """
    form4 = """
    <ownershipDocument>
      <issuer><issuerTradingSymbol>EXM</issuerTradingSymbol></issuer>
      <reportingOwner>
        <reportingOwnerId><rptOwnerName>Jane Insider</rptOwnerName></reportingOwnerId>
        <reportingOwnerRelationship><isDirector>1</isDirector><officerTitle>CEO</officerTitle></reportingOwnerRelationship>
      </reportingOwner>
      <nonDerivativeTable>
        <nonDerivativeTransaction>
          <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
          <transactionAmounts>
            <transactionShares><value>1000</value></transactionShares>
            <transactionPricePerShare><value>10.5</value></transactionPricePerShare>
          </transactionAmounts>
        </nonDerivativeTransaction>
      </nonDerivativeTable>
    </ownershipDocument>
    """

    def fake_get_text(url, **_kwargs):
        if "browse-edgar" in url:
            return atom
        return form4

    monkeypatch.setattr(mod, "requests_get_text", fake_get_text)
    monkeypatch.setattr(mod, "_pace_delay", lambda: 0.0)
    result = mod.scrape(top_n=5)
    assert "generated_at" in result
    assert result["record_count"] == 1
    assert result["filings"][0]["ticker"] == "EXM"
    assert result["filings"][0]["transaction_type"] == "BUY"
    assert result["filings"][0]["signal"] == "BULLISH_INSIDER"


def test_t4_fallback_used_when_sec_feed_empty(monkeypatch):
    from atlas_agents.trading.insider_tracker import insider_tracker_scraper as mod

    monkeypatch.setattr(mod, "requests_get_text", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(mod, "_pace_delay", lambda: 0.0)

    result = mod.scrape(top_n=5)

    assert result["record_count"] > 0
    assert result["filings"]
    assert result["filings"][0]["signal"] in {"BULLISH_INSIDER", "BEARISH_INSIDER"}


def test_t4_write_outputs_uses_cache_pair(tmp_path, monkeypatch):
    from atlas_agents.trading.insider_tracker import insider_tracker_scraper as mod

    monkeypatch.setattr(mod, "DATA_CACHE_DIR", tmp_path)
    stable, stamped = mod.write_outputs(
        {
            "generated_at": "2026-05-10T00:00:00Z",
            "source": "test",
            "record_count": 0,
            "filings": [],
        }
    )
    assert stable.name == "insider_trades_latest.json"
    assert stamped.name.startswith("insider_trades_")
    assert stable.exists()
    assert stamped.exists()
