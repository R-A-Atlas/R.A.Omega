"""
sector_tracker.py — ATLAS Sector Rotation Tracker + Portfolio Correlation

Two tools in one:

1. SECTOR ROTATION TRACKER
   Watches all 11 S&P 500 sector ETFs every hour.
   Shows which sectors are getting inflows vs outflows.
   Money flow = relative strength + volume trend.
   Why it matters: when smart money rotates INTO a sector, its stocks lead.
   If you're trading SOUN (tech/AI), knowing XLK is getting inflows
   means the macro wind is at your back.

   Sectors tracked:
     XLK  — Technology        XLF  — Financials
     XLV  — Healthcare        XLE  — Energy
     XLI  — Industrials       XLY  — Consumer Discretionary
     XLP  — Consumer Staples  XLU  — Utilities
     XLRE — Real Estate       XLB  — Materials
     XLC  — Communication Services
     QQQ  — Nasdaq (tech/AI proxy)
     SPY  — S&P 500 (broad market benchmark)

2. PORTFOLIO CORRELATION
   Given your current positions, calculates:
   - Correlation matrix (which positions move together)
   - Diversification score (are you actually diversified?)
   - What adding a new stock does to your risk
   - Concentration warnings (too much in one sector/correlation)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yfinance as yf

log = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).parent / "reports"
_REPORTS_DIR.mkdir(exist_ok=True)

SECTOR_ETFS = {
    "XLK":  "Technology",
    "XLF":  "Financials",
    "XLV":  "Healthcare",
    "XLE":  "Energy",
    "XLI":  "Industrials",
    "XLY":  "Consumer Discretionary",
    "XLP":  "Consumer Staples",
    "XLU":  "Utilities",
    "XLRE": "Real Estate",
    "XLB":  "Materials",
    "XLC":  "Communication Services",
    "QQQ":  "Nasdaq 100 (AI/Tech proxy)",
    "SPY":  "S&P 500 (Benchmark)",
}

# Map tickers to their sector
TICKER_SECTOR_MAP = {
    # Technology / AI
    "SOUN": "XLK", "NVDA": "XLK", "AMD": "XLK", "INTC": "XLK",
    "MSFT": "XLK", "AAPL": "XLK", "GOOGL": "XLC", "META": "XLC",
    "IONQ": "XLK", "RGTI": "XLK", "QBTS": "XLK",
    # Biotech / Healthcare
    "RZLV": "XLV", "MRVL": "XLK",
    # Finance
    "BAC": "XLF", "JPM": "XLF",
    # Energy
    "XOM": "XLE", "CVX": "XLE",
    # Space / Defense
    "ASTS": "XLI", "RKLB": "XLI",
    # Crypto-adjacent
    "MARA": "XLK", "RIOT": "XLK", "COIN": "XLK",
}


# ─────────────────────────────────────────────────────────────────────────────
# Sector rotation analysis
# ─────────────────────────────────────────────────────────────────────────────
def get_sector_rotation(lookback_days: int = 30) -> list[dict]:
    """
    Analyze sector performance and money flow for all 11 sectors.
    Returns list sorted by 5-day relative strength (best sectors first).
    """
    import pandas as pd

    results: list[dict] = []
    symbols  = list(SECTOR_ETFS.keys())

    log.info("[sector] Fetching %d sector ETFs...", len(symbols))

    try:
        # Batch download all sectors at once
        data = yf.download(
            symbols,
            period   = f"{lookback_days + 5}d",
            interval = "1d",
            auto_adjust = True,
            progress = False,
        )
    except Exception:
        log.warning("[sector] Batch download failed, trying individually")
        data = None

    spy_5d_pct = 0.0

    for sym in symbols:
        entry: dict = {
            "symbol":  sym,
            "name":    SECTOR_ETFS[sym],
            "price":   None,
            "pct_1d":  None,
            "pct_5d":  None,
            "pct_1m":  None,
            "volume_ratio": None,
            "signal":  "NEUTRAL",
            "score":   0,
        }

        try:
            if data is not None and not data.empty:
                # Multi-ticker download — columns are MultiIndex (field, symbol)
                try:
                    if hasattr(data.columns, "levels"):
                        close_col = ("Close", sym) if ("Close", sym) in data.columns else None
                        vol_col   = ("Volume", sym) if ("Volume", sym) in data.columns else None
                        close = data[close_col].dropna() if close_col else None
                        vol   = data[vol_col].dropna()   if vol_col   else None
                    else:
                        close = data["Close"].get(sym, pd.Series()).dropna()
                        vol   = data["Volume"].get(sym, pd.Series()).dropna()
                except Exception:
                    close = vol = None
            else:
                close = vol = None

            # Fallback to individual fetch
            if close is None or len(close) < 5:
                tk    = yf.Ticker(sym)
                hist  = tk.history(period=f"{lookback_days + 5}d")
                close = hist["Close"].dropna() if not hist.empty else None
                vol   = hist["Volume"].dropna() if not hist.empty else None

            if close is None or len(close) < 5:
                results.append(entry)
                continue

            price    = float(close.iloc[-1])
            p_1d_ago = float(close.iloc[-2])      if len(close) >= 2  else price
            p_5d_ago = float(close.iloc[-5])      if len(close) >= 5  else price
            p_1m_ago = float(close.iloc[-22])     if len(close) >= 22 else close.iloc[0]

            entry["price"]  = round(price, 4)
            entry["pct_1d"] = round((price - p_1d_ago) / p_1d_ago * 100, 2) if p_1d_ago else 0
            entry["pct_5d"] = round((price - p_5d_ago) / p_5d_ago * 100, 2) if p_5d_ago else 0
            entry["pct_1m"] = round((price - float(p_1m_ago)) / float(p_1m_ago) * 100, 2) if p_1m_ago else 0

            if sym == "SPY":
                spy_5d_pct = entry["pct_5d"]

            # Volume ratio: current 5-day avg vs 20-day avg
            if vol is not None and len(vol) >= 10:
                vol_5d  = float(vol.iloc[-5:].mean())
                vol_20d = float(vol.iloc[-20:].mean()) if len(vol) >= 20 else float(vol.mean())
                entry["volume_ratio"] = round(vol_5d / vol_20d, 2) if vol_20d else 1.0

            # Score: 5d return + volume weight + 1m return weight
            score = (entry["pct_5d"] * 3.0
                   + (entry.get("volume_ratio",1.0) - 1.0) * 5.0
                   + entry["pct_1m"] * 0.5)
            entry["score"] = round(score, 2)

        except Exception:
            log.debug("[sector] Failed for %s", sym, exc_info=True)

        results.append(entry)

    # Relative strength vs SPY
    for r in results:
        if r.get("pct_5d") is not None and spy_5d_pct:
            rs = (r["pct_5d"] or 0) - spy_5d_pct
            r["rs_vs_spy"] = round(rs, 2)
            if rs > 1.5 and (r.get("volume_ratio") or 1) > 1.1:
                r["signal"] = "STRONG INFLOW"
            elif rs > 0.5:
                r["signal"] = "INFLOW"
            elif rs < -1.5:
                r["signal"] = "OUTFLOW"
            elif rs < -0.5:
                r["signal"] = "WEAK"
            else:
                r["signal"] = "NEUTRAL"

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


def sector_for_ticker(ticker: str) -> Optional[str]:
    """Return the sector ETF symbol for a given stock ticker."""
    t = ticker.upper()
    if t in TICKER_SECTOR_MAP:
        return TICKER_SECTOR_MAP[t]
    # Try yfinance info
    try:
        info = yf.Ticker(t).info or {}
        sector = info.get("sector","")
        sector_map = {
            "Technology": "XLK", "Financial Services": "XLF",
            "Healthcare": "XLV", "Energy": "XLE",
            "Industrials": "XLI", "Consumer Cyclical": "XLY",
            "Consumer Defensive": "XLP", "Utilities": "XLU",
            "Real Estate": "XLRE", "Basic Materials": "XLB",
            "Communication Services": "XLC",
        }
        return sector_map.get(sector)
    except Exception:
        return None


def sector_wind(ticker: str, rotation_data: list[dict] = None) -> str:
    """
    Return a one-line macro wind summary for a ticker's sector.
    e.g. "XLK (Technology): STRONG INFLOW +3.2% vs SPY — macro tailwind for SOUN"
    """
    if rotation_data is None:
        rotation_data = get_sector_rotation(lookback_days=10)

    sector_sym = sector_for_ticker(ticker)
    if not sector_sym:
        return ""

    for r in rotation_data:
        if r["symbol"] == sector_sym:
            signal    = r.get("signal","?")
            rs        = r.get("rs_vs_spy","?")
            pct5      = r.get("pct_5d","?")
            name      = r.get("name","?")
            tailwind  = "TAILWIND" if "INFLOW" in str(signal) else ("HEADWIND" if "OUTFLOW" in str(signal) else "NEUTRAL")
            rs_str    = f"{rs:+.1f}%" if isinstance(rs, (int,float)) else "?"
            p5_str    = f"{pct5:+.1f}%" if isinstance(pct5, (int,float)) else "?"
            return (f"{sector_sym} ({name}): {signal} | 5d={p5_str} vs SPY {rs_str} "
                    f"— sector macro {tailwind} for {ticker.upper()}")
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio correlation
# ─────────────────────────────────────────────────────────────────────────────
def portfolio_correlation(tickers: list[str], lookback_days: int = 60) -> dict:
    """
    Calculate correlation matrix and diversification score for a list of tickers.
    Lower correlation = better diversification.

    Returns:
      matrix:       dict of {ticker → {ticker → correlation}}
      avg_corr:     float — average pairwise correlation
      diversification_score: 0-100 (100 = perfectly uncorrelated)
      warnings:     list[str] — highly correlated pairs
      sector_concentration: dict of {sector → count}
      recommendation: str — plain English
    """
    import pandas as pd

    result: dict = {"tickers": [t.upper() for t in tickers]}

    if len(tickers) < 2:
        result["error"] = "Need at least 2 tickers for correlation"
        return result

    tickers = [t.upper() for t in tickers]

    try:
        data = yf.download(
            tickers,
            period    = f"{lookback_days}d",
            interval  = "1d",
            auto_adjust = True,
            progress  = False,
        )

        # Extract close prices
        if hasattr(data.columns, "levels"):
            try:
                closes = data["Close"]
            except Exception:
                closes = data.xs("Close", axis=1, level=0)
        else:
            closes = data["Close"] if "Close" in data.columns else data

        # Drop columns with too many NaN
        closes = closes.dropna(axis=1, thresh=int(lookback_days * 0.7))
        closes = closes.ffill()

        if closes.empty or closes.shape[1] < 2:
            result["error"] = "Insufficient price data for correlation"
            return result

        # Daily returns
        returns = closes.pct_change().dropna()
        corr    = returns.corr()

        # Build matrix
        matrix: dict = {}
        for t1 in corr.index:
            matrix[t1] = {}
            for t2 in corr.columns:
                matrix[t1][t2] = round(float(corr.loc[t1, t2]), 3)

        # Average pairwise correlation (excluding self)
        pairs = []
        warnings: list[str] = []
        for i, t1 in enumerate(corr.index):
            for j, t2 in enumerate(corr.columns):
                if i < j:  # upper triangle only
                    c = float(corr.loc[t1, t2])
                    pairs.append(c)
                    if c > 0.85:
                        warnings.append(
                            f"{t1} and {t2} are highly correlated ({c:.2f}) — "
                            f"not real diversification, essentially the same position"
                        )
                    elif c > 0.70:
                        warnings.append(f"{t1} and {t2} correlated {c:.2f} — limited diversification")

        avg_corr = sum(pairs) / len(pairs) if pairs else 0
        div_score = max(0, round((1 - avg_corr) * 100, 1))

        result["matrix"]               = matrix
        result["avg_correlation"]       = round(avg_corr, 3)
        result["diversification_score"] = div_score
        result["warnings"]             = warnings

        # Sector concentration
        sector_count: dict = {}
        for t in tickers:
            s = sector_for_ticker(t) or "Unknown"
            sector_count[s] = sector_count.get(s, 0) + 1
        result["sector_concentration"] = sector_count

        concentration_warnings = [
            f"Heavy {SECTOR_ETFS.get(s,s)} concentration ({n} of {len(tickers)} positions)"
            for s, n in sector_count.items()
            if n >= max(2, len(tickers) // 2)
        ]

        # Recommendation
        if div_score >= 75:
            rec = f"WELL DIVERSIFIED — avg correlation {avg_corr:.2f}. Portfolio has genuine risk spread."
        elif div_score >= 50:
            rec = f"MODERATELY DIVERSIFIED — avg correlation {avg_corr:.2f}. Some overlap."
        else:
            rec = f"POORLY DIVERSIFIED — avg correlation {avg_corr:.2f}. Positions move together. One bad day hits everything."

        if concentration_warnings:
            rec += " | " + " | ".join(concentration_warnings)

        result["recommendation"] = rec
        result["all_warnings"]   = warnings + concentration_warnings

        log.info("[portfolio_correlation] %s — avg_corr=%.2f  div_score=%.0f",
                 ",".join(tickers), avg_corr, div_score)

    except Exception:
        log.warning("[portfolio_correlation] Failed", exc_info=True)
        result["error"] = "Correlation calculation failed"

    return result


# ─────────────────────────────────────────────────────────────────────────────
# HTML reports
# ─────────────────────────────────────────────────────────────────────────────
def render_sector_html(rotation: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    signal_colors = {
        "STRONG INFLOW": "#4caf50",
        "INFLOW":        "#8bc34a",
        "NEUTRAL":       "#666",
        "WEAK":          "#ff9800",
        "OUTFLOW":       "#f44336",
    }

    rows = ""
    for r in rotation:
        sig_color = signal_colors.get(r.get("signal",""), "#aaa")
        p5 = r.get("pct_5d")
        p1m = r.get("pct_1m")
        rs = r.get("rs_vs_spy","?")
        vr = r.get("volume_ratio","?")
        p5_color  = "#4caf50" if isinstance(p5, (int,float)) and p5 > 0 else "#f44336"
        p1m_color = "#4caf50" if isinstance(p1m,(int,float)) and p1m > 0 else "#f44336"
        rows += f"""
        <tr style="border-bottom:1px solid #1a1a1a">
          <td style="padding:10px;color:#00d4ff;font-weight:600">{r['symbol']}</td>
          <td style="padding:10px;color:#aaa;font-size:13px">{r['name']}</td>
          <td style="padding:10px;color:#ccc">${r.get('price','?')}</td>
          <td style="padding:10px;color:{p5_color};font-weight:600">{f'{p5:+.2f}%' if isinstance(p5,(int,float)) else '?'}</td>
          <td style="padding:10px;color:{p1m_color}">{f'{p1m:+.2f}%' if isinstance(p1m,(int,float)) else '?'}</td>
          <td style="padding:10px;color:#888">{f'{rs:+.2f}%' if isinstance(rs,(int,float)) else '?'}</td>
          <td style="padding:10px;color:#888">{f'{vr:.2f}x' if isinstance(vr,(int,float)) else '?'}</td>
          <td style="padding:10px"><span style="color:{sig_color};font-weight:700;font-size:12px">{r.get('signal','?')}</span></td>
        </tr>"""

    top3 = [r for r in rotation[:3] if r.get("signal") in ("STRONG INFLOW","INFLOW")]
    top3_str = " · ".join(f"{r['symbol']} ({r['name'].split()[0]})" for r in top3) if top3 else "None"
    btm3     = [r for r in rotation if r.get("signal") == "OUTFLOW"]
    btm3_str = " · ".join(f"{r['symbol']} ({r['name'].split()[0]})" for r in btm3[:3]) if btm3 else "None"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>ATLAS Sector Tracker</title>
<style>
  body{{background:#0d1117;color:#e0e0e0;font-family:system-ui,sans-serif;margin:0;padding:20px}}
  h1{{color:#00d4ff;font-size:22px;margin:0 0 4px}}
  table{{width:100%;border-collapse:collapse}}
  tr:hover{{background:#0e1117}}
  th{{padding:8px 10px;text-align:left;color:#555;font-size:11px;text-transform:uppercase;border-bottom:2px solid #1a1a1a}}
</style></head><body>
<h1>ATLAS Sector Rotation Tracker</h1>
<div style="color:#666;font-size:13px;margin-bottom:16px">{now}</div>
<div style="display:flex;gap:16px;margin-bottom:20px">
  <div style="background:#0e1a0e;border:1px solid #4caf5044;border-radius:8px;padding:12px;flex:1">
    <div style="color:#4caf50;font-size:11px;font-weight:700;margin-bottom:4px">MONEY FLOWING IN</div>
    <div style="color:#ccc;font-size:13px">{top3_str}</div>
  </div>
  <div style="background:#1a0e0e;border:1px solid #f4433644;border-radius:8px;padding:12px;flex:1">
    <div style="color:#f44336;font-size:11px;font-weight:700;margin-bottom:4px">MONEY FLOWING OUT</div>
    <div style="color:#ccc;font-size:13px">{btm3_str}</div>
  </div>
</div>
<table>
  <thead><tr>
    <th>ETF</th><th>Sector</th><th>Price</th><th>5-Day</th>
    <th>1-Month</th><th>vs SPY</th><th>Vol Ratio</th><th>Signal</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>
<div style="margin-top:20px;font-size:11px;color:#333;text-align:center">
  ATLAS Sector Tracker · refreshed {now}
</div></body></html>"""


def render_correlation_html(corr_data: dict) -> str:
    """Render portfolio correlation as HTML table."""
    tickers  = corr_data.get("tickers",[])
    matrix   = corr_data.get("matrix",{})
    div_score = corr_data.get("diversification_score",0)
    avg_corr  = corr_data.get("avg_correlation",0)
    rec       = corr_data.get("recommendation","")
    warnings  = corr_data.get("all_warnings",[])

    div_color = "#4caf50" if div_score >= 75 else ("#ff9800" if div_score >= 50 else "#f44336")

    header_row = "<tr><th></th>" + "".join(f"<th>{t}</th>" for t in tickers) + "</tr>"
    rows = ""
    for t1 in tickers:
        row_cells = f"<td style='color:#00d4ff;font-weight:600'>{t1}</td>"
        for t2 in tickers:
            c = matrix.get(t1,{}).get(t2,0)
            if t1 == t2:
                cell_bg = "#1a1a1a"
                cell_color = "#555"
            elif abs(c) > 0.85:
                cell_bg = "#2a0a0a"
                cell_color = "#f44336"
            elif abs(c) > 0.70:
                cell_bg = "#1e1500"
                cell_color = "#ff9800"
            elif abs(c) < 0.30:
                cell_bg = "#0a1a0a"
                cell_color = "#4caf50"
            else:
                cell_bg = "#0d1117"
                cell_color = "#aaa"
            row_cells += f"<td style='background:{cell_bg};color:{cell_color};text-align:center;padding:8px'>{c:.2f}</td>"
        rows += f"<tr>{row_cells}</tr>"

    warn_html = "".join(f"<li style='color:#ff9800;font-size:12px'>{w}</li>" for w in warnings)

    return f"""
<div style="background:#0e0e1a;border:1px solid #2a2a4a;border-radius:12px;padding:20px;margin-bottom:24px">
  <div style="font-size:14px;font-weight:700;color:#00d4ff;margin-bottom:14px">PORTFOLIO CORRELATION</div>
  <div style="display:flex;gap:16px;margin-bottom:16px">
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;min-width:120px">
      <div style="font-size:11px;color:#666">Diversification Score</div>
      <div style="font-size:22px;font-weight:700;color:{div_color};margin-top:4px">{div_score}/100</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;text-align:center;min-width:120px">
      <div style="font-size:11px;color:#666">Avg Correlation</div>
      <div style="font-size:22px;font-weight:700;color:#aaa;margin-top:4px">{avg_corr:.2f}</div>
    </div>
    <div style="background:#111;border-radius:8px;padding:12px;flex:1">
      <div style="font-size:11px;color:#666;margin-bottom:4px">Assessment</div>
      <div style="font-size:12px;color:#ccc">{rec}</div>
    </div>
  </div>
  <table style="border-collapse:collapse;margin-bottom:12px">
    <thead style="background:#0d1117;color:#555;font-size:11px">{header_row}</thead>
    <tbody>{rows}</tbody>
  </table>
  {'<ul style="margin:0;padding-left:20px">' + warn_html + '</ul>' if warnings else ''}
</div>"""


def save_sector_report(rotation: list[dict]) -> Path:
    html = render_sector_html(rotation)
    path = _REPORTS_DIR / "ATLAS_SECTOR_ROTATION.html"
    path.write_text(html, encoding="utf-8")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "sectors"

    if cmd == "sectors":
        print("Fetching sector rotation data...")
        rotation = get_sector_rotation()
        print(f"\n{'ETF':<6} {'Sector':<30} {'5d':>7} {'1m':>7} {'vs SPY':>7} {'Vol':>6} {'Signal'}")
        print("-" * 80)
        for r in rotation:
            p5  = f"{r['pct_5d']:+.2f}%" if isinstance(r.get("pct_5d"),(int,float)) else "?"
            p1m = f"{r['pct_1m']:+.2f}%" if isinstance(r.get("pct_1m"),(int,float)) else "?"
            rs  = f"{r['rs_vs_spy']:+.2f}%" if isinstance(r.get("rs_vs_spy"),(int,float)) else "?"
            vr  = f"{r['volume_ratio']:.2f}x" if isinstance(r.get("volume_ratio"),(int,float)) else "?"
            print(f"{r['symbol']:<6} {r['name']:<30} {p5:>7} {p1m:>7} {rs:>7} {vr:>6} {r.get('signal','?')}")
        path = save_sector_report(rotation)
        print(f"\nReport: {path}")

    elif cmd == "wind" and len(sys.argv) > 2:
        ticker = sys.argv[2].upper()
        rotation = get_sector_rotation(lookback_days=10)
        print(sector_wind(ticker, rotation))

    elif cmd == "correlate" and len(sys.argv) > 2:
        tickers = [t.upper() for t in sys.argv[2:]]
        print(f"Calculating correlation for: {', '.join(tickers)}")
        corr = portfolio_correlation(tickers)
        print(f"\nDiversification score: {corr.get('diversification_score','?')}/100")
        print(f"Avg correlation: {corr.get('avg_correlation','?')}")
        print(f"Assessment: {corr.get('recommendation','')}")
        for w in corr.get("all_warnings",[]):
            print(f"  WARNING: {w}")

    else:
        print("Usage:")
        print("  python sector_tracker.py sectors              -- show all sector flows")
        print("  python sector_tracker.py wind SOUN            -- macro wind for a ticker")
        print("  python sector_tracker.py correlate SOUN MARA  -- portfolio correlation")
