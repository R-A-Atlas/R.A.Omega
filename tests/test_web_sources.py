from orchestration.web_sources import parse_duckduckgo_html, sources_prompt_block


def test_parse_duckduckgo_html_extracts_result_links() -> None:
    html = """
    <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fnvda">NVDA earnings</a>
    <a class="result__snippet">NVIDIA reported revenue growth.</a>
    <a rel="nofollow" class="result__a" href="https://example.org/macro">Macro update</a>
    <a class="result__snippet">Rates moved lower.</a>
    """
    sources = parse_duckduckgo_html(html, max_results=3)
    assert sources[0].title == "NVDA earnings"
    assert sources[0].url == "https://example.com/nvda"
    assert "NVIDIA" in sources[0].snippet
    assert sources[1].url == "https://example.org/macro"


def test_sources_prompt_block_is_compact_and_citation_safe() -> None:
    block = sources_prompt_block(
        [{"title": "SEC filing", "url": "https://sec.gov/example", "snippet": "10-K filing"}]
    )
    assert "[Web source discovery]" in block
    assert "SEC filing" in block
    assert "do not fabricate citations" in block
