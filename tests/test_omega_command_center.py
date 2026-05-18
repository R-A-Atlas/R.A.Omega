"""
tests/test_omega_command_center.py

Binary evals for omega_command_center.html — user-facing finance dashboard.
All checks are True/False (DBS eval standard).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent
HTML = ROOT / "omega_command_center.html"


# ── File existence ─────────────────────────────────────────────────────────────

def test_command_center_exists():
    assert HTML.is_file()


# ── Route wiring ──────────────────────────────────────────────────────────────

def test_route_wired_in_api_server():
    text = (ROOT / "api_server.py").read_text(encoding="utf-8")
    assert "/command-center" in text


def test_route_serves_command_center_html():
    text = (ROOT / "api_server.py").read_text(encoding="utf-8")
    assert "omega_command_center.html" in text


# ── Design system ─────────────────────────────────────────────────────────────

def test_links_design_system_css():
    assert "design_system.css" in HTML.read_text(encoding="utf-8")


def test_uses_css_variables():
    text = HTML.read_text(encoding="utf-8")
    assert "--color-accent" in text or "var(--color" in text


# ── Core layout elements ──────────────────────────────────────────────────────

def test_has_top_nav():
    assert "top-nav" in HTML.read_text(encoding="utf-8")


def test_has_left_sidebar():
    assert "left-sidebar" in HTML.read_text(encoding="utf-8")


def test_has_center_main():
    assert "center-main" in HTML.read_text(encoding="utf-8")


def test_has_right_panel():
    assert "right-panel" in HTML.read_text(encoding="utf-8")


# ── User-facing feature elements ──────────────────────────────────────────────

def test_has_query_input():
    assert "query-input" in HTML.read_text(encoding="utf-8")


def test_has_sessions_list():
    assert "sessions-list" in HTML.read_text(encoding="utf-8")


def test_has_watchlist_list():
    assert "watchlist-list" in HTML.read_text(encoding="utf-8")


def test_has_reports_grid():
    assert "reports-grid" in HTML.read_text(encoding="utf-8")


def test_has_alerts_list():
    assert "alerts-list" in HTML.read_text(encoding="utf-8")


def test_has_regime_display():
    text = HTML.read_text(encoding="utf-8")
    assert "regime-pill" in text or "regime-card" in text


def test_has_quick_prompts():
    text = HTML.read_text(encoding="utf-8")
    assert "prompt-chip" in text


def test_has_new_analysis_button():
    text = HTML.read_text(encoding="utf-8")
    assert "New Analysis" in text


def test_has_send_button():
    assert "send-btn" in HTML.read_text(encoding="utf-8")


# ── Navigation links ──────────────────────────────────────────────────────────

def test_links_to_app():
    assert '"/app"' in HTML.read_text(encoding="utf-8") or "href=\"/app\"" in HTML.read_text(encoding="utf-8")


def test_links_to_dashboard():
    assert "/v2" in HTML.read_text(encoding="utf-8")


def test_links_to_brain_network():
    assert "/omega-os/brain-network" in HTML.read_text(encoding="utf-8")


# ── Live data endpoints ───────────────────────────────────────────────────────

def test_fetches_regime():
    assert '"/regime"' in HTML.read_text(encoding="utf-8") or "fetch(\"/regime\"" in HTML.read_text(encoding="utf-8")


def test_fetches_sessions():
    assert '"/sessions"' in HTML.read_text(encoding="utf-8") or "fetch(\"/sessions\"" in HTML.read_text(encoding="utf-8")


def test_fetches_watchlist():
    assert '"/watchlist"' in HTML.read_text(encoding="utf-8") or "fetch(\"/watchlist\"" in HTML.read_text(encoding="utf-8")


def test_fetches_alerts():
    assert '"/alerts"' in HTML.read_text(encoding="utf-8") or "fetch(\"/alerts\"" in HTML.read_text(encoding="utf-8")


def test_fetches_history_reports():
    assert "/history/reports" in HTML.read_text(encoding="utf-8")


# ── Security ──────────────────────────────────────────────────────────────────

def test_has_xss_escape_function():
    assert "escHtml" in HTML.read_text(encoding="utf-8")


def test_no_hardcoded_api_keys():
    text = HTML.read_text(encoding="utf-8").lower()
    assert "sk-" not in text
    assert "api_key" not in text


def test_no_hardcoded_secrets():
    text = HTML.read_text(encoding="utf-8").lower()
    assert "password" not in text
    assert "secret" not in text


def test_auth_header_helper():
    assert "_authHeaders" in HTML.read_text(encoding="utf-8")


# ── Responsive design ─────────────────────────────────────────────────────────

def test_has_viewport_meta():
    assert 'name="viewport"' in HTML.read_text(encoding="utf-8")


def test_has_mobile_media_query():
    text = HTML.read_text(encoding="utf-8")
    assert "@media (max-width:" in text


def test_has_skeleton_loading():
    assert "skel" in HTML.read_text(encoding="utf-8")


def test_auth_header_helper_uses_ra_omega_token_keys():
    text = HTML.read_text(encoding="utf-8")
    assert "atlas_access_token" in text
    assert "ATLAS_TEST_JWT" in text
    assert "atlas_user_email" in text


# ── Welcome greeting ──────────────────────────────────────────────────────────

def test_has_dynamic_greeting():
    text = HTML.read_text(encoding="utf-8")
    assert "Good morning" in text or "welcome-heading" in text


# ── Session storage passthrough ───────────────────────────────────────────────

def test_stores_pending_query_on_submit():
    assert "omega_pending_query" in HTML.read_text(encoding="utf-8")


def test_stores_query_mode_on_submit():
    assert "omega_query_mode" in HTML.read_text(encoding="utf-8")
