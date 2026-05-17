"""
api_server.py - R.A. Omega FastAPI Backend
==========================================
Wraps all R.A. Omega engines as HTTP endpoints.
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
    GET  /, /auth         — Zenith landing (Supabase sign in / sign up)
    GET  /app             — Main R.A. Omega chat UI
    GET  /dashboard       — Finance dashboard (atlas_dashboard_v4.html)
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
import hmac
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
    from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, Response, RedirectResponse
    from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ImportError:
    print("Install FastAPI: pip install fastapi uvicorn --break-system-packages")
    sys.exit(1)

# Project module path (api_server.py lives in project root with all modules)
BASE_DIR = Path(__file__).resolve().parent
ATLAS_DIR = BASE_DIR
ATLAS_DASHBOARD_V4 = ATLAS_DIR / "atlas_dashboard_v4.html"  # kept for compatibility
COMMAND_CENTER = ATLAS_DIR / "command_center.html"
AGENTS_NETWORK = ATLAS_DIR / "agents_network.html"
RA_OMEGA_APP = ATLAS_DIR / "ra_omega_app.html"
ATLAS_ZENITH_LANDING = ATLAS_DIR / "index_1778228972988.html"
ATLAS_AUTH = ATLAS_DIR / "auth.html"
sys.path.insert(0, str(BASE_DIR))

import atlas_db  # noqa: E402
import agent_audit  # noqa: E402
import omega_config  # noqa: E402
from pipeline_planner import plan_pipeline, AgentPlan  # noqa: E402
from project_sandbox import create_sandbox, attach_result as attach_sandbox_result, get_sandbox, list_sandboxes, delete_sandbox  # noqa: E402
from multi_agent import orchestrate as multi_agent_orchestrate  # noqa: E402
from prompt_architect import build_blueprint as build_prompt_blueprint  # noqa: E402
from intelligence_hub import get_snapshot as hub_snapshot, get_brief as hub_brief  # noqa: E402
from division_sandbox import (  # noqa: E402
    get_division,
    list_divisions,
    learn as division_learn,
    get_playbook_context,
    get_division_memories,
)
from hermes_operator import (  # noqa: E402
    start_hermes,
    stop_hermes,
    run_cadence as hermes_run_cadence,
    list_cadences as hermes_list_cadences,
    get_today_brief as hermes_today_brief,
    get_latest_brief as hermes_latest_brief,
    get_action_queue as hermes_action_queue,
    dismiss_action as hermes_dismiss_action,
    execute_action as hermes_execute_action,
    CADENCES as HERMES_CADENCES,
)
from orchestration.router_policy import RouteDecision, decide_route  # noqa: E402
from orchestration.agent_graph import activate_specialists  # noqa: E402
from orchestration.agent_packets import build_specialist_packets, specialist_packets_prompt_block  # noqa: E402
from orchestration import research_jobs  # noqa: E402
from orchestration.web_sources import discover_sources, sources_prompt_block  # noqa: E402

try:
    from gemini_limiter import is_rate_limit_error
except ImportError:
    def is_rate_limit_error(_exc: Exception) -> bool:
        return False

try:
    from query_router import GeminiQuotaExceededError, QueryCancelledError
except ImportError:
    class GeminiQuotaExceededError(Exception):
        """Fallback if query_router not importable at startup."""

        user_message = "API Rate Limit Exceeded - Please wait 60 seconds"

    class QueryCancelledError(Exception):
        """Fallback if query_router not importable at startup."""

# Prefer output_modes.py; fall back to query_router then hardcoded stub
try:
    from output_modes import resolve_output_mode
except ImportError:
    try:
        from query_router import resolve_output_mode  # type: ignore[assignment]
    except ImportError:
        def resolve_output_mode(raw_query: str, intent: str) -> str:  # type: ignore[misc]
            return "finance_answer"

try:
    from quality_firewall import validate_response as _qfw_validate
    from response_judge import judge_response as _judge_response
    _QFW_AVAILABLE = True
except ImportError:
    _QFW_AVAILABLE = False

    def _qfw_validate(raw_query, intent, output_mode, answer):  # type: ignore[misc]
        class _R:
            passed = True
            reason = ""
            repair_instruction = ""
        return _R()

    def _judge_response(raw_query, intent, output_mode, answer):  # type: ignore[misc]
        class _R:
            verdict = "PASS"
            reason = ""
            repair_instruction = ""
        return _R()

RATE_LIMIT_UI_MESSAGE = "API Rate Limit Exceeded - Please wait 60 seconds"
research_jobs.configure_store(BASE_DIR / "data_cache" / "research_jobs.json")

PLAN_DAILY_QUERY_CAPS = {
    "free": 5,
    "starter": 25,
    "pro": 250,
    "business": 1000,
    "enterprise": 100000,
    "developer": 100000,
}

CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8765",
    "http://127.0.0.1:8765",
]
CORS_ORIGINS.extend(omega_config.cors_origins())


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
    try:
        from omega_os.skills.cadence_wirer.tools.start_cadence import start_cadence_if_enabled

        start_cadence_if_enabled()
    except Exception as e:
        log.warning("Cadence wirer not started: %s", e)
    try:
        start_hermes(tick_interval=60)
        log.info("Hermes Operator started.")
    except Exception as e:
        log.warning("Hermes Operator not started: %s", e)
    yield
    log.info("R.A. Omega API Server shutting down.")
    try:
        stop_hermes()
    except Exception:
        pass

app = FastAPI(
    title="R.A. Omega Financial Intelligence API",
    version="4.0",
    description="Universal financial intelligence agent — stocks, options, crypto, personal finance, business intelligence.",
    lifespan=lifespan,
)

_static_dir = BASE_DIR / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

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
    source_strictness: Optional[str] = Field(default=None, max_length=40)
    report_depth: Optional[str] = Field(default=None, max_length=40)
    citation_preference: Optional[str] = Field(default=None, max_length=40)
    compliance_level: Optional[str] = Field(default=None, max_length=40)
    research_job_id: Optional[str] = Field(default=None, max_length=80)


class ResearchPlanRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=10_000)
    session_id: Optional[str] = None
    research_mode: str = Field(default="deep", pattern="^(normal|web|deep)$")
    web_search: bool = False


class UserPreferencesRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=120)
    default_research_mode: Optional[str] = Field(default=None, pattern="^(normal|web|deep)$")
    answer_style: Optional[str] = Field(default=None, max_length=40)
    risk_profile: Optional[str] = Field(default=None, max_length=40)
    market_focus: Optional[str] = Field(default=None, max_length=80)
    source_strictness: Optional[str] = Field(default=None, max_length=40)
    report_depth: Optional[str] = Field(default=None, max_length=40)
    card_density: Optional[str] = Field(default=None, max_length=40)
    voice_dictation: Optional[bool] = None
    citation_preference: Optional[str] = Field(default=None, max_length=40)
    compliance_level: Optional[str] = Field(default=None, max_length=40)
    memory_enabled: Optional[bool] = None
    notifications_enabled: Optional[bool] = None
    accent_color: Optional[str] = Field(default=None, max_length=40)
    subscription_tier: Optional[str] = Field(
        default=None,
        pattern="^(free|starter|pro|business|enterprise|developer)$",
    )
    subscription_status: Optional[str] = Field(default=None, max_length=40)
    stripe_customer_id: Optional[str] = Field(default=None, max_length=120)
    extra_json: Optional[dict[str, Any]] = None


class BillingCheckoutRequest(BaseModel):
    plan: str = Field(pattern="^(starter|pro|business|enterprise)$")
    success_url: str = Field(..., min_length=8, max_length=500)
    cancel_url: str = Field(..., min_length=8, max_length=500)


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


def _auth_disabled() -> bool:
    return omega_config.auth_disabled()


def get_current_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer_scheme)],
) -> str:
    """Validate Supabase JWT from Authorization: Bearer and return auth.users.id as str."""
    if _auth_disabled():
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
    allowed = set(omega_config.developer_api_keys())
    if not allowed:
        raise HTTPException(
            status_code=503,
            detail="Developer API keys not configured (set ATLAS_DEV_API_KEY or ATLAS_DEV_API_KEYS)",
        )
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


def _extract_response_tickers(shaped: dict, query_text: str) -> list[str]:
    """Best-effort ticker extraction for lightweight market context attachment."""
    found: list[str] = []
    seen: set[str] = set()

    def add(raw: Any) -> None:
        sym = str(raw or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{1,5}", sym):
            return
        if sym in _CHAT_FALSE_POSITIVE_TICKERS or sym in {"CEO", "CFO", "SEC", "IRS", "USA", "USD"}:
            return
        if sym not in seen:
            seen.add(sym)
            found.append(sym)

    pq = shaped.get("parsed_query") if isinstance(shaped.get("parsed_query"), dict) else {}
    fr = shaped.get("final_report") if isinstance(shaped.get("final_report"), dict) else {}
    for src in (pq.get("tickers"), pq.get("symbols")):
        if isinstance(src, list):
            for item in src:
                add(item)
    for key in ("ticker", "symbol"):
        add(pq.get(key))
        add(fr.get(key))
    for m in re.finditer(r"\b[A-Z]{1,5}\b", query_text or ""):
        add(m.group(0))
    return found[:8]


def _attach_market_intelligence_if_relevant(
    shaped: dict,
    query_text: str,
    route_decision: Optional[RouteDecision],
) -> dict:
    """Attach compact D2/D3/D4 cache context for ticker finance responses.

    This is deliberately metadata, not prose. It keeps normal chat fast and plain
    while giving the UI/export layer a reliable source-backed market context block
    for ticker questions.
    """
    if not isinstance(shaped, dict) or is_plain_chat_response_for_api(shaped):
        return shaped
    route = route_decision.route_band if route_decision else ""
    if route == "quick_chat":
        return shaped
    tickers = _extract_response_tickers(shaped, query_text)
    if not tickers:
        return shaped
    try:
        from atlas_omega import UserContext, build_market_intelligence_context

        bundle = build_market_intelligence_context(
            query_text,
            UserContext(tickers=tickers),
            include_full=route in {"deep_research", "market_snapshot"},
        )
    except Exception as e:
        log.debug("[market_intelligence] attach failed: %s", e)
        return shaped
    shaped["_market_intelligence"] = {
        "snapshot": bundle.get("snapshot"),
        "generated_at": bundle.get("generated_at"),
        "tickers": tickers,
        "record_counts": bundle.get("record_counts") or {},
        "ticker_slices": bundle.get("ticker_slices") or {},
        "quality": bundle.get("quality") or {},
    }
    audit = shaped.get("audit_notes")
    if not isinstance(audit, list):
        audit = []
    audit.append("Attached D2/D3/D4 market intelligence cache slices for ticker context.")
    shaped["audit_notes"] = audit
    return shaped


def is_plain_chat_response_for_api(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    pq = data.get("parsed_query") if isinstance(data.get("parsed_query"), dict) else {}
    timing = data.get("timing") if isinstance(data.get("timing"), dict) else {}
    loops = timing.get("loops")
    try:
        loops_n = float(loops)
    except (TypeError, ValueError):
        loops_n = None
    return bool(
        pq.get("_chat_mode") is True
        or timing.get("_chat_mode") is True
        or pq.get("intent_route") == "CONVERSATION"
        or pq.get("query_type") == "CONVERSATION"
        or loops_n == 0
    )


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
    route_decision: Optional[RouteDecision] = None,
) -> Optional[dict]:
    mode = getattr(req, "research_mode", "normal") or "normal"
    if getattr(req, "crypto_snapshot", False):
        return None
    if mode == "deep" or (route_decision and route_decision.route_band == "deep_research"):
        return None
    if route_decision and route_decision.route_band != "quick_chat":
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
            "source_strictness": getattr(req, "source_strictness", None),
            "report_depth": getattr(req, "report_depth", None),
            "citation_preference": getattr(req, "citation_preference", None),
            "compliance_level": getattr(req, "compliance_level", None),
        },
    }
    if route_decision is not None:
        shaped["_route_decision"] = route_decision.to_dict()
    log.info("[/query] fast chat reply (%d chars)", len(q_store))
    return _ensure_query_ui_envelope(shaped, q_store)


def _build_research_activity_payload(query: str, route_decision: RouteDecision) -> dict:
    """Visible research plan/activity summaries. No hidden chain-of-thought."""
    route = route_decision.route_band
    if route == "quick_chat":
        return {}
    plan_by_route = {
        "market_snapshot": [
            ("scope", "Identify the market/entity snapshot requested"),
            ("cache", "Check fresh cached market and macro data"),
            ("answer", "Return a compact answer with visuals only if useful"),
        ],
        "focused_analysis": [
            ("scope", "Classify tickers, timeframe, and decision context"),
            ("evidence", "Gather cache/RAG/market evidence and note missing slots"),
            ("risk", "Check catalysts, levels, scenarios, and failure modes"),
            ("answer", "Shape a focused finance memo"),
        ],
        "deep_research": [
            ("plan", "Build a decision-grade research plan"),
            ("gather", "Gather cached and live evidence across relevant finance sources"),
            ("verify", "Cross-check conflicts, freshness, and missing evidence"),
            ("synthesize", "Compile the final cited report and artifacts"),
        ],
        "compliance_escalation": [
            ("scope", "Identify the regulated or advice-sensitive part of the request"),
            ("policy", "Apply finance safety and disclosure policy"),
            ("answer", "Return research framing, safer alternatives, or refusal where required"),
        ],
    }
    events_by_route = {
        "market_snapshot": [
            ("analysis_summary", "Choosing market snapshot mode", "The request appears answerable with a small evidence budget."),
            ("search_batch", "Checking market context", "Using cached prices, regime, breadth, and relevant data feeds where available."),
        ],
        "focused_analysis": [
            ("analysis_summary", "Choosing focused analysis", "The request needs finance reasoning, but not a full background research job."),
            ("verification", "Checking evidence quality", "The response should expose risks, assumptions, and missing data rather than overstate certainty."),
        ],
        "deep_research": [
            ("analysis_summary", "Choosing deep research", "The request was explicitly routed to the full research lane."),
            ("search_batch", "Planning evidence gathering", "The job should use multiple source categories and preserve an activity trail."),
            ("verification", "Preparing report verification", "The final answer should separate evidence, assumptions, risks, and action boundaries."),
        ],
        "compliance_escalation": [
            ("analysis_summary", "Compliance review triggered", "The request may involve personalized advice, guarantees, or regulated finance context."),
            ("verification", "Constraining output", "The response should avoid prohibited advice and keep an auditable research frame."),
        ],
    }
    plan = [
        {"id": key, "title": title, "status": "todo"}
        for key, title in plan_by_route.get(route, [])
    ]
    for idx, item in enumerate(plan):
        if route in {"market_snapshot", "focused_analysis", "compliance_escalation"} and idx < len(plan) - 1:
            item["status"] = "done"
        elif route == "deep_research" and idx == 0:
            item["status"] = "done"
        elif idx == 1:
            item["status"] = "doing"

    events = [
        {
            "id": f"evt_{idx + 1}",
            "kind": kind,
            "title": title,
            "body": body,
            "sources": [],
            "status": "done" if route != "deep_research" or idx == 0 else "queued",
        }
        for idx, (kind, title, body) in enumerate(events_by_route.get(route, []))
    ]
    source_chips = {
        "market_snapshot": ["data_cache", "market_regime"],
        "focused_analysis": ["data_cache", "RAG", "market_tools"],
        "deep_research": ["data_cache", "RAG", "market_tools", "filings", "web_sources"],
        "compliance_escalation": ["policy", "audit_log"],
    }.get(route, [])
    return {
        "job_id": None,
        "status": "completed",
        "final_response_available": True,
        "route_band": route,
        "progress_pct": 100,
        "current_stage": "Research plan and activity trail prepared",
        "current_message": "Showing the visible research plan and activity summaries, not hidden reasoning.",
        "search_count": min(route_decision.tool_budget * 4, 40),
        "query": query,
        "plan": plan,
        "events": events,
        "sources": source_chips,
        "artifacts": [],
    }


def _create_research_job_for_request(
    *,
    query: str,
    user_id: str,
    session_id: Optional[str],
    route_decision: RouteDecision,
) -> dict:
    activity = _build_research_activity_payload(query, route_decision)
    if not activity:
        activity = {
            "status": "queued",
            "route_band": route_decision.route_band,
            "progress_pct": 5,
            "current_stage": "Queued",
            "current_message": "Research job queued.",
            "search_count": 0,
            "query": query,
            "plan": [],
            "events": [],
            "sources": [],
            "artifacts": [],
        }
    activity["status"] = "queued"
    activity["progress_pct"] = min(int(activity.get("progress_pct") or 0), 20)
    job = research_jobs.create_job(
        user_id=user_id,
        query=query,
        route_decision=route_decision.to_dict(),
        activity=activity,
        session_id=session_id,
    )
    return job


def _detect_doc_type(query: str) -> Optional[str]:
    """Detect if the user wants a specific document output format."""
    ql = (query or "").lower()
    if re.search(r"\binfographic\b|\bvisual\s+summary\b", ql):
        return "infographic"
    if re.search(r"\bpowerpoint\b|\bpresentation\b|\bslide\s+deck\b|\bslides\b", ql):
        return "pptx"
    if re.search(r"\bexcel\b|\bspreadsheet\b|\bxlsx\b", ql):
        return "excel"
    if re.search(r"\bemail\s+digest\b|\bdaily\s+brief\b", ql):
        return "email_digest"
    if re.search(r"\bcompare\b.{0,40}\bvs\b|\bvs\b.{0,40}\bcompare\b|\bside\s+by\s+side\b", ql):
        return "compare"
    if re.search(r"\bportfolio\s+report\b|\bportfolio\s+analysis\b", ql):
        return "portfolio_report"
    if re.search(r"\bpdf\b|\bpdf\s+report\b", ql):
        return "pdf"
    if re.search(r"\bhtml\s+report\b|\bvisual\s+report\b|\bgive.*report\b|\bgenerate.*report\b", ql):
        return "html_report"
    return None


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
    doc_type = _detect_doc_type(q_store)
    if doc_type:
        shaped["_requested_doc_type"] = doc_type
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
    # Auto-pilot: trigger sandbox learning after every non-casual query
    _output_mode = shaped.get("_output_mode", "") or ""
    if _output_mode in ("trade_plan", "company_report", "finance_answer"):
        background_tasks.add_task(_sandbox_learn_bg, q_store, _output_mode)
    return shaped


def _sandbox_learn_bg(query: str, domain: str) -> None:
    """Fire one sandbox training batch in the background after each real query."""
    if os.environ.get("ATLAS_DISABLE_AUTH") == "true":
        return  # skip in dev to avoid noise during local testing
    try:
        from atlas_sandbox.sandbox_loop import run_batch
        _domain_map = {
            "trade_plan": "equities",
            "company_report": "equities",
            "finance_answer": "personal_wealth",
        }
        run_batch(n=1, domains=[_domain_map.get(domain, "equities")], dry_run=False)
    except Exception:
        pass


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


def _request_has_browser_session(request: Request) -> bool:
    if _auth_disabled():
        return True
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer ") and len(auth) > 16:
        return True
    token = (request.cookies.get("atlas_access_token") or "").strip()
    return bool(token)


def _subscription_tier_for_user(user_id: str) -> str:
    if user_id == "test_user_local" or not user_id:
        return "developer"
    default_tier = omega_config.default_subscription_tier()
    try:
        prefs = atlas_db.get_user_preferences(user_id)
    except Exception as e:
        log.debug("[tier] user preference lookup failed: %s", e)
        return default_tier
    tier = str(prefs.get("subscription_tier") or "").strip().lower()
    if not tier:
        extra = prefs.get("extra_json") if isinstance(prefs.get("extra_json"), dict) else {}
        tier = str(extra.get("subscription_tier") or extra.get("tier") or "").strip().lower()
    return tier or default_tier


def _daily_cap_for_tier(tier: str) -> int:
    default = PLAN_DAILY_QUERY_CAPS.get((tier or "free").lower(), PLAN_DAILY_QUERY_CAPS["free"])
    return max(0, omega_config.tier_daily_limit(tier, default))


def _enforce_query_tier_gate(user_id: str, req: "QueryRequest") -> dict[str, Any]:
    """Return tier metadata or raise 402/429 before expensive query execution."""
    if _auth_disabled() or user_id == "test_user_local":
        return {"tier": "developer", "daily_cap": None, "used_today": 0, "remaining_today": None}
    tier = _subscription_tier_for_user(user_id)
    cap = _daily_cap_for_tier(tier)
    if cap <= 0:
        raise HTTPException(
            status_code=402,
            detail="Your R.A. Omega plan is inactive. Update billing to continue.",
        )
    try:
        used = atlas_db.count_queries_today(user_id)
    except Exception as e:
        log.warning("[tier] count_queries_today failed: %s", e)
        used = 0
    if used >= cap:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_query_limit_reached",
                "tier": tier,
                "daily_cap": cap,
                "used_today": used,
                "upgrade_hint": "Upgrade to Pro or Business for a higher daily research limit.",
            },
        )
    return {
        "tier": tier,
        "daily_cap": cap,
        "used_today": used,
        "remaining_today": max(cap - used - 1, 0),
        "research_mode": getattr(req, "research_mode", "normal"),
    }


def _stripe_secret_key() -> str:
    return omega_config.stripe_secret_key()


def _stripe_price_for_plan(plan: str) -> str:
    return omega_config.stripe_price_for_plan(plan)


def _verify_stripe_signature(payload: bytes, signature_header: str, secret: str) -> None:
    parts: dict[str, list[str]] = {}
    for item in (signature_header or "").split(","):
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        parts.setdefault(k, []).append(v)
    ts = (parts.get("t") or [""])[0]
    sigs = parts.get("v1") or []
    if not ts or not sigs:
        raise HTTPException(status_code=400, detail="Missing Stripe signature parts")
    signed = ts.encode("utf-8") + b"." + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in sigs):
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")


def _apply_billing_event(event: dict[str, Any]) -> dict[str, Any]:
    typ = str(event.get("type") or "")
    obj = ((event.get("data") or {}).get("object") or {}) if isinstance(event.get("data"), dict) else {}
    if not isinstance(obj, dict):
        return {"handled": False, "reason": "missing_object"}
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    user_id = str(metadata.get("user_id") or obj.get("client_reference_id") or "").strip()
    plan = str(metadata.get("plan") or "").strip().lower()
    if typ in {"checkout.session.completed", "customer.subscription.created", "customer.subscription.updated"}:
        if not user_id:
            return {"handled": False, "reason": "missing_user_id"}
        updates = {
            "subscription_tier": plan or "pro",
            "subscription_status": str(obj.get("status") or "active"),
            "stripe_customer_id": str(obj.get("customer") or ""),
        }
        atlas_db.update_user_preferences(user_id, updates)
        return {"handled": True, "user_id": user_id, "tier": updates["subscription_tier"]}
    if typ in {"customer.subscription.deleted", "customer.subscription.paused"} and user_id:
        atlas_db.update_user_preferences(
            user_id,
            {"subscription_tier": "free", "subscription_status": str(obj.get("status") or "inactive")},
        )
        return {"handled": True, "user_id": user_id, "tier": "free"}
    return {"handled": False, "reason": f"ignored:{typ}"}


def _transcribe_whisper_openai(content: bytes, filename: str) -> str:
    import requests

    key = omega_config.openai_api_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY not configured for voice transcription",
        )
    url = "https://api.openai.com/v1/audio/transcriptions"
    model = omega_config.openai_whisper_model()
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

    key = omega_config.openai_api_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY not configured for TTS",
        )
    vid = omega_config.openai_tts_voice(voice)
    model = omega_config.openai_tts_model()
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

    key = omega_config.elevenlabs_api_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="ELEVENLABS_API_KEY not configured for TTS",
        )
    vid = omega_config.elevenlabs_voice_id(voice)
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
    key = omega_config.google_api_key()
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

    prompt = f"""You edit R.A. Omega dashboard query report JSON. Apply the user's instruction.
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
    model = omega_config.gemini_model()
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
    tier_usage = _enforce_query_tier_gate(user_id, req)
    route_input = q_store
    mode = getattr(req, "research_mode", "normal") or "normal"
    route_decision = decide_route(
        q_store,
        forced_mode=mode,
        web_search=bool(getattr(req, "web_search", False)),
    )
    activation = activate_specialists(q_store, route_decision)
    specialist_packets = build_specialist_packets(activation)
    job: Optional[dict] = None
    if req.research_job_id:
        job = research_jobs.get_job(req.research_job_id, user_id=user_id)
        if job and job.get("status") == "cancelled":
            body = _ensure_query_ui_envelope(
                {
                    "parsed_query": {},
                    "final_report": {
                        "executive_summary": "Research was cancelled before completion.",
                    },
                    "tldr": "Research was cancelled before completion.",
                    "_route_decision": route_decision.to_dict(),
                    "_research_activity": research_jobs.activity_from_job(job),
                },
                q_store,
            )
            return _finalize_query_response(body, req, user_id, background_tasks, q_store, time.time())
    elif route_decision.route_band in {"deep_research", "market_snapshot"}:
        job = _create_research_job_for_request(
            query=q_store,
            user_id=user_id,
            session_id=req.session_id,
            route_decision=route_decision,
        )
    if job:
        research_jobs.update_job(
            job["job_id"],
            user_id=user_id,
            status="in_progress",
            progress_pct=max(int(job.get("progress_pct") or 0), 25),
            current_stage="Running analysis",
            current_message="Omega is gathering evidence and preparing the response.",
        )
    if req.user_display_name and str(req.user_display_name).strip():
        nick = str(req.user_display_name).strip()[:120]
        route_input = (
            f"[User personalization: address the user as “{nick}” when natural in prose.]\n\n{q_store}"
        )

    discovered_sources: list[dict[str, str]] = []
    if mode in {"web", "deep"} or getattr(req, "web_search", False):
        if job:
            research_jobs.update_job(
                job["job_id"],
                user_id=user_id,
                progress_pct=18,
                current_stage="Source discovery",
                current_message="Finding lightweight web source candidates before analysis.",
                event={
                    "type": "source_discovery",
                    "label": "Source discovery",
                    "detail": "Searching for current source candidates.",
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
        try:
            discovered_sources = discover_sources(q_store, max_results=8 if mode == "deep" else 5)
        except Exception as e:
            log.debug("[web_sources] discovery failed: %s", e)
            discovered_sources = []
        if discovered_sources:
            block = sources_prompt_block(discovered_sources)
            if block:
                route_input = f"{block}\n\n{route_input}"
            if job:
                research_jobs.update_job(
                    job["job_id"],
                    user_id=user_id,
                    progress_pct=22,
                    current_stage="Sources found",
                    current_message=f"Found {len(discovered_sources)} source candidates.",
                    event={
                        "type": "sources_found",
                        "label": "Sources found",
                        "detail": f"{len(discovered_sources)} source candidates collected.",
                        "ts": datetime.now(timezone.utc).isoformat(),
                    },
                    artifacts=[
                        {
                            "type": "web_sources",
                            "label": "Source candidates",
                            "items": discovered_sources,
                        }
                    ],
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
    if req.source_strictness:
        strictness = str(req.source_strictness).strip()[:40]
        if strictness == "strict":
            request_hints.append("Source strictness: strict. Prefer primary sources and label unverified or fallback evidence.")
        elif strictness == "speed":
            request_hints.append("Source strictness: speed. Keep source checks efficient while preserving safety-critical validation.")
        else:
            request_hints.append(f"Source strictness: {strictness}.")
    if req.report_depth:
        request_hints.append(f"Preferred report depth: {str(req.report_depth).strip()[:40]}.")
    if req.citation_preference:
        request_hints.append(f"Citation preference: {str(req.citation_preference).strip()[:40]}.")
    if req.compliance_level:
        request_hints.append(f"Compliance disclaimer level: {str(req.compliance_level).strip()[:40]}.")
    request_hints.append(
        "Route decision: "
        f"{route_decision.route_band} "
        f"(deep_score={route_decision.deep_score:.2f}, tool_budget={route_decision.tool_budget}, output={route_decision.output_shape})."
    )
    if route_decision.compliance_flags:
        request_hints.append("Compliance flags: " + ", ".join(route_decision.compliance_flags) + ".")
    packet_block = specialist_packets_prompt_block(specialist_packets)
    if packet_block:
        route_input = f"{packet_block}\n\n{route_input}"
    if request_hints:
        route_input = "[Request controls]\n- " + "\n- ".join(request_hints) + f"\n\n{route_input}"

    router = get_router()
    if not router:
        raise HTTPException(status_code=503, detail="QueryRouter not loaded — check server logs")

    start = time.time()
    log.info("[/query] %s", q_store[:100])

    try:
        fast = _maybe_fast_chat_shaped(router, q_store, req, start, route_decision)
        if fast is not None:
            return _finalize_query_response(
                fast, req, user_id, background_tasks, q_store, start
            )

        if job:
            latest_job = research_jobs.get_job(job["job_id"], user_id=user_id)
            if latest_job and latest_job.get("cancel_requested"):
                cancelled = research_jobs.cancel_job(job["job_id"], user_id=user_id) or latest_job
                body = _ensure_query_ui_envelope(
                    {
                        "parsed_query": {},
                        "final_report": {
                            "executive_summary": "Research was cancelled before the 10-loop engine started.",
                        },
                        "tldr": "Research was cancelled before the 10-loop engine started.",
                        "_route_decision": route_decision.to_dict(),
                        "_research_activity": research_jobs.activity_from_job(cancelled),
                    },
                    q_store,
                )
                return _finalize_query_response(body, req, user_id, background_tasks, q_store, start)

        def progress_callback(event: dict[str, Any]) -> None:
            if not job:
                return
            stage = str(event.get("stage") or "Research")
            message = str(event.get("message") or "")
            loop = event.get("loop")
            research_jobs.update_job(
                job["job_id"],
                user_id=user_id,
                progress_pct=int(event.get("progress_pct") or 0),
                current_stage=stage,
                current_message=message,
                event={
                    "type": "pipeline_stage",
                    "label": stage,
                    "detail": message,
                    "loop": loop,
                    "ts": event.get("ts") or datetime.now(timezone.utc).isoformat(),
                },
            )

        def cancel_check() -> bool:
            if not job:
                return False
            latest = research_jobs.get_job(job["job_id"], user_id=user_id)
            return bool(latest and latest.get("cancel_requested"))

        _full_ctx = ""
        try:
            from atlas_memory.memory_injector import get_relevant_context as _get_mem
            _mem_ctx = _get_mem(q_store, user_id)
            if _mem_ctx:
                _full_ctx += _mem_ctx + "\n"
        except Exception:
            pass
        try:
            from atlas_vault.obsidian_connector import inject_vault_context as _get_vault
            _vault_ctx = _get_vault(q_store, user_id or "anonymous")
            if _vault_ctx:
                _full_ctx += _vault_ctx + "\n"
        except Exception:
            pass
        if _full_ctx:
            route_input = f"{_full_ctx.strip()}\n\n{route_input}"

        raw = router.route(
            q_store,
            user_id=user_id,
            session_id=req.session_id,
            crypto_snapshot=req.crypto_snapshot,
            research_mode=mode,
            progress_callback=progress_callback if job else None,
            cancel_check=cancel_check if job else None,
        )
        if job:
            latest_job = research_jobs.get_job(job["job_id"], user_id=user_id)
            if latest_job and latest_job.get("cancel_requested"):
                cancelled = research_jobs.cancel_job(job["job_id"], user_id=user_id) or latest_job
                body = _ensure_query_ui_envelope(
                    {
                        "parsed_query": {},
                        "final_report": {
                            "executive_summary": "Research was cancelled. The completed draft was discarded.",
                        },
                        "tldr": "Research was cancelled. The completed draft was discarded.",
                        "_route_decision": route_decision.to_dict(),
                        "_research_activity": research_jobs.activity_from_job(cancelled),
                    },
                    q_store,
                )
                return _finalize_query_response(body, req, user_id, background_tasks, q_store, start)
        shaped = _ensure_query_ui_envelope(raw, q_store)
        _intent = (shaped.get("parsed_query") or {}).get("intent_route", "GENERAL_FINANCE")
        try:
            from omega_pipeline import select_output_mode as _pipeline_select_om
            _output_mode = _pipeline_select_om(
                q_store, _intent, {"research_mode": mode}
            )
        except Exception:
            _output_mode = resolve_output_mode(q_store, _intent)
        shaped["_output_mode"] = _output_mode

        # ── Quality firewall + response judge (one repair log) ────────────────
        if _QFW_AVAILABLE:
            try:
                _answer_text = " ".join(filter(None, [
                    str(shaped.get("tldr") or ""),
                    str((shaped.get("final_report") or {}).get("executive_summary") or ""),
                    str(shaped.get("trader_memo") or ""),
                ]))
                _qfw = _qfw_validate(q_store, _intent, _output_mode, _answer_text)
                if not _qfw.passed:
                    log.warning("[quality_firewall] %s | repair: %s", _qfw.reason, _qfw.repair_instruction[:80])
                    shaped["_quality_firewall"] = {"passed": False, "reason": _qfw.reason}
                else:
                    _judge = _judge_response(q_store, _intent, _output_mode, _answer_text)
                    if _judge.verdict == "FAIL":
                        log.warning("[response_judge] %s | repair: %s", _judge.reason, _judge.repair_instruction[:80])
                        shaped["_response_judge"] = {"verdict": "FAIL", "reason": _judge.reason}
            except Exception:
                log.debug("[quality_firewall] check failed", exc_info=True)

        try:
            from atlas_memory.memory_injector import save_to_memory as _save_mem
            _save_mem(q_store, shaped, user_id)
        except Exception:
            pass
        shaped["_request_controls"] = {
            "research_mode": mode,
            "web_search": bool(getattr(req, "web_search", False) or mode in ("web", "deep")),
            "answer_style": req.answer_style,
            "risk_profile": req.risk_profile,
            "market_focus": req.market_focus,
            "source_strictness": req.source_strictness,
            "report_depth": req.report_depth,
            "citation_preference": req.citation_preference,
            "compliance_level": req.compliance_level,
        }
        shaped["_tier_usage"] = tier_usage
        shaped["_route_decision"] = route_decision.to_dict()
        shaped["_active_agents"] = activation.to_dict()
        shaped["_specialist_packets"] = specialist_packets
        # ── Prompt Architect — parse query into structured blueprint ─────────
        try:
            _bp = build_prompt_blueprint(
                query=q_store,
                intent=_intent,
                output_mode=_output_mode,
                user_id=user_id if user_id != "test_user_local" else None,
            )
            shaped["_prompt_blueprint"] = _bp.to_dict()
        except Exception:
            log.debug("[prompt_architect] blueprint failed", exc_info=True)
        _pipeline_plan_dict: dict = {}
        try:
            _pipeline_plan = plan_pipeline(
                query=q_store,
                intent=_intent,
                output_mode=_output_mode,
                research_mode=mode,
                user_id=user_id if user_id != "test_user_local" else None,
            )
            _pipeline_plan_dict = _pipeline_plan.to_dict()
            shaped["_pipeline_plan"] = _pipeline_plan_dict
        except Exception:
            log.debug("[pipeline_planner] plan generation failed", exc_info=True)
        # ── Multi-agent collaboration layer ───────────────────────────────────
        try:
            _ma_session = multi_agent_orchestrate(
                query=q_store,
                intent=_intent,
                plan=_pipeline_plan_dict,
                research_mode=mode,
                user_id=user_id if user_id != "test_user_local" else None,
            )
            shaped["_multi_agent"] = _ma_session.to_dict()
        except Exception:
            log.debug("[multi_agent] orchestration failed", exc_info=True)
        # ── Division Sandbox — inject playbook + memories for active division ───
        try:
            _div_playbook = get_playbook_context(_intent, max_rules=5)
            _div_memories = get_division_memories(_intent, limit=3)
            shaped["_division_playbook"] = _div_playbook
            shaped["_division_memories"] = _div_memories
        except Exception:
            log.debug("[division_sandbox] context inject failed", exc_info=True)
        # ── Project Sandbox — persist workspace for non-trivial queries ────────
        if user_id and user_id != "test_user_local" and _intent not in ("CONVERSATION", "GENERAL_CHAT"):
            try:
                _sb = create_sandbox(
                    query=q_store,
                    user_id=user_id,
                    session_id=getattr(req, "session_id", None),
                    intent=_intent,
                    research_mode=mode,
                    plan=_pipeline_plan_dict,
                )
                attach_sandbox_result(_sb["sandbox_id"], shaped)
                shaped["_sandbox_id"] = _sb["sandbox_id"]
            except Exception:
                log.debug("[project_sandbox] sandbox creation failed", exc_info=True)
        shaped = _attach_market_intelligence_if_relevant(shaped, q_store, route_decision)
        activity = _build_research_activity_payload(q_store, route_decision)
        if job:
            updated_job = research_jobs.update_job(
                job["job_id"],
                user_id=user_id,
                status="completed",
                progress_pct=100,
                current_stage="Completed",
                current_message="Research complete. Final response is ready.",
                activity={**activity, "status": "completed", "progress_pct": 100},
                event={
                    "type": "complete",
                    "label": "Done",
                    "detail": "Final answer ready. Progress stream closed.",
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
            if updated_job:
                activity = research_jobs.activity_from_job(updated_job)
        if activity:
            shaped["_research_activity"] = activity
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
        if job:
            failed = research_jobs.update_job(
                job["job_id"],
                user_id=user_id,
                status="failed",
                current_stage="Rate limited",
                current_message=msg,
            )
            if failed:
                body["_research_activity"] = research_jobs.activity_from_job(failed)
        return JSONResponse(status_code=429, content=body)
    except QueryCancelledError as e:
        msg = str(e) or "Research was cancelled."
        cancelled = research_jobs.cancel_job(job["job_id"], user_id=user_id) if job else None
        body = _ensure_query_ui_envelope(
            {
                "parsed_query": {},
                "final_report": {"executive_summary": msg},
                "tldr": msg,
                "trader_memo": msg,
                "hedge_fund_brief": msg,
            },
            q_store,
        )
        body["_route_decision"] = route_decision.to_dict()
        if cancelled:
            body["_research_activity"] = research_jobs.activity_from_job(cancelled)
        return _finalize_query_response(body, req, user_id, background_tasks, q_store, start)
    except HTTPException:
        raise
    except Exception as e:
        log.error("[/query] Error: %s", e)
        if job:
            research_jobs.update_job(
                job["job_id"],
                user_id=user_id,
                status="failed",
                current_stage="Failed",
                current_message=str(e),
            )
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
    pub = omega_config.supabase_config().public
    inject = f"<script>window.__ATLAS_SB_CONFIG__={json.dumps(pub)};</script>\n"
    if "</head>" in raw:
        html = raw.replace("</head>", inject + "</head>", 1)
    else:
        html = inject + raw
    return HTMLResponse(html, media_type="text/html; charset=utf-8")


def _pricing_html_response() -> HTMLResponse:
    """Self-contained pricing page with Stripe Checkout hooks."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>R.A. Omega - Pricing</title>
  <style>
    :root { --base:#0B1020; --surface:#101827; --line:rgba(220,226,235,.12); --text:#F4F7FB; --muted:rgba(157,169,183,.78); --teal:#18C6C8; --emerald:#2ED47A; --amber:#FBBF24; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; background:radial-gradient(circle at 50% -10%, rgba(24,198,200,.14), transparent 42%), var(--base); color:var(--text); font-family:Inter, ui-sans-serif, system-ui, sans-serif; }
    main { width:min(1120px, calc(100vw - 32px)); margin:0 auto; padding:42px 0 56px; }
    nav { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:64px; }
    .brand { font-weight:800; letter-spacing:.16em; color:var(--teal); }
    a { color:inherit; text-decoration:none; }
    .navlink { color:var(--muted); border:1px solid var(--line); padding:9px 12px; border-radius:8px; font-size:13px; }
    h1 { font-size:clamp(34px, 5vw, 68px); line-height:.98; margin:0; letter-spacing:-.03em; max-width:780px; }
    .lead { margin:18px 0 34px; max-width:680px; color:var(--muted); line-height:1.65; font-size:17px; }
    .plans { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; }
    .plan { border:1px solid var(--line); background:rgba(16,24,39,.78); border-radius:12px; padding:22px; min-height:315px; display:flex; flex-direction:column; }
    .plan.featured { border-color:rgba(24,198,200,.55); box-shadow:0 0 0 1px rgba(24,198,200,.18), 0 24px 80px rgba(0,0,0,.28); }
    .name { font-size:15px; color:var(--teal); font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
    .price { font-size:34px; font-weight:800; margin:18px 0 2px; }
    .price span { color:var(--muted); font-size:14px; font-weight:500; }
    .cap { color:var(--muted); font-size:13px; min-height:38px; }
    ul { padding-left:18px; color:var(--muted); line-height:1.7; font-size:14px; margin:18px 0 22px; }
    button { margin-top:auto; width:100%; border:0; border-radius:8px; padding:12px 14px; background:var(--teal); color:#041015; font-weight:800; cursor:pointer; }
    button.secondary { background:transparent; color:var(--text); border:1px solid var(--line); }
    button:disabled { opacity:.55; cursor:wait; }
    #status { margin-top:18px; min-height:22px; color:var(--amber); font-size:14px; }
    @media (max-width: 900px) { .plans { grid-template-columns:1fr 1fr; } }
    @media (max-width: 560px) { main { padding-top:24px; } nav { margin-bottom:36px; } .plans { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <main>
    <nav>
      <div class="brand">R.A. OMEGA_</div>
      <div>
        <a class="navlink" href="/app">Chat</a>
        <a class="navlink" href="/dashboard">Dashboard</a>
      </div>
    </nav>
    <h1>Pick your level of intelligence.</h1>
    <p class="lead">Start with normal chat, then upgrade when you need more reports, deeper research, exports, and business-grade usage. R.A. Omega keeps the main chat fast and only runs the heavy research lane when you choose it.</p>
    <section class="plans">
      <article class="plan">
        <div class="name">Free</div>
        <div class="price">$0 <span>/mo</span></div>
        <div class="cap">Starter access for testing the product.</div>
        <ul><li>3 queries per day</li><li>Normal chat</li><li>Basic finance answers</li></ul>
        <button class="secondary" onclick="location.href='/app'">Start free</button>
      </article>
      <article class="plan featured">
        <div class="name">Pro</div>
        <div class="price">$49 <span>/mo</span></div>
        <div class="cap">For active retail investors and traders.</div>
        <ul><li>Higher daily query cap</li><li>Web search and deep research</li><li>Saved sessions and reports</li></ul>
        <button onclick="checkout('pro')">Upgrade to Pro</button>
      </article>
      <article class="plan">
        <div class="name">Business</div>
        <div class="price">$149 <span>/mo</span></div>
        <div class="cap">For operators, advisors, and small teams.</div>
        <ul><li>Business-grade cap</li><li>PDF, Excel, and client-ready exports</li><li>Priority research workflows</li></ul>
        <button onclick="checkout('business')">Upgrade to Business</button>
      </article>
      <article class="plan">
        <div class="name">Developer</div>
        <div class="price">$0.10 <span>/call</span></div>
        <div class="cap">API access for builders and integrations.</div>
        <ul><li>Billable API route</li><li>Usage metadata</li><li>Integration-ready output</li></ul>
        <button class="secondary" onclick="location.href='/docs'">View API docs</button>
      </article>
    </section>
    <div id="status"></div>
  </main>
  <script>
    function authHeaders() {
      const token = localStorage.getItem('atlas_access_token') || localStorage.getItem('ATLAS_TEST_JWT') || '';
      const h = {'Content-Type':'application/json'};
      if (token) h.Authorization = 'Bearer ' + token;
      return h;
    }
    async function checkout(plan) {
      const status = document.getElementById('status');
      status.textContent = 'Creating Stripe checkout...';
      try {
        const r = await fetch('/billing/checkout', {
          method:'POST',
          headers: authHeaders(),
          body: JSON.stringify({
            plan,
            success_url: location.origin + '/app?billing=success',
            cancel_url: location.origin + '/pricing?billing=cancelled'
          })
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.detail || data.message || 'Checkout failed');
        if (data.url) location.href = data.url;
        else status.textContent = 'Checkout created, but Stripe did not return a URL.';
      } catch (e) {
        status.textContent = String(e.message || e);
      }
    }
  </script>
</body>
</html>"""
    return HTMLResponse(html, media_type="text/html; charset=utf-8")


def _zenith_landing_response() -> HTMLResponse:
    """Zenith sign-in landing (3D background + AuthPanel); injects Supabase anon config."""
    if not ATLAS_ZENITH_LANDING.is_file():
        return HTMLResponse("<h1>Landing page not found</h1>", status_code=404)
    html = ATLAS_ZENITH_LANDING.read_text(encoding="utf-8")
    cfg = omega_config.supabase_config().public
    injection = f"<script>window.__ATLAS_SB_CONFIG__ = {json.dumps(cfg)};</script>"
    html = html.replace("</head>", injection + "\n</head>", 1)
    return HTMLResponse(html, media_type="text/html; charset=utf-8")


@app.get("/")
def serve_home():
    return _zenith_landing_response()


@app.get("/pricing")
def serve_pricing():
    return _pricing_html_response()


@app.get("/dashboard")
@app.get("/v2")
def serve_command_center():
    if COMMAND_CENTER.is_file():
        return _dashboard_html_response(COMMAND_CENTER)
    # Fallback to old dashboard for backwards compat
    if not ATLAS_DASHBOARD_V4.is_file():
        raise HTTPException(status_code=404, detail="command_center.html not found")
    return _dashboard_html_response(ATLAS_DASHBOARD_V4)


@app.get("/agents")
@app.get("/network")
def serve_agents_network():
    if AGENTS_NETWORK.is_file():
        return _dashboard_html_response(AGENTS_NETWORK)
    raise HTTPException(status_code=404, detail="agents_network.html not found")


@app.get("/app")
def serve_ra_omega_app(request: Request):
    """Main R.A. Omega chat UI - same origin as API for POST /query and /omega."""
    if not _request_has_browser_session(request):
        return RedirectResponse(url="/auth", status_code=302)
    if not RA_OMEGA_APP.is_file():
        raise HTTPException(
            status_code=404,
            detail="Missing ra_omega_app.html next to api_server.py",
        )
    return FileResponse(RA_OMEGA_APP, media_type="text/html; charset=utf-8")


@app.get("/option1")
def redirect_option1():
    """Legacy alias — permanent redirect to /app."""
    return RedirectResponse(url="/app", status_code=301)


@app.get("/login")
def redirect_login():
    """Legacy alias — permanent redirect to /auth."""
    return RedirectResponse(url="/auth", status_code=301)


@app.get("/data-map")
def serve_data_map():
    path = BASE_DIR / "atlas_vault" / "03-Outputs" / "data_map.html"
    if not path.is_file():
        try:
            from atlas_core.data_map import main as generate_data_map

            generate_data_map()
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Data map is missing and could not be regenerated: {exc}",
            ) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Missing data_map.html")
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.get("/design_system.css")
def serve_design_system_css():
    """Serve the shared ATLAS design token stylesheet."""
    path = BASE_DIR / "design_system.css"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Missing design_system.css")
    return FileResponse(path, media_type="text/css; charset=utf-8")


@app.get("/omega-os/brain-network")
def serve_brain_network():
    """Serve the Omega Brain Live Network visualization page."""
    path = BASE_DIR / "omega_brain_network.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Missing omega_brain_network.html")
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.get("/command-center")
def serve_omega_command_center():
    """Serve the R.A. Omega user-facing product dashboard."""
    path = BASE_DIR / "omega_command_center.html"
    if not path.is_file():
        # Fall back to command_center.html if omega variant not found
        if COMMAND_CENTER.is_file():
            return _dashboard_html_response(COMMAND_CENTER)
        raise HTTPException(status_code=404, detail="Missing omega_command_center.html")
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.post("/jobs/plan")
def create_research_plan(req: ResearchPlanRequest, user_id: AtlasUserId):
    """Create a visible research plan/job before a long research request starts."""
    q = req.query.strip()
    route_decision = decide_route(
        q,
        forced_mode=req.research_mode or "deep",
        web_search=bool(req.web_search),
    )
    job = _create_research_job_for_request(
        query=q,
        user_id=user_id,
        session_id=req.session_id,
        route_decision=route_decision,
    )
    return {
        "ok": True,
        "job": job,
        "activity": research_jobs.activity_from_job(job),
        "route_decision": route_decision.to_dict(),
    }


@app.get("/sandboxes")
def list_sandboxes_api(
    user_id: AtlasUserId,
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """List project sandboxes for the current user."""
    items = list_sandboxes(user_id=user_id, session_id=session_id, limit=limit)
    return {"ok": True, "sandboxes": items, "count": len(items)}


@app.get("/sandboxes/{sandbox_id}")
def get_sandbox_api(sandbox_id: str, user_id: AtlasUserId):
    """Get a single sandbox by ID."""
    sb = get_sandbox(sandbox_id)
    if not sb:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    if sb.get("user_id") and sb["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your sandbox")
    return {"ok": True, "sandbox": sb}


@app.delete("/sandboxes/{sandbox_id}")
def delete_sandbox_api(sandbox_id: str, user_id: AtlasUserId):
    """Delete a sandbox workspace."""
    sb = get_sandbox(sandbox_id)
    if not sb:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    if sb.get("user_id") and sb["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not your sandbox")
    delete_sandbox(sandbox_id)
    return {"ok": True, "deleted": sandbox_id}


@app.get("/hub/snapshot")
def hub_snapshot_api(
    categories: Optional[str] = Query(default=None, description="Comma-separated category filter"),
):
    """Full intelligence hub snapshot — all signal categories from data_cache."""
    cat_list = [c.strip() for c in categories.split(",")] if categories else None
    try:
        return {"ok": True, **hub_snapshot(cat_list)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/hub/brief")
def hub_brief_api():
    """Condensed intelligence brief — top 3 signals per category."""
    try:
        return {"ok": True, **hub_brief()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/divisions")
def list_divisions_api():
    """List all 8 division sandboxes with summary stats."""
    try:
        return {"ok": True, "divisions": list_divisions()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/divisions/{division_id}")
def get_division_api(division_id: str):
    """Get full context for a single division sandbox."""
    try:
        div = get_division(division_id)
        if div is None:
            raise HTTPException(status_code=404, detail=f"Division '{division_id}' not found")
        return {"ok": True, "division": div}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class DivisionLearnRequest(BaseModel):
    query: str
    insight: str
    category: str = "general"
    confidence: float = 0.8
    source_intent: str = ""


@app.post("/divisions/{division_id}/learn")
def division_learn_api(division_id: str, req: DivisionLearnRequest, user_id: AtlasUserId):
    """Record a new learning into a division's memory."""
    try:
        entry = division_learn(
            division_id=division_id,
            query=req.query,
            insight=req.insight,
            category=req.category,
            confidence=req.confidence,
            source_intent=req.source_intent,
        )
        return {"ok": True, "entry": entry}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/hermes/brief")
def hermes_brief_api():
    """Return today's Hermes brief, or the most recent one if today's isn't ready."""
    brief = hermes_today_brief() or hermes_latest_brief()
    if brief is None:
        return {"ok": True, "brief": None, "message": "No brief generated yet — Hermes will generate one shortly."}
    return {"ok": True, "brief": brief}


@app.get("/hermes/cadences")
def hermes_cadences_api():
    """List all Hermes cadences with last_run / next_run / due status."""
    try:
        return {"ok": True, "cadences": hermes_list_cadences()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/hermes/cadences/{cadence_id}/run")
def hermes_run_cadence_api(cadence_id: str, user_id: AtlasUserId):
    """Manually trigger a Hermes cadence immediately."""
    if cadence_id not in HERMES_CADENCES:
        raise HTTPException(status_code=404, detail=f"Unknown cadence '{cadence_id}'")
    try:
        result = hermes_run_cadence(cadence_id)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/hermes/actions")
def hermes_actions_api(status: Optional[str] = Query(default=None, description="Filter by status: pending | dismissed | executed")):
    """Return the Hermes operator action queue."""
    try:
        queue = hermes_action_queue(status=status)
        return {"ok": True, "actions": queue, "total": len(queue)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/hermes/actions/{action_id}/dismiss")
def hermes_dismiss_api(action_id: str, user_id: AtlasUserId):
    """Dismiss a pending Hermes action."""
    found = hermes_dismiss_action(action_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")
    return {"ok": True, "action_id": action_id, "status": "dismissed"}


@app.post("/hermes/actions/{action_id}/execute")
def hermes_execute_api(action_id: str, user_id: AtlasUserId):
    """Mark a Hermes action as executed."""
    found = hermes_execute_action(action_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")
    return {"ok": True, "action_id": action_id, "status": "executed"}


@app.post("/transcripts/ingest")
def transcripts_ingest_api(user_id: AtlasUserId):
    """Convert new Claude Code sessions to .md and ingest into Chroma finance_knowledge."""
    try:
        from transcript_ingest import convert_sessions, ingest_transcripts
        new_files = convert_sessions(force=False)
        result = ingest_transcripts()
        return {
            "ok": True,
            "new_sessions_converted": len(new_files),
            "new_files": [str(f.name) for f in new_files],
            **result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/transcripts/status")
def transcripts_status_api():
    """Return transcript ingest status and Chroma chunk counts."""
    try:
        from transcript_ingest import _load_state, TRANSCRIPT_DIR
        state = _load_state()
        md_files = len(list(TRANSCRIPT_DIR.glob("session_*.md"))) if TRANSCRIPT_DIR.exists() else 0
        return {
            "ok": True,
            "converted_sessions": len(state.get("converted", {})),
            "md_files": md_files,
            "last_ingest": state.get("last_ingest"),
            "last_ingest_result": state.get("last_ingest_result"),
            "sessions": list(state.get("converted", {}).values()),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/pipeline/plan")
def pipeline_plan_endpoint(req: ResearchPlanRequest, user_id: AtlasUserId):
    """Return the optimal agent team and execution plan for a query.

    This is a fast, read-only planning step — no LLM call is made.
    The UI can call this immediately after the user submits a query to
    display which agents are activated before the full response arrives.
    """
    q = req.query.strip()
    if not q:
        raise HTTPException(status_code=422, detail="query is required")

    route_decision = decide_route(
        q,
        forced_mode=req.research_mode or "normal",
        web_search=bool(req.web_search),
    )
    intent = getattr(route_decision, "intent", "GENERAL_FINANCE")
    output_mode = getattr(route_decision, "output_mode", "chat")

    plan: AgentPlan = plan_pipeline(
        query=q,
        intent=intent,
        output_mode=output_mode,
        research_mode=req.research_mode or "normal",
        user_id=user_id if user_id != "test_user_local" else None,
    )
    return {"ok": True, "plan": plan.to_dict()}


@app.get("/jobs")
def list_research_jobs_api(
    user_id: AtlasUserId,
    session_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    jobs = research_jobs.list_jobs(user_id, session_id=session_id, limit=limit)
    return {
        "ok": True,
        "jobs": jobs,
        "activities": [research_jobs.activity_from_job(job) for job in jobs],
    }


@app.get("/user/preferences")
def get_user_preferences_api(user_id: AtlasUserId):
    return {"ok": True, "preferences": atlas_db.get_user_preferences(user_id)}


@app.patch("/user/preferences")
def update_user_preferences_api(req: UserPreferencesRequest, user_id: AtlasUserId):
    updates = req.model_dump(exclude_unset=True)
    return {"ok": True, "preferences": atlas_db.update_user_preferences(user_id, updates)}


@app.post("/billing/checkout")
def create_billing_checkout(req: BillingCheckoutRequest, user_id: AtlasUserId):
    """Create a Stripe Checkout session for hosted subscription plans."""
    import requests

    secret = _stripe_secret_key()
    price_id = _stripe_price_for_plan(req.plan)
    if not secret or not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Billing is not configured for plan '{req.plan}'",
        )
    try:
        resp = requests.post(
            "https://api.stripe.com/v1/checkout/sessions",
            auth=(secret, ""),
            data={
                "mode": "subscription",
                "line_items[0][price]": price_id,
                "line_items[0][quantity]": "1",
                "success_url": req.success_url,
                "cancel_url": req.cancel_url,
                "client_reference_id": user_id,
                "metadata[user_id]": user_id,
                "metadata[plan]": req.plan,
                "subscription_data[metadata][user_id]": user_id,
                "subscription_data[metadata][plan]": req.plan,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("[billing] checkout failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Stripe checkout failed: {e}") from e
    return {"ok": True, "checkout_session_id": data.get("id"), "url": data.get("url")}


@app.post("/billing/webhook")
async def stripe_billing_webhook(request: Request):
    """Stripe webhook for subscription tier activation/deactivation."""
    payload = await request.body()
    secret = omega_config.stripe_webhook_secret()
    if secret:
        _verify_stripe_signature(payload, request.headers.get("stripe-signature") or "", secret)
    elif not omega_config.allow_unsigned_stripe_webhook():
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")
    try:
        event = json.loads(payload.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Stripe webhook JSON: {e}") from e
    result = _apply_billing_event(event)
    return {"ok": True, **result}


@app.get("/jobs/{job_id}")
def get_research_job(job_id: str, user_id: AtlasUserId):
    job = research_jobs.get_job(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Research job not found")
    return {
        "ok": True,
        "job": job,
        "activity": research_jobs.activity_from_job(job),
        "route_decision": job.get("route_decision") or {},
    }


@app.post("/jobs/{job_id}/cancel")
def cancel_research_job(job_id: str, user_id: AtlasUserId):
    job = research_jobs.cancel_job(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Research job not found")
    return {"ok": True, "job": job, "activity": research_jobs.activity_from_job(job)}


@app.get("/auth")
def serve_auth():
    """Clean vanilla-JS sign-in page (no CDN dependencies that Edge blocks)."""
    if not ATLAS_AUTH.is_file():
        return _zenith_landing_response()
    return FileResponse(ATLAS_AUTH, media_type="text/html; charset=utf-8")


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


@app.get("/agents/status")
def agents_status(_user: AtlasUserId):
    """Filesystem-backed status of all R.A. Omega agent prompt directories."""
    return agent_audit.collect_agent_audit()


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
    loop = asyncio.get_running_loop()
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
    source_strictness: Optional[str] = Form(None),
    report_depth: Optional[str] = Form(None),
    citation_preference: Optional[str] = Form(None),
    compliance_level: Optional[str] = Form(None),
    research_job_id: Optional[str] = Form(None),
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
        source_strictness=(source_strictness or "").strip() or None,
        report_depth=(report_depth or "").strip() or None,
        citation_preference=(citation_preference or "").strip() or None,
        compliance_level=(compliance_level or "").strip() or None,
        research_job_id=(research_job_id or "").strip() or None,
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

    oai = bool(omega_config.openai_api_key())
    el = bool(omega_config.elevenlabs_api_key())

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


@app.post("/export/docx")
@app.post("/export/word")
def export_docx_payload(user_id: AtlasUserId, body: dict[str, Any] = Body(...)):
    """Persist POST /query-shaped JSON to atlas_vault/03-Outputs/Reports and return DOCX."""
    _ = user_id
    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="JSON object required")
    try:
        from atlas_export.build_docx import write_query_envelope_docx

        path = write_query_envelope_docx(body)
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"python-docx missing: {e}") from e
    except Exception as e:
        log.exception("[/export/docx]")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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


# ── Sandbox endpoints ─────────────────────────────────────────────────────────

@app.post("/sandbox/run")
async def sandbox_run(request: Request):
    """Run a sandbox batch: { n_queries, domains, sandboxes, dry_run }"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    n = int(body.get("n_queries", 3))
    domain = body.get("domains") or None
    if isinstance(domain, list):
        domain = domain[0] if domain else None
    dry_run = bool(body.get("dry_run", False))
    try:
        from atlas_sandbox.sandbox_loop import run_batch
        result = run_batch(n=n, domain=domain, dry_run=dry_run, verbose=False)
        return {"status": "ok", "approved": result["approved"], "total": result["batch_size"], "vault_total": result["vault_total"]}
    except Exception as exc:
        logger.error("Sandbox run error: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/sandbox/progress")
def sandbox_progress():
    """GET sandbox training vault progress."""
    try:
        from atlas_sandbox.sandbox_loop import PROGRESS_FILE, get_vault_count
        if PROGRESS_FILE.exists():
            import json as _json
            prog = _json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        else:
            count = get_vault_count()
            prog = {"vault_total": count, "target": 50000, "pct": round(count / 50000 * 100, 2)}
        return prog
    except Exception as exc:
        return {"vault_total": 0, "target": 50000, "pct": 0.0, "error": str(exc)}


@app.get("/sandbox/agent-health")
def sandbox_agent_health():
    """GET latest agent health report (or generate fresh if missing)."""
    try:
        from atlas_sandbox.sandbox_loop import AGENT_HEALTH_REPORT, run_agent_health
        if not AGENT_HEALTH_REPORT.exists():
            return run_agent_health()
        import json as _json
        return _json.loads(AGENT_HEALTH_REPORT.read_text(encoding="utf-8"))
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


# ── Vault endpoints ───────────────────────────────────────────────────────────

_VAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@app.post("/vault/upload")
async def vault_upload(
    user_id: AtlasUserId,
    file: UploadFile = File(..., description="Markdown (.md) or zip archive (.zip) of .md files"),
):
    """
    Upload an Obsidian vault or individual note.
    .md  → saved directly to atlas_vault/user_vaults/{user_id}/
    .zip → all .md files extracted to atlas_vault/user_vaults/{user_id}/
    """
    import zipfile as _zf
    from atlas_vault.obsidian_connector import save_vault_note, USER_VAULTS_DIR

    filename = (file.filename or "upload").lower()
    body = await file.read()

    if len(body) > _VAULT_MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    if not (filename.endswith(".md") or filename.endswith(".zip")):
        raise HTTPException(status_code=400, detail="Only .md and .zip files are accepted")

    vault_dir = USER_VAULTS_DIR / user_id
    vault_dir.mkdir(parents=True, exist_ok=True)

    files_indexed = 0

    if filename.endswith(".md"):
        ok = save_vault_note(user_id, file.filename or "upload.md", body.decode("utf-8", errors="replace"))
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to save note")
        files_indexed = 1
    else:
        import io as _io
        try:
            with _zf.ZipFile(_io.BytesIO(body)) as zf:
                for member in zf.infolist():
                    if member.filename.endswith(".md") and not member.is_dir():
                        md_bytes = zf.read(member.filename)
                        safe_name = Path(member.filename).name
                        ok = save_vault_note(
                            user_id, safe_name, md_bytes.decode("utf-8", errors="replace")
                        )
                        if ok:
                            files_indexed += 1
        except _zf.BadZipFile:
            raise HTTPException(status_code=400, detail="Corrupt or invalid zip file")

    total_notes = sum(1 for _ in vault_dir.rglob("*.md"))
    return {"files_indexed": files_indexed, "total_notes": total_notes, "status": "ok"}


@app.get("/vault/status")
def vault_status(user_id: AtlasUserId):
    """Return the current vault configuration and note count for this user."""
    from atlas_vault.obsidian_connector import USER_VAULTS_DIR

    vault_dir = USER_VAULTS_DIR / user_id
    vault_path_str = str(Path("atlas_vault") / "user_vaults" / user_id)

    if not vault_dir.exists():
        return {
            "vault_configured": False,
            "note_count": 0,
            "last_updated": None,
            "vault_path": vault_path_str,
        }

    md_files = list(vault_dir.rglob("*.md"))
    note_count = len(md_files)

    last_updated = None
    if md_files:
        latest_mtime = max(f.stat().st_mtime for f in md_files)
        last_updated = datetime.utcfromtimestamp(latest_mtime).isoformat() + "Z"

    return {
        "vault_configured": note_count > 0,
        "note_count": note_count,
        "last_updated": last_updated,
        "vault_path": vault_path_str,
    }


# ── Omega OS endpoints (read-only, no auth required for list endpoints) ───────

@app.get("/omega-os/audit")
def omega_os_audit_endpoint():
    """Return the current Four C audit scores for the Omega OS layer."""
    try:
        from omega_audit import run_audit
        return run_audit()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Audit failed: {exc}")


@app.get("/omega-os/skills")
def omega_os_skills_endpoint():
    """Return Level 1 skill list (name + description) for all Omega OS skills."""
    try:
        from omega_os_loader import list_skills
        return {"skills": list_skills()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Skills list failed: {exc}")


@app.get("/omega-os/connections")
def omega_os_connections_endpoint():
    """Return the connection registry summary."""
    try:
        from omega_connections import registry_summary
        return registry_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Connections registry failed: {exc}")


@app.get("/omega-os/cadence")
def omega_os_cadence_endpoint():
    """Return the cadence plan summary."""
    try:
        from omega_cadence import cadence_summary
        return cadence_summary()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cadence plan failed: {exc}")


@app.post("/omega-os/level-up")
async def omega_os_level_up_endpoint(request: Request):
    """
    Return level-up recommendations.
    Body (optional JSON): {"weekly_actions": ["ran company report 5x", ...]}
    """
    try:
        from omega_level_up import analyze
        body: dict = {}
        try:
            body = await request.json()
        except Exception:
            pass
        weekly_actions = body.get("weekly_actions", []) if isinstance(body, dict) else []
        return analyze(weekly_actions=weekly_actions)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Level-up analysis failed: {exc}")


@app.get("/omega-os/skill-select")
def omega_os_skill_select_endpoint(q: str = "", intent: str = "", output_mode: str = ""):
    """
    Return the selected skill for a query/intent/output_mode combination.
    Query params: q=<raw_query>, intent=<intent>, output_mode=<output_mode>
    Never routes — this is synthesis-time context selection only.
    """
    try:
        from omega_os_loader import select_skill, load_relevant_context, _INTENT_CONTEXT_MAP
        skill = select_skill(q, intent, output_mode)
        context_files = _INTENT_CONTEXT_MAP.get(intent, ["preferences.md"])
        if skill:
            context_files = list(context_files) + [f"skills/{skill}/skill.md"]
        return {
            "selected_skill": skill,
            "context_files_used": context_files,
            "intent": intent,
            "output_mode": output_mode,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Skill select failed: {exc}")


@app.get("/omega-os/sec-filings/{company}")
def omega_os_sec_filings_endpoint(company: str):
    """
    Return recent SEC EDGAR filings for a company name or ticker.
    Only available when SEC_USER_AGENT is configured in the environment.
    Returns: cik, sec_filings_used, latest_10k, latest_10q, latest_8k, filing_context
    """
    try:
        from omega_sec_edgar import get_filing_summary, is_available
        if not is_available():
            return {
                "available": False,
                "message": "Set SEC_USER_AGENT in .env to activate SEC EDGAR integration. Format: 'App Name contact@yourdomain.com'",
                "sec_filings_used": False,
            }
        result = get_filing_summary(company)
        result["available"] = True
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SEC EDGAR lookup failed: {exc}")


# ── Omega OS — Persistence endpoints ─────────────────────────────────────────

@app.get("/omega-os/persistence/status")
def omega_os_persistence_status():
    """Return persistence layer status (mode, counts, runtime dir)."""
    try:
        from omega_persistence import get_persistence_status
        return get_persistence_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Persistence status failed: {exc}")


@app.get("/omega-os/reports/recent")
def omega_os_recent_reports(limit: int = 10):
    """Return recent report metadata, newest first (max 100)."""
    try:
        from omega_persistence import get_recent_reports
        return {"reports": get_recent_reports(limit=limit), "limit": limit}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Recent reports failed: {exc}")


@app.get("/omega-os/research-queue")
def omega_os_research_queue(limit: int = 10):
    """Return queued research tasks, highest priority first (max 100)."""
    try:
        from omega_persistence import get_research_queue
        return {"tasks": get_research_queue(limit=limit), "limit": limit}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research queue failed: {exc}")


@app.post("/omega-os/research-task")
async def omega_os_create_research_task(request: Request):
    """
    Queue a research task.
    Body: {query (required), intent?, company?, ticker?, priority?, session_id?, notes?}
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Request body must be valid JSON")
    if not body.get("query"):
        raise HTTPException(status_code=422, detail="'query' field is required")
    try:
        from omega_persistence import save_research_task
        record = save_research_task(body)
        return {"task": record, "status": "queued"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Research task save failed: {exc}")


# ── Omega OS — Google Workspace export endpoints ──────────────────────────────

@app.get("/omega-os/google-workspace/status")
def omega_os_google_workspace_status():
    """Return Google Workspace integration status (configured, missing vars, available ops)."""
    try:
        from omega_google_workspace import get_google_workspace_status
        return get_google_workspace_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Google Workspace status failed: {exc}")


@app.post("/omega-os/export-report")
async def omega_os_export_report(request: Request):
    """
    Export a report to Google Workspace (Docs and/or Sheets).
    Body: {report_id (required), formats?: ["doc","sheet"]}
    Returns not_configured when Google credentials are absent — never crashes.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=422, detail="Request body must be valid JSON")
    if not body.get("report_id"):
        raise HTTPException(status_code=422, detail="'report_id' field is required")
    try:
        from omega_google_workspace import export_report_bundle
        formats = body.get("formats", ["doc", "sheet"])
        result = export_report_bundle(report_id=body["report_id"], formats=formats)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export report failed: {exc}")


@app.get("/omega-os/dashboard")
def omega_os_dashboard():
    """
    Return a full Command Center snapshot aggregating all Omega OS subsystems.
    Degrades gracefully — all subsystem failures produce empty/default values.
    No credentials required.
    """
    try:
        from omega_dashboard import build_command_center_snapshot
        return build_command_center_snapshot()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dashboard snapshot failed: {exc}")


@app.get("/omega-os/brain")
def omega_os_brain():
    """
    Return a Brain snapshot describing Omega OS knowledge state.
    Includes context files, decisions, skills, memory files, and recommended questions.
    No credentials required.
    """
    try:
        from omega_dashboard import build_omega_brain_snapshot
        return build_omega_brain_snapshot()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Brain snapshot failed: {exc}")


# ── Capture inbox ─────────────────────────────────────────────────────────────

@app.get("/omega-os/capture/status")
def capture_status_endpoint():
    """Return capture inbox status (counts by type/source). No credentials required."""
    try:
        from omega_capture import get_capture_status
        return get_capture_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Capture status failed: {exc}")


@app.get("/omega-os/capture/inbox")
def capture_inbox_endpoint(limit: int = 20):
    """Return recent unprocessed captures (status=inbox), newest first."""
    try:
        from omega_capture import get_capture_inbox
        return {"captures": get_capture_inbox(limit=limit)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Capture inbox failed: {exc}")


@app.post("/omega-os/capture")
async def capture_save_endpoint(request: Request):
    """
    Manually save a text capture to the inbox.

    Body: {"text": "...", "source": "web", "metadata": {...}}
    """
    try:
        from omega_capture import save_capture
        body: dict = {}
        try:
            body = await request.json()
        except Exception:
            pass
        text = str(body.get("text", "")).strip()
        if not text:
            raise HTTPException(status_code=400, detail="'text' field is required")
        source   = str(body.get("source", "web"))[:50]
        metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        capture  = save_capture(raw_text=text, source=source, metadata=metadata)
        return {"status": "captured", "capture": capture}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Capture save failed: {exc}")


@app.post("/omega-os/capture/{capture_id}/triage")
def capture_triage_endpoint(capture_id: str):
    """Mark a capture as triaged."""
    try:
        from omega_capture import triage_capture
        result = triage_capture(capture_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Triage failed: {exc}")


# ── Telegram adapter ──────────────────────────────────────────────────────────

@app.get("/omega-os/telegram/status")
def telegram_status_endpoint():
    """Return Telegram adapter status. No credentials required — returns not_configured when missing."""
    try:
        from omega_telegram import get_telegram_status
        return get_telegram_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Telegram status failed: {exc}")


@app.post("/omega-os/telegram/webhook")
async def telegram_webhook_endpoint(request: Request):
    """
    Receive Telegram webhook updates.

    Routes text messages to the capture inbox.
    Rejects unauthorized user IDs silently (returns 200 to avoid Telegram retries).
    Voice messages fail safely when not configured.
    """
    try:
        from omega_telegram import (
            is_telegram_configured,
            normalize_telegram_message,
            process_telegram_text_message,
            process_telegram_voice_message,
        )

        if not is_telegram_configured():
            # Return 200 so Telegram doesn't retry; log the misconfiguration
            return {"ok": False, "status": "not_configured"}

        payload: dict = {}
        try:
            payload = await request.json()
        except Exception:
            return {"ok": False, "status": "invalid_payload"}

        msg = normalize_telegram_message(payload)
        message_type = msg.get("message_type", "invalid")

        if message_type == "text":
            result = process_telegram_text_message(payload)
        elif message_type in ("voice", "audio"):
            result = process_telegram_voice_message(payload)
        else:
            result = {"status": "ignored", "message_type": message_type}

        return {"ok": True, "result": result}

    except Exception as exc:
        # Never 500 a Telegram webhook — Telegram will retry on errors
        return {"ok": False, "status": "error", "detail": str(exc)}


# ── Dev entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print()
    print("  Zenith / auth:          http://127.0.0.1:8000/  ·  http://127.0.0.1:8000/auth")
    print("  Main chat:              http://127.0.0.1:8000/app")
    print("  Dashboard:              http://127.0.0.1:8000/dashboard")
    print("  Health:                 http://127.0.0.1:8000/health")
    print()
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
