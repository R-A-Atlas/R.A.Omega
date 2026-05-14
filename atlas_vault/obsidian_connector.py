"""
atlas_vault/obsidian_connector.py

Obsidian knowledge-base integration for R.A. Omega.

load_vault(vault_path) -> dict
    Walk vault_path recursively, index all .md files.
    Returns { "notes": [...], "indexed_at": timestamp, "count": n }

search_vault(query, vault_index, top_k) -> list[str]
    TF-IDF search (sklearn) with word-overlap fallback.
    Returns top_k formatted excerpt strings.

inject_vault_context(query, user_id) -> str
    Looks up user's vault at atlas_vault/user_vaults/{user_id}/,
    searches it, and returns "FROM YOUR KNOWLEDGE BASE:\\n..." or "".

save_vault_note(user_id, filename, content) -> bool
    Persists a single .md file to atlas_vault/user_vaults/{user_id}/.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
USER_VAULTS_DIR = BASE_DIR / "atlas_vault" / "user_vaults"
VAULT_CONFIG_FILE = BASE_DIR / "atlas_vault" / "user_vault_config.json"

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_MDLINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_TAG_RE = re.compile(r"(?m)^#\w+")


# ── Vault path resolution ─────────────────────────────────────────────────────

def _get_vault_path(user_id: str) -> Path:
    if VAULT_CONFIG_FILE.exists():
        try:
            config = json.loads(VAULT_CONFIG_FILE.read_text(encoding="utf-8"))
            custom = config.get(user_id)
            if custom:
                return Path(custom)
        except Exception:
            pass
    return USER_VAULTS_DIR / user_id


# ── Core loader ───────────────────────────────────────────────────────────────

def load_vault(vault_path: str) -> dict:
    """
    Walk vault_path recursively, parse all .md files.
    Returns { "notes": [...], "indexed_at": ISO str, "count": int }.
    Handles missing path, permission errors, and empty vaults gracefully.
    """
    path = Path(vault_path)
    if not path.exists():
        return {"notes": [], "indexed_at": datetime.utcnow().isoformat(), "count": 0}

    try:
        md_files = list(path.rglob("*.md"))
    except PermissionError as exc:
        log.warning("load_vault permission error at %s: %s", path, exc)
        return {"notes": [], "indexed_at": datetime.utcnow().isoformat(), "count": 0}

    notes: list[dict[str, Any]] = []
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            tags = _TAG_RE.findall(content)
            wikilinks = _WIKILINK_RE.findall(content)
            md_pairs = _MDLINK_RE.findall(content)
            links = wikilinks + [text for text, _url in md_pairs]
            mtime = datetime.utcfromtimestamp(md_file.stat().st_mtime).isoformat()
            notes.append(
                {
                    "filename": md_file.name,
                    "path": str(md_file.relative_to(path)),
                    "content": content,
                    "tags": tags,
                    "links": links,
                    "modified_date": mtime,
                }
            )
        except Exception as exc:
            log.warning("load_vault skipping %s: %s", md_file, exc)

    return {
        "notes": notes,
        "indexed_at": datetime.utcnow().isoformat(),
        "count": len(notes),
    }


# ── Search ────────────────────────────────────────────────────────────────────

def _word_overlap_score(query: str, text: str) -> float:
    q_words = set(re.findall(r"\w+", query.lower()))
    t_words = re.findall(r"\w+", text.lower())
    if not q_words or not t_words:
        return 0.0
    freq: dict[str, int] = {}
    for w in t_words:
        freq[w] = freq.get(w, 0) + 1
    return sum(freq.get(w, 0) for w in q_words) / (len(t_words) + 1)


def search_vault(query: str, vault_index: dict, top_k: int = 5) -> list[str]:
    """
    TF-IDF search using sklearn when available; word-overlap fallback otherwise.
    Returns top_k strings formatted as "[filename]\\n[excerpt]\\n".
    """
    notes: list[dict] = vault_index.get("notes") or []
    if not notes:
        return []

    contents = [n.get("content", "") for n in notes]
    scores: list[float]

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        corpus = contents + [query]
        vec = TfidfVectorizer(stop_words="english", max_features=5000)
        tfidf = vec.fit_transform(corpus)
        sims = cosine_similarity(tfidf[-1], tfidf[:-1]).flatten()
        scores = sims.tolist()
    except ImportError:
        scores = [_word_overlap_score(query, c) for c in contents]

    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    results: list[str] = []
    for idx, score in ranked[:top_k]:
        if score <= 0:
            continue
        note = notes[idx]
        excerpt = note.get("content", "").strip().replace("\n", " ")[:150]
        results.append(f"[{note['filename']}]\n{excerpt}\n")

    return results


# ── Public API ────────────────────────────────────────────────────────────────

def inject_vault_context(query: str, user_id: str) -> str:
    """
    Return a "FROM YOUR KNOWLEDGE BASE:\\n..." block for the user's vault,
    or empty string if no vault exists or any error occurs.
    """
    try:
        vault_path = _get_vault_path(user_id)
        if not vault_path.exists():
            return ""

        vault_index = load_vault(str(vault_path))
        if not vault_index.get("count"):
            return ""

        results = search_vault(query, vault_index, top_k=5)
        if not results:
            return ""

        header = "FROM YOUR KNOWLEDGE BASE:\n"
        body = "\n".join(results)
        full = header + body

        # Hard cap at 600 tokens (~600 words)
        words = full.split()
        if len(words) > 600:
            full = " ".join(words[:600]) + "…"

        return full
    except Exception as exc:
        log.warning("inject_vault_context error for user %s: %s", user_id, exc)
        return ""


def save_vault_note(user_id: str, filename: str, content: str) -> bool:
    """
    Save content as a .md file under atlas_vault/user_vaults/{user_id}/.
    Creates the directory if needed. Returns True on success, False on failure.
    """
    try:
        vault_dir = USER_VAULTS_DIR / user_id
        vault_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        (vault_dir / safe_name).write_text(content, encoding="utf-8")
        return True
    except Exception as exc:
        log.warning("save_vault_note error for user %s, file %s: %s", user_id, filename, exc)
        return False
