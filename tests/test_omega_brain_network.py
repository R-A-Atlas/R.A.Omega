"""
tests/test_omega_brain_network.py

Evals for the Omega Brain Live Network page and its supporting assets.
All checks are binary True/False (DBS eval standard).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
BRAIN_HTML   = ROOT / "omega_brain_network.html"
DESIGN_CSS   = ROOT / "design_system.css"
API_SERVER   = ROOT / "api_server.py"


# ── Static asset checks ────────────────────────────────────────────────────

def test_brain_network_html_exists():
    assert BRAIN_HTML.is_file(), "omega_brain_network.html must exist"


def test_design_system_css_exists():
    assert DESIGN_CSS.is_file(), "design_system.css must exist"


# ── design_system.css content ─────────────────────────────────────────────

def test_design_system_has_color_tokens():
    css = DESIGN_CSS.read_text(encoding="utf-8")
    for token in ("--color-bg", "--color-accent", "--color-surface", "--color-text"):
        assert token in css, f"design_system.css must define {token}"


def test_design_system_has_font_tokens():
    css = DESIGN_CSS.read_text(encoding="utf-8")
    assert "--font-sans" in css
    assert "--font-mono" in css


def test_design_system_has_node_color_tokens():
    css = DESIGN_CSS.read_text(encoding="utf-8")
    for token in ("--node-core", "--node-pipeline", "--node-skill", "--node-agent",
                  "--node-integration", "--node-output"):
        assert token in css, f"design_system.css must define {token}"


def test_design_system_has_animation_keyframes():
    css = DESIGN_CSS.read_text(encoding="utf-8")
    assert "@keyframes" in css


def test_design_system_imports_google_fonts():
    css = DESIGN_CSS.read_text(encoding="utf-8")
    assert "fonts.googleapis.com" in css


# ── Brain network HTML content ────────────────────────────────────────────

def test_brain_html_imports_design_system():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "/design_system.css" in html, "Brain network page must import /design_system.css"


def test_brain_html_has_canvas():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "brain-canvas" in html, "Must have brain-canvas element"


def test_brain_html_has_inspector_panel():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "inspector" in html, "Must have inspector panel"


def test_brain_html_has_left_panel():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "left-panel" in html, "Must have left panel"


def test_brain_html_has_right_panel():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "right-panel" in html, "Must have right panel"


def test_brain_html_has_node_data():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    # All 6 node groups must be represented
    for group in ("core", "pipeline", "skill", "agent", "integration", "output"):
        assert f"group: '{group}'" in html, f"NODES array must include group '{group}'"


def test_brain_html_has_five_orbit_radii():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "ORBIT_RADII" in html, "Must define ORBIT_RADII array"


def test_brain_html_fetches_dashboard_api():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "/omega-os/dashboard" in html, "Must fetch /omega-os/dashboard"


def test_brain_html_fetches_brain_api():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "/omega-os/brain" in html, "Must fetch /omega-os/brain"


def test_brain_html_has_particle_system():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "spawnParticle" in html, "Must have particle animation system"


def test_brain_html_has_filter_buttons():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "filter-btn" in html, "Must have filter buttons for node groups"


def test_brain_html_no_hardcoded_api_keys():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    # No obvious key patterns
    assert "sk-" not in html
    assert "AIza" not in html


def test_brain_html_dashboard_link():
    html = BRAIN_HTML.read_text(encoding="utf-8")
    assert "/dashboard" in html, "Must have link back to dashboard"


# ── api_server.py routes ──────────────────────────────────────────────────

def test_api_server_has_design_system_route():
    src = API_SERVER.read_text(encoding="utf-8")
    assert '"/design_system.css"' in src, "api_server must serve /design_system.css"


def test_api_server_has_brain_network_route():
    src = API_SERVER.read_text(encoding="utf-8")
    assert '"/omega-os/brain-network"' in src, "api_server must serve /omega-os/brain-network"


def test_api_server_brain_network_serves_html():
    src = API_SERVER.read_text(encoding="utf-8")
    assert "omega_brain_network.html" in src, "Route must reference omega_brain_network.html"


# ── Python compile checks ─────────────────────────────────────────────────

def test_api_server_compiles():
    import py_compile, tempfile, shutil
    tmp = tempfile.mktemp(suffix=".py")
    shutil.copy(API_SERVER, tmp)
    try:
        py_compile.compile(tmp, doraise=True)
    finally:
        Path(tmp).unlink(missing_ok=True)
