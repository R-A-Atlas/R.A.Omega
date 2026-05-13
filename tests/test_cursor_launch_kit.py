from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cursor_cloud_launch_kit_has_25_agents():
    content = (ROOT / "docs" / "CURSOR_CLOUD_24_7_LAUNCH.md").read_text(encoding="utf-8")
    for i in range(1, 26):
        assert f"CC-{i:02d}" in content
        assert f"cursor/cc-{i:02d}" in content
    assert "This file turns the 25-agent roster into launch-ready Cursor Cloud tasks." in content
    assert "It does not start agents by itself." in content


def test_auth_and_landing_are_ra_omega_branded():
    auth = (ROOT / "auth.html").read_text(encoding="utf-8")
    landing = (ROOT / "index_1778228972988.html").read_text(encoding="utf-8")
    legacy_landing = (ROOT / "index_1778307874705.html").read_text(encoding="utf-8")
    assert "R.A. OMEGA_" in auth
    assert "R.A. OMEGA" in landing
    assert "KNOW WHAT" in landing
    assert "117 SPECIALISTS" not in landing
    assert "Finance-first intelligence" not in landing
    assert "ATLAS<span" not in landing
    assert '<div class="brand-name">ATLAS_' not in auth
    assert "#18C6C8" in auth
    assert "#18C6C8" in landing
    assert "FINANCIAL INTELLIGENCE AT SCALE" not in legacy_landing
    assert "#0044FF" not in legacy_landing
    assert 'window.location.replace("/")' in legacy_landing


def test_chat_ui_does_not_use_atlas_sender_label():
    app = (ROOT / "ra_omega_app.html").read_text(encoding="utf-8")
    assert "sender: 'ATLAS'" not in app
    assert 'sender: "ATLAS"' not in app
    assert "const ASSISTANT_SENDER = 'OMEGA'" in app
    assert "log.sender === 'USR' ? 'You' : 'R.A. Omega'" in app
