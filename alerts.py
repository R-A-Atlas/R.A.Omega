"""
alerts.py — ATLAS Real-Time Price Alert System

Runs as a background thread, checks your positions every 60 seconds.
Fires a desktop notification + sound the SECOND a key level is crossed.

Alert types:
  PRICE_ABOVE     — stock breaks above a resistance level
  PRICE_BELOW     — stock drops below a support / stop loss
  PERCENT_MOVE    — stock moves more than X% in one check interval
  VOLUME_SPIKE    — volume exceeds X times the daily average
  EARNINGS_TODAY  — reminder when earnings are today
  NEWS_ALERT      — new headline detected since last check

Delivery:
  - Windows desktop toast notification (plyer)
  - System beep sound (winsound on Windows — import and Beep calls are wrapped;
    non-Windows / headless environments skip audio safely)
  - Logged to atlas_alerts.log
  - Printed to console

Alerts survive restarts — saved to atlas_alerts.json
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time

try:
    import winsound
    _WINSOUND_OK = True
except ImportError:
    winsound = None  # type: ignore
    _WINSOUND_OK = False

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yfinance as yf

log = logging.getLogger(__name__)

_ALERTS_FILE = Path(__file__).parent / "atlas_alerts.json"
_LOG_FILE    = Path(__file__).parent / "atlas_alerts.log"
_CHECK_INTERVAL_SECONDS = 60

# ─────────────────────────────────────────────────────────────────────────────
# Notification helper
# ─────────────────────────────────────────────────────────────────────────────
def _notify(title: str, message: str, urgent: bool = False) -> None:
    """Fire a desktop notification + sound."""
    # Log it always
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{ts}] {title}: {message}"
    log.info("ALERT: %s — %s", title, message)
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
    except Exception:
        pass

    # Desktop notification via plyer
    try:
        from plyer import notification
        notification.notify(
            title   = f"ATLAS: {title}",
            message = message,
            app_name = "ATLAS Trading",
            timeout  = 8 if urgent else 5,
        )
    except Exception:
        # Fallback: just print loudly
        print(f"\n{'!'*60}")
        print(f"  ALERT: {title}")
        print(f"  {message}")
        print(f"{'!'*60}\n")

    # Sound alert
    try:
        if _WINSOUND_OK and winsound:
            if urgent:
                for _ in range(3):
                    winsound.Beep(1000, 400)
                    time.sleep(0.1)
            else:
                winsound.Beep(800, 300)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Alert data model
# ─────────────────────────────────────────────────────────────────────────────
class Alert:
    def __init__(self, ticker: str, alert_type: str, trigger_value: float,
                 message: str = "", one_shot: bool = True,
                 alert_id: str = None):
        self.ticker        = ticker.upper()
        self.alert_type    = alert_type     # PRICE_ABOVE, PRICE_BELOW, PCT_MOVE, VOLUME_SPIKE
        self.trigger_value = trigger_value
        self.message       = message
        self.one_shot      = one_shot       # if True, auto-remove after firing
        self.triggered     = False
        self.created_at    = datetime.now(timezone.utc).isoformat()
        self.triggered_at  = None
        self.id            = alert_id or f"{ticker}_{alert_type}_{trigger_value}"

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "ticker":        self.ticker,
            "alert_type":    self.alert_type,
            "trigger_value": self.trigger_value,
            "message":       self.message,
            "one_shot":      self.one_shot,
            "triggered":     self.triggered,
            "created_at":    self.created_at,
            "triggered_at":  self.triggered_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Alert":
        a = cls(
            ticker        = d["ticker"],
            alert_type    = d["alert_type"],
            trigger_value = d["trigger_value"],
            message       = d.get("message",""),
            one_shot      = d.get("one_shot", True),
            alert_id      = d.get("id"),
        )
        a.triggered    = d.get("triggered", False)
        a.created_at   = d.get("created_at","")
        a.triggered_at = d.get("triggered_at")
        return a


# ─────────────────────────────────────────────────────────────────────────────
# Alert manager
# ─────────────────────────────────────────────────────────────────────────────
class AlertMonitor:
    """
    Background thread that polls prices every 60 seconds and fires alerts.
    Runs silently — you only hear from it when something matters.
    """

    def __init__(self):
        self._alerts:  list[Alert] = []
        self._lock     = threading.Lock()
        self._thread:  Optional[threading.Thread] = None
        self._running  = False
        self._last_prices: dict[str, float] = {}
        self._last_headlines: dict[str, set] = {}
        self._load_alerts()

    # ── Persistence ──────────────────────────────────────────────────────────
    def _load_alerts(self) -> None:
        if _ALERTS_FILE.exists():
            try:
                data = json.loads(_ALERTS_FILE.read_text(encoding="utf-8"))
                with self._lock:
                    self._alerts = [Alert.from_dict(d) for d in data
                                    if not d.get("triggered") or not d.get("one_shot")]
                log.info("Loaded %d active alerts from disk", len(self._alerts))
            except Exception:
                log.debug("Failed to load alerts file", exc_info=True)

    def _save_alerts(self) -> None:
        try:
            with self._lock:
                data = [a.to_dict() for a in self._alerts]
            _ALERTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ── Alert management ─────────────────────────────────────────────────────
    def add(self, ticker: str, alert_type: str, trigger_value: float,
            message: str = "", one_shot: bool = True) -> str:
        """Add a new price alert. Returns the alert ID."""
        ticker = ticker.upper()
        if not message:
            message = self._default_message(ticker, alert_type, trigger_value)

        alert = Alert(ticker, alert_type, trigger_value, message, one_shot)
        with self._lock:
            # Remove any existing alert of same type for same ticker/value
            self._alerts = [a for a in self._alerts
                            if not (a.ticker == ticker and a.alert_type == alert_type
                                    and a.trigger_value == trigger_value)]
            self._alerts.append(alert)
        self._save_alerts()
        log.info("Alert added: %s %s @ %.2f", ticker, alert_type, trigger_value)
        return alert.id

    def remove(self, alert_id: str) -> bool:
        with self._lock:
            before = len(self._alerts)
            self._alerts = [a for a in self._alerts if a.id != alert_id]
            removed = len(self._alerts) < before
        if removed:
            self._save_alerts()
        return removed

    def list_alerts(self) -> list[dict]:
        with self._lock:
            return [a.to_dict() for a in self._alerts if not a.triggered]

    def clear_ticker(self, ticker: str) -> int:
        ticker = ticker.upper()
        with self._lock:
            before = len(self._alerts)
            self._alerts = [a for a in self._alerts if a.ticker != ticker]
        self._save_alerts()
        return before - len(self._alerts)

    def _default_message(self, ticker: str, alert_type: str, value: float) -> str:
        if alert_type == "PRICE_ABOVE":
            return f"{ticker} broke above ${value:.2f} — resistance breached!"
        elif alert_type == "PRICE_BELOW":
            return f"{ticker} dropped below ${value:.2f} — check your stop loss!"
        elif alert_type == "PCT_MOVE":
            return f"{ticker} moved {value:+.1f}% — unusual price action!"
        elif alert_type == "VOLUME_SPIKE":
            return f"{ticker} volume spike {value:.1f}x average — something happening!"
        elif alert_type == "EARNINGS_TODAY":
            return f"{ticker} reports earnings today — be ready!"
        return f"{ticker} alert triggered at ${value:.2f}"

    # ── Auto-setup from research ──────────────────────────────────────────────
    def setup_from_research(self, research: dict) -> int:
        """
        Automatically set up sensible alerts from a deep research result.
        Called after every research run.
        Returns number of alerts created.
        """
        ticker = (research.get("ticker") or "").upper()
        if not ticker:
            return 0

        syn  = research.get("synthesis") or {}
        tp   = syn.get("trade_plan") or {}
        pl   = syn.get("price_levels") or {}
        mkt  = research.get("mktdata") or {}
        ea   = syn.get("earnings_analysis") or {}
        count = 0

        # Stop loss alert
        stop = tp.get("stop_loss") or pl.get("strong_support")
        if stop:
            try:
                self.add(ticker, "PRICE_BELOW", float(stop),
                         f"{ticker} hit stop loss ${stop} — consider exiting position!")
                count += 1
            except Exception:
                pass

        # Target 1 alert
        t1 = tp.get("target_1") or pl.get("immediate_resistance")
        if t1:
            try:
                self.add(ticker, "PRICE_ABOVE", float(t1),
                         f"{ticker} reached target 1 ${t1} — consider taking partial profit!")
                count += 1
            except Exception:
                pass

        # Target 2 alert
        t2 = tp.get("target_2") or pl.get("strong_resistance")
        if t2:
            try:
                self.add(ticker, "PRICE_ABOVE", float(t2),
                         f"{ticker} hit target 2 ${t2} — full profit target reached!")
                count += 1
            except Exception:
                pass

        # Earnings day alert
        next_e = ea.get("next_date") or mkt.get("next_earnings")
        if next_e and next_e != "unknown":
            try:
                from datetime import date
                ed = datetime.strptime(str(next_e)[:10], "%Y-%m-%d").date()
                if ed >= date.today():
                    self.add(ticker, "EARNINGS_TODAY", 0,
                             f"{ticker} earnings today ({next_e}) — check your position size!")
                    count += 1
            except Exception:
                pass

        log.info("Auto-setup %d alerts for %s", count, ticker)
        return count

    # ── Monitoring loop ───────────────────────────────────────────────────────
    def _check_once(self) -> None:
        with self._lock:
            active = [a for a in self._alerts if not a.triggered]

        if not active:
            return

        # Group by ticker to batch yfinance calls
        tickers = list(set(a.ticker for a in active))
        prices: dict[str, float] = {}
        volumes: dict[str, float] = {}
        avg_volumes: dict[str, float] = {}

        for ticker in tickers:
            try:
                tk   = yf.Ticker(ticker)
                info = tk.info or {}
                price = (info.get("currentPrice") or info.get("regularMarketPrice")
                         or info.get("previousClose") or 0)
                prices[ticker]      = float(price)
                volumes[ticker]     = float(info.get("volume") or 0)
                avg_volumes[ticker] = float(info.get("averageVolume") or 1)
            except Exception:
                log.debug("Price fetch failed for %s", ticker)

        now = datetime.now(timezone.utc).isoformat()
        to_remove: list[str] = []

        for alert in active:
            ticker = alert.ticker
            price  = prices.get(ticker, 0)
            if not price:
                continue

            fired = False
            last  = self._last_prices.get(ticker, price)

            if alert.alert_type == "PRICE_ABOVE" and price >= alert.trigger_value:
                _notify(f"{ticker} BREAKOUT", alert.message, urgent=True)
                fired = True

            elif alert.alert_type == "PRICE_BELOW" and price <= alert.trigger_value:
                _notify(f"{ticker} STOP HIT", alert.message, urgent=True)
                fired = True

            elif alert.alert_type == "PCT_MOVE" and last:
                pct = abs((price - last) / last * 100)
                if pct >= abs(alert.trigger_value):
                    direction = "up" if price > last else "down"
                    _notify(
                        f"{ticker} MOVING {direction.upper()}",
                        f"{ticker} moved {pct:.1f}% {direction} to ${price:.2f}",
                        urgent=(pct > 10)
                    )
                    fired = True

            elif alert.alert_type == "VOLUME_SPIKE":
                vol     = volumes.get(ticker, 0)
                avg_vol = avg_volumes.get(ticker, 1)
                if avg_vol and (vol / avg_vol) >= alert.trigger_value:
                    _notify(
                        f"{ticker} VOLUME SPIKE",
                        f"Volume {vol/avg_vol:.1f}x average — unusual activity!",
                    )
                    fired = True

            elif alert.alert_type == "EARNINGS_TODAY":
                today_s = datetime.now().strftime("%Y-%m-%d")
                if str(alert.trigger_value) == today_s or (
                    alert.message and today_s in alert.message
                ):
                    _notify(f"{ticker} EARNINGS TODAY", alert.message, urgent=True)
                    fired = True

            if fired:
                alert.triggered    = True
                alert.triggered_at = now
                if alert.one_shot:
                    to_remove.append(alert.id)

            self._last_prices[ticker] = price

        if to_remove:
            with self._lock:
                self._alerts = [a for a in self._alerts if a.id not in to_remove]
            self._save_alerts()

    def _monitor_loop(self) -> None:
        log.info("Alert monitor started — checking every %ds", _CHECK_INTERVAL_SECONDS)
        while self._running:
            try:
                self._check_once()
            except Exception:
                log.debug("Alert check error", exc_info=True)
            time.sleep(_CHECK_INTERVAL_SECONDS)
        log.info("Alert monitor stopped.")

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(
            target = self._monitor_loop,
            name   = "atlas-alerts",
            daemon = True
        )
        self._thread.start()
        log.info("Alert monitor running in background (%d active alerts)",
                 len(self._alerts))

    def stop(self) -> None:
        self._running = False


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────────────────────
_monitor: Optional[AlertMonitor] = None


def get_monitor() -> AlertMonitor:
    """Get or create the global alert monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = AlertMonitor()
    return _monitor


def add_alert(ticker: str, condition: str, value: float, message: str = "") -> str:
    """Quick shortcut: add_alert('SOUN', 'PRICE_ABOVE', 10.0)"""
    return get_monitor().add(ticker, condition, value, message)


def add_price_alert(
    ticker: str,
    price: float,
    direction: str,
    message: str = "",
) -> Optional[str]:
    """
    Loop 6 / execution-rules compatibility hook — maps direction to PRICE_ABOVE / PRICE_BELOW.
    Returns alert id, or None if no price alert should be created (e.g. time-based rule).
    """
    if price is None:
        return None
    try:
        trigger = float(price)
    except (TypeError, ValueError):
        return None
    d = (direction or "").lower().strip()
    if d in ("time", "options_deadline", ""):
        return None
    if d in ("above",):
        atype = "PRICE_ABOVE"
    elif d in ("below", "at_or_below"):
        atype = "PRICE_BELOW"
    else:
        return None
    t = (ticker or "").upper().strip()
    if not t:
        return None
    return get_monitor().add(t, atype, trigger, message or "")


def start_monitor() -> AlertMonitor:
    """Start the background alert monitor and return it."""
    m = get_monitor()
    m.start()
    return m


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    m   = get_monitor()

    if cmd == "list":
        alerts = m.list_alerts()
        if not alerts:
            print("No active alerts.")
        else:
            print(f"{len(alerts)} active alerts:")
            for a in alerts:
                print(f"  [{a['alert_type']}] {a['ticker']} @ {a['trigger_value']} — {a['message'][:60]}")

    elif cmd == "add" and len(sys.argv) >= 5:
        # python alerts.py add SOUN PRICE_ABOVE 10.50
        ticker = sys.argv[2].upper()
        atype  = sys.argv[3].upper()
        value  = float(sys.argv[4])
        msg    = " ".join(sys.argv[5:]) if len(sys.argv) > 5 else ""
        aid    = m.add(ticker, atype, value, msg)
        print(f"Alert added: {aid}")

    elif cmd == "remove" and len(sys.argv) >= 3:
        removed = m.remove(sys.argv[2])
        print("Alert removed." if removed else "Alert not found.")

    elif cmd == "watch":
        # Run the monitor in the foreground for testing
        print("Starting alert monitor (Ctrl+C to stop)...")
        m.start()
        try:
            while True:
                time.sleep(10)
                prices = {a["ticker"] for a in m.list_alerts()}
                if prices:
                    print(f"  Monitoring: {', '.join(prices)}")
        except KeyboardInterrupt:
            m.stop()
            print("\nMonitor stopped.")

    elif cmd == "test":
        # Fire a test notification
        _notify("Test Alert", "ATLAS alert system is working!", urgent=False)
        print("Test notification sent.")

    else:
        print("Usage:")
        print("  python alerts.py list                              -- show active alerts")
        print("  python alerts.py add SOUN PRICE_ABOVE 10.50       -- add price alert")
        print("  python alerts.py add SOUN PRICE_BELOW 8.00        -- add stop alert")
        print("  python alerts.py add SOUN PCT_MOVE 5              -- alert if 5% move")
        print("  python alerts.py add SOUN VOLUME_SPIKE 3          -- 3x volume spike")
        print("  python alerts.py remove <alert_id>                -- remove alert")
        print("  python alerts.py watch                            -- run monitor live")
        print("  python alerts.py test                             -- test notification")
