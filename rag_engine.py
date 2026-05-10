"""
rag_engine.py - ATLAS Financial RAG Pipeline

Downloads SEC 10-K and 8-K filings for any ticker via the free EDGAR API
(no key needed), chunks the text, and stores semantic embeddings in a local
ChromaDB vector database. ATLAS retrieves the most relevant context chunks
during deep research — risk disclosures, debt covenants, guidance buried
on page 87 that no headline ever surfaces.

Storage:  ./atlas_rag/   (persistent Chroma path; collections: atlas_filings, finance_knowledge)
Embedder: all-MiniLM-L6-v2 via chromadb's built-in ONNX runtime (~79MB, downloaded once)

Usage:
    python rag_engine.py AAPL                        # ingest latest 10-K + 3 recent 8-Ks
    python rag_engine.py AAPL "debt and risk factors"  # semantic query
    python rag_engine.py --status                    # show DB stats
    python rag_engine.py --clear AAPL               # delete AAPL from DB
    python rag_engine.py --ingest-kb [--force]      # index rag_ingest/*.md,*.txt,*.pdf
    python rag_engine.py --query-kb "your question"  # query finance_knowledge only
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
RAG_DIR        = Path(__file__).parent / "atlas_rag"
RAG_INGEST_DIR = Path(__file__).parent / "rag_ingest"
INGESTED_FILE  = RAG_DIR / "ingested.json"
COLLECTION     = "atlas_filings"
COLLECTION_KB  = "finance_knowledge"

KB_MAX_CHUNKS_PER_FILE = 120
KB_ALLOWED_SUFFIXES    = {".md", ".txt", ".pdf"}

EDGAR_UA       = "ATLAS trading-platform research@atlas.local"
EDGAR_BASE     = "https://data.sec.gov"
EDGAR_ARCHIVE  = "https://www.sec.gov/Archives/edgar"
TICKERS_URL    = "https://www.sec.gov/files/company_tickers.json"

CHUNK_WORDS    = 300     # target words per chunk
OVERLAP_WORDS  = 50      # words of overlap between chunks
MAX_CHARS      = 200_000 # max chars extracted per filing (cap huge 10-Ks)
MAX_CHUNKS_TICKER = 250  # max chunks stored per ticker total
N_RESULTS      = 5       # default query results

# Forms to ingest and how many of each
FORMS_CONFIG = {
    "10-K": 1,   # latest annual report
    "8-K":  3,   # last 3 material event reports
}

# Default questions asked during synthesis context generation
SYNTHESIS_QUESTIONS = [
    "risk factors debt obligations financial risks covenants",
    "revenue guidance outlook growth forward looking statements",
    "competition market share threats business risks",
    "key financial metrics earnings cash flow balance sheet",
]

_HEADERS = {"User-Agent": EDGAR_UA, "Accept-Encoding": "gzip, deflate"}

# ─────────────────────────────────────────────────────────────────────────────
# ChromaDB client (lazy, module-level singleton)
# ─────────────────────────────────────────────────────────────────────────────
_chroma_client = None
_collection    = None  # SEC filings
_kb_collection = None  # finance_knowledge (local docs)


def reset_client_cache() -> None:
    """Clear module singletons after deleting files under atlas_rag (workspace reset)."""
    global _chroma_client, _collection, _kb_collection
    _chroma_client = None
    _collection    = None
    _kb_collection = None


def _get_chroma_client():
    """Single persistent client for all collections under RAG_DIR."""
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client
    try:
        import chromadb
        RAG_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(RAG_DIR))
        return _chroma_client
    except Exception as e:
        log.error("[rag] ChromaDB client init failed: %s", e)
        return None


def _get_collection():
    """Return (or create) the SEC filings ChromaDB collection."""
    global _collection
    if _collection is not None:
        return _collection
    client = _get_chroma_client()
    if not client:
        return None
    try:
        _collection = client.get_or_create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        log.debug("[rag] filings collection ready — %d chunks", _collection.count())
        return _collection
    except Exception as e:
        log.error("[rag] filings collection failed: %s", e)
        return None


def _get_kb_collection():
    """Return (or create) finance_knowledge collection (rag_ingest corpus)."""
    global _kb_collection
    if _kb_collection is not None:
        return _kb_collection
    client = _get_chroma_client()
    if not client:
        return None
    try:
        _kb_collection = client.get_or_create_collection(
            name=COLLECTION_KB,
            metadata={"hnsw:space": "cosine"},
        )
        log.debug("[rag] finance_knowledge ready — %d chunks", _kb_collection.count())
        return _kb_collection
    except Exception as e:
        log.error("[rag] finance_knowledge collection failed: %s", e)
        return None


def _reset_finance_knowledge_collection() -> None:
    """Drop and lazy-recreate finance_knowledge (used for --ingest-kb --force)."""
    global _kb_collection
    _kb_collection = None
    client = _get_chroma_client()
    if not client:
        return
    try:
        client.delete_collection(COLLECTION_KB)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion tracker (avoids re-downloading on every run)
# ─────────────────────────────────────────────────────────────────────────────
def _load_ingested() -> dict:
    if INGESTED_FILE.exists():
        try:
            return json.loads(INGESTED_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _mark_ingested(ticker: str, info: dict) -> None:
    RAG_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_ingested()
    data[ticker.upper()] = {**info, "ingested_at": datetime.now(timezone.utc).isoformat()}
    INGESTED_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_ingested(ticker: str) -> bool:
    return ticker.upper() in _load_ingested()


# ─────────────────────────────────────────────────────────────────────────────
# SEC EDGAR helpers
# ─────────────────────────────────────────────────────────────────────────────
_cik_cache: dict[str, str] = {}


def ticker_to_cik(ticker: str) -> Optional[str]:
    """Look up the SEC CIK for a ticker symbol. Returns zero-padded 10-digit string."""
    tk = ticker.upper()
    if tk in _cik_cache:
        return _cik_cache[tk]
    try:
        resp = requests.get(TICKERS_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for entry in data.values():
            if entry.get("ticker", "").upper() == tk:
                cik = str(entry["cik_str"]).zfill(10)
                _cik_cache[tk] = cik
                log.debug("[rag] CIK for %s: %s", tk, cik)
                return cik
        log.warning("[rag] No CIK found for ticker %s", tk)
        return None
    except Exception as e:
        log.error("[rag] ticker_to_cik failed for %s: %s", tk, e)
        return None


def _get_filings_meta(cik: str) -> dict:
    """Fetch the EDGAR submissions JSON for a CIK."""
    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def get_filing_urls(ticker: str, forms: Optional[dict] = None) -> list[dict]:
    """
    Return list of {form_type, filing_date, url} for the target forms.
    Uses the primaryDocument field from the EDGAR submissions JSON directly —
    no secondary index lookup needed.
    forms: dict of {form_type: max_count}, defaults to FORMS_CONFIG.
    """
    if forms is None:
        forms = FORMS_CONFIG
    cik = ticker_to_cik(ticker)
    if not cik:
        return []

    try:
        meta      = _get_filings_meta(cik)
        recent    = meta.get("filings", {}).get("recent", {})
        form_list = recent.get("form", [])
        date_list = recent.get("filingDate", [])
        acc_list  = recent.get("accessionNumber", [])
        prim_docs = recent.get("primaryDocument", [])

        results: list[dict] = []
        counts: dict[str, int] = {f: 0 for f in forms}
        cik_int = int(cik)

        for form, date, acc, pdoc in zip(form_list, date_list, acc_list, prim_docs):
            if form not in forms:
                continue
            if counts[form] >= forms[form]:
                continue
            if not pdoc:
                continue

            acc_clean = acc.replace("-", "")
            doc_url   = f"{EDGAR_ARCHIVE}/data/{cik_int}/{acc_clean}/{pdoc}"

            results.append({
                "form_type":   form,
                "filing_date": date,
                "url":         doc_url,
                "accession":   acc,
            })
            counts[form] += 1
            log.info("[rag] Found %s filed %s: %s", form, date, pdoc)

            if all(counts[f] >= forms[f] for f in forms):
                break

        return results

    except Exception as e:
        log.error("[rag] get_filing_urls failed for %s: %s", ticker, e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Text extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_text(url: str) -> str:
    """Download a filing and extract clean plaintext."""
    try:
        time.sleep(0.3)  # be polite to SEC servers
        resp = requests.get(url, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        html = resp.text

        # Strip with BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style tags
        for tag in soup(["script", "style", "meta", "head"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        # Remove very short tokens (table borders, etc.)
        text = re.sub(r"\b[|_\-=]{3,}\b", " ", text)

        # Cap length
        if len(text) > MAX_CHARS:
            log.debug("[rag] Truncating filing from %d to %d chars", len(text), MAX_CHARS)
            text = text[:MAX_CHARS]

        return text
    except Exception as e:
        log.error("[rag] extract_text failed for %s: %s", url, e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Text chunking
# ─────────────────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_words: int = CHUNK_WORDS,
               overlap_words: int = OVERLAP_WORDS) -> list[str]:
    """Split text into overlapping word-count chunks."""
    words = text.split()
    if not words:
        return []

    chunks = []
    start  = 0
    while start < len(words):
        end   = min(start + chunk_words, len(words))
        chunk = " ".join(words[start:end]).strip()
        if len(chunk) > 50:  # skip trivially small chunks
            chunks.append(chunk)
        start += chunk_words - overlap_words
        if start >= len(words):
            break

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Finance knowledge corpus (rag_ingest — .md / .txt / .pdf)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        log.warning("[rag] pypdf not installed — cannot read PDF")
        return ""
    try:
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return re.sub(r"\s+", " ", "\n".join(parts)).strip()
    except Exception as e:
        log.error("[rag] pdf read failed %s: %s", path, e)
        return ""


def _read_local_document(path: Path) -> str:
    suf = path.suffix.lower()
    try:
        if suf in (".md", ".txt"):
            raw = path.read_text(encoding="utf-8", errors="replace")
            return re.sub(r"\s+", " ", raw).strip()
        if suf == ".pdf":
            return _extract_pdf_text(path)
    except Exception as e:
        log.error("[rag] read local doc %s: %s", path, e)
    return ""


def ingest_finance_knowledge_dir(
    directory: Optional[Path] = None,
    *,
    force: bool = False,
) -> dict:
    """
    Walk ``rag_ingest/`` (or ``directory``) for .md, .txt, .pdf; chunk and upsert into
    collection ``finance_knowledge``. Stable IDs: ``kb:<relative_path>:NNNNN``.

    If ``force=True``, drops the entire ``finance_knowledge`` collection first.
    """
    base = Path(directory) if directory else RAG_INGEST_DIR
    if not base.is_dir():
        base.mkdir(parents=True, exist_ok=True)
        return {
            "ok": True,
            "files": 0,
            "chunks_upserted": 0,
            "directory": str(base.resolve()),
            "note": "created empty rag_ingest — add documents and re-run",
        }

    if force:
        _reset_finance_knowledge_collection()

    col = _get_kb_collection()
    if col is None:
        return {"ok": False, "error": "ChromaDB unavailable", "chunks_upserted": 0}

    all_ids: list[str] = []
    all_docs: list[str] = []
    all_metas: list[dict] = []
    files_processed = 0

    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        suf = path.suffix.lower()
        if suf not in KB_ALLOWED_SUFFIXES:
            continue
        try:
            rel = path.relative_to(base).as_posix()
        except ValueError:
            rel = path.name
        text = _read_local_document(path)
        if not text or len(text) < 80:
            log.warning("[rag] kb skip (empty/short): %s", rel)
            continue
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS]
        chunks = chunk_text(text)
        if len(chunks) > KB_MAX_CHUNKS_PER_FILE:
            chunks = chunks[:KB_MAX_CHUNKS_PER_FILE]
        doc_kind = suf.lstrip(".")
        for i, chunk in enumerate(chunks):
            all_ids.append(f"kb:{rel}:{i:05d}")
            all_docs.append(chunk)
            all_metas.append({
                "source_path": rel,
                "doc_kind":    doc_kind,
            })
        files_processed += 1

    batch = 50
    for b in range(0, len(all_ids), batch):
        col.upsert(
            ids=all_ids[b : b + batch],
            documents=all_docs[b : b + batch],
            metadatas=all_metas[b : b + batch],
        )

    log.info(
        "[rag] finance_knowledge ingest: %d files, %d chunks → %s",
        files_processed,
        len(all_ids),
        base.resolve(),
    )
    return {
        "ok": True,
        "files": files_processed,
        "chunks_upserted": len(all_ids),
        "directory": str(base.resolve()),
    }


def query_finance_knowledge(question: str, n: int = N_RESULTS) -> list[dict]:
    """
    Semantic search over ``finance_knowledge`` (no SEC auto-ingest).
    Returns [{"text", "source_path", "doc_kind", "distance"}, ...].
    """
    col = _get_kb_collection()
    if col is None:
        return []
    try:
        cnt = col.count()
    except Exception:
        cnt = 0
    if cnt == 0:
        return []
    q = (question or "").strip() or "financial research"
    try:
        results = col.query(
            query_texts=[q],
            n_results=min(max(1, n), cnt),
        )
        chunks: list[dict] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            chunks.append({
                "text":         doc,
                "source_path":  (meta or {}).get("source_path", "?"),
                "doc_kind":     (meta or {}).get("doc_kind", "?"),
                "distance":     round(float(dist), 4) if dist is not None else None,
            })
        return chunks
    except Exception as e:
        log.error("[rag] query_finance_knowledge failed: %s", e)
        return []


def get_finance_knowledge_context(
    intent_summary: str,
    raw_query: str = "",
    *,
    n_results: int = 6,
    max_total_chars: int = 7500,
) -> str:
    """
    Build a formatted block for ``loop_batch_synthesize`` (INTERNAL KNOWLEDGE).
    Query embedding = intent_summary + excerpt of user query.
    """
    parts: list[str] = []
    ins = (intent_summary or "").strip()
    if ins:
        parts.append(ins)
    rq = (raw_query or "").strip()
    if rq:
        parts.append(rq[:1800])
    qtext = "\n".join(parts).strip() or "financial markets research methodology"
    chunks = query_finance_knowledge(qtext, n=n_results)
    if not chunks:
        return ""

    lines = [
        "Passages below are from locally indexed documents (rag_ingest/). "
        "Each line lists source_path — cite as [KB: <source_path>] when using a fact.",
        "",
    ]
    total = 0
    for i, c in enumerate(chunks, 1):
        sp = c.get("source_path", "?")
        dk = c.get("doc_kind", "?")
        dist = c.get("distance")
        tx = c.get("text") or ""
        if len(tx) > 900:
            tx = tx[:900] + "..."
        block = (
            f"[{i}] source_path={sp} doc_kind={dk} distance={dist}\n{tx}\n"
        )
        if total + len(block) > max_total_chars:
            break
        lines.append(block)
        total += len(block)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Core: ingest a ticker
# ─────────────────────────────────────────────────────────────────────────────

def ingest_ticker(ticker: str, force: bool = False) -> dict:
    """
    Download, chunk, and embed SEC filings for a ticker into ChromaDB.
    Skips if already ingested (unless force=True).

    Returns: {"ticker": str, "chunks_added": int, "filings": int, "skipped": bool}
    """
    tk  = ticker.upper()
    col = _get_collection()
    if col is None:
        return {"ticker": tk, "error": "ChromaDB unavailable"}

    if not force and is_ingested(tk):
        existing = _load_ingested().get(tk, {})
        log.info("[rag] %s already ingested (%d chunks, %s). Use force=True to refresh.",
                 tk, existing.get("chunks", 0), existing.get("ingested_at", "?")[:10])
        return {"ticker": tk, "skipped": True, "chunks": existing.get("chunks", 0)}

    log.info("[rag] Ingesting %s from SEC EDGAR...", tk)
    filing_urls = get_filing_urls(tk)
    if not filing_urls:
        log.warning("[rag] No filings found for %s", tk)
        return {"ticker": tk, "filings": 0, "chunks_added": 0}

    total_chunks = 0

    for filing in filing_urls:
        form_type   = filing["form_type"]
        filing_date = filing["filing_date"]
        url         = filing["url"]

        log.info("[rag]  → Extracting %s %s from %s...", tk, form_type, filing_date)
        text = extract_text(url)
        if not text:
            log.warning("[rag]  → Empty text for %s %s — skipping", tk, form_type)
            continue

        chunks = chunk_text(text)
        log.info("[rag]  → %d chunks from %s %s", len(chunks), form_type, filing_date)

        # Build IDs and metadata
        ids      = []
        docs     = []
        metas    = []
        for i, chunk in enumerate(chunks):
            chunk_id = f"{tk}_{form_type}_{filing_date}_{i:05d}"
            ids.append(chunk_id)
            docs.append(chunk)
            metas.append({
                "ticker":      tk,
                "form_type":   form_type,
                "filing_date": filing_date,
                "chunk_idx":   i,
                "source_url":  url[:200],
            })

        # Upsert in batches of 50 (ChromaDB performance sweet spot)
        batch = 50
        for b in range(0, len(ids), batch):
            col.upsert(
                ids       = ids[b:b+batch],
                documents = docs[b:b+batch],
                metadatas = metas[b:b+batch],
            )

        total_chunks += len(chunks)

        # Stay under per-ticker limit
        if total_chunks >= MAX_CHUNKS_TICKER:
            log.info("[rag] Reached max chunks (%d) for %s — stopping early", MAX_CHUNKS_TICKER, tk)
            break

    _mark_ingested(tk, {"chunks": total_chunks, "filings": len(filing_urls)})
    log.info("[rag] %s ingestion complete: %d chunks across %d filings",
             tk, total_chunks, len(filing_urls))

    return {
        "ticker":      tk,
        "chunks_added": total_chunks,
        "filings":     len(filing_urls),
        "skipped":     False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core: query
# ─────────────────────────────────────────────────────────────────────────────

def query_ticker(ticker: str, question: str,
                 n: int = N_RESULTS) -> list[dict]:
    """
    Semantic search: return top-n most relevant chunks for a question.

    Returns list of {"text": str, "form_type": str, "filing_date": str, "distance": float}
    """
    tk  = ticker.upper()
    col = _get_collection()
    if col is None:
        return []

    # Auto-ingest if not present
    if not is_ingested(tk):
        log.info("[rag] Auto-ingesting %s before query...", tk)
        result = ingest_ticker(tk)
        if result.get("chunks_added", 0) == 0 and not result.get("skipped"):
            return []

    try:
        results = col.query(
            query_texts = [question],
            n_results   = min(n, col.count()),
            where       = {"ticker": tk},
        )
        chunks = []
        docs      = results.get("documents", [[]])[0]
        metas     = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            chunks.append({
                "text":        doc,
                "form_type":   meta.get("form_type", "?"),
                "filing_date": meta.get("filing_date", "?"),
                "distance":    round(dist, 4),
            })
        return chunks
    except Exception as e:
        log.error("[rag] query_ticker failed for %s: %s", tk, e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Synthesis context builder
# ─────────────────────────────────────────────────────────────────────────────

def get_rag_context(ticker: str,
                    questions: Optional[list[str]] = None,
                    auto_ingest: bool = True) -> str:
    """
    Build a formatted RAG context string for injection into the synthesis prompt.
    Runs multiple semantic queries and deduplicates results.

    Returns "" if no filings are available (never blocks synthesis).
    """
    tk = ticker.upper()
    col = _get_collection()
    if col is None:
        return ""

    if not is_ingested(tk):
        if not auto_ingest:
            return ""
        log.info("[rag] Auto-ingesting %s for synthesis context...", tk)
        result = ingest_ticker(tk)
        if result.get("chunks_added", 0) == 0 and not result.get("skipped"):
            return ""

    qs = questions or SYNTHESIS_QUESTIONS
    seen_texts: set[str] = set()
    all_chunks: list[dict] = []

    for q in qs:
        chunks = query_ticker(tk, q, n=3)
        for c in chunks:
            key = c["text"][:80]  # deduplicate by first 80 chars
            if key not in seen_texts:
                seen_texts.add(key)
                all_chunks.append(c)

    if not all_chunks:
        return ""

    ingested_info = _load_ingested().get(tk, {})
    filings_count = ingested_info.get("filings", 0)
    ingested_date = ingested_info.get("ingested_at", "")[:10]

    lines = [
        f"\n=== SEC FILING RAG CONTEXT FOR {tk} ===",
        f"(Source: {filings_count} SEC filings ingested via EDGAR on {ingested_date})",
        f"(All-MiniLM-L6-v2 semantic retrieval — {len(all_chunks)} most relevant passages)",
        "",
    ]

    for i, c in enumerate(all_chunks, 1):
        form   = c["form_type"]
        date   = c["filing_date"]
        text   = c["text"]
        # Truncate very long chunks for the prompt
        if len(text) > 600:
            text = text[:600] + "..."
        lines.append(f"[{i}] {form} filed {date}:")
        lines.append(text)
        lines.append("")

    lines.append(
        "INSTRUCTION: The passages above are from actual SEC filings. "
        "Cite specific risks, debt levels, or guidance you find here. "
        "These facts override any estimates or assumptions.\n"
    )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────────────

def rag_stats() -> dict:
    """Return summary stats for the RAG database (SEC + finance_knowledge)."""
    col = _get_collection()
    total = col.count() if col else 0
    kb_col = _get_kb_collection()
    kb_total = kb_col.count() if kb_col else 0
    ingested = _load_ingested()
    return {
        "total_chunks":               total,
        "finance_knowledge_chunks":   kb_total,
        "tickers_ingested":           len(ingested),
        "tickers":                    list(ingested.keys()),
        "db_path":                    str(RAG_DIR),
        "rag_ingest_dir":             str(RAG_INGEST_DIR),
    }


def clear_ticker(ticker: str) -> int:
    """Delete all chunks for a ticker from ChromaDB."""
    tk  = ticker.upper()
    col = _get_collection()
    if col is None:
        return 0
    try:
        results = col.get(where={"ticker": tk})
        ids = results.get("ids", [])
        if ids:
            col.delete(ids=ids)
        data = _load_ingested()
        data.pop(tk, None)
        INGESTED_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        log.info("[rag] Cleared %d chunks for %s", len(ids), tk)
        return len(ids)
    except Exception as e:
        log.error("[rag] clear_ticker failed for %s: %s", tk, e)
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    args = sys.argv[1:]

    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)

    if args[0] == "--status":
        stats = rag_stats()
        print(f"\nATLAS RAG Database")
        print(f"  Path:                  {stats['db_path']}")
        print(f"  SEC chunks:            {stats['total_chunks']:,}")
        print(f"  Finance KB chunks:   {stats['finance_knowledge_chunks']:,}")
        print(f"  rag_ingest:           {stats.get('rag_ingest_dir', '')}")
        print(f"  Tickers (SEC):        {stats['tickers_ingested']}")
        if stats["tickers"]:
            ingested = _load_ingested()
            for tk in stats["tickers"]:
                info = ingested[tk]
                print(f"    {tk}: {info.get('chunks',0)} chunks | {info.get('filings',0)} filings | {info.get('ingested_at','?')[:10]}")
        sys.exit(0)

    if args[0] == "--ingest-kb":
        force = "--force" in args
        out = ingest_finance_knowledge_dir(force=force)
        print(out)
        sys.exit(0)

    if args[0] == "--query-kb":
        q = " ".join(args[1:]).strip()
        if not q:
            print("Usage: python rag_engine.py --query-kb \"your question\"")
            sys.exit(1)
        chunks = query_finance_knowledge(q, n=5)
        if not chunks:
            print("No results — run: python rag_engine.py --ingest-kb")
        else:
            for i, c in enumerate(chunks, 1):
                print(f"\n[{i}] {c.get('source_path')} ({c.get('doc_kind')}) dist={c.get('distance')}")
                print(f"  {(c.get('text') or '')[:500]}...")
        sys.exit(0)

    if args[0] == "--clear" and len(args) > 1:
        n = clear_ticker(args[1])
        print(f"Cleared {n} chunks for {args[1].upper()}")
        sys.exit(0)

    ticker = args[0].upper()

    if len(args) == 1:
        # Ingest mode
        print(f"\nIngesting SEC filings for {ticker}...")
        result = ingest_ticker(ticker, force=False)
        if result.get("skipped"):
            print(f"  Already ingested ({result.get('chunks',0)} chunks). Use --force to refresh.")
            print(f"  Run:  python rag_engine.py {ticker} --force   to re-ingest")
        else:
            print(f"  Done: {result.get('chunks_added',0)} chunks from {result.get('filings',0)} filings")

    elif len(args) >= 2 and args[1] == "--force":
        print(f"\nForce re-ingesting {ticker}...")
        result = ingest_ticker(ticker, force=True)
        print(f"  Done: {result.get('chunks_added',0)} chunks from {result.get('filings',0)} filings")

    else:
        # Query mode
        question = " ".join(args[1:])
        print(f"\nQuerying {ticker}: '{question}'")
        chunks = query_ticker(ticker, question, n=5)
        if not chunks:
            print(f"  No results. Try ingesting first: python rag_engine.py {ticker}")
        else:
            for i, c in enumerate(chunks, 1):
                print(f"\n[{i}] {c['form_type']} filed {c['filing_date']} (distance={c['distance']}):")
                print(f"  {c['text'][:400]}...")
