#!/usr/bin/env python3
"""
Context-Aware Algorithmic Research Agent  — ATLAS v3
------------------------------------------------------
Layers:
  1) HTML-driven ticker extraction (Tier 1 Catalysts + Options Trading)
  2) Daily macro DEEP RESEARCH @ 07:00 local → Gemini multi-step → daily_sentiment.json
  3) Intraday tactical loop every 15 min → multi-expiry options scan → LIVE_DASHBOARD.html
  4) Robinhood positions (read-only) — stocks + options, joint + individual, labeled
     • Auth: direct requests against Robinhood REST API — NO robin_stocks dependency
     • Token cached to ~/.tokens/robinhood_atlas.json; phone approval required on first run only

WHAT'S NEW in v3:
  • Robinhood: replaced robin_stocks with direct requests (device challenge + token refresh)
  • Multi-expiry scan: checks 21 DTE, 30 DTE, 45 DTE, 60 DTE per ticker, picks best strike
  • Deep research: multi-step Gemini pipeline (news → SEC → macro → synthesis) like ChatGPT
    deep research — runs each ticker independently then synthesises a master recommendation

Environment (.env next to this file):
  GOOGLE_API_KEY                       — required for Gemini
  GEMINI_MODEL                         — optional, default gemini-2.5-flash
  ROBINHOOD_USERNAME                   — Robinhood login email
  ROBINHOOD_PASSWORD                   — Robinhood password
  ROBINHOOD_MFA_CODE                   — optional 6-digit TOTP if MFA enabled
  ROBINHOOD_CHALLENGE_CODE             — optional SMS/email code (rare fallback)
  ROBINHOOD_JOINT_ACCOUNT_NUMBER       — substring match for joint account URL
  ROBINHOOD_JOINT_ACCOUNT_NUMBERS      — comma-separated (alternative)
  ROBINHOOD_INDIVIDUAL_ACCOUNT_NUMBER  — substring match for individual account URL
  ROBINHOOD_INDIVIDUAL_ACCOUNT_NUMBERS — comma-separated (alternative)
  ROBINHOOD_POSITIONS_ACCOUNT_FILTER   — all | joint | individual (default all)
  ROBINHOOD_DEVICE_POLL_SEC            — seconds to wait for app approval (default 180)
  ROBINHOOD_DEVICE_POLL_INTERVAL_SEC   — poll tick interval (default 3)
  MARKET_TZ                            — timezone (default America/New_York)
  OPTIONS_DTE_LIST                     — comma-separated DTE values to scan (default 21,30,45,60)
  MAX_ASK_PER_SHARE                    — max call ask price per share (default 0.50)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import schedule
import yfinance as yf
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from gemini_limiter import wait_for_slot

try:
    from google import genai
except ImportError:
    genai = None  # type: ignore

try:
    import robin_stocks.robinhood as rh
except ImportError:
    rh = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────────────
# Paths & constants
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR            = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")
load_dotenv()

TEMPLATE_HTML         = SCRIPT_DIR / "stock_research_v3.html"
OUTPUT_HTML           = SCRIPT_DIR / "LIVE_DASHBOARD.html"
DAILY_SENTIMENT_JSON  = SCRIPT_DIR / "daily_sentiment.json"
KILL_SWITCH_STATE_JSON= SCRIPT_DIR / "kill_switch_state.json"
TOKEN_CACHE_PATH      = Path.home() / ".tokens" / "robinhood_atlas.json"

# Options scan config — override via env
MAX_ASK_PER_SHARE     = float(os.environ.get("MAX_ASK_PER_SHARE", "0.50"))
_dte_raw              = os.environ.get("OPTIONS_DTE_LIST", "21,30,45,60")
DTE_LIST: list[int]   = [int(x.strip()) for x in _dte_raw.split(",") if x.strip().isdigit()]
if not DTE_LIST:
    DTE_LIST = [21, 30, 45, 60]

MARKET_TZ_NAME        = os.environ.get("MARKET_TZ", "America/New_York")
KILL_WINDOW_START     = (9, 30)
KILL_WINDOW_END       = (10, 15)
PREMIUM_DROP_THRESHOLD= 0.20
FLAT_EPSILON          = 0.002
GEMINI_MODEL          = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Robinhood — public OAuth client_id (same as Robinhood mobile app)
RH_CLIENT_ID          = "c82SH0WZOsabOXGP2sxqcj34FxkvfnWRZBKlBjFS"
RH_BASE               = "https://api.robinhood.com"
RH_OAUTH_URL          = f"{RH_BASE}/oauth2/token/"

_RH_SESSION           = requests.Session()
_RH_SESSION.headers.update({
    "Content-Type":            "application/json",
    "Accept":                  "application/json",
    # Keep User-Agent close to current Robinhood iOS app to avoid 400 rejections
    "User-Agent":              "Robinhood/24.22.0 (iPhone; iOS 17.5.1; Scale/3.00)",
    "X-Robinhood-API-Version": "1.431.4",
    "X-TimeZone-Id":           "America/New_York",
})

_rh_logged_in: bool       = False
_rh_access_token: str|None= None


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Small helpers
# ─────────────────────────────────────────────────────────────────────────────
def slugify_symbol(sym: str) -> str:
    return sym.upper().strip().replace(".", "-").lower()


def safe_read_template() -> str:
    try:
        return TEMPLATE_HTML.read_text(encoding="utf-8")
    except OSError:
        logging.exception("Failed reading template HTML: %s", TEMPLATE_HTML)
        raise


def safe_write_dashboard(html: str) -> None:
    try:
        OUTPUT_HTML.write_text(html, encoding="utf-8")
        logging.info("Wrote dashboard → %s", OUTPUT_HTML)
    except OSError:
        logging.exception("Failed writing LIVE_DASHBOARD.html")
        raise


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return f if f == f else None  # NaN guard
    except (ValueError, TypeError):
        return None


def fmt_money(x: float | None, empty: str = "—") -> str:
    return f"${x:,.2f}" if x is not None else empty


def fmt_pct(x: float | None, empty: str = "—") -> str:
    return f"{x:+.2f}%" if x is not None else empty


def parse_gemini_json_blob(text: str) -> dict | None:
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", t)
        t = re.sub(r"\s*```\s*$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", t)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Robinhood — account-number helpers
# ─────────────────────────────────────────────────────────────────────────────
def _rh_csv_account_tokens(*env_keys: str) -> list[str]:
    parts: list[str] = []
    for key in env_keys:
        raw = os.environ.get(key, "").strip()
        if raw:
            parts.extend(x.strip() for x in raw.split(",") if x.strip())
    seen: set[str] = set()
    out: list[str] = []
    for m in parts:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _rh_joint_markers() -> list[str]:
    m = _rh_csv_account_tokens("ROBINHOOD_JOINT_ACCOUNT_NUMBERS", "ROBINHOOD_JOINT_ACCOUNT_NUMBER")
    return m if m else ["116292414707"]  # legacy default


def _rh_individual_markers() -> list[str]:
    return _rh_csv_account_tokens(
        "ROBINHOOD_INDIVIDUAL_ACCOUNT_NUMBERS", "ROBINHOOD_INDIVIDUAL_ACCOUNT_NUMBER"
    )


def _is_joint(acct_url: str) -> bool:
    if any(m in acct_url for m in _rh_joint_markers()):
        return True
    if any(m in acct_url for m in _rh_individual_markers()):
        return False
    return False


def _keep_acct(acct_url: str) -> bool:
    filt = os.environ.get("ROBINHOOD_POSITIONS_ACCOUNT_FILTER", "all").strip().lower()
    if filt in ("", "all"):
        return True
    joint = _is_joint(acct_url)
    if filt == "joint":
        return joint
    if filt == "individual":
        return not joint
    logging.warning("Unknown ROBINHOOD_POSITIONS_ACCOUNT_FILTER=%r — using all.", filt)
    return True


def _acct_label(acct_url: str) -> str:
    return "joint" if _is_joint(acct_url) else "individual"


# ─────────────────────────────────────────────────────────────────────────────
# Robinhood — token cache
# ─────────────────────────────────────────────────────────────────────────────
def _device_token() -> str:
    TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    cache = _load_token_cache()
    if "device_token" in cache:
        return cache["device_token"]
    token = str(uuid.uuid4())
    cache["device_token"] = token
    _save_token_cache(cache)
    return token


def _load_token_cache() -> dict:
    if TOKEN_CACHE_PATH.is_file():
        try:
            return json.loads(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            logging.warning("Token cache unreadable — starting fresh.")
    return {}


def _save_token_cache(data: dict) -> None:
    TOKEN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        TOKEN_CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        logging.warning("Could not persist token cache.", exc_info=True)


def _rh_set_auth(access_token: str) -> None:
    global _rh_access_token
    _rh_access_token = access_token
    _RH_SESSION.headers["Authorization"] = f"Bearer {access_token}"


def _rh_try_refresh(refresh_token: str, device_token: str) -> bool:
    payload = {
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
        "client_id":     RH_CLIENT_ID,
        "device_token":  device_token,
        "scope":         "internal",
    }
    try:
        r = _RH_SESSION.post(RH_OAUTH_URL, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            if "access_token" in data:
                _rh_set_auth(data["access_token"])
                cache = _load_token_cache()
                cache.update({
                    "access_token":  data["access_token"],
                    "refresh_token": data.get("refresh_token", refresh_token),
                    "token_type":    data.get("token_type", "Bearer"),
                })
                _save_token_cache(cache)
                logging.info("Robinhood: token refreshed from cache (no phone needed).")
                return True
    except Exception:
        logging.debug("Refresh attempt exception.", exc_info=True)
    return False


def _rh_password_login(username: str, password: str, device_token: str) -> None:
    """
    Full OAuth password grant — handles MFA, verification_workflow (approve in app),
    and legacy challenge (SMS/email code).
    Writes tokens to cache and sets auth on success.
    Raises RuntimeError on failure.
    """
    mfa_code = os.environ.get("ROBINHOOD_MFA_CODE", "").strip()
    payload: dict[str, Any] = {
        "client_id":                      RH_CLIENT_ID,
        "grant_type":                     "password",
        "username":                       username,
        "password":                       password,
        "device_token":                   device_token,
        "scope":                          "internal",
        "expires_in":                     86400,
        # Required by newer Robinhood API versions (avoids HTTP 400 "Update to newest version")
        "try_passkeys":                   False,
        "token_request_path":             "/login",
        "create_read_only_secondary_token": True,
    }
    if mfa_code:
        payload["mfa_code"] = mfa_code

    r    = _RH_SESSION.post(RH_OAUTH_URL, json=payload, timeout=30)
    logging.debug("RH OAuth status=%s body=%s", r.status_code, r.text[:600])

    # Robinhood sometimes returns non-JSON on certain errors
    try:
        data = r.json()
    except Exception:
        data = {}

    # ── Log full response if something looks wrong ────────────────────────────
    if r.status_code not in (200, 201) and not any(
        k in data for k in ("mfa_required", "verification_workflow", "challenge", "access_token")
    ):
        logging.error(
            "Robinhood OAuth HTTP %s — full response: %s",
            r.status_code, r.text[:800] or "(empty body)"
        )

    # ── MFA required ──────────────────────────────────────────────────────────
    if data.get("mfa_required"):
        if not mfa_code:
            raise RuntimeError(
                "Robinhood requires MFA.  Add ROBINHOOD_MFA_CODE=<6-digit-code> to .env and retry."
            )
        payload["mfa_code"] = mfa_code
        r    = _RH_SESSION.post(RH_OAUTH_URL, json=payload, timeout=30)
        data = r.json()
        if r.status_code != 200 or "access_token" not in data:
            raise RuntimeError("Robinhood MFA rejected.  Check ROBINHOOD_MFA_CODE.")

    # ── Approve in app (verification_workflow) ────────────────────────────────
    elif data.get("verification_workflow"):
        wf    = data["verification_workflow"]
        wf_id = wf.get("id") if isinstance(wf, dict) else wf
        poll  = int(os.environ.get("ROBINHOOD_DEVICE_POLL_SEC", "180"))
        tick  = float(os.environ.get("ROBINHOOD_DEVICE_POLL_INTERVAL_SEC", "3"))
        logging.info(
            "📲  Open the Robinhood app → Account → Security → Approve this login.\n"
            "    Waiting up to %d seconds ...", poll
        )
        deadline = time.time() + poll
        approved = False
        while time.time() < deadline:
            time.sleep(tick)
            try:
                cr = _RH_SESSION.get(
                    f"{RH_BASE}/pathfinder/verification_workflow/{wf_id}/", timeout=20
                )
                status = (cr.json().get("status") or cr.json().get("state") or "").lower()
                if status in ("approved", "completed"):
                    approved = True
                    break
            except Exception:
                pass
        if not approved:
            raise RuntimeError(
                f"Device approval timed out after {poll}s.  "
                "Approve in Robinhood app, or increase ROBINHOOD_DEVICE_POLL_SEC."
            )
        r    = _RH_SESSION.post(RH_OAUTH_URL, json=payload, timeout=30)
        data = r.json()

    # ── Legacy challenge (SMS / email code) ───────────────────────────────────
    elif "challenge" in data:
        challenge_id = data["challenge"]["id"]
        code = os.environ.get("ROBINHOOD_CHALLENGE_CODE", "").strip()
        if code:
            logging.info("Submitting ROBINHOOD_CHALLENGE_CODE ...")
            _RH_SESSION.post(
                f"{RH_BASE}/challenge/{challenge_id}/respond/",
                json={"response": code}, timeout=20
            )
        else:
            poll = int(os.environ.get("ROBINHOOD_DEVICE_POLL_SEC", "180"))
            tick = float(os.environ.get("ROBINHOOD_DEVICE_POLL_INTERVAL_SEC", "3"))
            logging.info(
                "📲  Robinhood sent a challenge code to your phone/email.\n"
                "    Set ROBINHOOD_CHALLENGE_CODE=<code> in .env and restart, OR\n"
                "    approve on your Robinhood app.  Waiting %d seconds ...", poll
            )
            deadline  = time.time() + poll
            confirmed = False
            while time.time() < deadline:
                time.sleep(tick)
                try:
                    cr = _RH_SESSION.get(f"{RH_BASE}/challenge/{challenge_id}/", timeout=20)
                    st = cr.json().get("challenge", {}).get("status", "").lower()
                    if st in ("validated", "approved"):
                        confirmed = True
                        break
                except Exception:
                    pass
            if not confirmed:
                raise RuntimeError(
                    f"Challenge timed out after {poll}s.  "
                    "Set ROBINHOOD_CHALLENGE_CODE or increase ROBINHOOD_DEVICE_POLL_SEC."
                )
        _RH_SESSION.headers["X-ROBINHOOD-CHALLENGE-RESPONSE-ID"] = challenge_id
        r    = _RH_SESSION.post(RH_OAUTH_URL, json=payload, timeout=30)
        data = r.json()

    # ── Validate ──────────────────────────────────────────────────────────────
    if "access_token" not in data:
        # Log the FULL Robinhood error so we know exactly what happened
        import json as _json
        full_err = _json.dumps(data, default=str)[:1000]
        detail = (
            data.get("detail")
            or data.get("error_description")
            or (data.get("non_field_errors") or [""])[0]
            or full_err
        )
        logging.error("Robinhood RAW error response: %s", full_err)
        raise RuntimeError(f"Robinhood login failed: {detail}")

    _rh_set_auth(data["access_token"])
    cache = _load_token_cache()
    cache.update({
        "access_token":  data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "token_type":    data.get("token_type", "Bearer"),
        "device_token":  device_token,
        "username":      username,
    })
    _save_token_cache(cache)
    logging.info("Robinhood: password login successful.")


def robinhood_login() -> bool:
    """
    Authenticate once per process using robin_stocks' own login() flow.
    robin_stocks handles pickle caching, verification_workflow (approve in app),
    and challenge codes automatically.
    """
    global _rh_logged_in
    if _rh_logged_in:
        return True
    if rh is None:
        logging.warning("robin_stocks not available — Robinhood data skipped.")
        return False

    username = os.environ.get("ROBINHOOD_USERNAME", "").strip()
    password = os.environ.get("ROBINHOOD_PASSWORD", "").strip()
    if not username or not password:
        logging.warning(
            "ROBINHOOD_USERNAME / ROBINHOOD_PASSWORD not in .env — Robinhood data skipped."
        )
        return False

    mfa_code = os.environ.get("ROBINHOOD_MFA_CODE", "").strip() or None

    try:
        import io, contextlib, glob as _glob, pathlib as _pathlib
        logging.info("Logging into Robinhood as %s ...", username)

        # Delete any stale pickle so we always get a fresh session with all accounts.
        # robin_stocks stores tokens in ~/.tokens/robinhood.pickle (or similar).
        for _pkl in _glob.glob(str(_pathlib.Path.home() / ".tokens" / "*.pickle")):
            try:
                _pathlib.Path(_pkl).unlink()
                logging.debug("Deleted stale session pickle: %s", _pkl)
            except Exception:
                pass

        buf = io.StringIO()
        # rh.login() prints status to stdout; capture and re-emit via logging
        with contextlib.redirect_stdout(buf):
            result = rh.login(username=username, password=password,
                              mfa_code=mfa_code, store_session=True)
        for line in buf.getvalue().splitlines():
            if line.strip():
                logging.info("RH: %s", line.strip())

        if result and isinstance(result, dict) and "access_token" in result:
            _rh_logged_in = True
            logging.info("Robinhood login successful.")
            # Sync the auth token from robin_stocks' session into _RH_SESSION
            # so our own _rh_paginated calls also work.
            try:
                from robin_stocks.robinhood.globals import SESSION as _rs_session
                auth_header = _rs_session.headers.get("Authorization", "")
                if auth_header:
                    _RH_SESSION.headers["Authorization"] = auth_header
                    logging.debug("Synced RH auth token to _RH_SESSION.")
            except Exception:
                logging.debug("Could not sync auth header from robin_stocks session.", exc_info=True)
            return True
        else:
            logging.error(
                "Robinhood login failed — unexpected result: %s",
                str(result)[:300]
            )
            logging.error(
                "Tips:\n"
                "  • First run: open the Robinhood app and approve the device login prompt.\n"
                "  • If MFA is on: add ROBINHOOD_MFA_CODE=<6-digit-code> to .env.\n"
                "  • If SMS code arrives: enter it when the script prompts, or add\n"
                "    ROBINHOOD_CHALLENGE_CODE=<code> to .env and re-run."
            )
            return False
    except Exception as exc:
        logging.error("Robinhood login exception: %s", exc)
        logging.error(
            "Tips:\n"
            "  • First run: open the Robinhood app and approve the device login prompt.\n"
            "  • If MFA is on: add ROBINHOOD_MFA_CODE=<6-digit-code> to .env."
        )
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Robinhood — REST helpers
# ─────────────────────────────────────────────────────────────────────────────
def _rh_session():
    """Return robin_stocks' own authenticated session (has all cookies + headers)."""
    try:
        from robin_stocks.robinhood.globals import SESSION as _rs_session
        return _rs_session
    except Exception:
        return _RH_SESSION


def _rh_paginated(url: str, params: dict | None = None) -> list[dict]:
    session = _rh_session()
    results: list[dict] = []
    next_url: str | None = url
    while next_url:
        try:
            r = session.get(
                next_url, params=params if next_url == url else None, timeout=30
            )
            r.raise_for_status()
            data = r.json()
        except Exception:
            logging.exception("_rh_paginated failed at %s", next_url)
            break
        results.extend(data.get("results") or [])
        next_url = data.get("next")
    return results


def _rh_get(url: str, params: dict | None = None) -> dict | list | None:
    try:
        r = _rh_session().get(url, params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        logging.exception("_rh_get failed: %s", url)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class RobinhoodPosition:
    symbol:                 str
    option_type:            str
    strike:                 float | None
    expiration:             str | None
    quantity:               float
    average_price:          float | None
    current_price:          float | None
    current_contract_value: float | None
    pnl:                    float | None
    pnl_pct:                float | None
    chain_symbol:           str
    account_type:           str   # 'joint' or 'individual'


@dataclass
class RobinhoodStockHolding:
    symbol:            str   # "AAPL (joint)"
    ticker:            str   # "AAPL"
    quantity:          float
    average_buy_price: float | None
    current_price:     float | None
    market_value:      float | None
    pnl:               float | None
    pnl_pct:           float | None
    account_type:      str


# ─────────────────────────────────────────────────────────────────────────────
# Robinhood — fetch option positions
# ─────────────────────────────────────────────────────────────────────────────
def _rh_discover_account_urls() -> list[str]:
    """
    Query /accounts/ to get all account URLs.
    Logs the full raw structure so we can see exactly what Robinhood returns.
    """
    try:
        session = _rh_session()
        r = session.get(f"{RH_BASE}/accounts/", timeout=30)
        r.raise_for_status()
        data = r.json()

        # Log the full raw structure at DEBUG level (truncated)
        import json as _json
        raw_text = _json.dumps(data, indent=2)
        logging.debug("Raw /accounts/ response (%d bytes):\n%s", len(raw_text),
                      raw_text[:4000])

        urls: list[str] = []

        # Standard paginated structure: {"results": [...]}
        results = data.get("results") or []
        if isinstance(data, list):
            results = data  # top-level list

        for acct in results:
            url = acct.get("url") or ""
            if url and url not in urls:
                urls.append(url)
            logging.info(
                "  Account: url=%s  number=%s  type=%s  deactivated=%s",
                url,
                acct.get("account_number", acct.get("number", "?")),
                acct.get("type", "?"),
                acct.get("deactivated", "?"),
            )

        # Some Robinhood responses have extra top-level keys with account data
        for key, val in (data.items() if isinstance(data, dict) else []):
            if key in ("results", "next", "previous"):
                continue
            if isinstance(val, dict) and val.get("url"):
                url = val["url"]
                if url not in urls:
                    urls.append(url)
                    logging.info("  Extra account key '%s': url=%s", key, url)

        if not urls:
            logging.warning("No account URLs found — raw keys: %s",
                            list(data.keys()) if isinstance(data, dict) else type(data))
        return urls
    except Exception:
        logging.exception("Could not discover account URLs from /accounts/")
        return []


def _rh_fetch_all_positions(endpoint_suffix: str, params: dict | None = None) -> list[dict]:
    """
    Fetch positions from every account discovered at /accounts/,
    then de-duplicate by position URL.  Falls back to the generic endpoint.
    endpoint_suffix: e.g. 'positions/' or 'options/positions/'
    """
    all_rows: list[dict] = []
    seen_pos_urls: set[str] = set()

    acct_urls = _rh_discover_account_urls()
    for acct_url in acct_urls:
        pos_url = acct_url.rstrip("/") + "/" + endpoint_suffix
        rows = _rh_paginated(pos_url, params)
        logging.info("  %s → %d row(s)", pos_url, len(rows))
        for r in rows:
            key = r.get("url") or str(r)
            if key not in seen_pos_urls:
                seen_pos_urls.add(key)
                all_rows.append(r)

    # Always also try the generic endpoint — it may return accounts not listed above
    generic_url = f"{RH_BASE}/{endpoint_suffix}"
    rows = _rh_paginated(generic_url, params)
    logging.info("  Generic %s → %d row(s)", generic_url, len(rows))
    for r in rows:
        key = r.get("url") or str(r)
        if key not in seen_pos_urls:
            seen_pos_urls.add(key)
            all_rows.append(r)

    return all_rows


def _load_manual_stock_holdings() -> list[RobinhoodStockHolding]:
    """
    Read RH_MANUAL_STOCKS from .env and return synthetic holding objects.
    Format: TICKER:QTY:AVG_BUY_PRICE  (comma-separated entries)
    Example: SOUN:50:8.75,BBAI:100:3.50,IONQ:25:42.00
    Prices are fetched live from yfinance.
    """
    raw = os.environ.get("RH_MANUAL_STOCKS", "").strip()
    if not raw:
        return []

    entries = [e.strip() for e in raw.split(",") if e.strip()]
    parsed: list[tuple[str, float, float | None]] = []
    for entry in entries:
        parts = entry.split(":")
        if len(parts) < 2:
            logging.warning("RH_MANUAL_STOCKS: bad entry '%s' — expected TICKER:QTY[:AVG]", entry)
            continue
        ticker   = parts[0].upper().strip()
        qty      = _safe_float(parts[1]) or 0.0
        avg_buy  = _safe_float(parts[2]) if len(parts) >= 3 else None
        if qty > 0:
            parsed.append((ticker, qty, avg_buy))

    if not parsed:
        return []

    logging.info("Manual stock holdings: %d entry/entries from RH_MANUAL_STOCKS", len(parsed))

    # Fetch live quotes
    tickers_uniq = sorted({t for t, _, _ in parsed})
    quote_map: dict[str, float | None] = {}
    try:
        for sym in tickers_uniq:
            fi = getattr(yf.Ticker(sym), "fast_info", {}) or {}
            quote_map[sym] = _safe_float(
                fi.get("last_price") or fi.get("regular_market_price")
            )
    except Exception:
        logging.exception("Live quote fetch failed for manual stocks.")

    holdings: list[RobinhoodStockHolding] = []
    for ticker, qty, avg_buy in parsed:
        current_price = quote_map.get(ticker)
        market_value = round(current_price * qty, 2) if current_price else None
        pnl = pnl_pct = None
        if market_value is not None and avg_buy is not None:
            cost = avg_buy * qty
            pnl = round(market_value - cost, 2)
            pnl_pct = round(pnl / cost * 100, 2) if cost > 0 else None
        holdings.append(RobinhoodStockHolding(
            symbol=f"{ticker} (joint)",
            ticker=ticker,
            quantity=qty,
            average_buy_price=avg_buy,
            current_price=current_price,
            market_value=market_value,
            pnl=pnl,
            pnl_pct=pnl_pct,
            account_type="joint",
        ))
        logging.info("  Manual stock: %s qty=%s avg=%s current=%s pnl=%s",
                     ticker, qty, avg_buy, current_price, fmt_money(pnl))
    return holdings


def _load_manual_option_positions() -> list[RobinhoodPosition]:
    """
    Read RH_MANUAL_OPTIONS from .env and return synthetic position objects.
    Format: TICKER:call|put:STRIKE:EXPIRY:QTY:AVG_PRICE  (comma-separated)
    Example: SOUN:call:8.00:2026-05-16:1:1.50
    """
    raw = os.environ.get("RH_MANUAL_OPTIONS", "").strip()
    if not raw:
        return []

    entries = [e.strip() for e in raw.split(",") if e.strip()]
    positions: list[RobinhoodPosition] = []
    for entry in entries:
        parts = entry.split(":")
        if len(parts) < 5:
            logging.warning("RH_MANUAL_OPTIONS: bad entry '%s' — need TICKER:type:STRIKE:EXPIRY:QTY[:AVG]", entry)
            continue
        ticker      = parts[0].upper().strip()
        option_type = parts[1].lower().strip()
        strike      = _safe_float(parts[2])
        expiration  = parts[3].strip()
        qty         = _safe_float(parts[4]) or 0.0
        avg_price   = _safe_float(parts[5]) if len(parts) >= 6 else None
        if qty <= 0:
            continue

        current_price = current_contract_value = pnl = pnl_pct = None
        # Try to get live mark from yfinance
        try:
            import datetime as _dt
            exp_dt = _dt.date.fromisoformat(expiration)
            tk = yf.Ticker(ticker)
            chain = tk.option_chain(expiration)
            df = chain.calls if option_type == "call" else chain.puts
            row = df[df["strike"] == strike] if strike and not df.empty else None
            if row is not None and not row.empty:
                current_price = _safe_float(row.iloc[0].get("lastPrice") or row.iloc[0].get("bid"))
        except Exception:
            pass

        if current_price is not None:
            current_contract_value = round(current_price * 100 * qty, 2)
            if avg_price is not None:
                cost = avg_price * 100 * qty
                pnl = round(current_contract_value - cost, 2)
                pnl_pct = round(pnl / cost * 100, 2) if cost > 0 else None

        positions.append(RobinhoodPosition(
            symbol=f"{ticker} (joint)",
            option_type=option_type,
            strike=strike,
            expiration=expiration,
            quantity=qty,
            average_price=avg_price,
            current_price=current_price,
            current_contract_value=current_contract_value,
            pnl=pnl,
            pnl_pct=pnl_pct,
            chain_symbol=ticker,
            account_type="joint",
        ))
        logging.info("  Manual option: %s %s strike=%s exp=%s qty=%s avg=%s pnl=%s",
                     ticker, option_type, strike, expiration, qty, avg_price, fmt_money(pnl))
    return positions


def fetch_robinhood_positions() -> list[RobinhoodPosition]:
    # Manual override takes priority — API is fallback
    manual = _load_manual_option_positions()
    if manual:
        logging.info("Using manual option positions (%d) from RH_MANUAL_OPTIONS.", len(manual))
        return manual

    if not robinhood_login():
        return []
    logging.info("Fetching Robinhood open option positions ...")
    raw_list = _rh_fetch_all_positions("options/positions/", params={"nonzero": "true"})
    if not raw_list:
        logging.info("Robinhood: no open option positions.")
        return []

    logging.info("Options raw rows: %d", len(raw_list))
    positions: list[RobinhoodPosition] = []
    for pos in raw_list:
        try:
            qty = _safe_float(pos.get("quantity")) or 0.0
            if qty <= 0:
                continue
            acct_url = pos.get("account") or ""
            if not _keep_acct(acct_url):
                continue

            acct_type    = _acct_label(acct_url)
            chain_symbol = (pos.get("chain_symbol") or "").upper().strip()
            avg_price    = _safe_float(pos.get("average_price"))

            # Resolve instrument for strike/expiry/type
            instrument: dict = {}
            inst_url = pos.get("option") or ""
            if inst_url:
                d = _rh_get(inst_url)
                if isinstance(d, dict):
                    instrument = d

            strike      = _safe_float(instrument.get("strike_price"))
            expiration  = instrument.get("expiration_date")
            option_type = (instrument.get("type") or "").lower()

            # Market price
            current_price = current_contract_value = pnl = pnl_pct = None
            if inst_url:
                md = _rh_get(
                    f"{RH_BASE}/marketdata/options/",
                    params={"instruments": inst_url},
                )
                items = []
                if isinstance(md, dict):
                    items = md.get("results") or []
                elif isinstance(md, list):
                    items = md
                if items:
                    current_price = _safe_float(items[0].get("adjusted_mark_price"))

            if current_price is not None:
                current_contract_value = round(current_price * 100 * qty, 2)
                if avg_price is not None:
                    cost_basis = avg_price * 100 * qty
                    pnl        = round(current_contract_value - cost_basis, 2)
                    if cost_basis > 0:
                        pnl_pct = round(pnl / cost_basis * 100, 2)

            suffix  = " (joint)" if acct_type == "joint" else " (individual)"
            positions.append(RobinhoodPosition(
                symbol=chain_symbol + suffix,
                option_type=option_type,
                strike=strike,
                expiration=expiration,
                quantity=qty,
                average_price=avg_price,
                current_price=current_price,
                current_contract_value=current_contract_value,
                pnl=pnl,
                pnl_pct=pnl_pct,
                chain_symbol=chain_symbol,
                account_type=acct_type,
            ))
            logging.info(
                "  Option: %s %s strike=%s exp=%s acct=%s qty=%s pnl=%s",
                chain_symbol, option_type, strike, expiration, acct_type, qty, fmt_money(pnl)
            )
        except Exception:
            logging.exception("Error parsing one option position — skipping.")

    logging.info("Robinhood options: %d position(s) parsed.", len(positions))
    return positions


# ─────────────────────────────────────────────────────────────────────────────
# Robinhood — fetch stock holdings
# ─────────────────────────────────────────────────────────────────────────────
def fetch_robinhood_stock_holdings() -> list[RobinhoodStockHolding]:
    # Manual override takes priority — API is fallback
    manual = _load_manual_stock_holdings()
    if manual:
        logging.info("Using manual stock holdings (%d) from RH_MANUAL_STOCKS.", len(manual))
        return manual

    if not robinhood_login():
        return []
    logging.info("Fetching Robinhood open stock positions ...")
    raw_list = _rh_fetch_all_positions("positions/", params={"nonzero": "true"})
    if not raw_list:
        logging.info("Robinhood: no open stock positions.")
        return []

    logging.info("Stocks raw rows: %d", len(raw_list))
    pending: list[tuple[str, str, float, float | None, str]] = []

    for pos in raw_list:
        try:
            qty = _safe_float(pos.get("quantity")) or 0.0
            if qty <= 0:
                continue
            acct_url = pos.get("account") or ""
            if not _keep_acct(acct_url):
                continue
            avg_buy   = _safe_float(pos.get("average_buy_price"))
            acct_type = _acct_label(acct_url)
            ticker    = ""
            inst_url  = pos.get("instrument") or ""
            if inst_url:
                d = _rh_get(inst_url)
                if isinstance(d, dict):
                    ticker = (d.get("symbol") or "").upper().strip()
            if not ticker:
                logging.warning("Stock row: could not resolve ticker — skipping.")
                continue
            suffix  = " (joint)" if acct_type == "joint" else " (individual)"
            pending.append((ticker + suffix, ticker, qty, avg_buy, acct_type))
            logging.info("  Stock: %s qty=%s acct=%s", ticker, qty, acct_type)
        except Exception:
            logging.exception("Error parsing one stock row — skipping.")

    if not pending:
        return []

    # Batch quote via yfinance
    tickers_uniq = sorted({row[1] for row in pending})
    quote_map: dict[str, float | None] = {}
    try:
        if len(tickers_uniq) == 1:
            sym = tickers_uniq[0]
            fi  = getattr(yf.Ticker(sym), "fast_info", {}) or {}
            quote_map[sym] = _safe_float(
                fi.get("last_price") or fi.get("regular_market_price")
            )
        else:
            data = yf.download(
                " ".join(tickers_uniq), period="1d",
                auto_adjust=True, progress=False
            )
            if not data.empty:
                close = data["Close"] if "Close" in data.columns else data.iloc[:, 0]
                if hasattr(close, "columns"):
                    for sym in tickers_uniq:
                        if sym in close.columns:
                            v = close[sym].dropna()
                            quote_map[sym] = float(v.iloc[-1]) if not v.empty else None
                else:
                    v = close.dropna()
                    if not v.empty:
                        quote_map[tickers_uniq[0]] = float(v.iloc[-1])
    except Exception:
        logging.exception("Stock quote batch failed — holdings shown without marks.")

    holdings: list[RobinhoodStockHolding] = []
    for display, ticker, qty, avg_buy, acct_type in pending:
        cur = quote_map.get(ticker)
        mv  = round(cur * qty, 2) if cur is not None else None
        pnl = pnl_pct = None
        if cur is not None and avg_buy is not None and mv is not None:
            cost   = avg_buy * qty
            pnl    = round(mv - cost, 2)
            pnl_pct= round(pnl / cost * 100, 2) if cost > 0 else None
        holdings.append(RobinhoodStockHolding(
            symbol=display, ticker=ticker, quantity=qty,
            average_buy_price=avg_buy, current_price=cur,
            market_value=mv, pnl=pnl, pnl_pct=pnl_pct, account_type=acct_type
        ))

    logging.info("Robinhood stocks: %d holding(s) parsed.", len(holdings))
    return holdings


# ─────────────────────────────────────────────────────────────────────────────
# Robinhood → dict serialisers
# ─────────────────────────────────────────────────────────────────────────────
def rh_positions_to_dict(positions: list[RobinhoodPosition]) -> list[dict]:
    return [
        {
            "symbol": p.symbol, "option_type": p.option_type,
            "strike": p.strike, "expiration": p.expiration, "quantity": p.quantity,
            "average_price": p.average_price, "current_price": p.current_price,
            "current_contract_value": p.current_contract_value,
            "pnl": p.pnl, "pnl_pct": p.pnl_pct, "account_type": p.account_type,
        }
        for p in positions
    ]


def rh_stocks_to_dict(holdings: list[RobinhoodStockHolding]) -> list[dict]:
    return [
        {
            "symbol": h.symbol, "ticker": h.ticker, "quantity": h.quantity,
            "average_buy_price": h.average_buy_price, "current_price": h.current_price,
            "market_value": h.market_value, "pnl": h.pnl, "pnl_pct": h.pnl_pct,
            "account_type": h.account_type,
        }
        for h in holdings
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Ticker extraction
# ─────────────────────────────────────────────────────────────────────────────
def extract_tickers(html_text: str) -> list[str]:
    soup   = BeautifulSoup(html_text, "html.parser")
    seen: set[str] = set()
    ordered: list[str] = []

    def push(sym: str) -> None:
        u = sym.upper().strip()
        if not u or not re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", u):
            return
        if u not in seen:
            seen.add(u)
            ordered.append(u)

    tier = soup.select_one("#tier-1-catalysts")
    if tier:
        for span in tier.select(".research-ticker"):
            push(span.get_text(strip=True))
    else:
        logging.warning("#tier-1-catalysts not found in template.")

    opts = soup.select_one("#options-trading")
    if opts:
        for node in opts.select("[data-options-ticker]"):
            push((node.get("data-options-ticker") or "").strip())
    else:
        logging.warning("#options-trading not found in template.")

    logging.info("Extracted tickers: %s", ordered)
    return ordered


def extract_tickers_from_disk() -> list[str]:
    return extract_tickers(safe_read_template())


# ─────────────────────────────────────────────────────────────────────────────
# ★ NEW: Multi-expiry options scanner
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class OptionPick:
    symbol:        str
    spot:          float | None
    strike:        float | None
    expiration:    str | None
    dte:           int | None        # actual days-to-expiry chosen
    ask:           float | None
    contract_cost: float | None
    move_pct:      float | None
    iv:            float | None      # implied volatility if available
    note:          str
    all_expirations: list[dict] | None  # snapshot of all scanned expirations


def _nearest_expiry_for_dte(ticker: yf.Ticker, target_dte: int) -> tuple[str | None, int | None]:
    """Return (expiration_str, actual_dte) closest to target_dte."""
    dates = getattr(ticker, "options", None)
    if not dates:
        return None, None
    now    = datetime.now(timezone.utc).replace(tzinfo=None)
    target = now + timedelta(days=target_dte)
    best_str: str | None = None
    best_dte: int | None = None
    best_delta           = float("inf")
    for d in dates:
        try:
            dt    = datetime.strptime(str(d), "%Y-%m-%d")
            delta = abs((dt - target).total_seconds())
            if delta < best_delta:
                best_delta = delta
                best_str   = str(d)
                best_dte   = (dt - now).days
        except ValueError:
            continue
    return best_str, best_dte


def _pick_best_call(calls: pd.DataFrame, spot: float, max_ask: float) -> tuple[pd.Series | None, str]:
    if calls is None or calls.empty:
        return None, "empty chain"
    df = calls.copy()
    if "ask" not in df.columns or "strike" not in df.columns:
        return None, "missing columns"
    df = df[df["ask"].notna() & (df["ask"] > 0) & (df["ask"] <= max_ask)]
    if df.empty:
        return None, f"no call with ask ≤ ${max_ask:.2f}"
    df["_dist"] = (df["strike"] - spot).abs()
    df = df.sort_values(["_dist", "strike", "ask"])
    return df.iloc[0], "ok"


def _breakeven_move_pct(spot: float, strike: float, premium: float) -> float:
    if spot <= 0:
        return 0.0
    return (strike + premium - spot) / spot * 100.0


def _session_open(symbol: str) -> float | None:
    try:
        hist = yf.Ticker(symbol).history(period="5d")
        if hist is None or hist.empty:
            return None
        o = float(hist.iloc[-1].get("Open", float("nan")))
        return o if (o == o and o > 0) else None
    except Exception:
        return None


def scan_ticker(symbol: str) -> OptionPick:
    """
    Scan multiple expiration windows (DTE_LIST) and return the best OptionPick.
    'Best' = lowest breakeven move % among chains that have a qualifying ask.
    All candidates are attached in all_expirations for dashboard display.
    """
    logging.info("Multi-expiry scan: %s  (DTE targets: %s)", symbol, DTE_LIST)
    try:
        t    = yf.Ticker(symbol)
        fi   = getattr(t, "fast_info", {}) or {}
        spot = _safe_float(fi.get("last_price") or fi.get("regular_market_previous_close"))
        if spot is None or spot <= 0:
            hist = t.history(period="5d")
            if hist is not None and not hist.empty:
                spot = float(hist["Close"].iloc[-1])
        if spot is None or spot <= 0:
            return OptionPick(symbol, None, None, None, None, None, None, None, None,
                              "Could not read spot price", None)

        candidates: list[dict] = []
        seen_exp: set[str] = set()

        for target_dte in DTE_LIST:
            exp_str, actual_dte = _nearest_expiry_for_dte(t, target_dte)
            if not exp_str or exp_str in seen_exp:
                continue
            seen_exp.add(exp_str)
            try:
                chain = t.option_chain(exp_str)
                row, reason = _pick_best_call(chain.calls, spot, MAX_ASK_PER_SHARE)
            except Exception as e:
                candidates.append({
                    "target_dte": target_dte, "exp": exp_str, "actual_dte": actual_dte,
                    "strike": None, "ask": None, "cost": None,
                    "move_pct": None, "iv": None, "note": str(e),
                })
                continue

            if row is None:
                candidates.append({
                    "target_dte": target_dte, "exp": exp_str, "actual_dte": actual_dte,
                    "strike": None, "ask": None, "cost": None,
                    "move_pct": None, "iv": None, "note": reason,
                })
                continue

            ask    = float(row["ask"])
            strike = float(row["strike"])
            cost   = round(ask * 100.0, 2)
            move   = _breakeven_move_pct(spot, strike, ask)
            iv     = _safe_float(row.get("impliedVolatility"))

            candidates.append({
                "target_dte": target_dte, "exp": exp_str, "actual_dte": actual_dte,
                "strike": strike, "ask": ask, "cost": cost,
                "move_pct": round(move, 3), "iv": iv, "note": "",
            })
            logging.info(
                "  %s %s dte=%d strike=%.2f ask=%.4f cost=$%.2f move=%.2f%% iv=%s",
                symbol, exp_str, actual_dte or 0, strike, ask, cost, move,
                f"{iv*100:.1f}%" if iv else "n/a"
            )

        if not candidates:
            return OptionPick(symbol, spot, None, None, None, None, None, None, None,
                              "No expirations found", None)

        # Best = qualifying candidate with lowest breakeven move (cheapest % needed to profit)
        qualified = [c for c in candidates if c["move_pct"] is not None]
        if not qualified:
            note = candidates[0].get("note") or "No qualifying strikes across all expirations"
            return OptionPick(symbol, spot, None, None, None, None, None, None, None,
                              note, candidates)

        best = min(qualified, key=lambda c: c["move_pct"])
        logging.info(
            "%s → BEST: exp=%s dte=%d strike=%.2f ask=%.4f move=%.2f%%",
            symbol, best["exp"], best.get("actual_dte") or 0,
            best["strike"], best["ask"], best["move_pct"]
        )
        return OptionPick(
            symbol=symbol, spot=spot,
            strike=best["strike"], expiration=best["exp"],
            dte=best.get("actual_dte"),
            ask=best["ask"], contract_cost=best["cost"],
            move_pct=best["move_pct"], iv=best.get("iv"),
            note="", all_expirations=candidates,
        )

    except Exception as e:
        logging.exception("%s multi-expiry scan failed", symbol)
        return OptionPick(symbol, None, None, None, None, None, None, None, None,
                          f"error: {e}", None)


# ─────────────────────────────────────────────────────────────────────────────
# Kill switch (unchanged logic, updated for new OptionPick shape)
# ─────────────────────────────────────────────────────────────────────────────
def now_et() -> datetime:
    try:
        return datetime.now(ZoneInfo(MARKET_TZ_NAME))
    except Exception:
        return datetime.now(timezone.utc)


def in_kill_window(dt: datetime | None = None) -> bool:
    z   = dt or now_et()
    hm  = z.hour * 60 + z.minute
    s   = KILL_WINDOW_START[0] * 60 + KILL_WINDOW_START[1]
    e   = KILL_WINDOW_END[0]   * 60 + KILL_WINDOW_END[1]
    return s <= hm < e


def load_kill_state() -> dict:
    if not KILL_SWITCH_STATE_JSON.is_file():
        return {}
    try:
        return json.loads(KILL_SWITCH_STATE_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_kill_state(state: dict) -> None:
    try:
        KILL_SWITCH_STATE_JSON.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        logging.exception("Could not persist kill switch state.")


def evaluate_kill_switch(picks: dict[str, OptionPick]) -> list[str]:
    alerts: list[str] = []
    if not in_kill_window():
        return alerts
    et        = now_et()
    day_key   = et.strftime("%Y-%m-%d")
    state     = load_kill_state()
    day_bucket = state.setdefault("days", {}).setdefault(day_key, {})

    for sym, pick in picks.items():
        if pick.contract_cost is None or pick.spot is None:
            continue
        premium    = float(pick.contract_cost)
        spot       = float(pick.spot)
        sym_state  = day_bucket.setdefault(sym, {})
        if "baseline_premium" not in sym_state:
            sym_state.update({
                "baseline_premium": premium,
                "baseline_spot":    spot,
                "baseline_ts":      et.isoformat(),
            })
            logging.info("Kill-switch baseline %s premium=%.2f spot=%.4f", sym, premium, spot)

        b_prem  = float(sym_state["baseline_premium"])
        b_spot  = float(sym_state["baseline_spot"])
        s_open  = _session_open(sym)

        flat_vs_open = spot <= (s_open * (1.0 + FLAT_EPSILON)) if s_open else True
        flat_vs_base = spot <= b_spot * (1.0 + FLAT_EPSILON)
        flat_or_down = flat_vs_open and flat_vs_base
        drop = (b_prem - premium) / b_prem if b_prem > 0 else 0.0

        if drop > PREMIUM_DROP_THRESHOLD and flat_or_down:
            msg = (
                f"{sym}: ⚠️ CALL IT OFF — IV Crush detected.  "
                f"Premium −{drop*100:.1f}% vs open-window baseline; spot flat/down."
            )
            alerts.append(msg)
            logging.warning(msg)

    save_kill_state(state)
    return alerts


# ─────────────────────────────────────────────────────────────────────────────
# News helpers
# ─────────────────────────────────────────────────────────────────────────────
def fetch_news_last_24h(symbol: str) -> list[dict]:
    items: list[dict] = []
    try:
        raw    = getattr(yf.Ticker(symbol), "news", None) or []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        for entry in raw:
            ts = entry.get("providerPublishTime")
            dt = datetime.fromtimestamp(ts, tz=timezone.utc) if isinstance(ts, (int, float)) else None
            if dt is None or dt >= cutoff:
                items.append({
                    "title":     entry.get("title") or "",
                    "publisher": entry.get("publisher") or "",
                    "link":      entry.get("link") or "",
                    "published": dt.isoformat() if dt else None,
                })
    except Exception:
        logging.exception("News fetch failed for %s", symbol)
    return items


def build_news_digest(tickers: list[str]) -> str:
    lines: list[str] = []
    for sym in tickers:
        lines.append(f"=== {sym} ===")
        news = fetch_news_last_24h(sym)
        if not news:
            lines.append("(no recent news from yfinance)")
        else:
            for n in news[:15]:
                lines.append(f"- {n['title']} [{n['publisher']}] {n['link']}")
        lines.append("")
    return "\n".join(lines)


def _fetch_yf_fundamentals(symbol: str) -> dict:
    """Pull key fundamental data from yfinance for deep research."""
    out: dict = {}
    try:
        t    = yf.Ticker(symbol)
        info = t.info or {}
        for key in [
            "shortName", "sector", "industry", "marketCap", "trailingPE",
            "forwardPE", "priceToBook", "revenueGrowth", "earningsGrowth",
            "recommendationKey", "targetMeanPrice", "numberOfAnalystOpinions",
            "shortPercentOfFloat", "beta", "fiftyTwoWeekLow", "fiftyTwoWeekHigh",
            "nextEarningsDate",
        ]:
            v = info.get(key)
            if v is not None:
                out[key] = v
        # Earnings calendar
        try:
            cal = t.calendar
            if cal is not None and not (hasattr(cal, "empty") and cal.empty):
                if hasattr(cal, "to_dict"):
                    out["earnings_calendar"] = cal.to_dict()
                else:
                    out["earnings_calendar"] = str(cal)[:300]
        except Exception:
            pass
    except Exception:
        logging.debug("Fundamentals fetch failed for %s", symbol, exc_info=True)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# ★ NEW: Deep Research pipeline (multi-step, like ChatGPT / Gemini deep research)
# ─────────────────────────────────────────────────────────────────────────────
def _gemini_call(prompt: str) -> str:
    """Single Gemini call. Returns raw text or empty string on failure."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key or genai is None:
        return ""
    try:
        client   = genai.Client(api_key=api_key)
        wait_for_slot("auto_bot")
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return (response.text or "").strip()
    except Exception:
        logging.exception("Gemini call failed.")
        return ""


def _deep_research_single_ticker(
    symbol: str,
    news_headlines: str,
    fundamentals: dict,
    options_snapshot: list[dict] | None,
) -> dict:
    """
    Multi-step Gemini deep research for one ticker.
    Step 1 — Catalyst & sentiment analysis
    Step 2 — Risk / downside analysis
    Step 3 — Options strategy recommendation across supplied expirations
    Step 4 — Final synthesis JSON
    Returns structured dict.
    """
    fund_str = json.dumps(fundamentals, default=str)[:2000] if fundamentals else "(none)"
    opts_str = json.dumps(options_snapshot, default=str)[:1500] if options_snapshot else "(none)"

    # ── Step 1: Catalyst analysis ─────────────────────────────────────────────
    step1_prompt = f"""You are a senior equity research analyst doing deep market research.

Ticker: {symbol}

### Recent headlines (last 24h):
{news_headlines or "(none available)"}

### Fundamental data snapshot:
{fund_str}

TASK — Catalyst & Sentiment Analysis:
Identify the top 3 bullish and top 3 bearish catalysts currently in play for {symbol}.
Be specific: reference actual news items, earnings dates, sector dynamics, short interest, or technical setup.
Write 2–3 sentences per catalyst.  Format as plain prose, no bullet points."""

    step1 = _gemini_call(step1_prompt)
    logging.info("  [DeepResearch %s] Step 1 complete (%d chars)", symbol, len(step1))

    # ── Step 2: Risk analysis ─────────────────────────────────────────────────
    step2_prompt = f"""You are a risk analyst reviewing {symbol}.

Catalyst analysis (from previous step):
{step1[:2000] if step1 else "(no catalyst data)"}

### Fundamental snapshot:
{fund_str}

TASK — Risk & Downside Assessment:
What are the main scenarios in which a long call options trade on {symbol} would fail?
Cover: IV crush risk, earnings binary risk, sector rotation risk, macro headwinds.
Include a rough probability estimate (0–100%) that the stock is UP at 30-day horizon.
Write concise prose, 3–4 sentences total."""

    step2 = _gemini_call(step2_prompt)
    logging.info("  [DeepResearch %s] Step 2 complete (%d chars)", symbol, len(step2))

    # ── Step 3: Options strategy recommendation ───────────────────────────────
    step3_prompt = f"""You are an options strategist specialising in small-cap momentum trades.

Ticker: {symbol}
Available call contracts scanned across multiple expirations:
{opts_str}

Catalyst summary:
{step1[:1000] if step1 else "(none)"}

Risk summary:
{step2[:800] if step2 else "(none)"}

TASK — Best expiration & strike recommendation:
Given the catalysts and risks, which expiration (DTE) and strike gives the best risk-adjusted
expected value for a ≤$0.50/share premium call trade?
Explain WHY in 3–4 sentences — consider IV, time decay, and catalyst timing.
Be explicit about your recommended expiration date and strike price."""

    step3 = _gemini_call(step3_prompt)
    logging.info("  [DeepResearch %s] Step 3 complete (%d chars)", symbol, len(step3))

    # ── Step 4: Synthesise to JSON ────────────────────────────────────────────
    step4_prompt = f"""You are a trading desk analyst writing a structured summary.

Ticker: {symbol}
Catalyst analysis: {step1[:800] if step1 else "(none)"}
Risk analysis: {step2[:600] if step2 else "(none)"}
Options recommendation: {step3[:800] if step3 else "(none)"}

Return ONE valid JSON object only — no markdown fences, no commentary — with this exact schema:
{{
  "symbol": "{symbol}",
  "win_probability_30d_pct": <integer 0-100>,
  "recommended_action": "BUY_CALL | WATCH | AVOID",
  "recommended_expiration": "<YYYY-MM-DD or 'N/A'>",
  "recommended_strike": <number or null>,
  "catalyst_summary": "<2 sentences>",
  "risk_summary": "<2 sentences>",
  "options_rationale": "<2 sentences>",
  "confidence": "HIGH | MEDIUM | LOW"
}}"""

    step4_raw = _gemini_call(step4_prompt)
    logging.info("  [DeepResearch %s] Step 4 complete (%d chars)", symbol, len(step4_raw))
    step4_json = parse_gemini_json_blob(step4_raw)

    return {
        "symbol":          symbol,
        "step1_catalysts": step1,
        "step2_risks":     step2,
        "step3_options":   step3,
        "synthesis":       step4_json or {"raw": step4_raw},
    }


def call_gemini_daily_digest(
    tickers: list[str],
    news_digest: str,
    picks: dict[str, OptionPick] | None = None,
) -> tuple[str, dict | None]:
    """
    Deep-research mode:
    • Runs per-ticker multi-step analysis in sequence.
    • Produces a master synthesis across all tickers.
    Returns (raw_master_text, parsed_json).
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logging.error("GOOGLE_API_KEY not set — skipping deep research.")
        return "", None
    if genai is None:
        logging.error("google-genai not installed — pip install google-genai")
        return "", None

    logging.info("Starting deep research for %d ticker(s): %s", len(tickers), tickers)
    per_ticker_results: list[dict] = []

    for sym in tickers:
        logging.info("Deep research: processing %s ...", sym)
        sym_news   = "\n".join(
            f"- {n['title']} [{n['publisher']}]"
            for n in fetch_news_last_24h(sym)[:12]
        )
        sym_fund   = _fetch_yf_fundamentals(sym)
        sym_opts   = (picks[sym].all_expirations if picks and sym in picks else None) or None
        result     = _deep_research_single_ticker(sym, sym_news, sym_fund, sym_opts)
        per_ticker_results.append(result)

    # ── Master synthesis across all tickers ──────────────────────────────────
    summaries = []
    for r in per_ticker_results:
        syn = r.get("synthesis") or {}
        if isinstance(syn, dict) and "symbol" in syn:
            summaries.append(
                f"{syn['symbol']}: action={syn.get('recommended_action')} "
                f"win_prob={syn.get('win_probability_30d_pct')}% "
                f"exp={syn.get('recommended_expiration')} "
                f"strike={syn.get('recommended_strike')} "
                f"confidence={syn.get('confidence')}"
            )
        else:
            summaries.append(f"{r['symbol']}: synthesis not parsed")

    master_prompt = f"""You are a portfolio-level trading desk analyst.

Below are per-ticker deep research results for today:
{chr(10).join(summaries)}

Write a concise 4–6 sentence master narrative for the trading day:
• Which tickers have the highest conviction for a long call trade TODAY?
• Any tickers to AVOID or WATCH only?
• Key macro or sector themes tying them together?

After the narrative, return ONLY a valid JSON object (no fences):
{{
  "summary": "<your 4-6 sentence narrative>",
  "tickers": {{
    "SYM": {{
      "win_probability_pct": <int>,
      "negative_catalysts": "<text>",
      "notes": "<brief>",
      "recommended_action": "BUY_CALL | WATCH | AVOID",
      "recommended_expiration": "<YYYY-MM-DD or N/A>",
      "recommended_strike": <number or null>
    }}
  }}
}}"""

    master_raw    = _gemini_call(master_prompt)
    master_parsed = parse_gemini_json_blob(master_raw)

    # Merge per-ticker detail into parsed output
    if master_parsed and isinstance(master_parsed.get("tickers"), dict):
        for r in per_ticker_results:
            sym = r["symbol"]
            if sym in master_parsed["tickers"]:
                master_parsed["tickers"][sym]["deep_research"] = {
                    "catalysts": r.get("step1_catalysts", "")[:600],
                    "risks":     r.get("step2_risks", "")[:400],
                    "options":   r.get("step3_options", "")[:400],
                }

    logging.info("Deep research complete.  Master parsed: %s", bool(master_parsed))
    return master_raw, master_parsed


# ─────────────────────────────────────────────────────────────────────────────
# Daily job
# ─────────────────────────────────────────────────────────────────────────────
def daily_deep_research() -> None:
    logging.info("=== daily_deep_research() start ===")
    try:
        tickers = extract_tickers_from_disk()
        if not tickers:
            logging.error("No tickers extracted — aborting.")
            return
        news_digest        = build_news_digest(tickers)
        # Note: picks not yet available at daily-job time; pass None
        raw_text, parsed   = call_gemini_daily_digest(tickers, news_digest, picks=None)
        payload: dict = {
            "generated_at":      datetime.now(timezone.utc).isoformat(),
            "tickers":           tickers,
            "news_digest_chars": len(news_digest),
            "gemini_raw":        raw_text,
            "gemini_json":       parsed,
            "deep_research":     True,
        }
        if not raw_text and not parsed:
            payload["gemini_error"] = (
                "Gemini returned empty — check GOOGLE_API_KEY, quota, or GEMINI_MODEL."
            )
        DAILY_SENTIMENT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logging.info("Saved %s", DAILY_SENTIMENT_JSON)
    except Exception:
        logging.exception("daily_deep_research failed.")
    logging.info("=== daily_deep_research() end ===")


def load_daily_sentiment() -> dict | None:
    if not DAILY_SENTIMENT_JSON.is_file():
        return None
    try:
        return json.loads(DAILY_SENTIMENT_JSON.read_text(encoding="utf-8"))
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# HTML injection — option cards
# ─────────────────────────────────────────────────────────────────────────────
def ensure_option_cards(soup: BeautifulSoup, tickers: list[str]) -> None:
    grid = soup.select_one("#options-trading-grid") or soup.select_one("#options-trading")
    if grid is None:
        return
    existing = {
        (el.get("data-options-ticker") or "").upper().strip()
        for el in grid.select(".option-watch-card")
    }
    prototype = grid.select_one(".option-watch-card")
    if prototype is None:
        return
    for sym in tickers:
        if sym.upper() in existing:
            continue
        slug  = slugify_symbol(sym)
        clone = BeautifulSoup(str(prototype), "html.parser").select_one(".option-watch-card")
        if clone is None:
            continue
        clone["data-options-ticker"] = sym.upper()
        h2 = clone.find("h2")
        if h2:
            h2.string = sym.upper()
        id_map = [
            (f"{slug}-stock-price", "—"),
            (f"{slug}-strike-price", "—"),
            (f"{slug}-expiration", "—"),
            (f"{slug}-move-needed", "—"),
            (f"{slug}-cost", "—"),
            (f"{slug}-note", "—"),
        ]
        rows = clone.select(".row")
        for i, (nid, _) in enumerate(id_map):
            if i >= len(rows):
                break
            val = rows[i].select_one(".value")
            if val is not None:
                val.clear()
                val.append("—")
                val["id"] = nid
        grid.append(clone)
        existing.add(sym.upper())


# ─────────────────────────────────────────────────────────────────────────────
# HTML injection — Robinhood portfolio section
# ─────────────────────────────────────────────────────────────────────────────
def _stock_table_html(holdings: list[RobinhoodStockHolding]) -> str:
    if not holdings:
        return '<p style="color:#aaa;font-style:italic;">No stock holdings.</p>'
    rows = ""
    for h in holdings:
        color = "#4caf50" if (h.pnl or 0) >= 0 else "#f44336"
        qty   = f"{int(h.quantity)}" if float(h.quantity).is_integer() else f"{h.quantity:g}"
        rows += (
            f"<tr><td><strong>{h.ticker}</strong></td><td>{qty}</td>"
            f"<td>{fmt_money(h.average_buy_price)}</td><td>{fmt_money(h.current_price)}</td>"
            f"<td>{fmt_money(h.market_value)}</td>"
            f"<td style='color:{color};'>{fmt_money(h.pnl)} ({fmt_pct(h.pnl_pct)})</td></tr>"
        )
    return (
        "<table style='width:100%;border-collapse:collapse;font-size:.9em;margin-bottom:16px;'>"
        "<thead><tr style='border-bottom:1px solid #444;text-align:left;color:#aaa;'>"
        "<th>Ticker</th><th>Shares</th><th>Avg Cost</th><th>Last</th><th>Value</th><th>P&L</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _option_table_html(positions: list[RobinhoodPosition]) -> str:
    if not positions:
        return '<p style="color:#aaa;font-style:italic;">No open option positions.</p>'
    rows = ""
    for p in positions:
        color = "#4caf50" if (p.pnl or 0) >= 0 else "#f44336"
        rows += (
            f"<tr><td><strong>{p.chain_symbol}</strong></td>"
            f"<td>{(p.option_type or '').upper() or '—'}</td>"
            f"<td>{fmt_money(p.strike)}</td><td>{p.expiration or '—'}</td>"
            f"<td>{p.quantity:.0f}</td><td>{fmt_money(p.average_price)}</td>"
            f"<td>{fmt_money(p.current_price)}</td><td>{fmt_money(p.current_contract_value)}</td>"
            f"<td style='color:{color};'>{fmt_money(p.pnl)} ({fmt_pct(p.pnl_pct)})</td></tr>"
        )
    return (
        "<table style='width:100%;border-collapse:collapse;font-size:.9em;'>"
        "<thead><tr style='border-bottom:1px solid #444;text-align:left;color:#aaa;'>"
        "<th>Ticker</th><th>Type</th><th>Strike</th><th>Expiry</th>"
        "<th>Qty</th><th>Avg</th><th>Mark</th><th>Value</th><th>P&L</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def inject_robinhood_section(
    soup: BeautifulSoup,
    option_positions: list[RobinhoodPosition],
    stock_holdings: list[RobinhoodStockHolding],
) -> None:
    def _group_s(h: list[RobinhoodStockHolding]) -> dict:
        g: dict = {"joint": [], "individual": []}
        for x in h:
            g.setdefault(x.account_type, []).append(x)
        return g

    def _group_o(p: list[RobinhoodPosition]) -> dict:
        g: dict = {"joint": [], "individual": []}
        for x in p:
            g.setdefault(x.account_type, []).append(x)
        return g

    def _block(label: str, color: str,
               st: list[RobinhoodStockHolding], op: list[RobinhoodPosition]) -> str:
        return (
            f"<div style='margin-bottom:24px;border:1px solid #2a2a4a;"
            f"border-radius:6px;padding:12px;'>"
            f"<h4 style='margin:0 0 10px;color:{color};font-size:1em;'>{label} Account "
            f"<span style='font-weight:normal;color:#888;font-size:.85em;'>"
            f"({len(st)} stock, {len(op)} option)</span></h4>"
            f"<h5 style='margin:8px 0 4px;color:#aaa;font-size:.9em;'>Stocks</h5>"
            f"{_stock_table_html(st)}"
            f"<h5 style='margin:8px 0 4px;color:#aaa;font-size:.9em;'>Options</h5>"
            f"{_option_table_html(op)}</div>"
        )

    sg = _group_s(stock_holdings)
    og = _group_o(option_positions)
    block_html = (
        "<div id='robinhood-positions-root' style='margin:24px 0;padding:16px;"
        "background:#1a1a2e;border:1px solid #2a2a4a;border-radius:8px;'>"
        "<h3 style='margin:0 0 4px;color:#7c83fd;'>📊 Robinhood Portfolio Sync</h3>"
        f"<p style='margin:0 0 16px;color:#888;font-size:.85em;'>"
        f"{len(stock_holdings)} stock &nbsp;·&nbsp; {len(option_positions)} option &nbsp;·&nbsp; "
        f"Updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>"
        f"{_block('🤝 Joint',  '#7c83fd', sg['joint'],      og['joint'])}"
        f"{_block('👤 Individual', '#56cfe1', sg['individual'], og['individual'])}"
        "</div>"
    )
    container = soup.find(id="robinhood-positions-root")
    if container:
        container.replace_with(BeautifulSoup(block_html, "html.parser"))
    else:
        body = soup.find("body")
        if body:
            body.append(BeautifulSoup(block_html, "html.parser"))


# ─────────────────────────────────────────────────────────────────────────────
# HTML injection — multi-expiry comparison table
# ─────────────────────────────────────────────────────────────────────────────
def _multi_expiry_html(symbol: str, pick: OptionPick) -> str:
    """Build a small comparison table of all scanned expirations for one ticker."""
    if not pick.all_expirations:
        return ""
    rows = ""
    for c in pick.all_expirations:
        is_best = (c.get("exp") == pick.expiration and c.get("strike") == pick.strike)
        bg      = "background:#1e2a1e;" if is_best else ""
        star    = " ★ BEST" if is_best else ""
        rows += (
            f"<tr style='{bg}'>"
            f"<td>{c.get('exp','—')}</td>"
            f"<td>{c.get('actual_dte','—')}d</td>"
            f"<td>{'${:.2f}'.format(c['strike']) if c.get('strike') else '—'}</td>"
            f"<td>{'${:.4f}'.format(c['ask']) if c.get('ask') else '—'}</td>"
            f"<td>{'${:.2f}'.format(c['cost']) if c.get('cost') else '—'}</td>"
            f"<td>{'{:.2f}%'.format(c['move_pct']) if c.get('move_pct') is not None else '—'}</td>"
            f"<td>{'{:.1f}%'.format(c['iv']*100) if c.get('iv') else '—'}</td>"
            f"<td>{c.get('note','') or star}</td></tr>"
        )
    return (
        f"<details style='margin-top:8px;'><summary style='cursor:pointer;color:#7c83fd;"
        f"font-size:.85em;'>All {len(pick.all_expirations)} expirations scanned for {symbol}</summary>"
        "<table style='width:100%;border-collapse:collapse;font-size:.8em;margin-top:6px;'>"
        "<thead><tr style='border-bottom:1px solid #444;color:#aaa;'>"
        "<th>Expiry</th><th>DTE</th><th>Strike</th><th>Ask</th>"
        "<th>Cost</th><th>Move%</th><th>IV</th><th>Note</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></details>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard injection (master)
# ─────────────────────────────────────────────────────────────────────────────
def inject_dashboard(
    picks: dict[str, OptionPick],
    sentiment: dict | None,
    kill_alerts: list[str],
    rh_positions: list[RobinhoodPosition] | None = None,
    rh_stock_holdings: list[RobinhoodStockHolding] | None = None,
) -> None:
    html = safe_read_template()
    soup = BeautifulSoup(html, "html.parser")

    # Kill alerts
    crit = soup.find(id="critical-alerts-root")
    if crit:
        crit.clear()
        for msg in (kill_alerts or []):
            div        = soup.new_tag("div")
            div["class"] = ["kill-switch-alert"]
            div.string = msg
            crit.append(div)

    # Sentiment banner
    body_sent   = soup.find(id="daily-sentiment-body")
    win_prob_el = soup.find(id="daily-win-prob-summary")
    if sentiment:
        gem      = sentiment.get("gemini_json") or {}
        summary  = gem.get("summary") if isinstance(gem, dict) else None
        raw_fb   = sentiment.get("gemini_raw") or ""
        err_note = sentiment.get("gemini_error") or ""
        merged   = "\n\n".join(
            filter(None, [summary, err_note or (raw_fb if not summary else "")])
        ) or "No Gemini summary."
        if body_sent:
            body_sent.clear()
            body_sent.append(merged[:8000])
        if win_prob_el and isinstance(gem, dict):
            tick_blob = gem.get("tickers") or {}
            lines = [
                f"{sym}: win_prob={row.get('win_probability_pct')}% "
                f"action={row.get('recommended_action','—')} "
                f"exp={row.get('recommended_expiration','—')} "
                f"strike={row.get('recommended_strike','—')} "
                f"— {(row.get('negative_catalysts') or '')[:100]}"
                for sym, row in tick_blob.items() if isinstance(row, dict)
            ]
            win_prob_el.clear()
            win_prob_el.append("\n".join(lines) or "Win probabilities not parsed.")
    else:
        if body_sent:
            body_sent.clear()
            body_sent.append("No daily_sentiment.json yet — run daily job or wait for 07:00.")

    # Timestamp
    ts_el = soup.find(id="live-updated-at")
    if ts_el:
        ts_el.string = f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (local)"

    # Option cards
    ensure_option_cards(soup, list(picks.keys()))
    for sym, pick in picks.items():
        slug   = slugify_symbol(sym)
        note   = pick.note or (f"DTE: {pick.dte}d" if pick.dte else "")
        fields = {
            f"{slug}-stock-price":  fmt_money(pick.spot),
            f"{slug}-strike-price": fmt_money(pick.strike),
            f"{slug}-expiration":   pick.expiration or "—",
            f"{slug}-move-needed":  fmt_pct(pick.move_pct),
            f"{slug}-cost":         fmt_money(pick.contract_cost),
            f"{slug}-note":         note[:300] or "—",
        }
        for el_id, text in fields.items():
            node = soup.find(id=el_id)
            if node:
                node.clear()
                node.append(text)
        # Inject multi-expiry table after the card if we have data
        if pick.all_expirations:
            card = soup.find(attrs={"data-options-ticker": sym.upper()})
            if card:
                extra_html = _multi_expiry_html(sym, pick)
                if extra_html:
                    extra_node = BeautifulSoup(extra_html, "html.parser")
                    card.append(extra_node)

    # Robinhood section
    inject_robinhood_section(soup, rh_positions or [], rh_stock_holdings or [])
    safe_write_dashboard(str(soup))


# ─────────────────────────────────────────────────────────────────────────────
# agent_output.json
# ─────────────────────────────────────────────────────────────────────────────
def write_agent_json(
    picks: dict[str, OptionPick],
    sentiment: dict | None,
    kill_alerts: list[str],
    rh_positions: list[RobinhoodPosition] | None = None,
    rh_stock_holdings: list[RobinhoodStockHolding] | None = None,
) -> None:
    output: dict = {
        "updated_at":  datetime.now().isoformat(),
        "kill_alerts": kill_alerts,
        "picks": {
            sym: {
                "spot":             p.spot,
                "strike":           p.strike,
                "expiration":       p.expiration,
                "dte":              p.dte,
                "ask":              p.ask,
                "contract_cost":    p.contract_cost,
                "move_pct":         p.move_pct,
                "iv":               p.iv,
                "note":             p.note or "",
                "all_expirations":  p.all_expirations or [],
            }
            for sym, p in picks.items()
        },
        "sentiment":                sentiment,
        "robinhood_positions":      rh_positions_to_dict(rh_positions or []),
        "robinhood_stock_holdings": rh_stocks_to_dict(rh_stock_holdings or []),
    }
    out_path = SCRIPT_DIR / "agent_output.json"
    try:
        out_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
        logging.info("Wrote %s", out_path)
    except OSError:
        logging.exception("Failed writing agent_output.json")


# ─────────────────────────────────────────────────────────────────────────────
# Intraday loop
# ─────────────────────────────────────────────────────────────────────────────
def intraday_tracker() -> None:
    logging.info("--- intraday_tracker() ---")
    try:
        tickers           = extract_tickers_from_disk()
        if not tickers:
            logging.error("No tickers — skipping intraday cycle.")
            return
        picks             = {sym: scan_ticker(sym) for sym in tickers}
        alerts            = evaluate_kill_switch(picks)
        sentiment         = load_daily_sentiment()
        rh_positions      = fetch_robinhood_positions()
        rh_stock_holdings = fetch_robinhood_stock_holdings()
        inject_dashboard(picks, sentiment, alerts, rh_positions, rh_stock_holdings)
        write_agent_json(picks, sentiment, alerts, rh_positions, rh_stock_holdings)
    except Exception:
        logging.exception("intraday_tracker failed.")
    logging.info("--- intraday_tracker done ---\n")


def _safe_run(fn: Any, label: str) -> None:
    try:
        fn()
    except Exception:
        logging.exception("Job %r crashed.", label)


def run_scheduler_loop() -> None:
    logging.info(
        "Scheduler active | daily @ 07:00 | intraday every 15 min | TZ=%s | DTE=%s",
        MARKET_TZ_NAME, DTE_LIST
    )
    robinhood_login()
    schedule.every().day.at("07:00").do(lambda: _safe_run(daily_deep_research, "daily"))
    schedule.every(15).minutes.do(lambda: _safe_run(intraday_tracker, "intraday"))
    _safe_run(intraday_tracker, "initial")
    while True:
        try:
            schedule.run_pending()
        except Exception:
            logging.exception("schedule.run_pending error.")
        time.sleep(30)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def _startup_check():
    print('\n=== ATLAS STARTUP CHECK ===')
    key = os.environ.get('GOOGLE_API_KEY', '')
    if not key or 'your_key' in key.lower():
        print('[FAIL] GOOGLE_API_KEY missing')
    else:
        print(f'[ OK ] GOOGLE_API_KEY ({key[:8]}...)')
    pc = SCRIPT_DIR / 'positions_cache.json'
    if pc.exists():
        try:
            cache = json.loads(pc.read_text())
            null_exp = [o for o in cache.get('options',[]) if not o.get('expiry')]
            if null_exp:
                print(f'[WARN] {len(null_exp)} option(s) have null expiry — update positions_cache.json')
            else:
                print(f'[ OK ] positions_cache ({len(cache.get("options",[]))} options, all have expiry)')
        except Exception as e:
            print(f'[WARN] positions_cache error: {e}')
    try:
        import chromadb
        print('[ OK ] chromadb (RAG) installed')
    except ImportError:
        print('[WARN] chromadb missing — pip install chromadb')
    tr = os.environ.get('TRADIER_TOKEN','')
    print('[ OK ] TRADIER_TOKEN active' if tr else '[INFO] TRADIER_TOKEN not set (using yfinance fallback)')
    print('=== END STARTUP CHECK ===\n')


def main() -> int:
    _startup_check()
    parser = argparse.ArgumentParser(description="ATLAS Context-Aware Research Agent v3")
    parser.add_argument("--once-intraday", action="store_true",
                        help="Single intraday cycle then exit")
    parser.add_argument("--once-daily",    action="store_true",
                        help="Single Gemini deep-research cycle then exit")
    parser.add_argument("--diagnose-robinhood", action="store_true",
                        help="Test Robinhood login and print full diagnostic then exit")
    parser.add_argument("--watch",         action="store_true",
                        help="Start news scanner + alert monitor + delta watcher in background")
    parser.add_argument("--news-only",      action="store_true",
                        help="Start news scanner only (no screen capture)")
    parser.add_argument("--news-interval",  type=int, default=5, metavar="MIN",
                        help="News scan interval in minutes when using --watch or --news-only (default 5)")
    parser.add_argument("--deep-research",  metavar="TICKER",
                        help="Run 7-step deep research on a ticker, e.g. --deep-research SOUN")
    parser.add_argument("--discover",       metavar="THEME",
                        help='Discover high-potential stocks, e.g. --discover "AI penny stocks"')
    parser.add_argument("--budget",         type=float, default=100.0, metavar="USD",
                        help="Trade budget in dollars for deep research / discovery (default $100)")
    parser.add_argument("--max-discover",   type=int, default=6, metavar="N",
                        help="Max stocks to deep-research during discovery (default 6)")
    parser.add_argument("--verbose", "-v", action="store_true")
    # Intelligence layer commands
    parser.add_argument("--regime",         action="store_true",
                        help="Show current market regime (bull/bear/chop/panic)")
    parser.add_argument("--squeeze",        metavar="TICKER",
                        help="Short squeeze probability score for a ticker")
    parser.add_argument("--scan-dark-horses", action="store_true",
                        help="Scan for new squeeze candidates matching best ATLAS patterns")
    parser.add_argument("--self-tune",      action="store_true",
                        help="Run auto-tuner to optimize scoring weights from your trade history")
    parser.add_argument("--self-analyze",   action="store_true",
                        help="Run self-coder to analyze losses and generate code improvement proposals")
    parser.add_argument("--proposals",      action="store_true",
                        help="List pending self-coder code improvement proposals")
    parser.add_argument("--tuner-status",   action="store_true",
                        help="Show current auto-tuned weights and thresholds")
    # Phase 2A commands
    parser.add_argument("--congress",       metavar="TICKER",
                        help="Show Congressional trades for a ticker")
    parser.add_argument("--hot-congress",   action="store_true",
                        help="List tickers with most Congressional buying (last 30d)")
    parser.add_argument("--recent-congress", action="store_true",
                        help="Show most recent Congressional buys across all tickers")
    parser.add_argument("--alpaca-status",  action="store_true",
                        help="Show Alpaca paper trading account status and positions")
    parser.add_argument("--alpaca-buy",     metavar="TICKER",
                        help="Place a paper market BUY order on Alpaca (use --qty to set amount)")
    parser.add_argument("--alpaca-sell",    metavar="TICKER",
                        help="Place a paper market SELL order on Alpaca")
    parser.add_argument("--alpaca-close",   metavar="TICKER",
                        help="Close an entire Alpaca paper position")
    parser.add_argument("--alpaca-orders",  action="store_true",
                        help="List all open Alpaca paper orders")
    parser.add_argument("--qty",            type=float, default=1,
                        help="Quantity for --alpaca-buy / --alpaca-sell (default 1)")
    parser.add_argument("--tradier-chain",  metavar="TICKER",
                        help="Show Tradier live options chain for a ticker")
    parser.add_argument("--tradier-pcr",    metavar="TICKER",
                        help="Show Put/Call Ratio from Tradier for a ticker")
    parser.add_argument("--dashboard",      action="store_true",
                        help="Launch the live HTML dashboard at http://localhost:8765")
    parser.add_argument("--dashboard-no-browser", action="store_true",
                        help="Launch dashboard server without opening browser")
    parser.add_argument("--ingest",         metavar="TICKER",
                        help="Ingest SEC 10-K/8-K filings for a ticker into RAG database")
    parser.add_argument("--rag-query",      metavar="TICKER",
                        help="Semantic query against ingested SEC filings for a ticker")
    parser.add_argument("--rag-question",   metavar="QUESTION", default="risk factors debt revenue outlook",
                        help="Question to ask when using --rag-query")
    parser.add_argument("--rag-status",     action="store_true",
                        help="Show ChromaDB RAG database stats")
    parser.add_argument("--paper-status",   action="store_true",
                        help="Show all paper trades (open, closed, skipped)")
    parser.add_argument("--paper-monitor",  action="store_true",
                        help="Start the paper trade monitor loop (checks every 60s)")
    parser.add_argument("--paper-close",    metavar="TICKER",
                        help="Manually close an open paper trade")
    parser.add_argument("--paper-trade",    metavar="TICKER",
                        help="Run deep research + auto-propose a paper trade if conviction >= 7")
    parser.add_argument("--backtest",       metavar="TICKER",
                        help="Run a dynamic backtest for a ticker using Gemini-generated pandas code")
    parser.add_argument("--backtest-setup", metavar="SETUP",
                        default="",
                        help="Setup description for --backtest (default: auto-detect from setup tags)")
    args = parser.parse_args()
    setup_logging(args.verbose)

    # ── Early-exit commands (don't need the HTML template) ────────────────────
    if args.dashboard or args.dashboard_no_browser:
        try:
            import dashboard_server as ds
            if args.dashboard_no_browser:
                sys.argv = [sys.argv[0], "--no-browser"]
            else:
                sys.argv = [sys.argv[0]]
            ds.main()
        except ImportError:
            logging.error("dashboard_server.py not found in project folder")
        return 0

    if args.paper_status:
        try:
            import paper_trader
            paper_trader._print_summary()
        except ImportError:
            logging.error("paper_trader.py not found")
        return 0

    if args.paper_monitor:
        try:
            import paper_trader
            paper_trader.run_monitor_loop()
        except ImportError:
            logging.error("paper_trader.py not found")
        return 0

    if args.paper_close:
        try:
            import paper_trader
            ok = paper_trader.close_position_manual(args.paper_close)
            print(f"Manual close {'succeeded' if ok else 'failed'} for {args.paper_close.upper()}")
        except ImportError:
            logging.error("paper_trader.py not found")
        return 0

    if args.paper_trade:
        try:
            import deep_research as dr
            import paper_trader
            tk = args.paper_trade.upper()
            print(f"\nResearching {tk} and proposing paper trade...")
            research = dr.research_ticker(tk, budget=args.budget)
            research["auto_paper_trade"] = True
            trade = paper_trader.propose_trade(research)
            if trade:
                print(f"\n  ✅ Trade placed!")
                print(f"  {tk}: {trade['qty']} shares @ ${trade['entry_price']:.2f}")
                print(f"  Take-profit: ${trade['target_price']:.2f}  |  Stop-loss: ${trade['stop_loss']:.2f}")
                print(f"  Order ID: {trade.get('alpaca_order_id','?')[:16]}")
            else:
                print(f"\n  Trade skipped (confidence < 7 or market closed)")
        except ImportError as e:
            logging.error("Missing module: %s", e)
        return 0

    if args.rag_status:
        try:
            import rag_engine
            stats = rag_engine.rag_stats()
            print(f"\nATLAS RAG Database")
            print(f"  Path:    {stats['db_path']}")
            print(f"  Chunks:  {stats['total_chunks']:,}")
            print(f"  Tickers: {stats['tickers_ingested']}")
            if stats["tickers"]:
                ingested = rag_engine._load_ingested()
                for tk in stats["tickers"]:
                    info = ingested[tk]
                    print(f"    {tk}: {info.get('chunks',0)} chunks | "
                          f"{info.get('filings',0)} filings | "
                          f"{info.get('ingested_at','?')[:10]}")
        except ImportError:
            logging.error("rag_engine.py not found")
        return 0

    if args.ingest:
        try:
            import rag_engine
            tk = args.ingest.upper()
            print(f"\nIngesting SEC filings for {tk}...")
            result = rag_engine.ingest_ticker(tk, force=False)
            if result.get("skipped"):
                print(f"  Already ingested ({result.get('chunks',0)} chunks). "
                      f"Re-run with python rag_engine.py {tk} --force to refresh.")
            else:
                print(f"  Done: {result.get('chunks_added',0)} chunks from "
                      f"{result.get('filings',0)} filings")
        except ImportError:
            logging.error("rag_engine.py not found")
        return 0

    if args.rag_query:
        try:
            import rag_engine
            tk       = args.rag_query.upper()
            question = args.rag_question
            print(f"\nRAG query for {tk}: '{question}'")
            chunks = rag_engine.query_ticker(tk, question, n=5)
            if not chunks:
                print(f"  No results. Ingest first: python auto_bot.py --ingest {tk}")
            else:
                for i, c in enumerate(chunks, 1):
                    print(f"\n[{i}] {c['form_type']} filed {c['filing_date']} "
                          f"(score={c['distance']:.4f}):")
                    print(f"  {c['text'][:350]}...")
        except ImportError:
            logging.error("rag_engine.py not found")
        return 0

    if args.backtest:
        try:
            import backtest_sandbox as bs
            tk    = args.backtest.upper()
            setup = args.backtest_setup.strip() if args.backtest_setup else ""
            if not setup:
                # Try to infer from tracker history for this ticker
                try:
                    import tracker as _trk
                    recs = _trk.recent_recommendations(10)
                    tags = []
                    for r in recs:
                        if r.get("ticker", "").upper() == tk:
                            tags = r.get("setup_tags", [])
                            break
                    setup = bs._tags_to_description(tags) if tags else bs.DEFAULT_SETUP
                except Exception:
                    setup = bs.DEFAULT_SETUP

            print(f"\nRunning backtest: {tk}")
            print(f"Setup: {setup}\n")
            result = bs.run_backtest(tk, setup, use_cache=False)
            if not result:
                print("Backtest failed — see logs above for details")
            else:
                n        = result.get("n_occurrences", 0)
                win_rate = result.get("win_rate", 0) * 100
                avg_ret  = result.get("avg_return_10d", 0) * 100
                best     = result.get("best_return", 0) * 100
                worst    = result.get("worst_return", 0) * 100
                avg_win  = result.get("avg_win_return", 0) * 100
                avg_loss = result.get("avg_loss_return", 0) * 100
                years    = result.get("years_tested", 5)
                strength = ("STRONG" if win_rate >= 65 else
                            "MODERATE" if win_rate >= 55 else "WEAK")
                print(f"  Setup:         {result.get('setup_name','?')}")
                print(f"  Condition:     {result.get('setup_condition','?')}")
                print(f"  Occurrences:   {n} signals over {years} years")
                print(f"  Win rate:      {win_rate:.1f}%  ({strength})")
                print(f"  Avg 10d return: {avg_ret:+.2f}%")
                print(f"  Avg win:        {avg_win:+.2f}%")
                print(f"  Avg loss:       {avg_loss:+.2f}%")
                print(f"  Best / Worst:   {best:+.2f}% / {worst:+.2f}%")
        except ImportError as e:
            logging.error("backtest_sandbox.py not found: %s", e)
        return 0

    # Note: CLI-only commands (--regime, Alpaca, RAG, etc.) must NOT require
    # stock_research_v3.html. Template is enforced only below for scheduler jobs.

    # ── --watch : news scanner + alert monitor + tracker + delta watcher ──────────
    if args.watch or args.news_only:
        import importlib, threading as _threading

        threads: list[_threading.Thread] = []
        t_ns = None

        try:
            ns = importlib.import_module("news_scanner")
            t_ns = ns.start_background(interval_sec=args.news_interval * 60)
            threads.append(t_ns)
            logging.info("News scanner thread started (interval=%d min).", args.news_interval)
            time.sleep(15)  # stagger news scanner vs other Gemini consumers
        except ImportError:
            logging.error("news_scanner.py not found next to auto_bot.py.")
        except Exception:
            logging.exception("News scanner failed to start.")

        # ── Start real-time price alert monitor ─────────────────────────────
        try:
            alert_mod = importlib.import_module("alerts")
            alert_monitor = alert_mod.start_monitor()
            logging.info("Price alert monitor started (%d active alerts).",
                         len(alert_monitor.list_alerts()))
        except ImportError:
            logging.warning("alerts.py not found — price alerts disabled.")
        except Exception:
            logging.exception("Alert monitor failed to start.")

        # ── Auto-grade any pending tracker outcomes ──────────────────────────
        try:
            tracker_mod = importlib.import_module("tracker")
            n_graded = tracker_mod.auto_grade_pending()
            if n_graded:
                logging.info("Tracker: auto-graded %d pending recommendations.", n_graded)
            logging.info("Tracker: %s", tracker_mod.winrate_summary())
        except Exception:
            logging.debug("Tracker startup check failed", exc_info=True)

        # ── Start delta watcher for any known positions ───────────────────────
        try:
            delta_mod = importlib.import_module("delta_reporter")
            watch_tickers: list[str] = []
            try:
                watch_tickers = delta_mod.tickers_from_positions_cache()
            except Exception:
                watch_tickers = []
            if watch_tickers:
                delta_watcher = delta_mod.start_watcher(watch_tickers, interval_min=30)
                logging.info("Delta watcher started for: %s", ", ".join(watch_tickers))
            else:
                logging.info("Delta watcher skipped: no tickers in positions_cache.json or watchlist.json")
        except Exception:
            logging.debug("Delta watcher failed to start", exc_info=True)

        if not threads:
            logging.error("No background threads started. Exiting.")
            return 1

        # Log market regime on startup
        try:
            ms = importlib.import_module("market_scanner")
            regime = ms.detect_market_regime()
            logging.info("Market Regime: %s | VIX=%.1f | %s",
                         regime["regime"], regime.get("vix",0), regime["signal"])
        except Exception:
            pass

        logging.info(
            "--watch OUTPUT (open these files; LIVE_DASHBOARD is NOT touched by watch): "
            "LIVE_REPORTS.html · reports/TICKER_report.html · positions_cache.json"
        )

        logging.info("ATLAS watch mode running. "
                     "Reports: %s%sreports%s  |  Ctrl-C to stop.",
                     SCRIPT_DIR, os.sep, os.sep)

        _watch_tick = 0
        try:
            while True:
                time.sleep(60)
                _watch_tick += 1
                # Every 60 minutes: run auto-tune + self-coder analysis
                if _watch_tick % 60 == 0:
                    try:
                        at = importlib.import_module("auto_tuner")
                        tune_res = at.run_full_tune(min_outcomes=5)
                        if tune_res.get("changes"):
                            logging.info("[auto_tuner] %s", tune_res["changes"][0][:80])
                    except Exception:
                        pass
                    try:
                        sc = importlib.import_module("self_coder")
                        sc_res = sc.run_self_analysis(min_losses=2)
                        if sc_res.get("proposals_generated"):
                            logging.info("[self_coder] %d new proposals. Run: python auto_bot.py --proposals",
                                         len(sc_res["proposals_generated"]))
                    except Exception:
                        pass
        except KeyboardInterrupt:
            logging.info("Stopping ATLAS watch mode...")
            for mod_name in ("news_scanner",):
                try:
                    m = importlib.import_module(mod_name)
                    m.stop()
                except Exception:
                    pass
        return 0

    # ── --regime ─────────────────────────────────────────────────────────────
    if args.regime:
        try:
            import market_scanner as ms
            r = ms.detect_market_regime()
            print(f"\nMarket Regime: {r['regime']}")
            print(f"Signal:  {r['signal']}")
            print(f"VIX:     {r.get('vix','?')}")
            print(f"SPY 5d:  {r.get('spy_trend','?')}%\nSPY 20d: {r.get('spy_20d','?')}%")
            if r.get("dxy_trend") is not None:
                dxy_val = r["dxy_trend"]
                dxy_note = "headwind" if dxy_val > 0.8 else ("tailwind" if dxy_val < -0.8 else "neutral")
                print(f"DXY 5d:  {dxy_val:+.2f}% ({dxy_note})")
            print(f"Confidence multiplier: {r['confidence_multiplier']:.2f}x")
        except ImportError:
            logging.error("market_scanner.py not found")
        return 0

    # ── --squeeze TICKER ─────────────────────────────────────────────────────
    if args.squeeze:
        try:
            import market_scanner as ms
            s = ms.squeeze_score(args.squeeze.upper())
            print(f"\n{args.squeeze.upper()} Short Squeeze Score: {s['score']}/100")
            print(f"Label: {s['label']}")
            for k, v in s.get("components",{}).items():
                print(f"  {k:<20} {v['value']:>8}   ({v['pts']} pts)")
        except ImportError:
            logging.error("market_scanner.py not found")
        return 0

    # ── --scan-dark-horses ────────────────────────────────────────────────────
    if args.scan_dark_horses:
        try:
            import market_scanner as ms
            candidates = ms.scan_for_dark_horses()
            print(f"\nDark Horse Scanner — {len(candidates)} squeeze candidates found:")
            for c in candidates:
                print(f"  {c['ticker']:<6} score={c['score']}  SF={c['short_float']}  {c['why'][:60]}")
        except ImportError:
            logging.error("market_scanner.py not found")
        return 0

    # ── --self-tune ───────────────────────────────────────────────────────────
    if args.self_tune:
        try:
            import auto_tuner
            result = auto_tuner.run_full_tune(min_outcomes=3)
            print(f"\nAuto-Tune Complete ({result['outcomes_used']} outcomes used):")
            for c in result.get("changes",[]):
                print(f"  {c}")
            if "message" in result:
                print(f"  {result['message']}")
        except ImportError:
            logging.error("auto_tuner.py not found")
        return 0

    # ── --tuner-status ────────────────────────────────────────────────────────
    if args.tuner_status:
        try:
            import auto_tuner
            cfg = auto_tuner.get_current_config()
            print(f"\nATLAS Weights {'(DEFAULT)' if cfg['defaults_active'] else '(TUNED from outcomes)'}:")
            for k, v in cfg["weights"].items():
                print(f"  {k:<28} {v:.1f}")
            print(f"\nKey Thresholds:")
            for k, v in cfg["thresholds"].items():
                print(f"  {k:<32} {v}")
        except ImportError:
            logging.error("auto_tuner.py not found")
        return 0

    # ── --self-analyze ────────────────────────────────────────────────────────
    if args.self_analyze:
        try:
            import self_coder
            result = self_coder.run_self_analysis(min_losses=1)
            print(f"\nSelf-Analysis Complete:")
            print(f"  Losses analyzed:  {result['loss_count']}")
            print(f"  Patterns found:   {len(result['patterns'])}")
            print(f"  Proposals saved:  {len(result['proposals_generated'])}")
            for p in result["proposals_generated"]:
                print(f"    [{p['priority']}] {p['title']}")
            if result.get("report_path"):
                print(f"\nFull report: {result['report_path']}")
        except ImportError:
            logging.error("self_coder.py not found")
        return 0

    # ── --proposals ───────────────────────────────────────────────────────────
    if args.proposals:
        try:
            import self_coder
            proposals = self_coder.list_proposals()
            pending  = [p for p in proposals if p["status"] == "PENDING_REVIEW"]
            accepted = [p for p in proposals if p["status"] == "ACCEPTED"]
            print(f"\nATLAS Code Improvement Proposals")
            print(f"  Pending review: {len(pending)}")
            print(f"  Accepted:       {len(accepted)}")
            if pending:
                print(f"\nPending proposals (run to accept):")
                for p in pending:
                    pid = p['id'][:24]
                    print(f"\n  [{p.get('priority','?')}] {p['title']}")
                    print(f"  Pattern: {p.get('count',0)}x {p.get('label','')}")
                    print(f"  File:    {p.get('target_file','?')}")
                    print(f"  Accept:  python auto_bot.py self_coder accept {pid}")
            else:
                print("\n  No pending proposals. Run --self-analyze first.")
        except ImportError:
            logging.error("self_coder.py not found")
        return 0

    # ── Phase 2A: Congressional Trade Intelligence ────────────────────────────
    if args.congress:
        try:
            import congress_tracker as ct
            data = ct.get_trades_for_ticker(args.congress.upper())
            print(data["context_text"])
        except ImportError:
            logging.error("congress_tracker.py not found")
        return 0

    if args.hot_congress:
        try:
            import congress_tracker as ct
            hot = ct.hot_congressional_tickers()
            print(f"\nHot Congressional Tickers — last 30 days ({len(hot)} found):")
            for h in hot:
                cluster = "  *** CLUSTER SIGNAL" if h["cluster_signal"] else ""
                print(f"  {h['ticker']:<6} {h['buy_count']:>3} buys  {h['unique_buyers']} buyers  {h['latest_date']}{cluster}")
        except ImportError:
            logging.error("congress_tracker.py not found")
        return 0

    if args.recent_congress:
        try:
            import congress_tracker as ct
            recent = ct.get_recent_all_trades(top_n=30)
            print(f"\nRecent Congressional Buys (last 14 days) — {len(recent)} trades:")
            for t in recent:
                print(f"  {t['tx_date']}  {t['chamber'][:1]}  {t['senator'][:28]:<28}  BUY  {t['ticker']:<6}  {t['amount']}")
        except ImportError:
            logging.error("congress_tracker.py not found")
        return 0

    # ── Phase 2A: Alpaca Paper Trading ────────────────────────────────────────
    if args.alpaca_status:
        try:
            import broker_alpaca as alp
            snap = alp.portfolio_snapshot()
            acct = snap["account"]
            mode = "PAPER TRADING" if snap.get("paper") else "LIVE TRADING"
            print(f"\nAlpaca {mode} Account")
            print(f"  Portfolio Value: ${acct.get('portfolio_value',0):,.2f}")
            print(f"  Cash:            ${acct.get('cash',0):,.2f}")
            print(f"  Buying Power:    ${acct.get('buying_power',0):,.2f}")
            print(f"  Status:          {acct.get('status','?')}")
            if snap["positions"]:
                print(f"\n  Positions ({len(snap['positions'])}):")
                for p in snap["positions"]:
                    pl = f"  P/L ${p.get('unrealized_pl',0):+.2f}" if p.get("unrealized_pl") is not None else ""
                    print(f"    {p['symbol']:<8} {p['qty']:>8.2f} sh @ ${p.get('avg_entry_price',0):.2f}{pl}")
            if snap["orders"]:
                print(f"\n  Open Orders ({len(snap['orders'])}):")
                for o in snap["orders"]:
                    print(f"    {o['id'][:8]}  {o['symbol']:<6}  {o['side']}  qty={o.get('qty','?')}  status={o['status']}")
        except ImportError:
            logging.error("broker_alpaca.py not found")
        return 0

    if args.alpaca_buy:
        try:
            import broker_alpaca as alp
            result = alp.place_market_order(args.alpaca_buy.upper(), args.qty, "buy",
                                            reason="Manual order via ATLAS CLI")
            if result:
                print(f"\nPaper BUY placed: {result['symbol']} x{result['qty']} — order_id={result['order_id']}")
            else:
                print("Order failed. Check logs.")
        except ImportError:
            logging.error("broker_alpaca.py not found")
        return 0

    if args.alpaca_sell:
        try:
            import broker_alpaca as alp
            result = alp.place_market_order(args.alpaca_sell.upper(), args.qty, "sell",
                                            reason="Manual order via ATLAS CLI")
            if result:
                print(f"\nPaper SELL placed: {result['symbol']} x{result['qty']} — order_id={result['order_id']}")
            else:
                print("Order failed. Check logs.")
        except ImportError:
            logging.error("broker_alpaca.py not found")
        return 0

    if args.alpaca_close:
        try:
            import broker_alpaca as alp
            result = alp.close_position(args.alpaca_close.upper())
            if result:
                print(f"\nPosition closed: {result}")
            else:
                print("Close failed. Do you have an open position for that ticker?")
        except ImportError:
            logging.error("broker_alpaca.py not found")
        return 0

    if args.alpaca_orders:
        try:
            import broker_alpaca as alp
            orders = alp.get_open_orders()
            print(f"\nOpen Alpaca Orders ({len(orders)}):")
            for o in orders:
                print(f"  {o['id'][:8]}  {o['symbol']:<6}  {o['side']}  qty={o.get('qty','?')}  type={o['type']}  status={o['status']}")
            if not orders:
                print("  No open orders.")
        except ImportError:
            logging.error("broker_alpaca.py not found")
        return 0

    # ── Phase 2A: Tradier Options API ─────────────────────────────────────────
    if args.tradier_chain:
        try:
            import broker_tradier as trd
            if not trd._TOKEN:
                print("\n[tradier] No TRADIER_TOKEN in .env.")
                print("  Register free at: https://developer.tradier.com/user/sign_up")
                print("  Then add:  TRADIER_TOKEN=your_sandbox_token")
            else:
                chain = trd.get_near_money_chain(args.tradier_chain.upper(), strikes_above=5, strikes_below=5)
                print(f"\n{args.tradier_chain.upper()} — {chain.get('expiration')} | Price: ${chain.get('current_price')} | ATM: ${chain.get('atm_strike')}")
                iv = chain.get("iv_summary", {})
                if iv:
                    print(f"IV avg: {iv.get('avg_iv')}%  max: {iv.get('max_iv')}%")
                print("\nCALLS:")
                for c in chain.get("calls", []):
                    itm = "ITM" if c.get("in_the_money") else "OTM"
                    print(f"  ${c.get('strike',0):>8.2f} {itm}  bid={str(c.get('bid','-')):>6}  ask={str(c.get('ask','-')):>6}  "
                          f"delta={str(c.get('delta','-')):>7}  theta={str(c.get('theta','-')):>7}  vol={c.get('volume',0):>6,}")
        except ImportError:
            logging.error("broker_tradier.py not found")
        return 0

    if args.tradier_pcr:
        try:
            import broker_tradier as trd
            if not trd._TOKEN:
                print("\nAdd TRADIER_TOKEN to .env first. Free at developer.tradier.com")
            else:
                pcr = trd.get_pcr(args.tradier_pcr.upper())
                if pcr:
                    print(f"\n{args.tradier_pcr.upper()} PCR:")
                    print(f"  Volume PCR:   {pcr.get('pcr_volume','?')}")
                    print(f"  OI PCR:       {pcr.get('pcr_oi','?')}")
                    print(f"  Call Volume:  {pcr.get('call_volume',0):,}")
                    print(f"  Put Volume:   {pcr.get('put_volume',0):,}")
                    print(f"  Sentiment:    {pcr.get('sentiment','?')}")
        except ImportError:
            logging.error("broker_tradier.py not found")
        return 0

    # ── --deep-research TICKER ───────────────────────────────────────────────
    if args.deep_research:
        try:
            import deep_research as dr
            logging.info("Starting deep research on %s (budget=$%.0f)...",
                         args.deep_research.upper(), args.budget)
            research = dr.research_ticker(args.deep_research, budget=args.budget)
            if research:
                path = dr.write_report(research)
                logging.info("Done! Open: %s", path)
            else:
                logging.error("Deep research returned no data.")
        except ImportError:
            logging.error("deep_research.py not found next to auto_bot.py")
        return 0

    # ── --discover THEME ─────────────────────────────────────────────────────
    if args.discover:
        try:
            import deep_research as dr
            logging.info("Discovering stocks: '%s' (budget=$%.0f, max=%d)...",
                         args.discover, args.budget, args.max_discover)
            all_res = dr.discover_stocks(args.discover, budget=args.budget,
                                          max_results=args.max_discover)
            if all_res:
                for r in all_res:
                    dr.write_report(r)
                disc_path = dr.write_discovery_report(args.discover, all_res)
                logging.info("Discovery done! Open: %s", disc_path)
            else:
                logging.warning("No stocks discovered for: %s", args.discover)
        except ImportError:
            logging.error("deep_research.py not found next to auto_bot.py")
        return 0

    robinhood_login()   # phone approval happens here on first run

    if args.diagnose_robinhood:
        print("\n=== Robinhood Diagnostic ===")
        print(f"Username : {os.environ.get('ROBINHOOD_USERNAME', 'NOT SET')}")
        print(f"Password : {'SET (len=' + str(len(os.environ.get('ROBINHOOD_PASSWORD',''))) + ')' if os.environ.get('ROBINHOOD_PASSWORD') else 'NOT SET'}")
        print(f"Joint acct marker  : {os.environ.get('ROBINHOOD_JOINT_ACCOUNT_NUMBER', 'not set')}")
        print(f"Individual acct    : {os.environ.get('ROBINHOOD_INDIVIDUAL_ACCOUNT_NUMBER', 'not set')}")
        print(f"Login result : {'SUCCESS' if _rh_logged_in else 'FAILED — see ERROR lines above'}")
        return 0

    if args.once_daily:
        if not TEMPLATE_HTML.is_file():
            logging.error(
                "Missing template: %s (required for --once-daily to read watchlist tickers)",
                TEMPLATE_HTML,
            )
            return 1
        _safe_run(daily_deep_research, "--once-daily")
        return 0

    if args.once_intraday:
        if not TEMPLATE_HTML.is_file():
            logging.error(
                "Missing template: %s (required for --once-intraday dashboard refresh)",
                TEMPLATE_HTML,
            )
            return 1
        _safe_run(intraday_tracker, "--once-intraday")
        return 0

    if not TEMPLATE_HTML.is_file():
        logging.error("Missing template: %s", TEMPLATE_HTML)
        logging.info(
            "CLI commands (--regime, --alpaca-status, --deep-research, ...) work without "
            "this file. Add stock_research_v3.html beside auto_bot.py to run the "
            "default Robinhood/HTML scheduler."
        )
        return 1

    try:
        run_scheduler_loop()
    except KeyboardInterrupt:
        logging.info("Stopped by user.")
    return 0


if __name__ == "__main__":
    sys.exit(main())