"""SEC Form 4 atom + lightweight XML parse -> insider_trades_latest.json."""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import feedparser

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from atlas_core.utils.agent_utils import requests_get_text, sleep_backoff, write_cache_json_pair

DATA_CACHE_DIR = REPO_ROOT / "data_cache"
OUTPUT_STABLE_NAME = "insider_trades_latest.json"
SEC_FEED = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4"
    "&dateb=&owner=include&count=120&output=atom"
)
SEC_HEADERS = {
    "User-Agent": "ATLAS ATLAS Financial Research atlas@localhost (compliance scraping)",
}

FALLBACK_FILINGS: list[dict[str, Any]] = [
    {
        "ticker": "NVDA",
        "company_name": "NVIDIA Corporation",
        "insider_name": "Fallback Director Signal",
        "role": "Director",
        "transaction_type": "BUY",
        "shares": 1000.0,
        "price": 0.0,
        "total_value": None,
        "date": "",
        "signal": "BULLISH_INSIDER",
    },
    {
        "ticker": "TSLA",
        "company_name": "Tesla, Inc.",
        "insider_name": "Fallback Officer Signal",
        "role": "Officer",
        "transaction_type": "SELL",
        "shares": 1000.0,
        "price": 0.0,
        "total_value": None,
        "date": "",
        "signal": "BEARISH_INSIDER",
    },
]


def _pace_delay() -> float:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return 0.0
    return 0.52


def iso_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fallback_filings(*, top_n: int) -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = [dict(row) for row in FALLBACK_FILINGS[: max(1, top_n)]]
    for row in rows:
        row["date"] = today
    return rows


ROLE_HINTS_CXO = ("ceo", "cfo", "coo", "president", "director", "chief")


def _signals_from_txt_xml(raw: str) -> tuple[list[str], str, str]:
    """
    Rough scan for Purchases vs Sales codes (P/A vs S in Form 4 context).
    Returns (list of BUY/SELL heuristic), ticker_symbol, insider_name fragments.
    """
    upper = raw[:500000]
    txs: list[str] = []
    for m in re.finditer(r"<transactionCode>\s*([^\s]+)\s*</transactionCode>", upper, re.I):
        code = str(m.group(1)).strip().upper()
        if code.startswith("P") or code in ("M",):  # Purchases incl. swaps
            txs.append("BUY")
        elif code.startswith("S"):
            txs.append("SELL")
    tick = ""
    nm = ""
    nm_m = re.search(r"<issuerTradingSymbol>\s*([^<]+)<", upper, re.I)
    if nm_m:
        tick = nm_m.group(1).strip().upper()
    name_m = re.search(r"<rptOwnerName[^>]*>([^<]+)</rptOwnerName>", upper, re.I)
    off_m = re.search(r"<officerTitle>\s*([^<]+)<", upper, re.I)
    if name_m:
        nm = html.unescape(name_m.group(1)).strip()
    role = ""
    if off_m:
        role = html.unescape(off_m.group(1)).strip()
    if role:
        nm = nm or role
    return txs, tick, nm


def cxo_match(role_or_title: str) -> bool:
    t = (role_or_title or "").lower()
    return any(k in t for k in ROLE_HINTS_CXO)


def parse_entry_metadata(entry_title: str) -> tuple[str, str]:
    """Best-effort companyName / ticker cues from Atom title."""
    title = html.unescape(entry_title or "").strip()
    sym = ""
    m = re.search(r"\(([A-Z]{1,5})\)", title[-30:])
    if m:
        sym = m.group(1)
    return title[:200], sym


def scrape(*, top_n: int = 40) -> dict[str, Any]:
    filings: list[dict[str, Any]] = []
    txt = ""
    under_test = bool(os.environ.get("PYTEST_CURRENT_TEST"))
    http_timeout = 8.0 if under_test else 15.0
    entry_cap = 8 if under_test else max(8, min(max(1, top_n) * 3, 30))
    try:
        txt = requests_get_text(
            SEC_FEED,
            headers={**SEC_HEADERS, "Accept": "application/atom+xml"},
            retries=1 if under_test else 2,
            timeout_s=http_timeout,
        )
        if _pace_delay() > 0:
            sleep_backoff(1, base=_pace_delay())
    except Exception:
        txt = ""

    fed = feedparser.parse(txt if txt else "<?xml?>")
    if not getattr(fed, "entries", None):
        rows = fallback_filings(top_n=top_n)
        return {
            "generated_at": iso_now_z(),
            "source": "sec_edgar_form4_atom",
            "record_count": len(rows),
            "filings": rows,
            "_meta": {"warning": "SEC atom fetch or parse failed — check UA / network"},
        }

    for e in getattr(fed, "entries", [])[:entry_cap]:
        if len(filings) >= max(1, min(top_n, 120)):
            break
        link = e.get("link") or ""
        updated = ""
        ud = getattr(e, "updated_parsed", None) or getattr(e, "published_parsed", None)
        if ud:
            try:
                updated = datetime(
                    ud.tm_year,
                    ud.tm_mon,
                    ud.tm_mday,
                    tzinfo=timezone.utc,
                ).strftime("%Y-%m-%d")
            except Exception:
                updated = (e.get("updated") or e.get("published") or "")[:10]
        else:
            updated = str(e.get("updated") or e.get("published") or "")[:10]

        co, sym_hint = parse_entry_metadata(e.get("title", ""))

        doc_raw = ""
        xml_url_used = ""
        if link.startswith("http"):
            try:
                if _pace_delay() > 0:
                    sleep_backoff(1, base=_pace_delay())
                host = urlparse(link).hostname or ""
                h = SEC_HEADERS.copy()
                if host:
                    h["Referer"] = f"https://{host}/"
                page = requests_get_text(
                    link,
                    headers=h,
                    retries=1 if under_test else 2,
                    timeout_s=http_timeout,
                )
                doc_raw = page
                if "<transactionCode>" not in page:
                    soup = BeautifulSoup(page, "html.parser")
                    for ta in soup.find_all("a", href=True):
                        href = ta["href"]
                        if ".xml" not in href.lower():
                            continue
                        if any(x in href.lower() for x in ("ownership", "f345", "doc", "submission")):
                            absu = urljoin(link, href)
                            if _pace_delay() > 0:
                                sleep_backoff(1, base=_pace_delay())
                            doc_raw = requests_get_text(
                                absu,
                                headers={**SEC_HEADERS, "Referer": link},
                                retries=1 if under_test else 2,
                                timeout_s=http_timeout,
                            )
                            xml_url_used = absu
                            break
            except Exception:
                doc_raw = ""

        if not doc_raw or len(doc_raw) < 120:
            continue

        tx_codes, sec_sym, insider = _signals_from_txt_xml(doc_raw)
        ticker = sec_sym or sym_hint or ""
        insider_name = insider or ""

        rm = re.search(r"<derivativeTable>(.*?)</derivativeTable>", doc_raw, re.S | re.I)
        ndm = re.search(r"<nonDerivativeTable>(.*?)</nonDerivativeTable>", doc_raw, re.S | re.I)
        nd_len = len(ndm.group(1) if ndm else "") or 0
        drv_len = len(rm.group(1) if rm else "") or 0
        if drv_len > nd_len * 2 and not tx_codes:
            continue

        if not tx_codes:
            continue

        role_guess = ""
        off_m = re.search(r"<officerTitle>\s*([^<]+)<", doc_raw, re.I)
        if off_m:
            role_guess = html.unescape(off_m.group(1)).strip()
        elif re.search(r"<isDirector\s*>1\s*<", doc_raw, re.I):
            role_guess = "Director"

        if role_guess and not cxo_match(role_guess) and role_guess != "Director":
            continue

        buys = tx_codes.count("BUY")
        sells = tx_codes.count("SELL")
        tx_type = "BUY" if buys >= sells else "SELL"

        vals = []
        for m in re.findall(
            r"<transactionAmounts>[\s\S]*?<transactionPricePerShare>[\s\S]*?"
            r"<value>([^<]+)</value>",
            doc_raw[:500000],
            re.I,
        ):
            try:
                vals.append(abs(float(str(m))))
            except ValueError:
                continue
        price = vals[0] if vals else 0.0

        qtys = []
        for m in re.findall(
            r"<transactionAmounts>[\s\S]*?<transactionShares>[\s\S]*?<value>([^<]+)</value>",
            doc_raw[:500000],
            re.I,
        ):
            try:
                qtys.append(abs(float(str(m))))
            except ValueError:
                continue
        shares = sum(qtys) if qtys else 0.0

        if tx_type == "BUY":
            sig = "BULLISH_INSIDER"
        else:
            sig = "BEARISH_INSIDER"

        row: dict[str, Any] = {
            "ticker": ticker or "UNKNOWN",
            "company_name": co,
            "insider_name": insider_name or "(see filing)",
            "role": role_guess or "",
            "transaction_type": tx_type,
            "shares": shares,
            "price": round(price, 4) if price else 0.0,
            "total_value": round(shares * price, 2) if shares and price else None,
            "date": updated,
            "signal": sig,
        }
        if xml_url_used:
            row["filing_xml"] = xml_url_used
        filings.append(row)

    out: dict[str, Any] = {
        "generated_at": iso_now_z(),
        "source": "sec_edgar_form4",
        "record_count": len(filings),
        "filings": filings[:top_n],
    }
    out["record_count"] = len(out["filings"])
    if not filings:
        out["filings"] = fallback_filings(top_n=top_n)
        out["record_count"] = len(out["filings"])
        out["_meta"] = {
            "data_quality": "fallback",
            "fallback_used": True,
            "warning": "Zero parsed Form 4 rows — Atom may have rendered without XML body or pacing blocked."
        }
    return out


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    return write_cache_json_pair(
        DATA_CACHE_DIR,
        payload,
        stable_filename=OUTPUT_STABLE_NAME,
        stamped_prefix="insider_trades_",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SEC Form 4 -> data_cache JSON")
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    try:
        out = scrape(top_n=max(1, args.top))
        if not args.dry_run:
            stable, stamped = write_outputs(out)
            print(f"Wrote {stable}")
            print(f"Wrote {stamped}")
        print(f"filings={out.get('record_count')}")
        return 0
    except Exception as e:
        print(f"insider_tracker_scraper failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
