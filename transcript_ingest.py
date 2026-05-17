"""
transcript_ingest.py — Convert Claude Code sessions to RAG-ready markdown.

Reads .jsonl session files from the Claude Code projects directory,
extracts meaningful conversation content (user intent + assistant decisions),
and saves each session as a .md file in atlas_vault/01-Raw/Transcripts/.

Then ingests all transcripts into the finance_knowledge Chroma collection
so ATLAS can draw on institutional memory of how it was built and improved.

Usage:
    python transcript_ingest.py               # convert all new sessions + ingest
    python transcript_ingest.py --convert-only  # just write .md files, skip Chroma
    python transcript_ingest.py --ingest-only   # re-ingest existing .md files
    python transcript_ingest.py --status        # show counts
    python transcript_ingest.py --force         # re-convert already-done sessions
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_DIR        = Path(__file__).resolve().parent
TRANSCRIPT_DIR  = BASE_DIR / "atlas_vault" / "01-Raw" / "Transcripts"
STATE_FILE      = TRANSCRIPT_DIR / ".ingest_state.json"

# Claude Code stores sessions here (Windows path)
SESSION_DIR = Path.home() / ".claude" / "projects" / "C--Users-crist-Projects-R-A-Omega"

# Skip sessions smaller than this — usually test/noise sessions
MIN_SESSION_BYTES = 50_000

# Max words to extract per session (Chroma limits via KB_MAX_CHUNKS_PER_FILE=120 × 300w)
MAX_WORDS_PER_SESSION = 36_000

# Boilerplate user messages to skip
_SKIP_MESSAGES = {
    "claude --continue",
    "continue",
    "ok",
    "yes",
    "no",
    "start",
    "done",
    "next",
}

# ── JSONL extraction ──────────────────────────────────────────────────────────

def _extract_text_content(content) -> str:
    """Pull plain text from a message content field (str or list of blocks)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", "").strip())
                # skip tool_use, tool_result, image blocks
        return "\n".join(p for p in parts if p)
    return ""


def _is_boilerplate(text: str) -> bool:
    t = text.strip().lower()
    return t in _SKIP_MESSAGES or len(t) < 10


def extract_session(jsonl_path: Path) -> dict:
    """
    Parse a Claude Code .jsonl session file.
    Returns: {session_id, date, turns: [{role, text}], word_count}
    """
    session_id = jsonl_path.stem
    turns: list[dict] = []
    first_ts = None

    try:
        with jsonl_path.open(encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type", "")
                ts = entry.get("timestamp")
                if ts and first_ts is None:
                    first_ts = ts

                # User messages
                if entry_type == "user":
                    msg = entry.get("message", {})
                    if msg.get("role") != "user":
                        continue
                    text = _extract_text_content(msg.get("content", ""))
                    # Skip system-injected context blocks (long summaries prepended by the harness)
                    if len(text) > 8_000:
                        text = text[:8_000] + "\n[...truncated...]"
                    if _is_boilerplate(text):
                        continue
                    turns.append({"role": "user", "text": text})

                # Assistant messages — text blocks only, skip tool_use
                elif entry_type == "assistant":
                    msg = entry.get("message", {})
                    if msg.get("role") != "assistant":
                        continue
                    text = _extract_text_content(msg.get("content", ""))
                    if not text or len(text) < 20:
                        continue
                    # Trim excessively long assistant turns
                    if len(text) > 4_000:
                        text = text[:4_000] + "\n[...truncated...]"
                    turns.append({"role": "assistant", "text": text})

    except Exception as exc:
        log.warning("Failed to read %s: %s", jsonl_path.name, exc)
        return {}

    if not turns:
        return {}

    date_str = "unknown"
    if first_ts:
        try:
            date_str = datetime.fromisoformat(first_ts.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            pass

    total_words = sum(len(t["text"].split()) for t in turns)
    return {
        "session_id": session_id,
        "date": date_str,
        "turns": turns,
        "word_count": total_words,
    }


def session_to_markdown(session: dict) -> str:
    """Convert extracted session dict to a structured .md document."""
    lines = [
        f"# ATLAS Build Session — {session['date']}",
        f"",
        f"**Session ID:** `{session['session_id']}`  ",
        f"**Date:** {session['date']}  ",
        f"**Turns:** {len(session['turns'])}  ",
        f"**Word count:** ~{session['word_count']:,}",
        f"",
        "---",
        "",
        "## Conversation",
        "",
    ]

    total_words = 0
    for turn in session["turns"]:
        role = turn["role"]
        text = turn["text"]
        word_count = len(text.split())

        if total_words + word_count > MAX_WORDS_PER_SESSION:
            lines.append(f"\n*[Session truncated at {MAX_WORDS_PER_SESSION:,} words for RAG efficiency]*\n")
            break

        if role == "user":
            lines.append(f"### User\n\n{text}\n")
        else:
            lines.append(f"### Assistant\n\n{text}\n")

        total_words += word_count

    return "\n".join(lines)


# ── State tracking ────────────────────────────────────────────────────────────

def _load_state() -> dict:
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"converted": {}, "ingested": []}


def _save_state(state: dict) -> None:
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── Convert sessions → .md ────────────────────────────────────────────────────

def convert_sessions(force: bool = False) -> list[Path]:
    """Convert all qualifying .jsonl sessions to .md files. Returns list of new files."""
    if not SESSION_DIR.exists():
        log.error("Session directory not found: %s", SESSION_DIR)
        return []

    state = _load_state()
    converted_ids = set(state.get("converted", {}).keys())
    new_files: list[Path] = []

    sessions = sorted(
        SESSION_DIR.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
    )

    for jsonl_path in sessions:
        size = jsonl_path.stat().st_size
        if size < MIN_SESSION_BYTES:
            log.debug("Skip (too small, %d bytes): %s", size, jsonl_path.name)
            continue

        session_id = jsonl_path.stem
        if not force and session_id in converted_ids:
            log.info("Already converted: %s", jsonl_path.name)
            continue

        log.info("Converting %s (%.1f MB)...", jsonl_path.name, size / 1_048_576)
        session = extract_session(jsonl_path)
        if not session or len(session.get("turns", [])) < 3:
            log.warning("  → skipped (too few turns)")
            continue

        md_name = f"session_{session['date']}_{session_id[:8]}.md"
        md_path = TRANSCRIPT_DIR / md_name
        md_content = session_to_markdown(session)
        md_path.write_text(md_content, encoding="utf-8")

        state.setdefault("converted", {})[session_id] = {
            "md_file": md_name,
            "date": session["date"],
            "turns": len(session["turns"]),
            "word_count": session["word_count"],
            "converted_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_state(state)

        log.info("  → saved %s (%d turns, ~%d words)", md_name, len(session["turns"]), session["word_count"])
        new_files.append(md_path)

    return new_files


# ── Ingest .md files into Chroma ──────────────────────────────────────────────

def ingest_transcripts() -> dict:
    """Ingest all .md files in TRANSCRIPT_DIR into the finance_knowledge Chroma collection."""
    try:
        from rag_engine import ingest_finance_knowledge_dir
    except ImportError as exc:
        log.error("rag_engine not importable: %s", exc)
        return {"ok": False, "error": str(exc)}

    md_files = list(TRANSCRIPT_DIR.glob("session_*.md"))
    if not md_files:
        log.warning("No session .md files in %s — run convert first.", TRANSCRIPT_DIR)
        return {"ok": True, "files": 0, "chunks_upserted": 0}

    log.info("Ingesting %d transcript files into Chroma finance_knowledge...", len(md_files))
    result = ingest_finance_knowledge_dir(directory=TRANSCRIPT_DIR)

    state = _load_state()
    state["last_ingest"] = datetime.now(timezone.utc).isoformat()
    state["last_ingest_result"] = result
    _save_state(state)

    log.info("Ingest result: %s", result)
    return result


# ── Status ────────────────────────────────────────────────────────────────────

def show_status() -> None:
    state = _load_state()
    converted = state.get("converted", {})
    md_files = list(TRANSCRIPT_DIR.glob("session_*.md")) if TRANSCRIPT_DIR.exists() else []

    print(f"\nTranscript Ingest Status")
    print(f"========================")
    print(f"Session dir:    {SESSION_DIR}")
    print(f"Transcript dir: {TRANSCRIPT_DIR}")
    print(f"Converted:      {len(converted)} sessions")
    print(f"MD files:       {len(md_files)} files")
    if state.get("last_ingest"):
        r = state.get("last_ingest_result", {})
        print(f"Last ingest:    {state['last_ingest']}")
        print(f"  Files:        {r.get('files', '?')}")
        print(f"  Chunks:       {r.get('chunks_upserted', '?')}")
    else:
        print(f"Last ingest:    never")

    if converted:
        print(f"\nConverted sessions:")
        for sid, info in sorted(converted.items(), key=lambda x: x[1].get("date", "")):
            print(f"  {info['date']}  {info['md_file']}  ({info['turns']} turns, {info['word_count']:,} words)")

    # Check Chroma
    try:
        from rag_engine import _get_kb_collection
        col = _get_kb_collection()
        if col:
            transcript_chunks = len([
                doc_id for doc_id in col.get(where={"doc_kind": "md"}, include=[])["ids"]
            ])
            print(f"\nChroma finance_knowledge: {col.count()} total chunks")
    except Exception as exc:
        print(f"\nChroma status unavailable: {exc}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="ATLAS transcript → RAG pipeline")
    parser.add_argument("--convert-only", action="store_true", help="Only convert to .md, skip Chroma")
    parser.add_argument("--ingest-only",  action="store_true", help="Only ingest existing .md files")
    parser.add_argument("--status",       action="store_true", help="Show status and exit")
    parser.add_argument("--force",        action="store_true", help="Re-convert already-done sessions")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.ingest_only:
        result = ingest_transcripts()
        print(f"\nIngest complete: {result}")
        return

    # Default: convert + ingest
    new_files = convert_sessions(force=args.force)
    log.info("Converted %d new session(s).", len(new_files))

    if not args.convert_only:
        result = ingest_transcripts()
        print(f"\nIngest complete: {result}")


if __name__ == "__main__":
    main()
