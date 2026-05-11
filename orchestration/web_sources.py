"""Low-cost web source discovery for Web Search and Deep Research modes.

This module intentionally does discovery, not answer synthesis. It gathers a
small set of source candidates and hands compact citations to the existing
Omega/router pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests


USER_AGENT = "R.A. Omega research bot (contact: research@raomega.local)"


@dataclass(frozen=True)
class WebSource:
    title: str
    url: str
    snippet: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


def discover_sources(query: str, *, max_results: int = 5, timeout: float = 8.0) -> list[dict[str, str]]:
    q = (query or "").strip()
    if not q:
        return []
    url = f"https://duckduckgo.com/html/?q={quote_plus(q)}"
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        resp.raise_for_status()
    except Exception:
        return []
    return [src.to_dict() for src in parse_duckduckgo_html(resp.text, max_results=max_results)]


def parse_duckduckgo_html(html_text: str, *, max_results: int = 5) -> list[WebSource]:
    html = html_text or ""
    blocks = re.findall(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=<a[^>]+class="[^"]*result__a|\Z)',
        html,
        flags=re.I | re.S,
    )
    out: list[WebSource] = []
    seen: set[str] = set()
    for href, title_html, tail in blocks:
        title = _clean_html(title_html)
        url = _normalize_duckduckgo_url(unescape(href))
        snippet_match = re.search(
            r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</',
            tail,
            flags=re.I | re.S,
        )
        snippet = _clean_html(snippet_match.group(1)) if snippet_match else ""
        if not title or not url or url in seen:
            continue
        seen.add(url)
        out.append(WebSource(title=title[:180], url=url[:500], snippet=snippet[:300]))
        if len(out) >= max(1, min(10, int(max_results))):
            break
    return out


def sources_prompt_block(sources: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for idx, src in enumerate(sources[:10], 1):
        title = str(src.get("title") or "Untitled").strip()
        url = str(src.get("url") or "").strip()
        snippet = str(src.get("snippet") or "").strip()
        if not url:
            continue
        line = f"{idx}. {title} — {url}"
        if snippet:
            line += f"\n   Snippet: {snippet}"
        rows.append(line)
    if not rows:
        return ""
    return (
        "[Web source discovery]\n"
        "Use these as source candidates. Verify against internal market data when possible; "
        "do not fabricate citations if a source is only a search snippet.\n"
        + "\n".join(rows)
    )


def _normalize_duckduckgo_url(raw: str) -> str:
    href = unescape(raw or "").strip()
    if not href:
        return ""
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        uddg = qs.get("uddg", [""])[0]
        if uddg:
            return unquote(uddg)
    if href.startswith("//"):
        return "https:" + href
    return href


def _clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
