"""E4 — UI/UX Porter smoke tests."""
import importlib
import pathlib
import re

APP_HTML = pathlib.Path(__file__).resolve().parents[1] / "ra_omega_app.html"


def test_e4_package_importable():
    """atlas_agents.engineering.ui_porter package loads without error."""
    mod = importlib.import_module("atlas_agents.engineering.ui_porter")
    assert mod is not None


def test_e4_agent_prompt_exists():
    """AGENT_PROMPT.md exists and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "ui_porter"
        / "AGENT_PROMPT.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "AGENT_PROMPT.md is empty"


def test_e4_skill_md_exists():
    """SKILL.md exists in vault and is non-empty."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_vault"
        / "02-Wiki"
        / "Skills"
        / "ui_porter"
        / "SKILL.md"
    )
    assert p.exists(), f"Missing: {p}"
    assert p.stat().st_size > 0, "SKILL.md is empty"


def test_e4_quickstatsstrip_component_present():
    """QuickStatsStrip component exists in the primary app HTML file."""
    assert APP_HTML.exists(), "ra_omega_app.html missing"
    content = APP_HTML.read_text(encoding="utf-8")
    assert "QuickStatsStrip" in content, "QuickStatsStrip component not found in Option 1"


def test_e4_sessions_sidebar_present():
    """Live sessions sidebar (loadSessions / createNewChat) present in Option 1."""
    content = APP_HTML.read_text(encoding="utf-8")
    assert "loadSessions" in content, "loadSessions not found — sidebar not ported"
    assert "createNewChat" in content, "createNewChat not found — New Chat button missing"
    assert "activeSessionId" in content, "activeSessionId state not found"


def test_e4_session_id_sent_on_query():
    """POST /query body includes session_id when active session exists."""
    content = APP_HTML.read_text(encoding="utf-8")
    assert "session_id" in content, "session_id not wired into POST /query body"


def test_e4_chat_modes_and_settings_present():
    """Composer has explicit normal/web/deep modes and settings persist preferences."""
    content = APP_HTML.read_text(encoding="utf-8")
    assert "atlas_default_research_mode" in content, "default research mode preference missing"
    assert "research_mode" in content, "POST /query research_mode not wired"
    assert "web_search" in content, "POST /query web_search not wired"
    assert "Deep research" in content, "Deep research composer action missing"
    assert "Web search" in content, "Web search composer action missing"
    assert "atlas_answer_style" in content, "answer style personalization missing"
    assert "atlas_risk_profile" in content, "risk profile personalization missing"


def test_e4_fast_chat_renders_plain_text():
    """Conversation/zero-loop replies must not render through report cards."""
    content = APP_HTML.read_text(encoding="utf-8")
    assert "function isPlainChatResponse" in content, "plain chat detector missing"
    assert "function logFromQueryResponse" in content, "response log shaper missing"
    assert "log.rawData && !isPlainChatResponse(log.rawData)" in content, (
        "fast chat should bypass StructuredResponse"
    )
    assert "if (isPlainChatResponse(data))" in content, "plain chat formatter should dedupe response text"
    assert "pq.intent_route === 'CONVERSATION'" in content, "conversation route not recognized"
    assert "loops === 0" in content, "zero-loop fast chat not recognized"


def test_e4_backend_files_not_referenced_as_editable():
    """AGENT_PROMPT.md explicitly marks backend Python files as off-limits."""
    p = (
        pathlib.Path(__file__).resolve().parents[1]
        / "atlas_agents"
        / "engineering"
        / "ui_porter"
        / "AGENT_PROMPT.md"
    )
    content = p.read_text(encoding="utf-8")
    assert "Never touch backend" in content or "never touch" in content.lower(), (
        "AGENT_PROMPT.md must explicitly forbid editing backend Python files"
    )
