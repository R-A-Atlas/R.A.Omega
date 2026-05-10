"""
broker_alpaca.py — ATLAS Alpaca Paper Trading Interface

Alpaca Developer API — 100% free tier:
  - Real-time crypto quotes
  - 15-min delayed equity quotes (free tier)
  - Zero-commission paper trading (unlimited)
  - Historical OHLCV bars (yfinance still used for deep history)
  - WebSocket streaming for real-time position monitoring

Keys loaded from .env:
  ALPACA_API_KEY    = your API key
  ALPACA_SECRET_KEY = your secret
  ALPACA_PAPER      = True (always True until you explicitly change it)

Paper trading base URL: https://paper-api.alpaca.markets
Live trading base URL:  https://api.alpaca.markets  (NOT USED — PAPER ONLY BY DEFAULT)

This module is the foundation for:
  - Phase 2C: Paper Trading State Machine (paper_trader.py)
  - Phase 2D: Backtest data supplementation
  - Real-time portfolio tracking alongside Robinhood positions
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
load_dotenv()

log = logging.getLogger(__name__)

# ── Safety gate ──────────────────────────────────────────────────────────────
# Change ONLY when you explicitly want real-money trading.
# Paper mode = True means all orders go to paper-api.alpaca.markets only.
PAPER_MODE: bool = os.environ.get("ALPACA_PAPER", "True").strip().lower() not in ("false", "0", "no")

_API_KEY    = os.environ.get("ALPACA_API_KEY", "").strip().strip('"')
_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "").strip().strip('"')
_BASE_URL   = "https://paper-api.alpaca.markets" if PAPER_MODE else "https://api.alpaca.markets"
_DATA_URL   = "https://data.alpaca.markets"

_client     = None   # lazy-initialized TradingClient
_data_client = None  # lazy-initialized StockHistoricalDataClient


def _get_client():
    """Lazy-initialize Alpaca TradingClient."""
    global _client
    if _client is not None:
        return _client
    if not _API_KEY or not _SECRET_KEY:
        log.warning("[alpaca] No API keys found in .env. Set ALPACA_API_KEY and ALPACA_SECRET_KEY.")
        return None
    try:
        from alpaca.trading.client import TradingClient
        _client = TradingClient(_API_KEY, _SECRET_KEY, paper=PAPER_MODE)
        mode_str = "PAPER" if PAPER_MODE else "LIVE"
        log.info("[alpaca] TradingClient initialized — %s mode", mode_str)
        return _client
    except ImportError:
        log.error("[alpaca] alpaca-py not installed. Run: pip install alpaca-py")
        return None
    except Exception as e:
        log.error("[alpaca] Client init failed: %s", e)
        return None


def _get_data_client():
    """Lazy-initialize Alpaca data client."""
    global _data_client
    if _data_client is not None:
        return _data_client
    if not _API_KEY or not _SECRET_KEY:
        return None
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        _data_client = StockHistoricalDataClient(_API_KEY, _SECRET_KEY)
        return _data_client
    except ImportError:
        return None
    except Exception as e:
        log.debug("[alpaca] Data client init failed: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Account info
# ─────────────────────────────────────────────────────────────────────────────
def get_account() -> Optional[dict]:
    """
    Get paper account summary: equity, cash, buying power, P&L.
    """
    client = _get_client()
    if not client:
        return None
    try:
        acct = client.get_account()
        return {
            "equity":        float(acct.equity),
            "cash":          float(acct.cash),
            "buying_power":  float(acct.buying_power),
            "portfolio_value": float(acct.portfolio_value),
            "unrealized_pl": float(acct.unrealized_pl) if hasattr(acct, "unrealized_pl") else None,
            "unrealized_plpc": float(acct.unrealized_plpc) if hasattr(acct, "unrealized_plpc") else None,
            "status":        str(acct.status),
            "paper":         PAPER_MODE,
            "currency":      "USD",
        }
    except Exception as e:
        log.error("[alpaca] get_account failed: %s", e)
        return None


def get_positions() -> list[dict]:
    """Get all open paper positions."""
    client = _get_client()
    if not client:
        return []
    try:
        positions = client.get_all_positions()
        result = []
        for p in positions:
            result.append({
                "symbol":          p.symbol,
                "qty":             float(p.qty),
                "side":            str(p.side),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price":   float(p.current_price) if p.current_price else None,
                "market_value":    float(p.market_value) if p.market_value else None,
                "unrealized_pl":   float(p.unrealized_pl) if p.unrealized_pl else None,
                "unrealized_plpc": float(p.unrealized_plpc) if p.unrealized_plpc else None,
                "change_today":    float(p.change_today) if p.change_today else None,
            })
        return result
    except Exception as e:
        log.error("[alpaca] get_positions failed: %s", e)
        return []


def get_open_orders() -> list[dict]:
    """Get all open/pending orders."""
    client = _get_client()
    if not client:
        return []
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        req    = GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=50)
        orders = client.get_orders(req)
        result = []
        for o in orders:
            result.append({
                "id":           str(o.id),
                "symbol":       o.symbol,
                "qty":          float(o.qty) if o.qty else None,
                "side":         str(o.side),
                "type":         str(o.order_type),
                "status":       str(o.status),
                "limit_price":  float(o.limit_price) if o.limit_price else None,
                "stop_price":   float(o.stop_price) if o.stop_price else None,
                "filled_qty":   float(o.filled_qty) if o.filled_qty else 0,
                "submitted_at": str(o.submitted_at)[:19] if o.submitted_at else None,
            })
        return result
    except Exception as e:
        log.error("[alpaca] get_open_orders failed: %s", e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Quotes and bars
# ─────────────────────────────────────────────────────────────────────────────
def get_latest_quote(ticker: str) -> Optional[dict]:
    """Get the latest quote for a ticker."""
    client = _get_client()
    if not client:
        return None
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        dc  = _get_data_client()
        if not dc:
            return None
        req = StockLatestQuoteRequest(symbol_or_symbols=ticker.upper())
        quotes = dc.get_stock_latest_quote(req)
        q = quotes.get(ticker.upper())
        if not q:
            return None
        return {
            "symbol":    ticker.upper(),
            "bid":       float(q.bid_price) if q.bid_price else None,
            "ask":       float(q.ask_price) if q.ask_price else None,
            "bid_size":  int(q.bid_size) if q.bid_size else None,
            "ask_size":  int(q.ask_size) if q.ask_size else None,
            "timestamp": str(q.timestamp)[:19] if q.timestamp else None,
        }
    except Exception as e:
        log.debug("[alpaca] get_latest_quote failed for %s: %s", ticker, e)
        return None


def get_bars(ticker: str, days: int = 30, timeframe: str = "1Day") -> list[dict]:
    """
    Get historical OHLCV bars from Alpaca.
    Falls back to yfinance if Alpaca data is unavailable.
    """
    dc = _get_data_client()
    if not dc:
        return _bars_from_yfinance(ticker, days)

    try:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        tf_map = {
            "1Min": TimeFrame.Minute, "1Hour": TimeFrame.Hour,
            "1Day": TimeFrame.Day, "1Week": TimeFrame.Week,
        }
        tf  = tf_map.get(timeframe, TimeFrame.Day)
        req = StockBarsRequest(
            symbol_or_symbols = ticker.upper(),
            timeframe         = tf,
            start             = datetime.now(timezone.utc) - timedelta(days=days),
            end               = datetime.now(timezone.utc),
        )
        bars_data = dc.get_stock_bars(req)
        bars      = bars_data.get(ticker.upper(), [])
        result    = []
        for b in bars:
            result.append({
                "time":   str(b.timestamp)[:10],
                "open":   float(b.open),
                "high":   float(b.high),
                "low":    float(b.low),
                "close":  float(b.close),
                "volume": int(b.volume),
            })
        return result
    except Exception as e:
        log.debug("[alpaca] get_bars failed for %s: %s. Using yfinance fallback.", ticker, e)
        return _bars_from_yfinance(ticker, days)


def _bars_from_yfinance(ticker: str, days: int) -> list[dict]:
    """yfinance fallback for historical bars."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period=f"{days}d")
        return [
            {"time": str(i.date()), "open": float(r.Open), "high": float(r.High),
             "low": float(r.Low), "close": float(r.Close), "volume": int(r.Volume)}
            for i, r in hist.iterrows()
        ]
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Order placement — PAPER ONLY by default
# ─────────────────────────────────────────────────────────────────────────────
def place_market_order(ticker: str, qty: float, side: str,
                       reason: str = "") -> Optional[dict]:
    """
    Place a market order. PAPER MODE by default.
    side: 'buy' or 'sell'
    """
    if not PAPER_MODE:
        log.error("[alpaca] LIVE_TRADING requested but PAPER_MODE=False safety gate must be "
                  "manually disabled in broker_alpaca.py. Aborting.")
        return None

    client = _get_client()
    if not client:
        return None

    try:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        req       = MarketOrderRequest(
            symbol        = ticker.upper(),
            qty           = qty,
            side          = side_enum,
            time_in_force = TimeInForce.DAY,
        )
        order = client.submit_order(req)
        log.info("[alpaca] PAPER %s %s x%.2f — order_id=%s  reason: %s",
                 side.upper(), ticker.upper(), qty, order.id, reason[:60] if reason else "")
        return {
            "order_id":  str(order.id),
            "symbol":    order.symbol,
            "qty":       float(order.qty) if order.qty else qty,
            "side":      str(order.side),
            "status":    str(order.status),
            "submitted": str(order.submitted_at)[:19] if order.submitted_at else None,
            "paper":     True,
        }
    except Exception as e:
        log.error("[alpaca] place_market_order failed: %s", e)
        return None


def place_limit_order(ticker: str, qty: float, side: str,
                      limit_price: float, reason: str = "") -> Optional[dict]:
    """Place a limit order. PAPER MODE only."""
    if not PAPER_MODE:
        log.error("[alpaca] LIVE_TRADING not enabled. Paper mode only.")
        return None

    client = _get_client()
    if not client:
        return None

    try:
        from alpaca.trading.requests import LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        req       = LimitOrderRequest(
            symbol        = ticker.upper(),
            qty           = qty,
            side          = side_enum,
            limit_price   = round(limit_price, 2),
            time_in_force = TimeInForce.DAY,
        )
        order = client.submit_order(req)
        log.info("[alpaca] PAPER LIMIT %s %s x%.2f @ $%.2f — order_id=%s",
                 side.upper(), ticker.upper(), qty, limit_price, order.id)
        return {
            "order_id":    str(order.id),
            "symbol":      order.symbol,
            "qty":         float(order.qty) if order.qty else qty,
            "side":        str(order.side),
            "limit_price": limit_price,
            "status":      str(order.status),
            "paper":       True,
        }
    except Exception as e:
        log.error("[alpaca] place_limit_order failed: %s", e)
        return None


def place_bracket_order(ticker: str, qty: float, side: str,
                        take_profit: float, stop_loss: float,
                        reason: str = "") -> Optional[dict]:
    """
    Place a bracket order (entry + take-profit + stop-loss in one order).
    This is the primary order type for the paper trading state machine.
    PAPER MODE only.
    """
    if not PAPER_MODE:
        log.error("[alpaca] LIVE_TRADING not enabled.")
        return None

    client = _get_client()
    if not client:
        return None

    try:
        from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
        from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        req       = MarketOrderRequest(
            symbol        = ticker.upper(),
            qty           = qty,
            side          = side_enum,
            time_in_force = TimeInForce.DAY,
            order_class   = OrderClass.BRACKET,
            take_profit   = TakeProfitRequest(limit_price=round(take_profit, 2)),
            stop_loss     = StopLossRequest(stop_price=round(stop_loss, 2)),
        )
        order = client.submit_order(req)
        log.info("[alpaca] PAPER BRACKET %s %s x%.2f | TP=$%.2f | SL=$%.2f — %s",
                 side.upper(), ticker.upper(), qty, take_profit, stop_loss, reason[:50])
        return {
            "order_id":    str(order.id),
            "symbol":      order.symbol,
            "qty":         float(order.qty) if order.qty else qty,
            "side":        str(order.side),
            "take_profit": take_profit,
            "stop_loss":   stop_loss,
            "status":      str(order.status),
            "paper":       True,
        }
    except Exception as e:
        log.error("[alpaca] place_bracket_order failed: %s", e)
        return None


def cancel_order(order_id: str) -> bool:
    """Cancel an open order by ID."""
    client = _get_client()
    if not client:
        return False
    try:
        client.cancel_order_by_id(order_id)
        log.info("[alpaca] Cancelled order %s", order_id)
        return True
    except Exception as e:
        log.error("[alpaca] cancel_order failed: %s", e)
        return False


def close_position(ticker: str) -> Optional[dict]:
    """Close an entire position at market price."""
    client = _get_client()
    if not client:
        return None
    try:
        resp = client.close_position(ticker.upper())
        log.info("[alpaca] Closed position: %s", ticker.upper())
        return {"symbol": ticker.upper(), "status": "closed", "order_id": str(resp.id)}
    except Exception as e:
        log.error("[alpaca] close_position failed for %s: %s", ticker, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio snapshot — for ATLAS dashboard
# ─────────────────────────────────────────────────────────────────────────────
def portfolio_snapshot() -> dict:
    """
    Full paper portfolio snapshot for dashboard display.
    Returns account summary + all open positions + open orders.
    """
    acct      = get_account()
    positions = get_positions()
    orders    = get_open_orders()

    return {
        "account":   acct or {},
        "positions": positions,
        "orders":    orders,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "paper":      PAPER_MODE,
        "summary":   (
            f"Paper Portfolio: ${acct['portfolio_value']:,.2f} | "
            f"Cash: ${acct['cash']:,.2f} | "
            f"{len(positions)} positions | {len(orders)} open orders"
            if acct else "Alpaca account unavailable"
        ),
    }


def is_connected() -> bool:
    """Quick health check — returns True if Alpaca is reachable."""
    acct = get_account()
    return acct is not None


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cmd    = sys.argv[1] if len(sys.argv) > 1 else "status"
    ticker = sys.argv[2].upper() if len(sys.argv) > 2 else None

    if cmd == "status":
        snap = portfolio_snapshot()
        acct = snap["account"]
        print(f"\nAlpaca Paper Account")
        print(f"  Mode:            {'PAPER TRADING' if PAPER_MODE else '⚠ LIVE TRADING'}")
        print(f"  Status:          {acct.get('status','?')}")
        print(f"  Portfolio Value: ${acct.get('portfolio_value',0):,.2f}")
        print(f"  Cash:            ${acct.get('cash',0):,.2f}")
        print(f"  Buying Power:    ${acct.get('buying_power',0):,.2f}")
        print(f"  Open Positions:  {len(snap['positions'])}")
        print(f"  Open Orders:     {len(snap['orders'])}")

        if snap["positions"]:
            print("\nPositions:")
            for p in snap["positions"]:
                pl_str = f"  P/L: ${p.get('unrealized_pl',0):+.2f}" if p.get("unrealized_pl") is not None else ""
                print(f"  {p['symbol']:<8} {p['qty']:>8.2f} shares @ ${p.get('avg_entry_price',0):.2f}{pl_str}")

    elif cmd == "quote" and ticker:
        q = get_latest_quote(ticker)
        if q:
            print(f"\n{ticker} Quote: Bid ${q.get('bid','?')} x {q.get('bid_size','?')} | Ask ${q.get('ask','?')} x {q.get('ask_size','?')}")
        else:
            print(f"No quote available for {ticker}")

    elif cmd == "buy" and ticker:
        qty    = float(sys.argv[3]) if len(sys.argv) > 3 else 1
        result = place_market_order(ticker, qty, "buy", reason="Manual test order")
        print(f"\nOrder result: {result}")

    elif cmd == "sell" and ticker:
        qty    = float(sys.argv[3]) if len(sys.argv) > 3 else 1
        result = place_market_order(ticker, qty, "sell", reason="Manual test order")
        print(f"\nOrder result: {result}")

    elif cmd == "close" and ticker:
        result = close_position(ticker)
        print(f"\nClose result: {result}")

    elif cmd == "orders":
        orders = get_open_orders()
        print(f"\nOpen Orders ({len(orders)}):")
        for o in orders:
            print(f"  {o['id'][:8]}  {o['symbol']:<6}  {o['side']}  qty={o.get('qty','?')}  status={o['status']}")

    else:
        print("Usage: python broker_alpaca.py status | quote SOUN | buy SOUN 10 | sell SOUN 10 | close SOUN | orders")
