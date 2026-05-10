#!/usr/bin/env python3
"""
ATLAS Screen Watcher
--------------------
Watches the screen for Robinhood windows, extracts position data via Gemini
Vision, and writes positions_cache.json which the news scanner then monitors.

Optional screenshot files (disabled by default — captures stay in RAM unless enabled):
  SCREEN_WATCHER_SAVE=1     → each time Vision runs, write reports/watcher_last.png
  SCREEN_WATCHER_ARCHIVE=1 → also save timestamped copies under reports/watcher_captures/ (keeps last 25)

Usage (standalone):
    python screen_watcher.py                 # starts watching
    python screen_watcher.py --once          # one capture + extract, then exit
    python screen_watcher.py --once --save   # same + write reports/watcher_last.png

Designed to be run standalone if needed; auto_bot.py --watch no longer starts this
module (use dashboard POST /add_position and manual positions instead).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
import re as _re
from datetime import datetime as _dt, date as _date
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from gemini_limiter import wait_for_slot

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")
load_dotenv()

POSITIONS_CACHE = SCRIPT_DIR / "positions_cache.json"
CAPTURE_INTERVAL = 0.5          # seconds between screenshots
GEMINI_DEBOUNCE  = 4.0          # min seconds between Gemini Vision calls
DIFF_THRESHOLD   = 0.15         # fraction of pixels that must change to trigger Vision (~15%)

_last_vision_call = 0.0
_VISION_MIN_INTERVAL = 8.0       # seconds minimum between Vision API calls

# Screenshot disk export: SCREEN_WATCHER_SAVE=1 in .env, or CLI --save / save_captures=True

def _env_truthy(key: str) -> bool:
    return os.environ.get(key, "").strip().lower() in ("1", "true", "yes", "on")


def _should_save_disk(cli_override: bool | None) -> bool:
    if cli_override is True:
        return True
    if cli_override is False:
        return False
    return _env_truthy("SCREEN_WATCHER_SAVE")


def _save_screenshot_disk(png_bytes: bytes) -> None:
    """
    Latest frame sent to Gemini Vision -> reports/watcher_last.png.
    SCREEN_WATCHER_ARCHIVE=1 -> also reports/watcher_captures/capture_*.png (keeps last 25).
    """
    if not png_bytes:
        return
    try:
        reports_dir = SCRIPT_DIR / "reports"
        reports_dir.mkdir(exist_ok=True)
        last_path = reports_dir / "watcher_last.png"
        last_path.write_bytes(png_bytes)
        logging.info("Screenshot saved -> %s", last_path)

        if _env_truthy("SCREEN_WATCHER_ARCHIVE"):
            arc = reports_dir / "watcher_captures"
            arc.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            p = arc / f"capture_{ts}.png"
            p.write_bytes(png_bytes)
            files = sorted(arc.glob("capture_*.png"), key=lambda x: x.stat().st_mtime)
            for old in files[:-25]:
                try:
                    old.unlink()
                except OSError:
                    pass
    except Exception as e:
        logging.debug("Screenshot disk save failed: %s", e)

# ─────────────────────────────────────────────────────────────────────────────
# Optional deps — graceful fallback if not installed
# ─────────────────────────────────────────────────────────────────────────────
try:
    import mss
    import mss.tools
    _MSS_OK = True
except ImportError:
    _MSS_OK = False

try:
    from PIL import Image, ImageChops
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

try:
    from google import genai as _genai
    _GENAI_OK = True
except ImportError:
    _GENAI_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Gemini Vision client
# ─────────────────────────────────────────────────────────────────────────────
def _gemini_client():
    if not _GENAI_OK:
        return None
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return None
    return _genai.Client(api_key=api_key)


_VISION_PROMPT = """
You are reading a screenshot of the Robinhood brokerage app or website.

Extract ALL visible positions — both stock holdings AND options contracts.

Return a single JSON object with this exact structure (omit any field you
cannot see, but keep the key with null):

{
  "stocks": [
    {
      "ticker":          "SOUN",
      "company":         "SoundHound AI",
      "shares":          50,
      "avg_buy_price":   8.75,
      "current_price":   8.12,
      "market_value":    406.00,
      "total_return":    -31.50,
      "total_return_pct":-7.20
    }
  ],
  "options": [
    {
      "ticker":          "SOUN",
      "option_type":     "call",
      "strike":          8.00,
      "expiry":          "2026-05-16",
      "contracts":       1,
      "avg_premium":     1.50,
      "current_price":   0.85,
      "market_value":    85.00,
      "total_return":    -65.00,
      "total_return_pct":-43.33
    }
  ],
  "account_type": "joint",
  "cash_balance":  0.00,
  "page_type": "positions | stock_detail | options_chain | other",
  "timestamp": "ISO8601"
}

Rules:
- Use null for any number you cannot see clearly.
- For account_type: if you see "Joint" in the UI write "joint", else "individual".
- page_type describes what screen is visible.
- For options expiry: Robinhood shows dates as 'May 16', 'May 16 2026',
  '5/16', '5/16/26'. ALWAYS convert to ISO format YYYY-MM-DD.
  If year is missing, assume next calendar occurrence.
  NEVER return null for expiry if ANY date is visible on screen.
- avg_premium for options = premium per share (divide contract cost by 100).
- Return ONLY the JSON — no markdown, no explanation.
"""


def _extract_via_vision(img_bytes: bytes, client) -> dict | None:
    """Send screenshot bytes to Gemini Vision and parse returned JSON."""
    if client is None:
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        b64 = base64.b64encode(img_bytes).decode()
        response = None
        for _attempt in range(4):
            try:
                wait_for_slot("screen_watcher")
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        {
                            "parts": [
                                {"text": _VISION_PROMPT},
                                {"inline_data": {"mime_type": "image/png", "data": b64}},
                            ]
                        }
                    ],
                )
                break
            except Exception as _e:
                if ("429" in str(_e)
                        or "quota" in str(_e).lower()
                        or "RESOURCE_EXHAUSTED" in str(_e)):
                    wait = 20 * (2 ** _attempt)  # 20s, 40s, 80s, 160s
                    logging.warning("[gemini] 429 rate limit — waiting %ss before retry", wait)
                    time.sleep(wait)
                else:
                    raise
        else:
            logging.error("[gemini] All retries exhausted — skipping this synthesis")
            return None
        raw = response.text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            import re
            raw = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", raw)
            raw = re.sub(r"\s*```\s*$", "", raw).strip()
        return json.loads(raw)
    except Exception:
        logging.debug("Gemini Vision extraction failed.", exc_info=True)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Positions cache
# ─────────────────────────────────────────────────────────────────────────────
def _normalize_expiry(raw):
    """
    Convert any Robinhood expiry format to YYYY-MM-DD.
    Smart year inference: if month/day is still in the future this
    calendar year, use current year. If it has already passed, use
    next year. This means no manual edits are ever needed.
    """
    if not raw or str(raw).strip().lower() in ('null', 'none', '', 'unknown'):
        return None
    raw = str(raw).strip()

    # Already ISO format — return as-is
    if _re.match(r'2\d{3}-\d{2}-\d{2}$', raw):
        return raw

    def _resolve_year(month, day):
        """Pick current year if date is still upcoming, else next year."""
        today = _date.today()
        try:
            candidate = _date(today.year, month, day)
        except ValueError:
            return today.year  # invalid date fallback
        # Give a 1-day buffer so same-day expiry isn't bumped to next year
        if candidate >= today:
            return today.year
        else:
            return today.year + 1

    # M/D or M/D/YY or M/D/YYYY  (e.g. "6/18", "6/18/26", "6/18/2026")
    m = _re.match(r'^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$', raw)
    if m:
        mo, day = int(m.group(1)), int(m.group(2))
        if m.group(3):
            yr_raw = m.group(3)
            yr = int('20' + yr_raw[-2:]) if len(yr_raw) <= 2 else int(yr_raw)
        else:
            yr = _resolve_year(mo, day)
        return f"{yr}-{mo:02d}-{day:02d}"

    # "Jun 18" / "June 18" / "Jun 18, 2026" / "June 18 2026"
    cleaned = raw.replace(',', '').strip()
    for fmt in ('%b %d %Y', '%B %d %Y'):
        try:
            d = _dt.strptime(cleaned, fmt)
            return f"{d.year}-{d.month:02d}-{d.day:02d}"
        except ValueError:
            continue
    for fmt in ('%b %d', '%B %d'):
        try:
            d = _dt.strptime(cleaned, fmt)
            yr = _resolve_year(d.month, d.day)
            return f"{yr}-{d.month:02d}-{d.day:02d}"
        except ValueError:
            continue

    # Nothing matched — return raw string so it's visible, not silently lost
    return raw


def load_cache() -> dict:
    if POSITIONS_CACHE.exists():
        try:
            data = json.loads(POSITIONS_CACHE.read_text(encoding="utf-8"))
            for opt in data.get("options") or []:
                opt["expiry"] = _normalize_expiry(opt.get("expiry"))
            return data
        except Exception:
            pass
    return {"stocks": [], "options": [], "last_seen": None, "snapshots": []}


def save_cache(data: dict) -> None:
    data["last_seen"] = datetime.now(timezone.utc).isoformat()
    POSITIONS_CACHE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _merge_into_cache(cache: dict, extracted: dict) -> bool:
    """
    Merge freshly extracted positions into the persistent cache.
    Returns True if anything actually changed.
    """
    changed = False
    ts = datetime.now(timezone.utc).isoformat()

    for key in ("stocks", "options"):
        new_items: list[dict] = extracted.get(key) or []
        if not new_items:
            continue

        existing = {_item_key(i, key): i for i in (cache.get(key) or [])}
        for item in new_items:
            if key == "options":
                item["expiry"] = _normalize_expiry(item.get("expiry"))
            k = _item_key(item, key)
            if k not in existing or _differs(existing.get(k, {}), item):
                existing[k] = {**item, "last_updated": ts}
                changed = True

        cache[key] = list(existing.values())

    # Fallback: recover ISO expiry from option key if Vision omitted expiry
    for opt in cache.get("options") or []:
        if not opt.get("expiry"):
            key = _item_key(opt, "options")
            parts = key.split("_")
            if len(parts) < 4:
                parts = key.split("|")
            if len(parts) >= 4:
                candidate = parts[-1]
                if re.match(r"20\d{2}-\d{2}-\d{2}", candidate):
                    opt["expiry"] = _normalize_expiry(candidate)

    # Keep a rolling log of raw snapshots (last 50)
    snapshots: list[dict] = cache.get("snapshots") or []
    snapshots.append({
        "ts": ts,
        "page_type": extracted.get("page_type"),
        "account_type": extracted.get("account_type"),
        "stocks_count": len(extracted.get("stocks") or []),
        "options_count": len(extracted.get("options") or []),
    })
    cache["snapshots"] = snapshots[-50:]
    return changed


def _item_key(item: dict, kind: str) -> str:
    if kind == "stocks":
        return (item.get("ticker") or "?").upper()
    # options key: ticker+type+strike+expiry
    return "|".join([
        (item.get("ticker") or "?").upper(),
        (item.get("option_type") or "?").lower(),
        str(item.get("strike") or "?"),
        (item.get("expiry") or "?"),
    ])


def _differs(old: dict, new: dict) -> bool:
    """True if any numeric field changed by more than 0.01."""
    watch = ("current_price", "market_value", "total_return", "total_return_pct",
             "shares", "contracts")
    for k in watch:
        ov, nv = old.get(k), new.get(k)
        if ov is None and nv is None:
            continue
        if ov is None or nv is None:
            return True
        try:
            if abs(float(ov) - float(nv)) > 0.01:
                return True
        except (TypeError, ValueError):
            pass
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Screenshot + diff helpers
# ─────────────────────────────────────────────────────────────────────────────
def _capture_screen() -> bytes | None:
    """Capture entire primary monitor, return PNG bytes."""
    if not _MSS_OK or not _PIL_OK:
        return None
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary monitor
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            buf = BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue()
    except Exception:
        logging.debug("Screenshot failed.", exc_info=True)
        return None


def _img_hash(png_bytes: bytes) -> str:
    return hashlib.md5(png_bytes).hexdigest()


def _pixel_diff_fraction(prev_bytes: bytes, curr_bytes: bytes) -> float:
    """Return fraction [0..1] of pixels that changed between two PNG byte strings."""
    if not _PIL_OK:
        return 1.0  # always trigger if Pillow not available
    try:
        img1 = Image.open(BytesIO(prev_bytes)).convert("RGB")
        img2 = Image.open(BytesIO(curr_bytes)).convert("RGB")
        # Resize to 320×180 before diff — fast and accurate enough
        size = (320, 180)
        img1 = img1.resize(size, Image.BILINEAR)
        img2 = img2.resize(size, Image.BILINEAR)
        diff = ImageChops.difference(img1, img2)
        total_pixels = size[0] * size[1]
        changed = sum(1 for r, g, b in diff.getdata() if (r + g + b) > 15)
        return changed / total_pixels
    except Exception:
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Main watcher loop
# ─────────────────────────────────────────────────────────────────────────────
_stop_event = threading.Event()


def watch_loop(once: bool = False, save_captures: bool | None = None) -> None:
    """
    Main loop — call this in a background thread or directly.
    Set _stop_event to stop gracefully.
    """
    if not _MSS_OK:
        logging.error("screen_watcher: 'mss' not installed. Run: pip install mss Pillow")
        return
    if not _PIL_OK:
        logging.error("screen_watcher: 'Pillow' not installed. Run: pip install Pillow")
        return

    client = _gemini_client()
    if client is None:
        logging.error("screen_watcher: GOOGLE_API_KEY missing or google-genai not installed.")
        return

    cache = load_cache()
    prev_bytes: bytes | None = None
    last_vision_call: float  = 0.0
    heartbeat_due: float     = time.time() + 60.0
    frames_captured: int     = 0

    logging.info("Screen watcher started. Capturing every %.1fs. "
                 "Gemini Vision fires on ≥%.0f%% pixel change (debounce %.1fs).",
                 CAPTURE_INTERVAL, DIFF_THRESHOLD * 100, GEMINI_DEBOUNCE)

    while not _stop_event.is_set():
        tick_start = time.time()

        curr_bytes = _capture_screen()
        if curr_bytes is None:
            time.sleep(CAPTURE_INTERVAL)
            continue

        frames_captured += 1
        diff = 0.0
        should_vision = False

        if prev_bytes is None:
            # First frame always triggers
            should_vision = True
        else:
            diff = _pixel_diff_fraction(prev_bytes, curr_bytes)
            should_vision = diff >= DIFF_THRESHOLD

        # Enforce debounce
        if should_vision and (time.time() - last_vision_call) < GEMINI_DEBOUNCE:
            should_vision = False

        if should_vision:
            global _last_vision_call
            now = time.time()
            if now - _last_vision_call < _VISION_MIN_INTERVAL:
                logging.debug('[watcher] Rate limit — skipping Vision call (too soon)')
            else:
                _last_vision_call = now
                logging.info("Screen change detected (diff=%.1f%%) — sending to Gemini Vision...",
                             diff * 100)
                if _should_save_disk(save_captures):
                    _save_screenshot_disk(curr_bytes)
                extracted = _extract_via_vision(curr_bytes, client)
                last_vision_call = time.time()

                if extracted:
                    changed = _merge_into_cache(cache, extracted)
                    if changed:
                        save_cache(cache)
                        stocks  = [s.get("ticker") for s in (cache.get("stocks")  or [])]
                        options = [f"{o.get('ticker')} {o.get('option_type')} {o.get('strike')}"
                                   for o in (cache.get("options") or [])]
                        logging.info("Positions updated → stocks=%s | options=%s", stocks, options)
                    else:
                        logging.debug("Vision ran but no position changes detected.")
                else:
                    logging.debug("Gemini Vision returned no parseable data.")

        prev_bytes = curr_bytes

        # Heartbeat every 60 seconds
        if time.time() >= heartbeat_due:
            stocks_n  = len(cache.get("stocks")  or [])
            options_n = len(cache.get("options") or [])
            logging.info("[HEARTBEAT] frames=%d  known stocks=%d  known options=%d  "
                         "cache_path=%s",
                         frames_captured, stocks_n, options_n, POSITIONS_CACHE)
            heartbeat_due = time.time() + 60.0

        if once:
            break

        # Sleep for remainder of interval
        elapsed = time.time() - tick_start
        sleep_for = max(0.0, CAPTURE_INTERVAL - elapsed)
        time.sleep(sleep_for)

    logging.info("Screen watcher stopped.")


def start_background(save_captures: bool | None = None) -> threading.Thread:
    """Start the watcher in a daemon thread. Set SCREEN_WATCHER_SAVE=1 or pass save_captures."""
    t = threading.Thread(
        target=watch_loop,
        kwargs={"save_captures": save_captures},
        name="ScreenWatcher",
        daemon=True,
    )
    t.start()
    return t


def stop() -> None:
    _stop_event.set()


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="ATLAS Screen Watcher")
    ap.add_argument("--once",    action="store_true", help="Capture once and exit")
    ap.add_argument("--save",    action="store_true",
                    help="Write Vision frames to reports/watcher_last.png (also set SCREEN_WATCHER_SAVE=1 for --watch)")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    watch_loop(once=args.once, save_captures=True if args.save else None)
