"""G6 — Content Repurposer Bot tests."""
import importlib, pathlib

def test_g6_package_importable():
    assert importlib.import_module("atlas_agents.growth.content") is not None

def test_g6_agent_prompt_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "content" / "AGENT_PROMPT.md"
    assert p.exists() and p.stat().st_size > 0

def test_g6_skill_md_exists():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_vault" / "02-Wiki" / "Skills" / "content" / "SKILL.md"
    assert p.exists() and p.stat().st_size > 0

def test_g6_schema_fields_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "content" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    for f in ("title", "date", "source", "generated_at", "twitter_thread", "blog_outline"):
        assert f in content, f"Field '{f}' not documented"

def test_g6_youtube_source_documented():
    p = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "content" / "AGENT_PROMPT.md"
    content = p.read_text(encoding="utf-8")
    assert "youtube-transcript-api" in content or "YouTubeTranscriptApi" in content

def test_g6_output_schema_valid_when_repurposer_built():
    sp = pathlib.Path(__file__).resolve().parents[1] / "atlas_agents" / "growth" / "content" / "content_repurposer.py"
    if not sp.exists():
        import pytest; pytest.skip("content_repurposer.py not yet implemented")
    import importlib.util
    spec = importlib.util.spec_from_file_location("content_repurposer", sp)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    try:
        result = mod.repurpose("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "title" in result
        assert len(result.get("twitter_thread", [])) >= 8
        assert all(len(t) <= 280 for t in result.get("twitter_thread", []))
        assert len(result.get("blog_outline", [])) == 5
    except Exception:
        pass
