import json

from orchestration.agent_graph import activate_specialists
from orchestration.agent_packets import build_specialist_packets
from orchestration.router_policy import decide_route


def test_specialist_packets_load_active_agent_caches(tmp_path, monkeypatch):
    (tmp_path / "equities_latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-05-12T00:00:00Z",
                "source": "test",
                "record_count": 1,
                "gainers": [{"ticker": "NVDA", "price": 100}],
                "losers": [],
                "active": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "options_flow_latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-05-12T00:00:00Z",
                "source": "test",
                "record_count": 1,
                "unusual_activity": [{"ticker": "NVDA", "signal": "BULLISH_UNUSUAL"}],
                "_meta": {"data_quality": "fallback", "fallback_used": True},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ATLAS_DATA_CACHE_DIR", str(tmp_path))

    decision = decide_route("Analyze NVDA calls with options flow")
    activation = activate_specialists("Analyze NVDA calls with options flow", decision)
    packets = build_specialist_packets(activation)

    assert packets["packet_count"] > 0
    assert packets["packets"]["equities"]["record_count"] == 1
    assert packets["packets"]["options_flow"]["fallback_used"] is True
    assert packets["packets"]["options_flow"]["summary"]["unusual_activity"][0]["ticker"] == "NVDA"
    assert "D8" in packets["errors"]  # dark pool cache was not created in this tmp cache.


def test_specialist_packets_quick_chat_empty():
    decision = decide_route("hi")
    activation = activate_specialists("hi", decision)
    packets = build_specialist_packets(activation)

    assert packets["packet_count"] == 0
    assert packets["packets"] == {}
    assert packets["errors"] == {}
