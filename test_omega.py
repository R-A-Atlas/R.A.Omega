"""
test_omega.py — ATLAS 10-Loop Integration Test
Run this AFTER starting api_server.py with:
    uvicorn api_server:app --reload --port 8000

Then in a second terminal:
    python test_omega.py

If the API requires Supabase JWT, set ATLAS_TEST_JWT or SUPABASE_ACCESS_TOKEN
to a valid access_token (same as the dashboard uses).
"""
import os
import requests
import json
import sys

BASE = "http://127.0.0.1:8000"


def _auth_headers():
    tok = (os.environ.get("ATLAS_TEST_JWT") or os.environ.get("SUPABASE_ACCESS_TOKEN") or "").strip()
    if not tok:
        return {}
    return {"Authorization": f"Bearer {tok}"}


def test_soun_options_parse():
    """Local: ensure average cost / mark / IV map into ParsedQuery.options_context."""
    from query_router import QueryRouter

    q = (
        "Analyze my SOUN $14 Call (Exp 06/18). My average cost is $0.52, "
        "current mark is $0.44, and IV is 116.5%. Given the earnings revenue "
        "beat but the massive 11% AH drop to $8.69, what is my execution plan "
        "for the open?"
    )
    p = QueryRouter().parse_only(q)
    o = p.options_context
    assert abs(float(o.get("avg_premium", 0)) - 0.52) < 1e-6, f"avg_premium: {o}"
    assert abs(float(o.get("current_mark", 0)) - 0.44) < 1e-6, f"current_mark: {o}"
    assert abs(float(o.get("iv_pct", 0)) - 116.5) < 1e-6, f"iv_pct: {o}"
    print("test_soun_options_parse: OK —", o)


def test_health():
    """Verify the server is running and both engines loaded."""
    try:
        r = requests.get(f"{BASE}/health", timeout=10)
        data = r.json()
        print(f"Health:   {data.get('status')}")
        print(f"Engines:  {data.get('engines')}")
        print(f"Version:  {data.get('version')}")
        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        print("Make sure api_server is running: uvicorn api_server:app --reload --port 8000")
        return False


def test_soun_query():
    """
    Full 10-loop test via /query endpoint (QueryRouter.route).
    /omega uses OmegaAgent only (no 10-loop pipeline) — different JSON shape.
    """
    payload = {
        "query": (
            "Analyze my SOUN $14 Call (Exp 06/18) given today's earnings beat, "
            "the Walmart ONN TV integration, the 11% AH drop. My avg cost was $0.52. "
            "Should I hold, roll, or exit?"
        ),
    }

    print("\nRunning SOUN analysis via POST /query (10-loop QueryRouter)...")
    print("(Expect 60–180s depending on Gemini + scrapes)")

    try:
        r = requests.post(
            f"{BASE}/query",
            json=payload,
            timeout=300,
            headers=_auth_headers(),
        )
        result = r.json()
    except Exception as e:
        print(f"Request failed: {e}")
        return

    print(f"\n{'='*60}")
    print(f"Status:           {r.status_code}")
    if r.status_code == 401:
        print("401 Unauthorized — set ATLAS_TEST_JWT or SUPABASE_ACCESS_TOKEN to a valid Supabase access token.")
    elif r.status_code == 503:
        d = result.get("detail") if isinstance(result, dict) else None
        print(f"503 — {d or result}")
    if r.status_code != 200 or not isinstance(result, dict):
        print(f"\nRaw response (truncated):\n{json.dumps(result, indent=2, default=str)[:2000]}")
        return
    _required_ui = {
        "query",
        "parsed_query",
        "final_report",
        "tldr",
        "trader_memo",
        "hedge_fund_brief",
        "execution_rules",
        "failure_modes",
        "scenarios",
        "audit_notes",
        "loop_outputs",
        "timing",
    }
    keys = set(result.keys())
    missing = sorted(_required_ui - keys)
    print(f"Top-level keys:   {sorted(keys)}")
    if missing:
        print(f"MISSING UI keys:  {missing}")
    else:
        print("UI envelope:      all required keys present")
    print(f"TLDR:             {result.get('tldr', 'N/A')}")
    print(f"\nTrader memo:")
    print(f"  {str(result.get('trader_memo', 'N/A'))[:300]}")
    print(f"\nFinal rating:     {result.get('final_report', {}).get('overall_rating', 'N/A')}")
    print(f"Execution rules:  {len(result.get('execution_rules', []))} generated")
    print(f"Failure modes:    {len(result.get('failure_modes', []))} identified")
    print(f"Scenarios:        {len(result.get('scenarios', []))} with probabilities")

    timing = result.get("timing", {})
    if timing:
        print(f"\nLoop timing:")
        for k, v in timing.items():
            if k != "total":
                print(f"  {k:<25} {v}s")
        print(f"  {'TOTAL':<25} {timing.get('total','?')}s")

    cq = result.get("clarification_questions") or (result.get("final_report") or {}).get(
        "clarification_questions", []
    )
    if cq:
        print(f"\nclarification_questions ({len(cq)}):")
        for qline in cq:
            print(f"  - {qline}")

    fr = result.get("final_report") or {}
    core_ok = bool(
        (fr.get("executive_summary") or "").strip()
        or (result.get("tldr") or "").strip()
        or (result.get("trader_memo") or "").strip()
    )
    if not core_ok:
        print("\nWARNING: final_report / narrative fields look empty — check API keys / errors.")
    else:
        print("\nCore narrative fields: present (pipeline completed output).")

    cq_legacy = result.get("_clarifying_questions", [])
    if cq_legacy:
        print(f"\nLegacy _clarifying_questions:")
        for q in cq_legacy:
            print(f"  - {q}")

    output_file = "test_result_soun.json"
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nFull result saved to {output_file}")
    print(f"{'='*60}")


def test_car_omega():
    """Test the cross-domain agent with a non-stock query."""
    payload = {
        "query": (
            "I want to buy a car. My credit score is around 680, "
            "I have $3,000 to put down, I'm in Miami FL, "
            "and I can afford about $400/month. What should I do?"
        ),
    }
    print("\nRunning car buying query...")
    r = requests.post(f"{BASE}/omega", json=payload, timeout=120, headers=_auth_headers())
    result = r.json()
    print(f"Status:   {r.status_code}")
    print(f"Domain:   {result.get('domain', result.get('_meta',{}).get('domain','?'))}")
    print(f"TLDR:     {result.get('tldr', 'N/A')}")
    print(f"Headline: {result.get('headline', 'N/A')}")


if __name__ == "__main__":
    test_soun_options_parse()
    if not test_health():
        sys.exit(1)

    test_soun_query()

    if "--all" in sys.argv:
        test_car_omega()
