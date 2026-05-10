"""Scheduled morning email digest (regime, movers MVP, macro line)."""

from __future__ import annotations

import json
import logging
import os
import smtplib
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

log = logging.getLogger("atlas_digest")


def _root() -> Path:
    return Path(__file__).resolve().parent


def _gather_digest_payload() -> dict[str, Any]:
    out: dict[str, Any] = {"ts": datetime.now().isoformat()}
    try:
        import market_scanner as ms

        out["regime"] = ms.detect_market_regime()
    except Exception as e:
        out["regime_error"] = str(e)

    cache = _root() / "data_cache" / "crypto_top50_latest.json"
    if cache.is_file():
        try:
            raw = json.loads(cache.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                top = []
                for row in raw[:8]:
                    if isinstance(row, dict) and row.get("symbol"):
                        top.append(
                            {
                                "symbol": row.get("symbol"),
                                "chg": row.get("change_pct") or row.get("change"),
                            }
                        )
                    elif isinstance(row, str):
                        top.append({"symbol": row})
                out["crypto_movers_sample"] = top
        except (OSError, json.JSONDecodeError) as e:
            out["crypto_cache_error"] = str(e)

    for sym in ("SPY", "QQQ", "BTC-USD"):
        try:
            import yfinance as yf

            t = yf.Ticker(sym)
            h = t.history(period="5d")
            if h is not None and not h.empty:
                last = float(h["Close"].iloc[-1])
                prev = float(h["Close"].iloc[-2]) if len(h) > 1 else last
                gap_pct = (last / prev - 1.0) * 100 if prev else 0.0
                out.setdefault("equity_crypto_gaps", {})[sym] = round(gap_pct, 3)
        except Exception as e:
            out.setdefault("market_snap_errors", []).append(f"{sym}: {e}")

    out["insider_note"] = "Use ATLAS Option 1 / scrapers for symbol-level insider flow."
    return out


def _format_digest_email(payload: dict[str, Any]) -> str:
    lines = [
        "ATLAS Morning Digest",
        "",
        f"Generated: {payload.get('ts', '')}",
        "",
    ]
    reg = payload.get("regime") or {}
    if isinstance(reg, dict):
        lines.append(f"Regime: {reg.get('regime', '—')}")
        if reg.get("signal"):
            lines.append(str(reg.get("signal"))[:500])
    mv = payload.get("crypto_movers_sample")
    if isinstance(mv, list) and mv:
        lines.append("")
        lines.append("Crypto leaderboard (cached sample):")
        for x in mv[:6]:
            lines.append(f"  {x}")
    gaps = payload.get("equity_crypto_gaps")
    if isinstance(gaps, dict) and gaps:
        lines.append("")
        lines.append("Recent session change % (5d history, last vs prev close):")
        for k, v in gaps.items():
            lines.append(f"  {k}: {v}%")
    lines.extend(["", str(payload.get("insider_note", "")), "", "— ATLAS"])
    return "\n".join(lines)


def _send_sendgrid(to_addr: str, subject: str, text: str) -> None:
    import requests

    key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("SENDGRID_API_KEY missing")
    from_addr = (os.environ.get("DIGEST_FROM_EMAIL") or "atlas-digest@localhost").strip()
    url = "https://api.sendgrid.com/v3/mail/send"
    body = {
        "personalizations": [{"to": [{"email": to_addr}]}],
        "from": {"email": from_addr},
        "subject": subject,
        "content": [{"type": "text/plain", "value": text}],
    }
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=body, timeout=60)
    r.raise_for_status()


def _send_smtp(to_addr: str, subject: str, text: str) -> None:
    host = (os.environ.get("SMTP_HOST") or "").strip()
    if not host:
        raise RuntimeError("SMTP_HOST not set")
    port = int(os.environ.get("SMTP_PORT") or "587")
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = (os.environ.get("SMTP_PASSWORD") or "").strip()
    from_addr = (os.environ.get("DIGEST_FROM_EMAIL") or user or "atlas-digest@localhost").strip()
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(from_addr, [to_addr], msg.as_string())


def send_digest_email() -> None:
    to_addr = (os.environ.get("DIGEST_EMAIL") or "").strip()
    if not to_addr:
        return
    payload = _gather_digest_payload()
    text = _format_digest_email(payload)
    subject = f"ATLAS Digest — {datetime.now().strftime('%Y-%m-%d')}"
    if (os.environ.get("SENDGRID_API_KEY") or "").strip():
        _send_sendgrid(to_addr, subject, text)
    else:
        _send_smtp(to_addr, subject, text)
    log.info("Digest email sent to %s", to_addr.split("@")[0] + "@…")


def _digest_worker() -> None:
    state_path = _root() / "atlas_vault" / "03-Outputs" / ".digest_last_sent"
    tz_name = (os.environ.get("DIGEST_TZ") or "America/New_York").strip()
    while True:
        time.sleep(55)
        if not (os.environ.get("DIGEST_EMAIL") or "").strip():
            continue
        try:
            tz = ZoneInfo(tz_name)
            now = datetime.now(tz)
            if now.hour != 7 or now.minute > 12:
                continue
            day = now.strftime("%Y-%m-%d")
            if state_path.is_file() and state_path.read_text(encoding="utf-8").strip() == day:
                continue
            send_digest_email()
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(day, encoding="utf-8")
            time.sleep(300)
        except Exception:
            log.exception("digest worker tick")


def start_digest_worker() -> None:
    if not (os.environ.get("DIGEST_EMAIL") or "").strip():
        log.info("Daily digest disabled (unset DIGEST_EMAIL)")
        return
    has_sg = bool((os.environ.get("SENDGRID_API_KEY") or "").strip())
    has_smtp = bool((os.environ.get("SMTP_HOST") or "").strip())
    if not has_sg and not has_smtp:
        log.warning("Digest enabled but neither SENDGRID_API_KEY nor SMTP_HOST is set — worker idle")
        return
    t = threading.Thread(target=_digest_worker, daemon=True, name="atlas-digest")
    t.start()
    log.info("Digest worker started (DIGEST_TZ=%s)", os.environ.get("DIGEST_TZ", "America/New_York"))


__all__ = ["send_digest_email", "start_digest_worker"]
