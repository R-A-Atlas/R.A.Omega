"""
api_server.py — ATLAS FastAPI Backend
======================================
Wraps all ATLAS engines as HTTP endpoints.
Run with: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

Reverse proxies (nginx, Caddy, Cloudflare, etc.) in front of this API should use
a read timeout of at least 300 seconds for POST /query and POST /omega so long
batched Gemini responses are not cut off client-side.

Endpoints (research + query pipeline + portfolio require Authorization: Bearer <Supabase JWT> unless ATLAS_DISABLE_AUTH=true):
    POST /query          — Natural language query via QueryRouter (Omega for general finance, else 10-loop).
                          Short greetings / meta chat return immediately without the full pipeline.
                          Optional `crypto_snapshot: true` short-circuits to Omega with CRYPTO_MARKET_SCAN (cached JSON).
                          Optional `user_display_name` prepends a short personalization hint to the routed prompt (stored report uses the raw query only).
    POST /omega          — Universal financial query (stocks, car, debt, etc.). Optional body field
                          `crypto_snapshot: true` attaches data_cache/crypto_top50_latest.json via Omega.
    POST /research       — Single ticker deep dive
    GET  /health         — Health check + stats
    GET  /positions      — Portfolio from Supabase + paper_trades.json (local)
    POST /positions      — Add/update position in Supabase
    DELETE /positions/{ticker} — Remove position(s); optional ?strike=&option_type= for one option leg
    GET  /watchlist      — Per-user tickers in Supabase (JWT); test_user_local → empty
    POST /watchlist      — Add ticker for current user
    DELETE /watchlist/{ticker} — Remove ticker for current user
    GET  /alerts         — Active alerts
    GET  /regime         — Current market regime (cached 5min)
    GET  /rag/status     — Chroma RAG stats (SEC + finance_knowledge; JWT)
    GET  /, /auth, /login — Zenith landing (Supabase sign in / sign up)
    GET  /app            — Main R.A. Omega chat UI (stable product route)
    GET  /option1        — Legacy alias for the same chat UI
    GET  /v4             — Optional atlas_dashboard_v4.html (advanced dashboard)
    GET  /atlas_dashboard_v2.html — Legacy v2 UI only
    GET  /history/reports   — Query-report history (for dashboard)
    DELETE /history/{report_id} — Remove one saved query report
    PATCH  /history/{report_id} — Rename and/or move report to folder
    GET  /sessions         — Chat sessions (sidebar threads)
    POST /sessions         — Create session (New chat)
    PATCH /sessions/{id}   — Rename / archive / context
    DELETE /sessions/{id} — Remove session
    GET  /folders          — List project folder names
    POST /folders          — Create a folder label
    POST /voice/query      — Multipart audio → OpenAI Whisper → same envelope as POST /query (OPENAI_API_KEY).
    POST /tts             — Body {text, provider?, voice?} → audio/mpeg (OPENAI_API_KEY or ELEVENLABS_*).
    POST /export/pdf      — Body = POST /query JSON → WeasyPrint file in atlas_vault/03-Outputs/Reports/.
    POST /export/pptx     — Body = analysis JSON → python-pptx deck in atlas_vault/03-Outputs/Decks/.
    POST /export/xlsx     — Body = analysis JSON → openpyxl workbook in atlas_vault/03-Outputs/Models/.
    POST /compare          — Body {tickers: [...]} → single combined analysis (see compare_mode in response).
    POST /report/edit      — {report_id, instruction} → Gemini NL edit of stored result_json (GOOGLE_API_KEY).
    GET  /api/v1/query     — Billable developer API (X-ATLAS-DEV-KEY; logs $0.10 charge stub to atlas_dev_api_billing.log).

Environment (Supabase):
    SUPABASE_URL, SUPABASE_KEY  — server: DB + JWT verification (typically service_role).
    SUPABASE_ANON_KEY           — optional: injected into v4 HTML for browser Sign in only.
    TTS (POST /tts): OPENAI_API_KEY and/or ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID; optional OPENAI_TTS_VOICE.
    Digest email: DIGEST_EMAIL, DIGEST_TZ (default America/New_York), DIGEST_FROM_EMAIL;
                  SENDGRID_API_KEY — or SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD.
"""
from __future__ import annotations

import hashlib
import asyncio
import json
import re
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Annotated, Union

from dotenv import load_dotenv

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api_server")

# ── FastAPI ───────────────────────────────────────────────────────────────────
try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Query, Depends, UploadFile, File, Form, Header, Body
    from fastapi.exceptions import RequestValidationError
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, Response
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from pydantic import BaseModel, Field
except ImportError:
    print("Install FastAPI: pip install fastapi uvicorn --break-system-packages")
    sys.exit(1)

# ── ATLAS module path (api_server.py lives in project root with all modules) ─
BASE_DIR = Path(__file__).resolve().parent
ATLAS_DIR = BASE_DIR
ATLAS_DASHBOARD_V4 = ATLAS_DIR / "atlas_dashboard_v4.html"
ATLAS_DASHBOARD_V2 = ATLAS_DIR / "atlas_dashboard_v2.html"
RA_OMEGA_APP = ATLAS_DIR / "ra_omega_app.html"
ATLAS_ZENITH_LANDING = ATLAS_DIR / "index_1778228972988.html"
sys.path.insert(0, str(BASE_DIR))

import atlas_db  # noqa: E402

try:
    from gemini_limiter import is_rate_limit_error
except ImportError:
    def is_rate_limit_error(_exc: Exception) -> bool:
        return False

try:
    from query_router import GeminiQuotaExceededError
except ImportError:
    class GeminiQuotaExceededError(Exception):
        """Fallback if query_router not importable at startup."""

        user_message = "API Rate Limit Exceeded - Please wait 60 seconds"

RATE_LIMIT_UI_MESSAGE = "API Rate Limit Exceeded - Please wait 60 seconds"

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8765",
    "http://127.0.0.1:8765",
]
_extra_cors = os.environ.get("ATLAS_CORS_ORIGINS", "")
if _extra_cors.strip():
    CORS_ORIGINS.extend(
        x.strip() for x in _extra_cors.split(",") if x.strip()
    )


# ── Lazy imports (don't crash if modules missing) ─────────────────────────────
_query_router = None
_omega_agent  = None
_market_regime_cache = {"data": None, "ts": 0}

def get_router():
    global _query_router
    if _query_router is None:
        try:
            from query_router import QueryRouter
            _query_router = QueryRouter()
            log.info("QueryRouter loaded")
        except Exception as e:
            log.error("QueryRouter failed to load: %s", e)
    return _query_router

def get_omega():
    global _omega_agent
    if _omega_agent is None:
        try:
            from atlas_omega import OmegaAgent
            _omega_agent = OmegaAgent()
            log.info("OmegaAgent loaded")
        except Exception as e:
            log.error("OmegaAgent failed to load: %s", e)
    return _omega_agent

# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("R.A. Omega API Server starting...")
    log.info(
        "Web UI: http://127.0.0.1:8000/ (Zenith) · http://127.0.0.1:8000/app (main chat)",
    )
    # Pre-load engines in background
    import threading
    threading.Thread(target=get_router, daemon=True).start()
    threading.Thread(target=get_omega,  daemon=True).start()
    try:
        from atlas_digest import start_digest_worker

        start_digest_worker()
    except Exception as e:
        log.warning("Digest worker not started: %s", e)
    yield
    log.info("R.A. Omega API Server shutting down.")

app = FastAPI(
    title="R.A. Omega Financial Intelligence API",
    version="4.0",
    description="Universal financial intelligence agent — stocks, options, crypto, personal finance, business intelligence.",
    lifespan=lifespan,
)

# Allow configured dev origins (incl. React on :3000); extend via ATLAS_CORS_ORIGINS= comma list
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _atlas_safe_middleware(request: Request, call_next):
    """Catch unexpected errors so the process never returns an empty crash to the client."""
    try:
        return await call_next(request)
    except Exception as e:
        log.exception("Unhandled API error: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": "internal_error",
                "detail": str(e),
            },
        )


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": "http_error", "detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"ok": False, "error": "validation_error", "detail": exc.errors()},
    )

# ── Request/response models ───────────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    research_mode: str = Field(
        default="normal",
        pattern="^(normal|web|deep)$",
        description="normal = efficient default, web = source-checking mode, deep = explicit full research mode.",
    )
    web_search: bool = False
    # When true, Omega (or /query omega short-circuit) loads data_cache/crypto_top50_latest.json.
    crypto_snapshot: bool = False
    # Optional: "What should the assistant call you?" — woven into the routed prompt only (original query is persisted as-is).
    user_display_name: Optional[str] = Field(default=None, max_length=120)
    answer_style: Optional[str] = Field(default=None, max_length=40)
    risk_profile: Optional[str] = Field(default=None, max_length=40)
    market_focus: Optional[str] = Field(default=None, max_length=80)

class PositionRequest(BaseModel):
    ticker: str
    type: str = "stock"           # "stock" | "call" | "put"
    qty: float = 1
    avg_price: Optional[float] = None
    strike: Optional[float] = None
    expiry: Optional[str] = None   # YYYY-MM-DD
    premium: Optional[float] = None

class WatchlistRequest(BaseModel):
    ticker: str


class HistoryPatchRequest(BaseModel):
    title: Optional[str] = None
    folder_name: Optional[str] = None


class FolderCreateRequest(BaseModel):
    name: str


class SessionCreateRequest(BaseModel):
    title: Optional[str] = None


class SessionPatchRequest(BaseModel):
    title: Optional[str] = None
    archived: Optional[bool] = None
    context_topic: Optional[str] = None


class CompareRequest(BaseModel):
    tickers: list[str] = Field(..., min_length=2, max_length=8)
    session_id: Optional[str] = None
    crypto_snapshot: bool = False
    user_display_name: Optional[str] = Field(default=None, max_length=120)


class ReportEditRequest(BaseModel):
    report_id: str = Field(..., min_length=1)
    instruction: str = Field(..., min_length=1, max_length=8_000)


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=24_000)
    provider: Optional[str] = Field(
        default=None,
        description='Force "openai" or "elevenlabs"; omit for auto (OpenAI if OPENAI_API_KEY else ElevenLabs).',
    )
    voice: Optional[str] = Field(
        default=None,
        max_length=120,
        description="OpenAI voice id (e.g. alloy) or ElevenLabs voice id override.",
    )


_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer_scheme)],
) -> str:
    """Validate Supabase JWT from Authorization: Bearer and return auth.users.id as str."""
    if os.environ.get("ATLAS_DISABLE_AUTH", "").lower() == "true":
        return "test_user_local"
    if creds is None or not creds.credentials or not str(creds.credentials).strip():
        raise HTTPException(status_code=401, detail="Missing Authorization Bearer token")
    if not atlas_db.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured on this server",
        )
    client = atlas_db.get_supabase_client()
    if not client:
        raise HTTPException(status_code=503, detail="Supabase client failed to initialize")
    token = str(creds.credentials).strip()
    try:
        res = client.auth.get_user(token)
    except Exception as e:
        log.warning("Supabase auth.get_user failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e
    if res is None or getattr(res, "user", None) is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    uid = getattr(res.user, "id", None)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return str(uid)


AtlasUserId = Annotated[str, Depends(get_current_user)]


def get_dev_api_user(
    x_atlas_dev_key: Annotated[Optional[str], Header(alias="X-ATLAS-DEV-KEY")] = None,
) -> str:
    """
    Validate developer API key from header. Returns synthetic user id for persistence-skipped dev calls.
    """
    raw = (
        os.environ.get("ATLAS_DEV_API_KEYS", "").strip()
        or os.environ.get("ATLAS_DEV_API_KEY", "").strip()
    )
    if not raw:
        raise HTTPException(
            status_code=503,
            detail="Developer API keys not configured (set ATLAS_DEV_API_KEY or ATLAS_DEV_API_KEYS)",
        )
    allowed = {k.strip() for k in raw.split(",") if k.strip()}
    key = (x_atlas_dev_key or "").strip()
    if not key or key not in allowed:
        raise HTTPException(status_code=401, detail="Invalid or missing X-ATLAS-DEV-KEY")
    return f"dev_api_{hashlib.sha256(key.encode()).hexdigest()[:16]}"


DevApiUserId = Annotated[str, Depends(get_dev_api_user)]


def _normalize_option_expiry(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(s.replace("-", "/")[:10], fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        parsed = datetime.strptime(s, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _require_option_expiry(raw: Optional[str]) -> str:
    exp = _normalize_option_expiry(raw)
    if not exp or not re.match(r"^\d{4}-\d{2}-\d{2}$", exp):
        raise HTTPException(
            status_code=400,
            detail="Options require expiry as YYYY-MM-DD or MM/DD/YYYY (must not be null).",
        )
    return exp


def _ensure_query_ui_envelope(result: Any, query_text: str) -> dict:
    """Guarantee top-level keys expected by atlas_dashboard_v4.html for POST /query."""
    if not isinstance(result, dict):
        return {
            "query": query_text,
            "parsed_query": {},
            "final_report": {},
            "tldr": "",
            "trader_memo": "",
            "hedge_fund_brief": "",
            "execution_rules": [],
            "failure_modes": [],
            "scenarios": [],
            "audit_notes": [],
            "loop_outputs": {},
            "timing": {},
            "clarification_questions": [],
            "_malformed_router_response": True,
        }
    out = dict(result)
    final = dict(out.get("final_report")) if isinstance(out.get("final_report"), dict) else {}

    # Keep the UI contract stable even when a route returns report-shaped fields
    # at the top level instead of nesting them under final_report.
    report_keys = (
        "headline",
        "executive_summary",
        "executive_brief",
        "bull_thesis",
        "bear_thesis",
        "trade_plan",
        "price_levels",
        "catalysts_timeline",
        "key_risks",
        "hidden_angles",
        "overall_rating",
        "primary_recommendation",
        "confidence",
        "urgency",
        "ticker",
    )
    for key in report_keys:
        if key in out and key not in final:
            final[key] = out[key]
    if "executive_summary" in final and not final.get("executive_brief"):
        final["executive_brief"] = final["executive_summary"]
    if "executive_brief" in final and not final.get("executive_summary"):
        final["executive_summary"] = final["executive_brief"]
    for key in ("tldr", "trader_memo", "hedge_fund_brief", "execution_rules", "failure_modes", "scenarios"):
        if key in out and key not in final:
            final[key] = out[key]

    out.setdefault("query", query_text)
    out.setdefault("parsed_query", {})
    out["final_report"] = final
    out.setdefault("loop_outputs", {})
    out.setdefault("timing", {})
    out.setdefault("audit_notes", [])

    for k in ("tldr", "trader_memo", "hedge_fund_brief"):
        if not out.get(k):
            out[k] = final.get(k) or ""

    for k in ("execution_rules", "failure_modes"):
        if not isinstance(out.get(k), list):
            fb = final.get(k)
            out[k] = fb if isinstance(fb, list) else []

    if not isinstance(out.get("scenarios"), list):
        fb = final.get("scenarios")
        out["scenarios"] = fb if isinstance(fb, list) else []

    cqs = out.get("clarification_questions")
    if not isinstance(cqs, list) and isinstance(final, dict):
        cqs = final.get("clarification_questions")
    if isinstance(cqs, list):
        out["clarification_questions"] = [str(x).strip() for x in cqs if str(x).strip()]
    elif cqs is not None and str(cqs).strip():
        out["clarification_questions"] = [str(cqs).strip()]
    else:
        out.setdefault("clarification_questions", [])

    return out


# Short conversational / meta messages skip the 10-loop pipeline (and Omega) so the UI
# responds immediately; research-style phrasing and structured queries still route fully.
_CHAT_FALSE_POSITIVE_TICKERS = frozenset(
    {
        "HI",
        "OK",
        "LOL",
        "OMG",
        "TBH",
        "FYI",
        "DIY",
        "ETA",
        "ASAP",
        "BRB",
        "IMO",
        "IIRC",
        "BTW",
        "WTF",
        "NVM",
        "IDK",
        "SMH",
        "IKR",
        "RN",
        "THO",
        "TBC",
        "FWIW",
    }
)

_RESEARCH_FORCE_FULL_RE = re.compile(
    r"\b("
    r"analy[sz]e|analysis|research|investigate|due\s+diligence|\bdd\b|"
    r"look\s*up|lookup|dig\s+into|deep\s+dive|break\s+down|unpack|"
    r"data\s+on|information\s+on|tell\s+me\s+(?:more\s+)?about|"
    r"(?:give|get|fetch|pull|send)\s+(?:me\s+)?(?:data|info|information|numbers?|the)\b|"
    r"(?:find|show)\s+(?:me\s+)?(?:data|info|information|the)\b|"
    r"earnings|guidance|revenue|ebitda|margin|fundamental|valuation|multiple|"
    r"price\s+target|fair\s+value|intrinsic|"
    r"should\s+i\s+(?:buy|sell|hold)|worth\s+buying|is\s+it\s+a\s+buy|"
    r"\bstock\b|\bticker\b|shares?\b|equity|equities|"
    r"\boption(?:s)?\b|\bcalls?\b|\bputs?\b|strike|expir(?:e|y|ies)|dte\b|iv\s|theta|gamma|"
    r"crypto|bitcoin|ethereum|\bbtc\b|\beth\b|defi|nft\b|"
    r"\bmacro\b|inflation|\bfed\b|fomc|recession|rates?\b|yield\s+curve|"
    r"compare|vs\.?\s+\w+|screen|scanner\b|\bscan\b|"
    r"10-?k|10-?q|8-?k|\bsec\b|filing|s-?1\b|"
    r"portfolio|my\s+position|my\s+trade|"
    r"catalyst|thesis|short\s+interest|float|"
    r"chart|technicals?|rsi\b|macd\b|vwap\b|sma\b|ema\b|"
    r"market\s+(?:today|outlook|forecast)|\bspy\b|\bqqq\b|\biwm\b"
    r")\b",
    re.I,
)


def _conversational_reply_text(raw: str, user_display_name: Optional[str]) -> Optional[str]:
    s = (raw or "").strip()
    if not s:
        return None
    sl = s.lower()
    if len(sl) > 160:
        return None
    if _RESEARCH_FORCE_FULL_RE.search(sl):
        return None
    if re.search(r"\$\s*\d", s) or re.search(r"\d\s*%|\d+\.\d+%", s):
        return None

    nick = (user_display_name or "").strip()
    nick = nick[:72] if nick else ""
    addr = f", {nick}" if nick else ""

    if re.match(
        r"^(?:hi|hey|hello|yo|sup|howdy|greetings)\b",
        sl,
    ):
        return (
            f"Hey{addr}! I'm R.A. Omega - ready. "
            "When you want real work done, ask me to research a name, pull data, compare tickers, "
            "model risk, or dig into a finance topic and I'll run the full analysis pipeline."
        )
    if re.match(r"^(?:thanks?|thank\s+you|thx|ty|much\s+appreciated)\b", sl):
        return f"Anytime{addr}."
    if re.search(
        r"\bwho\s+are\s+you\b|\bwhat\s+are\s+you\b|\bwhat\s+do\s+you\s+do\b",
        sl,
    ):
        return (
            "I'm R.A. Omega - a finance-first AI operating system. "
            "Casual back-and-forth stays quick; when you ask me to analyze markets, debt, credit, business, real estate, tax strategy, or a portfolio, "
            "I'll spin up the deep pipeline."
        )
    if re.match(
        r"^(?:how\s+(?:are|r)\s+(?:you|u)\??|how'?s\s+it\s+going|how\s+are\s+things)\b",
        sl,
    ):
        well_addr = f", {nick}" if nick else ""
        return (
            f"I'm doing well{well_addr} - ready when you are. "
            "Ask the financial question directly and I'll decide whether it needs quick chat or the deeper Omega pipeline."
        )
    if re.match(
        r"^(?:ok+|okay|k\.|cool|nice|great|perfect|got\s+it|sounds\s+good|makes\s+sense)\.?!?\s*$",
        sl,
    ):
        return "Sounds good."
    if re.match(r"^(?:bye|goodbye|see\s+you|ttyl|cya|later)\b", sl):
        return "Catch you later — ask anytime you want research."
    if re.match(
        r"^(?:sure|yep|yup|yeah|yes|nope|nah|maybe)\.?!?\s*$",
        sl,
    ) and len(sl) <= 24:
        return "Got it."
    if re.match(r"^(?:help|commands|\?)\s*$", sl):
        return (
            "Ask naturally — e.g. “Research AAPL”, “What moved in crypto this week?”, "
            "or “Compare X vs Y.” I'll use the full pipeline for those. "
            "Short hellos and thanks stay in quick chat mode."
        )

    return None


def _maybe_fast_chat_shaped(
    router: Any,
    q_store: str,
    req: "QueryRequest",
    start: float,
) -> Optional[dict]:
    mode = getattr(req, "research_mode", "normal") or "normal"
    if getattr(req, "crypto_snapshot", False):
        return None
    if mode == "deep":
        return None
    reply = _conversational_reply_text(q_store, getattr(req, "user_display_name", None))
    if not reply:
        return None
    pq = {
        "raw_query": q_store,
        "tickers": [],
        "domain_tag": "CONVERSATION",
        "query_type": "CONVERSATION",
        "intent_route": "CONVERSATION",
        "_chat_mode": True,
    }

    shaped = {
        "query": q_store,
        "parsed_query": pq,
        "final_report": {
            "executive_summary": reply,
            "domain_tag": "CONVERSATION",
        },
        "tldr": reply,
        "trader_memo": reply,
        "hedge_fund_brief": reply,
        "execution_rules": [],
        "failure_modes": [],
        "scenarios": [],
        "audit_notes": ["Fast chat — skipped QueryRouter / Omega pipelines."],
        "loop_outputs": {"chat": {"status": "ok", "mode": "conversation", "text": reply}},
        "timing": {
            "total_s": round(time.time() - start, 3),
            "loops": 0,
            "_chat_mode": True,
        },
        "clarification_questions": [],
        "_request_controls": {
            "research_mode": mode,
            "web_search": bool(getattr(req, "web_search", False) or mode == "web"),
            "answer_style": getattr(req, "answer_style", None),
            "risk_profile": getattr(req, "risk_profile", None),
            "market_focus": getattr(req, "market_focus", None),
        },
    }
    log.info("[/query] fast chat reply (%d chars)", len(q_store))
    return _ensure_query_ui_envelope(shaped, q_store)


def _finalize_query_response(
    shaped: dict,
    req: "QueryRequest",
    user_id: str,
    background_tasks: BackgroundTasks,
    q_store: str,
    start: float,
) -> dict:
    shaped["_session_id"] = req.session_id
    shaped["_api_time_s"] = round(time.time() - start, 2)
    report_id = str(uuid.uuid4())
    shaped["_report_id"] = report_id
    try:
        to_store = json.loads(json.dumps(shaped, default=str))
    except Exception:
        to_store = shaped
    background_tasks.add_task(
        _persist_query_report_bg,
        user_id,
        report_id,
        q_store,
        to_store,
    )
    return shaped


def _log_dev_api_billing(dev_user_id: str, endpoint: str, query_len: int = 0) -> None:
    """Append a stub billing line ($0.10/call) for developer API usage."""
    try:
        line = (
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "user_fingerprint": dev_user_id,
                    "endpoint": endpoint,
                    "query_len": query_len,
                    "charge_usd": 0.10,
                },
                default=str,
            )
            + "\n"
        )
        p = BASE_DIR / "atlas_dev_api_billing.log"
        with p.open("a", encoding="utf-8") as f:
            f.write(line)
    except Exception as e:
        log.warning("[dev_api] billing log failed: %s", e)


def _transcribe_whisper_openai(content: bytes, filename: str) -> str:
    import requests

    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY not configured for voice transcription",
        )
    url = "https://api.openai.com/v1/audio/transcriptions"
    model = (os.environ.get("OPENAI_WHISPER_MODEL") or "whisper-1").strip()
    fn = filename or "audio.webm"
    files = {"file": (fn, content)}
    data = {"model": model}
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            files=files,
            data=data,
            timeout=120,
        )
        r.raise_for_status()
        j = r.json()
    except HTTPException:
        raise
    except Exception as e:
        log.error("[/voice/query] OpenAI transcription failed: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Transcription service error: {e}",
        ) from e
    text = (j.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Transcription returned empty text")
    return text


def _tts_openai_bytes(text: str, voice: Optional[str]) -> bytes:
    import requests

    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY not configured for TTS",
        )
    vid = (voice or os.environ.get("OPENAI_TTS_VOICE") or "alloy").strip()
    model = (os.environ.get("OPENAI_TTS_MODEL") or "tts-1").strip()
    url = "https://api.openai.com/v1/audio/speech"
    payload = {"model": model, "input": text[:24_000], "voice": vid}
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
        r.raise_for_status()
    except HTTPException:
        raise
    except Exception as e:
        log.error("[/tts] OpenAI TTS failed: %s", e)
        raise HTTPException(status_code=502, detail=f"TTS service error: {e}") from e
    return r.content


def _tts_elevenlabs_bytes(text: str, voice: Optional[str]) -> bytes:
    import requests

    key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="ELEVENLABS_API_KEY not configured for TTS",
        )
    vid = (voice or os.environ.get("ELEVENLABS_VOICE_ID") or "").strip()
    if not vid:
        raise HTTPException(
            status_code=503,
            detail="Set ELEVENLABS_VOICE_ID or pass voice in request body",
        )
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
    payload = {"text": text[:24_000]}
    try:
        r = requests.post(
            url,
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
            json=payload,
            timeout=180,
        )
        r.raise_for_status()
    except HTTPException:
        raise
    except Exception as e:
        log.error("[/tts] ElevenLabs TTS failed: %s", e)
        raise HTTPException(status_code=502, detail=f"TTS service error: {e}") from e
    return r.content


def _build_compare_query(tickers: list[str]) -> str:
    uniq: list[str] = []
    seen: set[str] = set()
    for x in tickers:
        t = str(x).strip().upper()
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    joined = ", ".join(uniq)
    return (
        f"Compare {joined} side by side: current setup and momentum, relative valuation, "
        f"key catalysts and risks, and which name is more attractive for a swing trade if applicable. "
        f"Use clear side-by-side sections per ticker plus a concise verdict."
    )


def _gemini_nl_edit_report_json(result_json: dict, instruction: str) -> dict:
    key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_API_KEY not configured for report editing",
        )
    try:
        import google.genai as genai
        import google.genai.types as gtypes
        from gemini_limiter import GEMINI_HTTP_TIMEOUT_MS, wait_for_slot
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"Gemini client not available: {e}") from e

    payload = json.dumps(result_json, default=str)
    if len(payload) > 100_000:
        payload = payload[:100_000] + "\n...[truncated]"

    prompt = f"""You edit ATLAS dashboard query report JSON. Apply the user's instruction.
Return ONE JSON object: the full updated report with the SAME top-level keys and structure as the input.
Preserve: parsed_query, final_report, tldr, trader_memo, hedge_fund_brief, execution_rules,
failure_modes, scenarios, clarification_questions, timing, loop_outputs, audit_notes when present.
Only change content needed for the instruction. No markdown fences.

USER INSTRUCTION:
{instruction.strip()}

CURRENT REPORT JSON:
{payload}"""

    client = genai.Client(
        api_key=key,
        http_options=gtypes.HttpOptions(timeout=GEMINI_HTTP_TIMEOUT_MS),
    )
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    wait_for_slot("report_edit")
    try:
        resp = client.models.generate_content(
            model=model,
            contents=prompt,
            config=gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                max_output_tokens=8192,
            ),
        )
        raw = (resp.text or "").strip()
    except Exception as e:
        log.exception("[report/edit] Gemini call failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9]*\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw).strip()
    try:
        out = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Model returned invalid JSON: {e}",
        ) from e
    if not isinstance(out, dict):
        raise HTTPException(status_code=502, detail="Model did not return a JSON object")
    return out


def dispatch_query_request(
    req: QueryRequest,
    user_id: str,
    background_tasks: BackgroundTasks,
) -> Union[dict, JSONResponse]:
    """Shared path for POST /query, /voice/query, /compare, and GET /api/v1/query."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")

    q_store = req.query.strip()
    route_input = q_store
    mode = getattr(req, "research_mode", "normal") or "normal"
    if req.user_display_name and str(req.user_display_name).strip():
        nick = str(req.user_display_name).strip()[:120]
        route_input = (
            f"[User personalization: address the user as “{nick}” when natural in prose.]\n\n{q_store}"
        )

    request_hints: list[str] = []
    if mode == "deep":
        request_hints.append(
            "Research mode: DEEP. Use the full research pipeline, broaden source/data checks, and synthesize a cited decision-grade report."
        )
    elif mode == "web" or getattr(req, "web_search", False):
        request_hints.append(
            "Research mode: WEB. Verify current facts with source/data checks before answering, but keep the response efficient."
        )
    else:
        request_hints.append(
            "Research mode: NORMAL. Stay fast and conversational unless the request clearly needs the full Omega analysis pipeline."
        )
    if req.answer_style:
        request_hints.append(f"Answer style: {str(req.answer_style).strip()[:40]}.")
    if req.risk_profile:
        request_hints.append(f"User risk profile: {str(req.risk_profile).strip()[:40]}.")
    if req.market_focus:
        request_hints.append(f"Market focus: {str(req.market_focus).strip()[:80]}.")
    if request_hints:
        route_input = "[Request controls]\n- " + "\n- ".join(request_hints) + f"\n\n{route_input}"

    router = get_router()
    if not router:
        raise HTTPException(status_code=503, detail="QueryRouter not loaded — check server logs")

    start = time.time()
    log.info("[/query] %s", q_store[:100])

    try:
        fast = _maybe_fast_chat_shaped(router, q_store, req, start)
        if fast is not None:
            return _finalize_query_response(
                fast, req, user_id, background_tasks, q_store, start
            )

        raw = router.route(
            route_input,
            user_id=user_id,
            session_id=req.session_id,
            crypto_snapshot=req.crypto_snapshot,
        )
        shaped = _ensure_query_ui_envelope(raw, q_store)
        shaped["_request_controls"] = {
            "research_mode": mode,
            "web_search": bool(getattr(req, "web_search", False) or mode in ("web", "deep")),
            "answer_style": req.answer_style,
            "risk_profile": req.risk_profile,
            "market_focus": req.market_focus,
        }
        return _finalize_query_response(
            shaped, req, user_id, background_tasks, q_store, start
        )
    except GeminiQuotaExceededError as e:
        msg = getattr(e, "user_message", None) or str(e) or RATE_LIMIT_UI_MESSAGE
        log.warning("[/query] Gemini rate limit: %s", msg)
        body = _ensure_query_ui_envelope(
            {
                "parsed_query": {},
                "final_report": {
                    "error": "rate_limit",
                    "executive_summary": msg,
                },
                "tldr": msg,
                "trader_memo": msg,
                "hedge_fund_brief": msg,
            },
            q_store,
        )
        body["ok"] = False
        body["error"] = "rate_limit"
        body["message"] = msg
        body["_api_time_s"] = round(time.time() - start, 2)
        return JSONResponse(status_code=429, content=body)
    except HTTPException:
        raise
    except Exception as e:
        log.error("[/query] Error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Legacy: positions_cache.json (deprecated scripts only; /positions uses Supabase) ─
def _positions_path() -> Path:
    p = ATLAS_DIR / "positions_cache.json"
    if not p.exists():
        p.write_text(json.dumps({"stocks": [], "options": []}, indent=2))
    return p

def _load_positions() -> dict:
    try:
        return json.loads(_positions_path().read_text())
    except Exception:
        return {"stocks": [], "options": []}

def _save_positions(data: dict):
    _positions_path().write_text(json.dumps(data, indent=2))


def _paper_trades_path() -> Path:
    return ATLAS_DIR / "paper_trades.json"


def _load_paper_trades_list() -> list:
    p = _paper_trades_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else []
    except Exception:
        return []


def _domain_tag_from_omega_result(result: dict) -> Optional[str]:
    dom = result.get("domain") or result.get("Domain")
    if dom:
        return str(dom).strip().upper().replace(" ", "_").replace("-", "_")
    dl = result.get("domain_label")
    if dl:
        return str(dl).strip().upper().replace(" ", "_").replace("-", "_")
    return None


def _build_ui_result_from_query_shaped(shaped: dict) -> dict[str, Any]:
    """Shape stored JSON same as atlas_dashboard_v4 runQuery (/query path)."""
    fr = shaped.get("final_report") if isinstance(shaped.get("final_report"), dict) else {}
    out = dict(fr)
    cq = shaped.get("clarification_questions")
    if isinstance(cq, list):
        out["clarification_questions"] = [str(x).strip() for x in cq if str(x).strip()]
    if isinstance(shaped.get("parsed_query"), dict):
        out["_parsed_query"] = shaped["parsed_query"]
    if isinstance(shaped.get("timing"), dict):
        out["_timing"] = shaped["timing"]
    for key in (
        "tldr",
        "trader_memo",
        "hedge_fund_brief",
        "execution_rules",
        "failure_modes",
        "scenarios",
        "audit_notes",
        "loop_outputs",
    ):
        if key in shaped and shaped[key] is not None:
            out[key] = shaped[key]
    dt = None
    if isinstance(fr, dict) and fr.get("domain_tag"):
        dt = fr.get("domain_tag")
    pq = shaped.get("parsed_query") if isinstance(shaped.get("parsed_query"), dict) else {}
    if not dt and isinstance(pq, dict):
        dt = pq.get("domain_tag") or pq.get("query_type")
    if dt:
        out["domain_tag"] = dt
    return out


def _build_ui_result_from_omega(result: dict) -> dict[str, Any]:
    r = dict(result) if isinstance(result, dict) else {}
    clar = r.get("clarification_questions")
    if not isinstance(clar, list) and isinstance(r.get("_clarifying_questions"), list):
        clar = r["_clarifying_questions"]
    out = {k: v for k, v in r.items() if not k.startswith("_") or k in ("_meta",)}
    if isinstance(clar, list):
        out["clarification_questions"] = [str(x).strip() for x in clar if str(x).strip()]
    dt = _domain_tag_from_omega_result(r)
    if dt:
        out["domain_tag"] = dt
    out["_parsed_query"] = {"query_type": dt or "GENERAL_FINANCE", "domain_tag": dt or "GENERAL_FINANCE"}
    return out


def _persist_query_report_bg(user_id: str, report_id: str, query_text: str, shaped: dict) -> None:
    if user_id == "test_user_local" or str(user_id).startswith("dev_api_"):
        return
    try:
        pq = shaped.get("parsed_query") if isinstance(shaped.get("parsed_query"), dict) else {}
        domain_tag = pq.get("domain_tag") or pq.get("query_type")
        fr = shaped.get("final_report") if isinstance(shaped.get("final_report"), dict) else {}
        if not domain_tag and isinstance(fr, dict):
            domain_tag = fr.get("domain_tag")
        result_ui = _build_ui_result_from_query_shaped(shaped)
        session_id = shaped.get("_session_id")
        if session_id:
            session_id = str(session_id).strip() or None
        atlas_db.insert_research_query(
            user_id,
            report_id,
            query_text,
            result_ui,
            domain_tag=domain_tag,
            session_id=session_id,
        )
        topic = pq.get("intent_route") or pq.get("domain_tag") or domain_tag
        if session_id and topic:
            atlas_db.touch_chat_session_topic(user_id, session_id, str(topic))
        log.info("[history] saved query report %s", report_id[:8])
    except Exception as e:
        log.warning("[history] persist failed: %s", e)


def _persist_omega_report_bg(
    user_id: str,
    report_id: str,
    query_text: str,
    result: dict,
    session_id: Optional[str] = None,
) -> None:
    if user_id == "test_user_local":
        return
    try:
        domain_tag = _domain_tag_from_omega_result(result)
        ui = _build_ui_result_from_omega(result)
        if domain_tag:
            ui.setdefault("domain_tag", domain_tag)
        sid = (session_id or "").strip() or None
        atlas_db.insert_research_query(
            user_id, report_id, query_text, ui, domain_tag=domain_tag, session_id=sid
        )
        if sid and domain_tag:
            atlas_db.touch_chat_session_topic(user_id, sid, str(domain_tag))
        log.info("[history] saved omega report %s", report_id[:8])
    except Exception as e:
        log.warning("[history] omega persist failed: %s", e)


def _normalize_omega_response(d: Any) -> dict:
    """Flatten nested Gemini JSON; map camelCase to snake_case for dashboards."""
    if not isinstance(d, dict):
        return {"error": "invalid response", "raw": str(d)}
    out = dict(d)
    for key in ("report", "analysis", "result", "payload", "data"):
        inner = out.get(key)
        if isinstance(inner, dict) and any(
            k in inner
            for k in ("headline", "executive_brief", "executiveBrief", "domain", "Domain")
        ):
            out = {**out, **inner}
            break
    camels = (
        ("executiveBrief", "executive_brief"),
        ("primaryRecommendation", "primary_recommendation"),
        ("domainLabel", "domain_label"),
        ("numbersThatMatter", "numbers_that_matter"),
        ("actionPlan", "action_plan"),
        ("hiddenAngles", "hidden_angles"),
        ("risksAndTripwires", "risks_and_tripwires"),
        ("situationAnalysis", "situation_analysis"),
        ("keyInsight", "key_insight"),
        ("namedResources", "named_resources"),
        ("followUpQuestions", "follow_up_questions"),
    )
    for a, b in camels:
        if a in out and (b not in out or out.get(b) in (None, "")):
            out[b] = out[a]
    if not out.get("headline") and out.get("title"):
        out["headline"] = out["title"]
    if not out.get("executive_brief") and out.get("summary"):
        out["executive_brief"] = out["summary"]
    meta = out.get("_meta") if isinstance(out.get("_meta"), dict) else {}
    dom = out.get("domain") or meta.get("domain")
    if dom and not out.get("domain_label"):
        out["domain_label"] = str(dom).replace("_", " ").title()
    return out

def _watchlist_path() -> Path:
    p = ATLAS_DIR / "watchlist.json"
    if not p.exists():
        p.write_text(json.dumps({"tickers": []}, indent=2))
    return p

# ── Routes ────────────────────────────────────────────────────────────────────


def _dashboard_html_response(path: Path) -> FileResponse | HTMLResponse:
    """Serve v4 HTML with inline public Supabase config for browser auth (anon key only)."""
    if path.name != "atlas_dashboard_v4.html":
        return FileResponse(path, media_type="text/html; charset=utf-8")
    raw = path.read_text(encoding="utf-8")
    pub = {
        "url": os.environ.get("SUPABASE_URL", "").strip(),
        "anonKey": (
            os.environ.get("SUPABASE_ANON_KEY", "").strip()
            or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()
        ),
    }
    inject = f"<script>window.__ATLAS_SB_CONFIG__={json.dumps(pub)};</script>\n"
    if "</head>" in raw:
        html = raw.replace("</head>", inject + "</head>", 1)
    else:
        html = inject + raw
    return HTMLResponse(html, media_type="text/html; charset=utf-8")


def _zenith_landing_response() -> HTMLResponse:
    """Zenith sign-in landing (3D background + AuthPanel); injects Supabase anon config."""
    if not ATLAS_ZENITH_LANDING.is_file():
        return HTMLResponse("<h1>Landing page not found</h1>", status_code=404)
    html = ATLAS_ZENITH_LANDING.read_text(encoding="utf-8")
    cfg = {
        "url": os.environ.get("SUPABASE_URL", "").strip(),
        "anonKey": (
            os.environ.get("SUPABASE_ANON_KEY", "").strip()
            or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "").strip()
        ),
    }
    injection = f"<script>window.__ATLAS_SB_CONFIG__ = {json.dumps(cfg)};</script>"
    html = html.replace("</head>", injection + "\n</head>", 1)
    return HTMLResponse(html, media_type="text/html; charset=utf-8")


@app.get("/")
def serve_home():
    return _zenith_landing_response()


@app.get("/v4")
@app.get("/atlas_dashboard_v4.html")
def serve_dashboard_v4():
    if not ATLAS_DASHBOARD_V4.is_file():
        raise HTTPException(
            status_code=404,
            detail="Missing atlas_dashboard_v4.html next to api_server.py",
        )
    return _dashboard_html_response(ATLAS_DASHBOARD_V4)


@app.get("/app")
@app.get("/chat")
@app.get("/ra-omega")
@app.get("/option1")
@app.get("/atlas_option1.html")
def serve_atlas_option1_chat():
    """Main R.A. Omega chat UI - same origin as API for POST /query and /omega."""
    if not RA_OMEGA_APP.is_file():
        raise HTTPException(
            status_code=404,
            detail="Missing ra_omega_app.html next to api_server.py",
        )
    return FileResponse(RA_OMEGA_APP, media_type="text/html; charset=utf-8")


@app.get("/atlas_dashboard_v2.html")
def serve_dashboard_v2_only():
    if not ATLAS_DASHBOARD_V2.is_file():
        raise HTTPException(
            status_code=404,
            detail="Missing atlas_dashboard_v2.html next to api_server.py",
        )
    return FileResponse(ATLAS_DASHBOARD_V2, media_type="text/html; charset=utf-8")


@app.get("/auth")
@app.get("/login")
def serve_auth():
    """Same Zenith landing as `/` so Option1 → /auth matches the home experience."""
    return _zenith_landing_response()


@app.get("/rag/status")
def rag_vector_status(_user: AtlasUserId):
    """ChromaDB RAG footprint: SEC filings (atlas_filings) + local finance_knowledge."""
    try:
        import rag_engine
    except ImportError as e:
        raise HTTPException(503, detail=f"rag_engine unavailable: {e}") from e
    try:
        return {"ok": True, **rag_engine.rag_stats()}
    except Exception as e:
        log.warning("/rag/status failed: %s", e)
        raise HTTPException(503, detail=str(e)) from e


@app.get("/health")
def health():
    """Health check — returns server status and loaded modules."""
    try:
        from gemini_limiter import get_stats
        gemini_stats = get_stats()
    except Exception:
        gemini_stats = {}

    payload = {
        "status": "ok",
        "version": "4.0",
        "ts": datetime.now(timezone.utc).isoformat(),
        "engines": {
            "query_router": _query_router is not None,
            "omega_agent":  _omega_agent  is not None,
        },
        "gemini": gemini_stats,
        "atlas_dir": str(ATLAS_DIR),
        "atlas_dir_exists": ATLAS_DIR.exists(),
        "supabase_configured": atlas_db.is_configured(),
    }
    if atlas_db.is_configured():
        payload["supabase_schema"] = atlas_db.supabase_schema_status()
    return payload


@app.post("/query")
async def run_query(req: QueryRequest, background_tasks: BackgroundTasks, user_id: AtlasUserId):
    """
    Natural language query → QueryRouter (Omega for general finance, else 10-loop pipeline).

    Runs dispatch_query_request in the shared thread-pool executor so the FastAPI event loop
    is never blocked while OmegaAgent or the research pipeline is thinking.

    Short conversational lines (greetings, thanks, “who are you”) return immediately without
    running the research pipeline; data requests and analysis phrasing still go through the full route.

    Response envelope includes: query, parsed_query, final_report, tldr,
    trader_memo, hedge_fund_brief, execution_rules, failure_modes, scenarios,
    audit_notes, loop_outputs, timing (for atlas_dashboard_v4.html).

    Example body: {"query": "Should I hold my SOUN $14 call expiring June 18?"}
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: dispatch_query_request(req, user_id, background_tasks)
    )


@app.get("/api/v1/query")
def dev_api_query(
    background_tasks: BackgroundTasks,
    dev_user_id: DevApiUserId,
    q: str = Query(..., min_length=1, description="Natural language query (keep under ~2k chars for URL limits)"),
    session_id: Optional[str] = None,
    crypto_snapshot: bool = False,
    user_display_name: Optional[str] = Query(None, max_length=120),
):
    """
    Developer API: same pipeline as POST /query. Requires X-ATLAS-DEV-KEY.
    Billable stub: each call appends one line to atlas_dev_api_billing.log (charge_usd 0.10).
    """
    _log_dev_api_billing(dev_user_id, "GET /api/v1/query", query_len=len(q))
    req = QueryRequest(
        query=q,
        session_id=(session_id or "").strip() or None,
        crypto_snapshot=crypto_snapshot,
        user_display_name=user_display_name,
    )
    return dispatch_query_request(req, dev_user_id, background_tasks)


@app.post("/compare")
async def run_compare(req: CompareRequest, background_tasks: BackgroundTasks, user_id: AtlasUserId):
    """
    Multi-ticker compare: one combined QueryRouter run (pipeline global lock serializes true parallelism).
    Response matches POST /query plus _compare.tickers and _compare.compare_mode.
    """
    tickers = [str(t).strip().upper() for t in req.tickers if str(t).strip()]
    tickers = list(dict.fromkeys(tickers))
    if len(tickers) < 2:
        raise HTTPException(status_code=400, detail="At least two distinct tickers required")
    if len(tickers) > 8:
        raise HTTPException(status_code=400, detail="Maximum 8 tickers for compare")

    q = _build_compare_query(tickers)
    qr = QueryRequest(
        query=q,
        session_id=req.session_id,
        crypto_snapshot=req.crypto_snapshot,
        user_display_name=req.user_display_name,
    )
    out = dispatch_query_request(qr, user_id, background_tasks)
    if isinstance(out, JSONResponse):
        return out
    if isinstance(out, dict):
        out = dict(out)
        out["_compare"] = {"tickers": tickers, "compare_mode": "single_query"}
    return out


@app.post("/report/edit")
def nl_report_edit(req: ReportEditRequest, user_id: AtlasUserId):
    """Apply a natural-language instruction to a saved report's result_json (Supabase queries row)."""
    if user_id == atlas_db.TEST_USER_LOCAL:
        raise HTTPException(
            status_code=404,
            detail="Saved reports are not available for test_user_local",
        )
    if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured on this server",
        )
    try:
        row = atlas_db.fetch_research_query_row(user_id, req.report_id.strip())
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    rj = row.get("result_json")
    if not isinstance(rj, dict):
        raise HTTPException(status_code=500, detail="Invalid stored report shape")
    try:
        updated = _gemini_nl_edit_report_json(rj, req.instruction)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("[/report/edit] failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    try:
        ok = atlas_db.update_research_query_result_json(user_id, req.report_id.strip(), updated)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to update report")
    return {"status": "ok", "report_id": req.report_id.strip(), "result": updated}


@app.post("/voice/query")
async def voice_query(
    background_tasks: BackgroundTasks,
    user_id: AtlasUserId,
    audio: UploadFile = File(..., description="Audio file for Whisper (webm, wav, mp3, m4a, etc.)"),
    session_id: Optional[str] = Form(None),
    research_mode: str = Form("normal"),
    web_search: str = Form("false"),
    crypto_snapshot: str = Form("false"),
    user_display_name: Optional[str] = Form(None),
    answer_style: Optional[str] = Form(None),
    risk_profile: Optional[str] = Form(None),
    market_focus: Optional[str] = Form(None),
):
    """Transcribe audio with OpenAI Whisper, then run the same path as POST /query."""
    body = await audio.read()
    if not body:
        raise HTTPException(status_code=400, detail="Empty audio file")
    fn = audio.filename or "audio.webm"
    text = _transcribe_whisper_openai(body, fn)
    cs = str(crypto_snapshot).strip().lower() in ("1", "true", "yes", "on")
    req = QueryRequest(
        query=text,
        session_id=(session_id or "").strip() or None,
        research_mode=(research_mode or "normal").strip() or "normal",
        web_search=str(web_search).strip().lower() in ("1", "true", "yes", "on"),
        crypto_snapshot=cs,
        user_display_name=(user_display_name or "").strip() or None,
        answer_style=(answer_style or "").strip() or None,
        risk_profile=(risk_profile or "").strip() or None,
        market_focus=(market_focus or "").strip() or None,
    )
    out = dispatch_query_request(req, user_id, background_tasks)
    if isinstance(out, dict):
        merged = dict(out)
        merged["_voice_transcript"] = text
        return merged
    return out


@app.post("/tts")
def tts_speak(req: TtsRequest, user_id: AtlasUserId):
    """
    Text-to-speech for TLDR / memo playback. Returns audio/mpeg bytes.

    Env: OPENAI_API_KEY (OpenAI TTS) and/or ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID.
    Optional body: provider=openai|elevenlabs, voice=...
    """
    _ = user_id  # same auth as /query
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text cannot be empty")
    prov = (req.provider or "").strip().lower()
    if prov not in ("", "openai", "elevenlabs", "auto"):
        raise HTTPException(status_code=400, detail='provider must be "openai", "elevenlabs", or omitted')

    oai = bool((os.environ.get("OPENAI_API_KEY") or "").strip())
    el = bool((os.environ.get("ELEVENLABS_API_KEY") or "").strip())

    if prov == "openai":
        raw = _tts_openai_bytes(text, req.voice)
    elif prov == "elevenlabs":
        raw = _tts_elevenlabs_bytes(text, req.voice)
    else:
        if oai:
            raw = _tts_openai_bytes(text, req.voice)
        elif el:
            raw = _tts_elevenlabs_bytes(text, req.voice)
        else:
            raise HTTPException(
                status_code=503,
                detail="No TTS provider configured (OPENAI_API_KEY or ELEVENLABS_API_KEY)",
            )

    return Response(content=raw, media_type="audio/mpeg")


@app.post("/export/pdf")
def export_pdf_payload(user_id: AtlasUserId, body: dict[str, Any] = Body(...)):
    """Persist POST /query-shaped JSON to atlas_vault/03-Outputs/Reports and return PDF."""
    _ = user_id
    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        from atlas_agents.documents.pdf.pdf_agent import generate_pdf

        path = generate_pdf(body)
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"weasyprint not installed or GTK missing: {e}",
        ) from e
    except Exception as e:
        log.exception("[/export/pdf]")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/pdf",
    )


@app.post("/export/html")
def export_html_payload(user_id: AtlasUserId, body: dict[str, Any] = Body(...)):
    """Persist POST /query-shaped JSON to atlas_vault/03-Outputs/Reports and return HTML."""
    _ = user_id
    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        from atlas_agents.documents.comparison.html_print_agent import generate_html

        path = generate_html(body)
    except Exception as e:
        log.exception("[/export/html]")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return FileResponse(
        path,
        filename=path.name,
        media_type="text/html; charset=utf-8",
    )


@app.post("/export/pptx")
def export_pptx_payload(user_id: AtlasUserId, body: dict[str, Any] = Body(...)):
    _ = user_id
    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        from atlas_export.build_deck import write_query_envelope_pptx

        path = write_query_envelope_pptx(body)
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"python-pptx missing: {e}") from e
    except Exception as e:
        log.exception("[/export/pptx]")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


@app.post("/export/xlsx")
@app.post("/export/excel")
def export_xlsx_payload(user_id: AtlasUserId, body: dict[str, Any] = Body(...)):
    _ = user_id
    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        from atlas_agents.documents.excel.excel_agent import generate_excel

        path = generate_excel(body)
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"openpyxl missing: {e}") from e
    except Exception as e:
        log.exception("[/export/xlsx]")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/omega")
async def run_omega(req: QueryRequest, background_tasks: BackgroundTasks, user_id: AtlasUserId):
    """
    Universal financial query → cross-domain analysis.
    
    Handles stocks, crypto, home buying, car buying, debt payoff,
    business intelligence, retirement, taxes — anything finance.
    
    Example body:
        {"query": "Compare meme vs utility risk in the current leaderboard", "crypto_snapshot": true}
    """
    if not req.query.strip():
        raise HTTPException(400, "query cannot be empty")

    omega = get_omega()
    if not omega:
        raise HTTPException(503, "OmegaAgent not loaded — check server logs")

    start = time.time()
    log.info("[/omega] %s", req.query[:100])

    try:
        # Ask for clarifying questions first (free, no AI call)
        clarifying = omega.ask_clarifying(req.query)

        # Run the full analysis
        try:
            from query_router import classify_sector_cache_intent, INTENT_CRYPTO_MARKET_SCAN
        except ImportError:
            classify_sector_cache_intent = lambda _q: None  # type: ignore[misc, assignment]
            INTENT_CRYPTO_MARKET_SCAN = "CRYPTO_MARKET_SCAN"
        dc_intent = classify_sector_cache_intent(req.query.strip())
        if getattr(req, "crypto_snapshot", False):
            dc_intent = INTENT_CRYPTO_MARKET_SCAN
            log.info("[/omega] crypto_snapshot=true → CRYPTO_MARKET_SCAN")
        # omega.query() is CPU+network bound — offload to thread pool so the
        # FastAPI event loop stays free to handle other requests concurrently.
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: omega.query(
                req.query, session_id=req.session_id, data_cache_intent=dc_intent
            ),
        )
        result = _normalize_omega_response(result)
        result["_clarifying_questions"] = clarifying
        if clarifying:
            result["clarification_questions"] = clarifying
        result["_api_time_s"] = round(time.time() - start, 2)
        report_id = str(uuid.uuid4())
        result["_report_id"] = report_id
        try:
            to_store = json.loads(json.dumps(result, default=str))
        except Exception:
            to_store = dict(result)
        background_tasks.add_task(
            _persist_omega_report_bg,
            user_id,
            report_id,
            req.query.strip(),
            to_store,
            req.session_id,
        )
        return result
    except Exception as e:
        if is_rate_limit_error(e):
            log.warning("[/omega] Gemini rate limit")
            return JSONResponse(
                status_code=429,
                content={
                    "ok": False,
                    "error": "rate_limit",
                    "message": RATE_LIMIT_UI_MESSAGE,
                    "detail": RATE_LIMIT_UI_MESSAGE,
                },
            )
        log.error("[/omega] Error: %s", e)
        raise HTTPException(500, str(e))


@app.get("/history/reports")
def list_query_history(
    user_id: AtlasUserId,
    session_id: Optional[str] = None,
):
    """All saved dashboard query results for the authenticated user; optional session filter."""
    sid = (session_id or "").strip() or None
    return {"reports": atlas_db.list_research_queries(user_id, session_id=sid)}


@app.post("/sessions")
def create_chat_session_api(req: SessionCreateRequest, user_id: AtlasUserId):
    """Explicit new chat / project thread for the sidebar."""
    if user_id != atlas_db.TEST_USER_LOCAL:
        if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
            raise HTTPException(
                status_code=503,
                detail="Supabase is not configured on this server",
            )
    try:
        s = atlas_db.create_chat_session(user_id, title=req.title)
    except Exception as e:
        raise HTTPException(503, str(e)) from e
    return {"ok": True, "session": s}


@app.get("/sessions")
def list_chat_sessions_api(
    user_id: AtlasUserId,
    include_archived: bool = False,
):
    if user_id != atlas_db.TEST_USER_LOCAL:
        if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
            raise HTTPException(
                status_code=503,
                detail="Supabase is not configured on this server",
            )
    return {"sessions": atlas_db.list_chat_sessions(user_id, include_archived=include_archived)}


@app.patch("/sessions/{session_id}")
def patch_chat_session_api(
    session_id: str,
    req: SessionPatchRequest,
    user_id: AtlasUserId,
):
    if user_id != atlas_db.TEST_USER_LOCAL:
        if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
            raise HTTPException(
                status_code=503,
                detail="Supabase is not configured on this server",
            )
    updated = atlas_db.update_chat_session(
        user_id,
        session_id,
        title=req.title,
        archived=req.archived,
        context_topic=req.context_topic,
    )
    if updated is None:
        raise HTTPException(404, "Session not found")
    return {"ok": True, "session": updated}


@app.delete("/sessions/{session_id}")
def delete_chat_session_api(session_id: str, user_id: AtlasUserId):
    if user_id != atlas_db.TEST_USER_LOCAL:
        if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
            raise HTTPException(
                status_code=503,
                detail="Supabase is not configured on this server",
            )
    if not atlas_db.delete_chat_session(user_id, session_id):
        raise HTTPException(404, "Session not found")
    return {"ok": True}


@app.delete("/history")
def clear_query_history(user_id: AtlasUserId):
    """Remove every saved research row for this user."""
    atlas_db.delete_all_research_queries(user_id)
    return {"ok": True}


@app.delete("/history/{report_id}")
def delete_history_report(report_id: str, user_id: AtlasUserId):
    if not atlas_db.delete_research_query(user_id, report_id):
        raise HTTPException(404, "Report not found")
    return {"ok": True}


@app.patch("/history/{report_id}")
def patch_history_report(report_id: str, req: HistoryPatchRequest, user_id: AtlasUserId):
    updated = atlas_db.update_research_query(
        user_id,
        report_id,
        title=req.title,
        folder_name=req.folder_name,
    )
    if updated is None:
        raise HTTPException(404, "Report not found")
    return {"ok": True, "report": updated}


@app.get("/folders")
def list_folders(user_id: AtlasUserId):
    return {"folders": atlas_db.list_folder_names_for_user(user_id)}


@app.post("/folders")
def create_folder(req: FolderCreateRequest, user_id: AtlasUserId):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name cannot be empty")
    folders = atlas_db.ensure_user_folder(user_id, name)
    return {"ok": True, "folders": folders}


@app.post("/research/{ticker}")
def research_ticker(ticker: str):
    """
    Deep dive on a specific ticker via the existing deep_research pipeline.
    Falls back to omega query if deep_research not available.
    """
    ticker = ticker.upper().strip()
    log.info("[/research] %s", ticker)

    try:
        import deep_research as dr
        result = dr.research_ticker(ticker)
        return result
    except Exception:
        # Fallback to omega
        omega = get_omega()
        if omega:
            return omega.query(f"Give me a full deep dive analysis on {ticker}")
        raise HTTPException(503, "Research engine not available")


@app.get("/positions")
def get_positions(user_id: AtlasUserId):
    """Return holdings from Supabase (stocks/options) plus paper_trades.json."""
    if user_id == atlas_db.TEST_USER_LOCAL:
        return {"stocks": [], "options": [], "paper_trades": []}
    if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured on this server",
        )
    stocks, options = atlas_db.fetch_positions_cache_shapes(user_id)
    return {
        "stocks": stocks,
        "options": options,
        "paper_trades": _load_paper_trades_list(),
    }


@app.post("/positions")
def add_position(req: PositionRequest, user_id: AtlasUserId):
    """Add or update a position in Supabase."""
    if user_id == atlas_db.TEST_USER_LOCAL:
        ticker = req.ticker.upper().strip()
        ptype = (req.type or "stock").lower().strip()
        log.debug("[/positions] skip persist (test_user_local)")
        return {"ok": True, "ticker": ticker, "type": ptype if ptype in ("call", "put") else "stock"}

    if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured on this server",
        )

    ticker = req.ticker.upper().strip()
    ptype = (req.type or "stock").lower().strip()
    try:
        if ptype == "stock":
            atlas_db.replace_stock_position(
                user_id,
                ticker,
                float(req.qty),
                req.avg_price,
            )
        else:
            ot = ptype
            if ot not in ("call", "put"):
                raise HTTPException(
                    status_code=400,
                    detail="For options, type must be 'call' or 'put'.",
                )
            exp_norm = _require_option_expiry(req.expiry)
            if req.strike is None:
                raise HTTPException(status_code=400, detail="Options require strike")
            atlas_db.replace_option_position(
                user_id,
                ticker,
                ot,
                float(req.strike),
                exp_norm,
                int(req.qty),
                req.premium,
            )
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        log.exception("[/positions] persist failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    log.info("[/positions] Added %s %s", ptype, ticker)
    return {"ok": True, "ticker": ticker, "type": ptype if ptype in ("call", "put") else "stock"}


@app.delete("/positions/{ticker}")
def remove_position(
    ticker: str,
    user_id: AtlasUserId,
    strike: Optional[float] = None,
    option_type: Optional[str] = Query(None, description="For options: call or put"),
):
    """
    Remove positions for a ticker.
    If strike (and optionally option_type) is set, only matching option legs are removed.
    Otherwise all stocks and options for that ticker are removed.
    """
    ticker = ticker.upper().strip()
    if user_id == atlas_db.TEST_USER_LOCAL:
        log.debug("[/positions] skip delete (test_user_local)")
        return {"ok": True, "ticker": ticker, "strike": strike, "option_type": option_type}

    if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured on this server",
        )

    try:
        if strike is not None:
            ot = (option_type or "").lower().strip()
            if ot not in ("call", "put"):
                raise HTTPException(
                    status_code=400,
                    detail="When strike is set, option_type must be 'call' or 'put'.",
                )
            atlas_db.delete_option_leg(user_id, ticker, float(strike), ot)
        else:
            atlas_db.delete_positions_for_ticker(user_id, ticker)
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        log.exception("[/positions] delete failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    log.info("[/positions] Removed %s strike=%s type=%s", ticker, strike, option_type)
    return {"ok": True, "ticker": ticker, "strike": strike, "option_type": option_type}


@app.get("/watchlist")
def get_watchlist(user_id: AtlasUserId):
    """Return watchlist tickers for the authenticated user (Supabase)."""
    if user_id == atlas_db.TEST_USER_LOCAL:
        return {"tickers": []}
    if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured on this server",
        )
    return {"tickers": atlas_db.list_watchlist_tickers(user_id)}


@app.post("/watchlist")
def add_to_watchlist(req: WatchlistRequest, user_id: AtlasUserId):
    """Add a ticker to the user's watchlist."""
    if user_id == atlas_db.TEST_USER_LOCAL:
        log.debug("[/watchlist] skip add (test_user_local)")
        return {"ok": True, "tickers": []}
    if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured on this server",
        )
    ticker = req.ticker.upper().strip()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker cannot be empty")
    try:
        atlas_db.add_watchlist_ticker(user_id, ticker)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        log.exception("[/watchlist] add failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"ok": True, "tickers": atlas_db.list_watchlist_tickers(user_id)}


@app.delete("/watchlist/{ticker}")
def remove_from_watchlist(ticker: str, user_id: AtlasUserId):
    """Remove a ticker from the user's watchlist."""
    if user_id == atlas_db.TEST_USER_LOCAL:
        log.debug("[/watchlist] skip delete (test_user_local)")
        return {"ok": True, "tickers": []}
    if not atlas_db.is_configured() or not atlas_db.get_supabase_client():
        raise HTTPException(
            status_code=503,
            detail="Supabase is not configured on this server",
        )
    try:
        atlas_db.remove_watchlist_ticker(user_id, ticker)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        log.exception("[/watchlist] delete failed")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"ok": True, "tickers": atlas_db.list_watchlist_tickers(user_id)}


@app.get("/alerts")
def list_alerts_api(user_id: AtlasUserId):
    """
    Active price alerts from alerts.py (server-local atlas_alerts.json).
    Auth-gated; not per-user until alerts are migrated to Supabase.
    """
    try:
        import alerts as _alerts

        alerts = _alerts.get_monitor().list_alerts()
        return {"status": "ok", "alerts": alerts, "count": len(alerts)}
    except Exception as e:
        log.error("[/alerts] error: %s", e)
        raise HTTPException(status_code=503, detail=str(e)) from e


@app.get("/regime")
def get_regime():
    """Current market regime — cached for 5 minutes."""
    now = time.time()
    if _market_regime_cache["data"] and now - _market_regime_cache["ts"] < 300:
        return _market_regime_cache["data"]

    try:
        import market_scanner as ms
        regime = ms.detect_market_regime()
        _market_regime_cache["data"] = regime
        _market_regime_cache["ts"] = now
        return regime
    except Exception as e:
        return {"regime": "UNKNOWN", "error": str(e)}


@app.get("/stats")
def get_stats():
    """Gemini usage stats and server metrics."""
    try:
        from gemini_limiter import get_stats as gs
        return gs()
    except Exception:
        return {"error": "gemini_limiter not loaded"}


# ── Dev entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print()
    print("  Zenith / auth:          http://127.0.0.1:8000/  ·  http://127.0.0.1:8000/auth")
    print("  Main chat:              http://127.0.0.1:8000/app")
    print("  Optional v4 dashboard: http://127.0.0.1:8000/v4  (atlas_dashboard_v4.html)")
    print("  Health:                 http://127.0.0.1:8000/health")
    print()
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
