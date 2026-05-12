# tests/test_api_endpoints.py
# FastAPI smoke tests + data_cache routing regression (no Gemini / 10-loop runs).
# Run: python -m pytest tests/test_api_endpoints.py -v
#
# New snapshot integration (one intent per session) requires:
#   - Intent string + data_cache/<name>_latest.json + JSON trimmer in atlas_omega.py
#   - topic/scan regex in classify_sector_cache_intent(); respect ticker DD exclude regex
#   - CommandDispatcher.execute() light path for the new intent if macro-only is intended

from __future__ import annotations

import os
import json

os.environ.setdefault("ATLAS_DISABLE_AUTH", "true")

import pytest
from fastapi.testclient import TestClient

from atlas_omega import (
    DC_INTENT_CRYPTO,
    DC_INTENT_EQUITIES,
    DC_INTENT_FOREX,
    DC_INTENT_INSIDER,
    DC_INTENT_OPTIONS_FLOW,
    DC_INTENT_WATCHES,
    _load_internal_knowledge_payload,
    build_market_intelligence_context,
    load_equities_payload,
    load_insider_payload,
    load_options_flow_payload,
    UserContext,
)
from query_router import (
    INTENT_CRYPTO_MARKET_SCAN,
    INTENT_EQUITIES_MARKET_SCAN,
    INTENT_FOREX_MARKET_SCAN,
    INTENT_COMMODITIES_MARKET_SCAN,
    INTENT_SUPPLY_CHAIN_MARKET_SCAN,
    INTENT_ENERGY_MARKET_SCAN,
    INTENT_CLIMATE_RISK_MARKET_SCAN,
    INTENT_TARIFFS_MARKET_SCAN,
    INTENT_JOBS_MARKET_SCAN,
    INTENT_CONGRESS_TRADES_MARKET_SCAN,
    INTENT_INSIDER_TRADES_MARKET_SCAN,
    INTENT_MARKET_DEEP_DIVE,
    INTENT_OPTIONS_FLOW_MARKET_SCAN,
    INTENT_WATCH_MARKET_SCAN,
    classify_intent_route,
    classify_sector_cache_intent,
)
import api_server
from api_server import app, get_current_user


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def test_health_returns_ok(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "engines" in body
    assert "query_router" in body["engines"]


@pytest.mark.parametrize("path", ["/app", "/chat", "/ra-omega", "/option1"])
def test_main_chat_routes_return_html(client: TestClient, path: str) -> None:
    r = client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "R.A. Omega" in r.text


@pytest.mark.parametrize("path", ["/dashboard", "/v4", "/atlas_dashboard_v4.html"])
def test_finance_dashboard_routes_return_html(client: TestClient, path: str) -> None:
    r = client.get(path)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_pricing_route_returns_checkout_page(client: TestClient) -> None:
    r = client.get("/pricing")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    assert "Pick your level of intelligence." in r.text
    assert "checkout('pro')" in r.text
    assert "/billing/checkout" in r.text
    assert "R.A. OMEGA_" in r.text


def test_regime_endpoint_returns_json(client: TestClient) -> None:
    r = client.get("/regime")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)
    assert "regime" in body


def test_stats_endpoint_returns_json(client: TestClient) -> None:
    r = client.get("/stats")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, dict)


def test_alerts_endpoint_returns_list(client: TestClient) -> None:
    r = client.get("/alerts")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert isinstance(body.get("alerts"), list)
    assert body.get("count") == len(body["alerts"])


def test_compare_requires_two_distinct_tickers(client: TestClient) -> None:
    r = client.post("/compare", json={"tickers": ["NVDA", "nvda"]})
    assert r.status_code == 400


def test_compare_adds_metadata(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    def fake_dispatch(req, uid, bt):
        return {"query": req.query, "parsed_query": {}}

    monkeypatch.setattr(api_server, "dispatch_query_request", fake_dispatch)
    r = client.post("/compare", json={"tickers": ["NVDA", "AMD"]})
    assert r.status_code == 200
    j = r.json()
    assert j["_compare"]["compare_mode"] == "single_query"
    assert j["_compare"]["tickers"] == ["NVDA", "AMD"]


def test_voice_query_transcribes_and_dispatches(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(
        api_server,
        "_transcribe_whisper_openai",
        lambda content, fn: "What is the Fed doing?",
    )
    monkeypatch.setattr(
        api_server,
        "dispatch_query_request",
        lambda req, uid, bt: {"ok": True, "query": req.query},
    )
    r = client.post(
        "/voice/query",
        files={"audio": ("note.webm", b"\x00\x02\xff", "audio/webm")},
    )
    assert r.status_code == 200
    assert r.json().get("query") == "What is the Fed doing?"


def test_report_edit_rejects_test_user(client: TestClient) -> None:
    r = client.post(
        "/report/edit",
        json={"report_id": "00000000-0000-0000-0000-000000000001", "instruction": "Shorten tldr"},
    )
    assert r.status_code == 404


def test_report_edit_updates_stored_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: "00000000-0000-4000-8000-000000000001"
    monkeypatch.setattr(api_server.atlas_db, "is_configured", lambda: True)
    monkeypatch.setattr(api_server.atlas_db, "get_supabase_client", lambda: object())
    monkeypatch.setattr(
        api_server.atlas_db,
        "fetch_research_query_row",
        lambda uid, rid: {"result_json": {"tldr": "old", "final_report": {}}},
    )
    monkeypatch.setattr(
        api_server.atlas_db,
        "update_research_query_result_json",
        lambda uid, rid, rj: True,
    )
    monkeypatch.setattr(
        api_server,
        "_gemini_nl_edit_report_json",
        lambda rj, instr: {"tldr": "new", "final_report": {}},
    )
    c = TestClient(app)
    r = c.post(
        "/report/edit",
        json={"report_id": "rep-1", "instruction": "Make tldr say new"},
    )
    app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["result"]["tldr"] == "new"


def test_query_ui_envelope_promotes_report_fields() -> None:
    shaped = api_server._ensure_query_ui_envelope(
        {
            "tldr": "Hold into the reclaim.",
            "executive_summary": "Desk summary",
            "trade_plan": {"entry": "14.00", "stop_loss": "12.75", "target_1": "16.50"},
            "scenarios": [{"label": "Base", "probability": 0.5}],
            "execution_rules": [{"trigger": "Reclaim VWAP", "action": "add"}],
            "failure_modes": [{"mode": "Breakdown", "severity": "high"}],
            "trader_memo": "Keep size modest.",
        },
        "Analyze SOUN",
    )
    fr = shaped["final_report"]
    assert fr["executive_summary"] == "Desk summary"
    assert fr["executive_brief"] == "Desk summary"
    assert fr["trade_plan"]["entry"] == "14.00"
    assert shaped["scenarios"] == fr["scenarios"]
    assert shaped["execution_rules"] == fr["execution_rules"]
    assert shaped["failure_modes"] == fr["failure_modes"]
    assert shaped["trader_memo"] == fr["trader_memo"]


def test_post_query_fast_chat_skips_router_parse(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    class NoParserRouter:
        def parse_only(self, _query: str):
            raise AssertionError("casual chat should not call parser")

        def route(self, *_args, **_kwargs):
            raise AssertionError("casual chat should not route")

    monkeypatch.setattr(api_server, "get_router", lambda: NoParserRouter())
    r = client.post("/query", json={"query": "hi"})
    assert r.status_code == 200
    body = r.json()
    assert body["parsed_query"]["intent_route"] == "CONVERSATION"
    assert body["timing"]["loops"] == 0
    assert "Hey" in body["tldr"]


def test_post_query_dispatches_router_and_returns_ui_payload(
    monkeypatch: pytest.MonkeyPatch, client: TestClient,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeRouter:
        def route(self, query: str, **kwargs):
            calls.append({"query": query, **kwargs})
            return {
                "parsed_query": {"query_type": "MARKET_DEEP_DIVE"},
                "final_report": {
                    "ticker": "NVDA",
                    "tldr": "NVDA remains constructive above support.",
                    "trader_memo": "Keep risk defined.",
                },
                "timing": {"total": 0.01},
            }

    monkeypatch.setattr(api_server, "get_router", lambda: FakeRouter())
    r = client.post(
        "/query",
        json={"query": "Analyze NVDA", "session_id": "session-1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert calls
    assert calls[0]["query"].endswith("Analyze NVDA")
    assert "Research mode: NORMAL" in calls[0]["query"]
    assert "[Active specialist packets]" in calls[0]["query"]
    assert '"packet_count"' in calls[0]["query"]
    assert calls[0]["user_id"] == "test_user_local"
    assert calls[0]["session_id"] == "session-1"
    assert calls[0]["crypto_snapshot"] is False
    assert body["query"] == "Analyze NVDA"
    assert body["parsed_query"]["query_type"] == "MARKET_DEEP_DIVE"
    assert body["final_report"]["ticker"] == "NVDA"
    assert body["tldr"] == "NVDA remains constructive above support."
    assert body["_route_decision"]["route_band"] == "focused_analysis"
    assert body["_active_agents"]["agent_ids"]
    assert "D2" in body["_active_agents"]["agent_ids"]
    assert body["_specialist_packets"]["agent_ids"] == body["_active_agents"]["agent_ids"]


def test_post_query_attaches_market_intelligence_for_tickers(
    monkeypatch: pytest.MonkeyPatch, tmp_path, client: TestClient,
) -> None:
    (tmp_path / "equities_latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-05-12T00:00:00Z",
                "source": "test",
                "record_count": 1,
                "gainers": [{"ticker": "NVDA", "price": 100, "signal": "BULLISH_MOMENTUM"}],
                "losers": [],
                "active": [],
                "most_active": [],
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
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "insider_trades_latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-05-12T00:00:00Z",
                "source": "test",
                "record_count": 1,
                "filings": [{"ticker": "NVDA", "signal": "BULLISH_INSIDER"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ATLAS_DATA_CACHE_DIR", str(tmp_path))

    class FakeRouter:
        def route(self, query: str, **kwargs):
            return {
                "parsed_query": {"query_type": "MARKET_DEEP_DIVE", "tickers": ["NVDA"]},
                "final_report": {
                    "ticker": "NVDA",
                    "tldr": "NVDA context ready.",
                },
                "tldr": "NVDA context ready.",
            }

    monkeypatch.setattr(api_server, "get_router", lambda: FakeRouter())
    r = client.post("/query", json={"query": "Analyze NVDA"})
    assert r.status_code == 200
    body = r.json()
    mi = body["_market_intelligence"]
    assert mi["snapshot"] == "d2_d3_d4_market_intelligence"
    assert mi["tickers"] == ["NVDA"]
    assert mi["ticker_slices"]["options_flow"][0]["signal"] == "BULLISH_UNUSUAL"
    assert mi["ticker_slices"]["insider_trades"][0]["signal"] == "BULLISH_INSIDER"


def test_post_query_accepts_research_controls(
    monkeypatch: pytest.MonkeyPatch, client: TestClient,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeRouter:
        def route(self, query: str, **kwargs):
            calls.append({"query": query, **kwargs})
            return {
                "parsed_query": {"query_type": "MARKET_DEEP_DIVE"},
                "final_report": {"executive_summary": "done"},
                "tldr": "done",
            }

    monkeypatch.setattr(api_server, "get_router", lambda: FakeRouter())
    r = client.post(
        "/query",
        json={
            "query": "hi",
            "research_mode": "deep",
            "web_search": True,
            "answer_style": "desk",
            "risk_profile": "conservative",
            "market_focus": "US equities",
            "report_depth": "full",
            "citation_preference": "always",
            "compliance_level": "strict",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["_request_controls"]["research_mode"] == "deep"
    assert body["_request_controls"]["web_search"] is True
    assert body["_route_decision"]["route_band"] == "deep_research"
    assert body["_research_activity"]["route_band"] == "deep_research"
    assert body["_research_activity"]["plan"]
    assert calls
    assert "Research mode: DEEP" in calls[0]["query"]
    assert "Route decision: deep_research" in calls[0]["query"]
    assert "Answer style: desk." in calls[0]["query"]
    assert "Preferred report depth: full." in calls[0]["query"]
    assert "Citation preference: always." in calls[0]["query"]
    assert "Compliance disclaimer level: strict." in calls[0]["query"]
    assert "hi" in calls[0]["query"]


def test_research_job_plan_get_and_cancel(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    api_server.research_jobs.configure_store(tmp_path / "research_jobs.json")
    c = TestClient(app)
    r = c.post(
        "/jobs/plan",
        json={"query": "deep research NVDA", "research_mode": "deep"},
    )
    assert r.status_code == 200
    body = r.json()
    job_id = body["activity"]["job_id"]
    assert job_id.startswith("research_")
    assert body["activity"]["status"] == "queued"
    assert body["route_decision"]["route_band"] == "deep_research"

    r2 = c.get(f"/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["activity"]["job_id"] == job_id

    r3 = c.post(f"/jobs/{job_id}/cancel")
    assert r3.status_code == 200
    assert r3.json()["activity"]["status"] == "cancelled"


def test_post_query_updates_existing_research_job(
    monkeypatch: pytest.MonkeyPatch, tmp_path, client: TestClient,
) -> None:
    api_server.research_jobs.configure_store(tmp_path / "research_jobs.json")

    class FakeRouter:
        def route(self, query: str, **kwargs):
            cb = kwargs.get("progress_callback")
            if cb:
                cb(
                    {
                        "stage": "Loop 1: market scrape",
                        "progress_pct": 15,
                        "message": "Gathering market context.",
                        "loop": 1,
                        "ts": "2026-05-11T00:00:00+00:00",
                    }
                )
            return {
                "parsed_query": {"query_type": "MARKET_DEEP_DIVE"},
                "final_report": {"executive_summary": "done"},
                "tldr": "done",
            }

    monkeypatch.setattr(api_server, "get_router", lambda: FakeRouter())
    plan = client.post(
        "/jobs/plan",
        json={"query": "deep research NVDA", "research_mode": "deep"},
    ).json()
    job_id = plan["activity"]["job_id"]
    r = client.post(
        "/query",
        json={
            "query": "deep research NVDA",
            "research_mode": "deep",
            "research_job_id": job_id,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["_research_activity"]["job_id"] == job_id
    assert body["_research_activity"]["status"] == "completed"
    assert any(
        event.get("label") == "Loop 1: market scrape"
        for event in body["_research_activity"]["events"]
    )
    assert client.get(f"/jobs/{job_id}").json()["activity"]["status"] == "completed"


def test_user_preferences_round_trip(client: TestClient) -> None:
    r = client.get("/user/preferences")
    assert r.status_code == 200
    assert r.json()["preferences"]["default_research_mode"] == "normal"

    r2 = client.patch(
        "/user/preferences",
        json={
            "display_name": "Roberto",
            "default_research_mode": "web",
            "answer_style": "desk",
            "risk_profile": "conservative",
            "market_focus": "US equities",
            "source_strictness": "strict",
            "report_depth": "full",
            "card_density": "compact",
            "voice_dictation": False,
            "citation_preference": "always",
            "compliance_level": "strict",
            "memory_enabled": False,
            "notifications_enabled": True,
            "accent_color": "green",
        },
    )
    assert r2.status_code == 200
    prefs = r2.json()["preferences"]
    assert prefs["display_name"] == "Roberto"
    assert prefs["default_research_mode"] == "web"
    assert prefs["report_depth"] == "full"
    assert prefs["card_density"] == "compact"
    assert prefs["voice_dictation"] is False
    assert prefs["citation_preference"] == "always"
    assert prefs["compliance_level"] == "strict"
    assert prefs["memory_enabled"] is False
    assert prefs["notifications_enabled"] is True


def test_query_tier_gate_blocks_over_daily_cap(
    monkeypatch: pytest.MonkeyPatch, client: TestClient,
) -> None:
    uid = "00000000-0000-0000-0000-000000000001"
    monkeypatch.setenv("ATLAS_DISABLE_AUTH", "false")
    monkeypatch.setattr(api_server.atlas_db, "get_user_preferences", lambda _uid: {"subscription_tier": "free"})
    monkeypatch.setattr(api_server.atlas_db, "count_queries_today", lambda _uid: 5)
    api_server.app.dependency_overrides[api_server.get_current_user] = lambda: uid
    try:
        r = client.post("/query", json={"query": "Analyze NVDA"}, headers={"Authorization": "Bearer test"})
    finally:
        api_server.app.dependency_overrides.pop(api_server.get_current_user, None)
        monkeypatch.setenv("ATLAS_DISABLE_AUTH", "true")
    assert r.status_code == 429
    body = r.json()["detail"]
    assert body["error"] == "daily_query_limit_reached"
    assert body["tier"] == "free"


def test_option1_redirects_without_cookie_when_auth_enabled(
    monkeypatch: pytest.MonkeyPatch, client: TestClient,
) -> None:
    monkeypatch.setenv("ATLAS_DISABLE_AUTH", "false")
    r = client.get("/option1", follow_redirects=False)
    monkeypatch.setenv("ATLAS_DISABLE_AUTH", "true")
    assert r.status_code == 302
    assert "/auth" in r.headers["location"]


def test_billing_checkout_returns_503_when_not_configured(client: TestClient) -> None:
    r = client.post(
        "/billing/checkout",
        json={
            "plan": "pro",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        },
    )
    assert r.status_code == 503


def test_billing_webhook_updates_subscription_without_network(
    monkeypatch: pytest.MonkeyPatch, client: TestClient,
) -> None:
    monkeypatch.setenv("ATLAS_ALLOW_UNSIGNED_STRIPE_WEBHOOK", "true")
    r = client.post(
        "/billing/webhook",
        json={
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": "test_user_local",
                    "customer": "cus_test",
                    "status": "active",
                    "metadata": {"user_id": "test_user_local", "plan": "pro"},
                }
            },
        },
    )
    assert r.status_code == 200
    assert r.json()["handled"] is True
    prefs = client.get("/user/preferences").json()["preferences"]
    assert prefs["subscription_tier"] == "pro"
    assert prefs["subscription_status"] == "active"


def test_api_v1_query_503_when_keys_not_configured(
    monkeypatch: pytest.MonkeyPatch, client: TestClient,
) -> None:
    monkeypatch.delenv("ATLAS_DEV_API_KEY", raising=False)
    monkeypatch.delenv("ATLAS_DEV_API_KEYS", raising=False)
    r = client.get(
        "/api/v1/query",
        params={"q": "hello"},
        headers={"X-ATLAS-DEV-KEY": "x"},
    )
    assert r.status_code == 503


def test_api_v1_query_401_with_wrong_key(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setenv("ATLAS_DEV_API_KEY", "secret")
    r = client.get(
        "/api/v1/query",
        params={"q": "hello"},
        headers={"X-ATLAS-DEV-KEY": "nope"},
    )
    assert r.status_code == 401


def test_api_v1_query_dispatches_with_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    monkeypatch.setenv("ATLAS_DEV_API_KEY", "k1")
    monkeypatch.setattr(api_server, "BASE_DIR", tmp_path)

    def fake_dispatch(req, uid, bt):
        return {"query": req.query, "dev_user": uid}

    monkeypatch.setattr(api_server, "dispatch_query_request", fake_dispatch)
    c = TestClient(app)
    r = c.get(
        "/api/v1/query",
        params={"q": "hello world"},
        headers={"X-ATLAS-DEV-KEY": "k1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("query") == "hello world"
    logf = tmp_path / "atlas_dev_api_billing.log"
    assert logf.is_file()
    logged = logf.read_text(encoding="utf-8")
    assert "charge_usd" in logged


def test_classify_sector_cache_excludes_single_ticker_analyze() -> None:
    assert classify_sector_cache_intent("Analyze NVDA") is None
    assert classify_sector_cache_intent("deep dive on AAPL") is None


def test_classify_intent_route_nvda_stays_market_deep_dive() -> None:
    assert classify_intent_route("Analyze NVDA") == INTENT_MARKET_DEEP_DIVE


def test_classify_sector_cache_crypto_movers() -> None:
    q = "What are the biggest crypto gainers right now?"
    assert classify_sector_cache_intent(q) == INTENT_CRYPTO_MARKET_SCAN


def test_classify_sector_cache_equities_movers() -> None:
    q = "What are the top stock gainers on the NYSE today?"
    assert classify_sector_cache_intent(q) == INTENT_EQUITIES_MARKET_SCAN


def test_classify_sector_cache_options_flow() -> None:
    assert (
        classify_sector_cache_intent("What is the unusual options flow today?")
        == INTENT_OPTIONS_FLOW_MARKET_SCAN
    )
    assert (
        classify_sector_cache_intent("Any NVDA options flow today?")
        == INTENT_OPTIONS_FLOW_MARKET_SCAN
    )


def test_classify_sector_cache_insider_buys() -> None:
    assert (
        classify_sector_cache_intent("Show me recent insider buys")
        == INTENT_INSIDER_TRADES_MARKET_SCAN
    )


def test_crypto_topic_without_scan_pattern_is_not_routed() -> None:
    assert classify_sector_cache_intent("Explain how bitcoin mining works") is None


def test_classify_sector_cache_luxury_watch_market_snapshot_a1() -> None:
    q = (
        "Luxury watch market snapshot — summarize premiums vs retail and trend signals "
        "from the cached Chrono24 scan."
    )
    assert classify_sector_cache_intent(q) == INTENT_WATCH_MARKET_SCAN


def test_luxury_watch_topic_without_scan_pattern_is_not_routed() -> None:
    assert classify_sector_cache_intent("When was the Rolex Submariner introduced?") is None


def test_classify_sector_cache_new_macro_agents() -> None:
    assert classify_sector_cache_intent("Forex market snapshot today") == INTENT_FOREX_MARKET_SCAN
    assert classify_sector_cache_intent("Commodities overview right now") == INTENT_COMMODITIES_MARKET_SCAN
    assert classify_sector_cache_intent("Supply chain freight snapshot today") == INTENT_SUPPLY_CHAIN_MARKET_SCAN
    assert classify_sector_cache_intent("Energy grid overview latest") == INTENT_ENERGY_MARKET_SCAN
    assert classify_sector_cache_intent("FEMA flood climate risk snapshot") == INTENT_CLIMATE_RISK_MARKET_SCAN
    assert classify_sector_cache_intent("Tariff trade war overview today") == INTENT_TARIFFS_MARKET_SCAN
    assert classify_sector_cache_intent("Jobs report labor market snapshot") == INTENT_JOBS_MARKET_SCAN
    assert classify_sector_cache_intent("Congressional trades recent snapshot") == INTENT_CONGRESS_TRADES_MARKET_SCAN


def test_internal_knowledge_payload_loads_crypto_and_equities() -> None:
    """Requires data_cache/crypto_top50_latest.json and equities_latest.json (dev fixtures)."""
    c_json, c_meta = _load_internal_knowledge_payload(DC_INTENT_CRYPTO)
    e_json, e_meta = _load_internal_knowledge_payload(DC_INTENT_EQUITIES)
    assert c_meta.get("intent") == DC_INTENT_CRYPTO
    assert e_meta.get("intent") == DC_INTENT_EQUITIES
    if c_meta.get("loaded"):
        assert c_json is not None
        assert c_json.get("snapshot") == "crypto_top50"
    else:
        assert "missing_file" in str(c_meta.get("error", "")) or c_meta.get("error")
    if e_meta.get("loaded"):
        assert e_json is not None
        assert e_json.get("snapshot") == "equities_screener"
    else:
        assert "missing_file" in str(e_meta.get("error", "")) or e_meta.get("error")


def test_internal_knowledge_payload_accepts_new_macro_intent() -> None:
    payload, meta = _load_internal_knowledge_payload(DC_INTENT_FOREX)
    assert meta.get("intent") == DC_INTENT_FOREX
    if meta.get("loaded"):
        assert payload is not None
        assert payload.get("snapshot") == "forex_rates"
    else:
        assert meta.get("error")


def test_d2_d3_d4_loaders_and_ticker_slices(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "equities_latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-05-10T00:00:00Z",
                "source": "test",
                "record_count": 1,
                "gainers": [{"ticker": "NVDA", "price": 100, "change_pct": 3.2, "signal": "BULLISH_MOMENTUM"}],
                "losers": [],
                "active": [],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "options_flow_latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-05-10T00:00:00Z",
                "source": "test",
                "record_count": 1,
                "unusual_activity": [
                    {
                        "ticker": "NVDA",
                        "expiry": "2026-06-19",
                        "strike": 150,
                        "type": "CALL",
                        "volume_oi_ratio": 4.5,
                        "signal": "BULLISH_UNUSUAL",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "insider_trades_latest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-05-10T00:00:00Z",
                "source": "test",
                "record_count": 1,
                "filings": [
                    {
                        "ticker": "NVDA",
                        "insider_name": "Jane Insider",
                        "transaction_type": "BUY",
                        "signal": "BULLISH_INSIDER",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ATLAS_DATA_CACHE_DIR", str(tmp_path))

    eq, eq_meta = load_equities_payload()
    opt, opt_meta = load_options_flow_payload()
    ins, ins_meta = load_insider_payload()
    assert eq_meta["loaded"] and eq["snapshot"] == "equities_screener"
    assert opt_meta["loaded"] and opt["snapshot"] == "options_flow"
    assert ins_meta["loaded"] and ins["snapshot"] == "sec_form4_filings"

    ctx = UserContext(tickers=["NVDA"])
    bundle = build_market_intelligence_context("Analyze NVDA options and insider tape", ctx)
    assert bundle["ticker_slices"]["equities"][0]["ticker"] == "NVDA"
    assert bundle["ticker_slices"]["options_flow"][0]["signal"] == "BULLISH_UNUSUAL"
    assert bundle["ticker_slices"]["insider_trades"][0]["signal"] == "BULLISH_INSIDER"


def test_internal_knowledge_payload_loads_options_and_insiders() -> None:
    opt_json, opt_meta = _load_internal_knowledge_payload(DC_INTENT_OPTIONS_FLOW)
    ins_json, ins_meta = _load_internal_knowledge_payload(DC_INTENT_INSIDER)
    assert opt_meta.get("intent") == DC_INTENT_OPTIONS_FLOW
    assert ins_meta.get("intent") == DC_INTENT_INSIDER
    if opt_meta.get("loaded"):
        assert opt_json is not None
        assert opt_json.get("snapshot") == "options_flow"
    else:
        assert "missing_file" in str(opt_meta.get("error", "")) or opt_meta.get("error")
    if ins_meta.get("loaded"):
        assert ins_json is not None
        assert ins_json.get("snapshot") == "sec_form4_filings"
    else:
        assert "missing_file" in str(ins_meta.get("error", "")) or ins_meta.get("error")


def test_internal_knowledge_payload_loads_watches_a1() -> None:
    w_json, w_meta = _load_internal_knowledge_payload(DC_INTENT_WATCHES)
    assert w_meta.get("intent") == DC_INTENT_WATCHES
    if w_meta.get("loaded"):
        assert w_json is not None
        assert w_json.get("snapshot") == "luxury_watch_market"
        assert isinstance(w_json.get("models"), list)
    else:
        assert "missing_file" in str(w_meta.get("error", "")) or w_meta.get("error")
