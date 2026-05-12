from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deployment_runbook_documents_production_requirements():
    content = (ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "ATLAS_DISABLE_AUTH=false" in content
    assert "STRIPE_WEBHOOK_SECRET" in content
    assert "SUPABASE_URL" in content
    assert "GOOGLE_API_KEY" in content
    assert "/pricing" in content
    assert "omega_health.ps1 -Full" in content


def test_railway_config_uses_health_route_and_port_env():
    content = (ROOT / "railway.toml").read_text(encoding="utf-8")
    assert "api_server:app" in content
    assert "--port $PORT" in content
    assert 'healthcheckPath = "/health"' in content


def test_omega_health_script_runs_core_checks():
    content = (ROOT / "scripts" / "omega_health.ps1").read_text(encoding="utf-8")
    assert "py_compile api_server.py atlas_db.py" in content
    assert "test_pricing_route_returns_checkout_page" in content
    assert "python -m pytest tests/ -q" in content
