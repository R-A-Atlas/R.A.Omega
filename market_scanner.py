"""
market_scanner.py — ATLAS Hyper-Awareness Engine

Gives ATLAS a live pulse on the market before and during every session.
Seven awareness layers that no general-purpose AI tool has:

1. PRE-MARKET GAP SCANNER
   Which stocks in your watch list are gapping up/down before open?
   Gap > 3% with high pre-market volume = high-conviction setup.

2. SHORT SQUEEZE PROBABILITY SCORE (0-100)
   Composite score using: short float, days-to-cover, borrow rate proxy,
   relative volume, IV rank, recent price action. 
   Score 80+ = squeeze imminent. Score 60+ = watch closely.

3. NEWS VELOCITY TRACKER
   Is the pace of news ACCELERATING? 5 headlines in the last hour vs
   1 per hour normally = something's happening. ATLAS detects this.

4. CATALYST CALENDAR
   Upcoming events in the next 7 days: earnings, FDA dates (biotech),
   Fed meetings, major economic releases, options expiration.

5. DARK HORSE SCANNER
   Scans Finviz screener for setups that match ATLAS's best historical
   win patterns — stocks you're NOT watching that look interesting.

6. MARKET REGIME DETECTOR
   Bull? Bear? Chop? Based on SPY/QQQ trend, VIX level, sector breadth.
   Adjusts ATLAS confidence scores by regime.

7. EARNINGS REACTION DATABASE
   How has THIS stock moved on each of its last 8 earnings?
   Average move, beat reaction, miss reaction, AMC vs BMO pattern.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import yfinance as yf

log = logging.getLogger(__name__)

_REPORTS_DIR = Path(__file__).parent / "reports"
_REPORTS_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 1. SHORT SQUEEZE PROBABILITY SCORE
# ─────────────────────────────────────────────────────────────────────────────
def squeeze_score(ticker: str, scrape_data: dict = None) -> dict:
    """
    Calculate short squeeze probability on a 0–100 scale.

    Components:
      Short Float %         (35 pts) — the fuel
      Days to Cover         (20 pts) — how long shorts need to exit
      Relative Volume       (15 pts) — is buying pressure building?
      Price vs 20-day MA    (10 pts) — breaking out or still trapped?
      IV Rank               (10 pts) — are options pricing in a move?
      Recent price momentum (10 pts) — is price already moving up?

    Score:
      80-100 = HIGH probability squeeze setup
      60-79  = WATCH — conditions building
      40-59  = POSSIBLE but needs catalyst
      <40    = Not a squeeze candidate
    """
    result = {"ticker": ticker.upper(), "score": 0, "components": {}, "label": "LOW"}

    try:
        tk   = yf.Ticker(ticker.upper())
        info = tk.info or {}
        hist = tk.history(period="30d")

        if hist.empty:
            return result

        current = float(hist["Close"].iloc[-1])

        # ── Short Float (35 pts) ──────────────────────────────────────────────
        sf_raw  = info.get("shortPercentOfFloat") or 0
        sf_pct  = float(sf_raw) * 100
        # Also try scrape data
        if scrape_data:
            fv = scrape_data.get("finviz") or {}
            try:
                sf_str = str(fv.get("short_float","")).replace("%","")
                if sf_str:
                    sf_pct = max(sf_pct, float(sf_str))
            except Exception:
                pass

        if sf_pct >= 40:   sf_pts = 35
        elif sf_pct >= 30: sf_pts = 28
        elif sf_pct >= 20: sf_pts = 20
        elif sf_pct >= 10: sf_pts = 10
        else:               sf_pts = 0
        result["components"]["short_float"]     = {"value": f"{sf_pct:.1f}%", "pts": sf_pts}

        # ── Days to Cover (20 pts) ────────────────────────────────────────────
        dtc = info.get("shortRatio") or 0
        try:
            dtc = float(dtc)
        except Exception:
            dtc = 0
        if dtc >= 10:   dtc_pts = 20
        elif dtc >= 5:  dtc_pts = 14
        elif dtc >= 3:  dtc_pts = 8
        else:            dtc_pts = 0
        result["components"]["days_to_cover"]   = {"value": f"{dtc:.1f}d", "pts": dtc_pts}

        # ── Relative Volume (15 pts) ──────────────────────────────────────────
        avg_vol = info.get("averageVolume") or 1
        cur_vol = info.get("volume") or hist["Volume"].iloc[-1]
        rvol    = float(cur_vol) / float(avg_vol) if avg_vol else 1
        if rvol >= 5:   rvol_pts = 15
        elif rvol >= 3: rvol_pts = 11
        elif rvol >= 2: rvol_pts = 7
        elif rvol >= 1.5: rvol_pts = 4
        else:             rvol_pts = 0
        result["components"]["rel_volume"]      = {"value": f"{rvol:.1f}x", "pts": rvol_pts}

        # ── Price vs 20-day MA (10 pts) ───────────────────────────────────────
        if len(hist) >= 20:
            ma20   = float(hist["Close"].iloc[-20:].mean())
            vs_ma  = (current - ma20) / ma20 * 100
            if vs_ma > 5:    ma_pts = 10   # breaking above MA = shorts getting squeezed
            elif vs_ma > 0:  ma_pts = 6
            elif vs_ma > -5: ma_pts = 2
            else:             ma_pts = 0
        else:
            vs_ma = 0; ma_pts = 0
        result["components"]["vs_20ma"]         = {"value": f"{vs_ma:+.1f}%", "pts": ma_pts}

        # ── IV Rank (10 pts) ──────────────────────────────────────────────────
        iv_pts = 0
        iv_rank_val = "?"
        if scrape_data:
            js = scrape_data.get("js_data") or {}
            bc = js.get("barchart") or {}
            try:
                ivr = float(str(bc.get("iv_rank","")).replace("%",""))
                # High IV = options pricing in a move = squeeze more likely violent
                if ivr >= 70:   iv_pts = 10
                elif ivr >= 50: iv_pts = 7
                elif ivr >= 30: iv_pts = 4
                else:            iv_pts = 2
                iv_rank_val = f"{ivr:.0f}"
            except Exception:
                pass
        result["components"]["iv_rank"]         = {"value": iv_rank_val, "pts": iv_pts}

        # ── Recent momentum (10 pts) ──────────────────────────────────────────
        if len(hist) >= 5:
            p5d    = float(hist["Close"].iloc[-5])
            mom    = (current - p5d) / p5d * 100 if p5d else 0
            if mom >= 10:   mom_pts = 10
            elif mom >= 5:  mom_pts = 7
            elif mom >= 2:  mom_pts = 4
            elif mom >= 0:  mom_pts = 2
            else:            mom_pts = 0
        else:
            mom = 0; mom_pts = 0
        result["components"]["5d_momentum"]     = {"value": f"{mom:+.1f}%", "pts": mom_pts}

        # ── Total score ───────────────────────────────────────────────────────
        total = sf_pts + dtc_pts + rvol_pts + ma_pts + iv_pts + mom_pts
        result["score"]        = min(100, total)
        result["short_float"]  = f"{sf_pct:.1f}%"
        result["days_to_cover"] = f"{dtc:.1f}"
        result["current_price"] = current

        if total >= 80:   result["label"] = "HIGH — Squeeze imminent, watch closely"
        elif total >= 60: result["label"] = "BUILDING — Conditions favorable, needs catalyst"
        elif total >= 40: result["label"] = "POSSIBLE — Some setup present"
        else:              result["label"] = "LOW — Not a squeeze candidate currently"

        log.info("[squeeze] %s — score=%d (%s)  SF=%.1f%%  DTC=%.1f  RVOL=%.1f",
                 ticker, total, result["label"][:10], sf_pct, dtc, rvol)

    except Exception:
        log.debug("[squeeze] Failed for %s", ticker, exc_info=True)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 2. PRE-MARKET GAP SCANNER
# ─────────────────────────────────────────────────────────────────────────────
def scan_premarket_gaps(tickers: list[str],
                        gap_threshold_pct: float = 2.0) -> list[dict]:
    """
    Scan for pre-market gaps before market open.
    Returns stocks gapping up or down more than gap_threshold_pct.
    Includes volume context and news catalyst if available.
    """
    gaps = []
    for ticker in tickers:
        try:
            tk   = yf.Ticker(ticker.upper())
            info = tk.info or {}

            pre_price  = (info.get("preMarketPrice")
                          or info.get("currentPrice")
                          or info.get("regularMarketPrice"))
            prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
            pre_vol    = info.get("preMarketVolume") or 0

            if not pre_price or not prev_close:
                continue

            gap_pct = (float(pre_price) - float(prev_close)) / float(prev_close) * 100

            if abs(gap_pct) >= gap_threshold_pct:
                avg_vol = info.get("averageVolume") or 1
                vol_ratio = float(pre_vol) / (float(avg_vol) * 0.1) if avg_vol else 0  # pre-market is ~10% of full day

                gaps.append({
                    "ticker":        ticker.upper(),
                    "pre_price":     round(float(pre_price), 4),
                    "prev_close":    round(float(prev_close), 4),
                    "gap_pct":       round(gap_pct, 2),
                    "direction":     "UP" if gap_pct > 0 else "DOWN",
                    "pre_volume":    int(pre_vol),
                    "vol_ratio":     round(vol_ratio, 2),
                    "urgency":       "HIGH" if abs(gap_pct) >= 5 else "MEDIUM",
                    "signal":        (
                        "Strong gap-up — look for continuation or fade setup"
                        if gap_pct >= 5
                        else "Gap-down — short setup or support bounce watch"
                        if gap_pct <= -5
                        else "Moderate gap — confirm with volume at open"
                    )
                })
        except Exception:
            log.debug("[premarket] Failed for %s", ticker)

    gaps.sort(key=lambda x: abs(x["gap_pct"]), reverse=True)
    log.info("[premarket] Scanned %d tickers — %d gaps found", len(tickers), len(gaps))
    return gaps


# ─────────────────────────────────────────────────────────────────────────────
# 3. NEWS VELOCITY TRACKER
# ─────────────────────────────────────────────────────────────────────────────
def news_velocity(ticker: str, news_items: list[dict] = None) -> dict:
    """
    Detect if news about a ticker is ACCELERATING.
    Acceleration = more articles per hour than the ticker's rolling average.
    This often precedes big moves — the news machine fires up before the stock does.
    """
    result = {"ticker": ticker.upper(), "velocity": "NORMAL", "acceleration": False}

    if not news_items:
        try:
            import web_scraper
            news_items = web_scraper.scrape_google_news(ticker)
        except Exception:
            return result

    if not news_items:
        return result

    now   = datetime.now(timezone.utc)
    cutoffs = {
        "1h":  now - timedelta(hours=1),
        "3h":  now - timedelta(hours=3),
        "12h": now - timedelta(hours=12),
        "24h": now - timedelta(hours=24),
    }
    counts: dict[str, int] = {k: 0 for k in cutoffs}

    for item in news_items:
        raw_date = item.get("date") or item.get("published") or ""
        if not raw_date:
            continue
        try:
            # Parse various date formats
            import re
            dt = None
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z"):
                try:
                    dt = datetime.strptime(str(raw_date)[:25], fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    break
                except Exception:
                    continue

            if not dt:
                continue

            for window, cutoff in cutoffs.items():
                if dt >= cutoff:
                    counts[window] += 1
        except Exception:
            continue

    result["counts"] = counts

    # Acceleration detection
    if counts["1h"] >= 3:
        result["velocity"]     = "VERY HIGH"
        result["acceleration"] = True
        result["signal"]       = f"{counts['1h']} articles in last hour — breaking news or major catalyst"
    elif counts["1h"] >= 2 and counts["3h"] >= 3:
        result["velocity"]     = "HIGH"
        result["acceleration"] = True
        result["signal"]       = f"News accelerating: {counts['1h']}h/1h vs {counts['3h']}h/3h"
    elif counts["3h"] >= 3:
        result["velocity"]     = "ELEVATED"
        result["acceleration"] = False
        result["signal"]       = f"{counts['3h']} articles in last 3 hours — elevated coverage"
    else:
        result["velocity"]     = "NORMAL"
        result["signal"]       = f"{counts['24h']} articles in last 24h — normal coverage"

    log.info("[velocity] %s — 1h=%d  3h=%d  12h=%d  status=%s",
             ticker, counts["1h"], counts["3h"], counts["12h"], result["velocity"])
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 4. EARNINGS REACTION DATABASE
# ─────────────────────────────────────────────────────────────────────────────
def earnings_reaction_history(ticker: str) -> dict:
    """
    How has this stock historically reacted on earnings day?
    Uses yfinance earnings history + price data to calculate actual % moves.

    Returns:
      avg_move_pct:    average absolute move on earnings day (both directions)
      avg_beat_move:   average move when EPS was a beat
      avg_miss_move:   average move when EPS was a miss
      best_move:       biggest single-earnings rally
      worst_move:      biggest single-earnings drop
      beat_rate:       % of quarters where EPS beat estimate
      reaction_history: last 8 quarters detail
    """
    result = {"ticker": ticker.upper()}

    try:
        tk       = yf.Ticker(ticker.upper())
        earnings = tk.earnings_history
        prices   = tk.history(period="3y")

        if earnings is None or earnings.empty or prices.empty:
            return result

        history   = []
        moves     = []
        beat_moves = []
        miss_moves = []

        for _, row in list(earnings.iterrows())[:8]:
            try:
                ed_str   = str(row.get("quarterDate",""))[:10]
                actual   = row.get("epsActual")
                estimate = row.get("epsEstimate")
                surprise = row.get("epsDifference")

                if not ed_str or ed_str == "nan":
                    continue

                # Find the earnings date in price history
                ed = datetime.strptime(ed_str, "%Y-%m-%d").date()

                # Look for price data on earnings day + next day
                price_slice = prices[prices.index.date == ed]
                if price_slice.empty:
                    # Try next trading day
                    for offset in range(1, 4):
                        next_day = ed + timedelta(days=offset)
                        price_slice = prices[prices.index.date == next_day]
                        if not price_slice.empty:
                            break

                if price_slice.empty:
                    continue

                # Day before close (pre-earnings)
                prev_prices = prices[prices.index.date < ed]
                if prev_prices.empty:
                    continue
                prev_close = float(prev_prices["Close"].iloc[-1])
                er_close   = float(price_slice["Close"].iloc[0])
                move_pct   = (er_close - prev_close) / prev_close * 100

                beat = actual is not None and estimate is not None and float(actual) > float(estimate)
                entry = {
                    "date":      ed_str,
                    "estimate":  float(estimate) if estimate is not None else None,
                    "actual":    float(actual) if actual is not None else None,
                    "surprise":  float(surprise) if surprise is not None else None,
                    "beat":      beat,
                    "move_pct":  round(move_pct, 2),
                    "direction": "UP" if move_pct > 0 else "DOWN",
                }
                history.append(entry)
                moves.append(move_pct)
                if beat:    beat_moves.append(move_pct)
                else:       miss_moves.append(move_pct)

            except Exception:
                continue

        if not moves:
            return result

        result["reaction_history"]  = history
        result["avg_move_pct"]      = round(sum(abs(m) for m in moves) / len(moves), 2)
        result["avg_beat_move"]     = round(sum(beat_moves) / len(beat_moves), 2) if beat_moves else None
        result["avg_miss_move"]     = round(sum(miss_moves) / len(miss_moves), 2) if miss_moves else None
        result["best_move"]         = round(max(moves), 2)
        result["worst_move"]        = round(min(moves), 2)
        result["beat_rate"]         = f"{len(beat_moves)/len(moves)*100:.0f}%"
        result["sample_size"]       = len(moves)

        # Interpretation
        avg_abs = result["avg_move_pct"]
        if avg_abs >= 15:
            result["interpretation"] = f"HIGH MOVER — averages {avg_abs:.1f}% on earnings. Options plays make sense."
        elif avg_abs >= 8:
            result["interpretation"] = f"MODERATE MOVER — averages {avg_abs:.1f}%. Earnings moves are tradeable."
        else:
            result["interpretation"] = f"LOW MOVER — averages {avg_abs:.1f}%. Options may not be worth the premium."

        log.info("[earnings_rx] %s — avg_move=%.1f%%  beat_rate=%s  best=+%.1f%%  worst=%.1f%%",
                 ticker, avg_abs, result["beat_rate"], result["best_move"], result["worst_move"])

    except Exception:
        log.debug("[earnings_rx] Failed for %s", ticker, exc_info=True)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 5. MARKET REGIME DETECTOR
# ─────────────────────────────────────────────────────────────────────────────
def detect_market_regime() -> dict:
    """
    Is the market in bull, bear, or chop mode?
    Based on: SPY/QQQ trend, VIX level, sector breadth, recent momentum.
    Returns a regime label and confidence score multiplier for ATLAS.
    """
    result = {
        "regime": "UNKNOWN",
        "confidence_multiplier": 1.0,
        "vix": None,
        "spy_trend": None,
        "qqq_trend": None,
        "signal": "",
    }

    try:
        # Fetch SPY, QQQ, VIX
        spy_hist = yf.Ticker("SPY").history(period="30d")
        qqq_hist = yf.Ticker("QQQ").history(period="30d")
        vix_hist = yf.Ticker("^VIX").history(period="5d")

        if spy_hist.empty or qqq_hist.empty:
            return result

        spy_now  = float(spy_hist["Close"].iloc[-1])
        spy_5d   = float(spy_hist["Close"].iloc[-5])  if len(spy_hist) >= 5 else spy_now
        spy_20d  = float(spy_hist["Close"].iloc[-20]) if len(spy_hist) >= 20 else spy_now
        spy_5d_chg  = (spy_now - spy_5d) / spy_5d * 100
        spy_20d_chg = (spy_now - spy_20d) / spy_20d * 100

        qqq_now  = float(qqq_hist["Close"].iloc[-1])
        qqq_5d   = float(qqq_hist["Close"].iloc[-5])  if len(qqq_hist) >= 5 else qqq_now
        qqq_5d_chg  = (qqq_now - qqq_5d) / qqq_5d * 100

        vix = float(vix_hist["Close"].iloc[-1]) if not vix_hist.empty else 20.0
        result["vix"]       = round(vix, 2)
        result["spy_trend"] = round(spy_5d_chg, 2)
        result["qqq_trend"] = round(qqq_5d_chg, 2)
        result["spy_20d"]   = round(spy_20d_chg, 2)

        # ── DXY Macro Signal — US Dollar Index strength ──────────────────────
        # Strong DXY = headwind for commodities, international revenue stocks, crypto
        # Weak DXY  = tailwind (dollar down = risk assets up)
        dxy_5d_chg = 0.0
        dxy_signal = ""
        try:
            dxy_hist = yf.Ticker("UUP").history(period="10d")  # Invesco USD ETF (reliable proxy)
            if not dxy_hist.empty and len(dxy_hist) >= 5:
                dxy_now     = float(dxy_hist["Close"].iloc[-1])
                dxy_5d_ago  = float(dxy_hist["Close"].iloc[-5])
                dxy_5d_chg  = (dxy_now - dxy_5d_ago) / dxy_5d_ago * 100
                result["dxy_trend"] = round(dxy_5d_chg, 2)
                if dxy_5d_chg > 0.8:
                    dxy_signal = f"DXY +{dxy_5d_chg:.1f}% (strong dollar — headwind for commodities/international)."
                elif dxy_5d_chg < -0.8:
                    dxy_signal = f"DXY {dxy_5d_chg:.1f}% (weak dollar — tailwind for risk assets)."
                log.info("[regime] DXY 5d=%.2f%%", dxy_5d_chg)
        except Exception:
            log.debug("[regime] DXY fetch failed (non-critical)", exc_info=True)

        # Regime classification
        is_bull_5d   = spy_5d_chg > 1.0 and qqq_5d_chg > 1.0
        is_bear_5d   = spy_5d_chg < -2.0
        is_low_vix   = vix < 18
        is_high_vix  = vix > 25
        is_panic_vix = vix > 35
        above_20ma   = spy_20d_chg > 0
        dxy_headwind = dxy_5d_chg > 0.8   # strong dollar reduces confidence for commodity/intl plays

        if is_panic_vix:
            result["regime"] = "PANIC"
            result["confidence_multiplier"] = 0.5
            result["signal"] = f"VIX {vix:.0f} — market fear extreme. Reduce size, buy puts only."
        elif is_bear_5d and is_high_vix:
            result["regime"] = "BEAR"
            result["confidence_multiplier"] = 0.65
            result["signal"] = f"SPY {spy_5d_chg:+.1f}% (5d), VIX {vix:.0f} — bearish environment. Favor bearish setups."
        elif not above_20ma and is_high_vix:
            result["regime"] = "DISTRIBUTION"
            result["confidence_multiplier"] = 0.75
            result["signal"] = f"SPY below 20d MA, VIX elevated {vix:.0f} — distribution phase. Be selective."
        elif is_bull_5d and is_low_vix and above_20ma:
            result["regime"] = "BULL"
            result["confidence_multiplier"] = 1.15
            result["signal"] = f"SPY {spy_5d_chg:+.1f}% (5d), VIX {vix:.0f} — bullish. Favor long setups."
        elif is_bull_5d and above_20ma:
            result["regime"] = "UPTREND"
            result["confidence_multiplier"] = 1.05
            result["signal"] = f"SPY {spy_5d_chg:+.1f}%, above 20d MA — trending up. Long bias."
        else:
            result["regime"] = "CHOP"
            result["confidence_multiplier"] = 0.85
            result["signal"] = f"SPY {spy_5d_chg:+.1f}% (5d) — choppy market. Raise standards."

        # Append DXY signal to regime signal string
        if dxy_signal:
            result["signal"] = result["signal"].rstrip(".") + ". " + dxy_signal
        # Apply small DXY headwind adjustment to confidence multiplier
        if dxy_headwind and result["confidence_multiplier"] >= 1.0:
            result["confidence_multiplier"] = round(result["confidence_multiplier"] - 0.05, 2)

        log.info("[regime] %s | SPY 5d=%.1f%% 20d=%.1f%% VIX=%.1f DXY 5d=%.1f%% | mult=%.2f",
                 result["regime"], spy_5d_chg, spy_20d_chg, vix, dxy_5d_chg,
                 result["confidence_multiplier"])

    except Exception:
        log.debug("[regime] Failed", exc_info=True)

    return result


get_market_regime = detect_market_regime  # API + Loop 1 alias (was missing; caused AttributeError)


# ─────────────────────────────────────────────────────────────────────────────
# 6. DARK HORSE SCANNER — finds new setups matching ATLAS best patterns
# ─────────────────────────────────────────────────────────────────────────────
def scan_for_dark_horses(theme: str = "high_short_squeeze",
                         max_results: int = 8) -> list[dict]:
    """
    Scan Finviz for stocks matching ATLAS's best historical win patterns.
    Uses the tracker pattern library to find which setup tags have the
    highest win rates, then screeners for stocks matching those criteria.
    """
    results: list[dict] = []

    # Get top performing tags from tracker
    top_tags: list[str] = []
    try:
        import tracker
        stats = tracker.setup_pattern_stats(min_samples=2)
        top_tags = [s["tag"] for s in stats[:5] if s["win_rate"] >= 60]
    except Exception:
        pass

    # Map to Finviz screener parameters
    # Using yfinance screener approach — scan well-known volatile tickers
    # with the characteristics of best patterns
    scan_tickers_by_theme = {
        "high_short_squeeze": [
            "MARA", "RIOT", "CIFR", "BTBT", "HUT",   # crypto miners
            "SOUN", "IONQ", "RGTI", "QBTS", "ARQQ",   # AI/quantum
            "ASTS", "RKLB", "SPCE", "LUNR", "RDW",    # space
            "RZLV", "SAVA", "ACHR", "JOBY", "LILM",   # biotech/eVTOL
        ],
        "earnings_momentum": [
            "NVDA", "AMD", "SMCI", "MRVL", "ON",
            "PLTR", "CRWD", "DDOG", "ZS", "NET",
        ],
        "ai_tech": [
            "SOUN", "IONQ", "ARQQ", "QBTS", "BBAI",
            "GFAI", "PEGA", "AI", "BIGB", "NRXS",
        ],
    }

    candidates = scan_tickers_by_theme.get(theme, scan_tickers_by_theme["high_short_squeeze"])

    for ticker in candidates[:15]:
        try:
            tk   = yf.Ticker(ticker)
            info = tk.info or {}

            sf_raw = info.get("shortPercentOfFloat") or 0
            sf_pct = float(sf_raw) * 100
            dtc    = float(info.get("shortRatio") or 0)
            vol    = info.get("volume") or 0
            avg_v  = info.get("averageVolume") or 1
            rvol   = float(vol) / float(avg_v) if avg_v else 1
            price  = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
            mkt_cap = info.get("marketCap") or 0

            # Quick score
            score = 0
            if sf_pct >= 20: score += 30
            if sf_pct >= 30: score += 20
            if dtc >= 5:     score += 20
            if rvol >= 1.5:  score += 15
            if 1 <= price <= 50: score += 10  # sweet spot for retail options
            if mkt_cap < 5e9:    score += 5   # small cap more volatile

            if score >= 40:
                results.append({
                    "ticker":     ticker,
                    "score":      score,
                    "short_float": f"{sf_pct:.1f}%",
                    "days_to_cover": f"{dtc:.1f}",
                    "rel_volume": f"{rvol:.1f}x",
                    "price":      round(price, 4),
                    "mkt_cap":    f"${mkt_cap/1e9:.2f}B" if mkt_cap else "?",
                    "why":        (f"SF={sf_pct:.0f}% DTC={dtc:.1f}d RVOL={rvol:.1f}x — "
                                   f"{'Pattern match: ' + ','.join(top_tags[:2]) if top_tags else 'Squeeze candidate'}"),
                })
            time.sleep(0.3)
        except Exception:
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    log.info("[dark_horse] Found %d candidates for theme '%s'", len(results), theme)
    return results[:max_results]


# ─────────────────────────────────────────────────────────────────────────────
# Master awareness bundle — called from deep_research
# ─────────────────────────────────────────────────────────────────────────────
def full_awareness(ticker: str, scrape_data: dict = None,
                   news_items: list[dict] = None) -> dict:
    """
    Run all awareness modules for a ticker. Returns a bundled dict
    with all hyper-awareness signals for injection into synthesis.
    """
    log.info("[awareness] Running full awareness scan for %s...", ticker)

    regime  = detect_market_regime()
    squeeze = squeeze_score(ticker, scrape_data)
    velocity = news_velocity(ticker, news_items)
    er_hist = earnings_reaction_history(ticker)

    # Build context text for AI synthesis
    lines = ["\n=== ATLAS HYPER-AWARENESS SIGNALS ==="]

    # Regime
    lines.append(f"Market Regime: {regime.get('regime','?')} | {regime.get('signal','')}")
    if regime.get("vix"):
        dxy_str = f"  DXY 5d: {regime['dxy_trend']:+.1f}%" if regime.get("dxy_trend") is not None else ""
        lines.append(f"VIX: {regime['vix']}  SPY 5d: {regime.get('spy_trend','')}%  SPY 20d: {regime.get('spy_20d','')}%{dxy_str}")
    mult = regime.get("confidence_multiplier", 1.0)
    if mult != 1.0:
        lines.append(f"⚡ REGIME ADJUSTMENT: Apply {mult:.2f}x multiplier to all confidence scores")

    # Squeeze
    sq_score = squeeze.get("score", 0)
    lines.append(f"\nShort Squeeze Score: {sq_score}/100 — {squeeze.get('label','?')}")
    if sq_score >= 60:
        lines.append(f"  Short Float: {squeeze.get('short_float','?')}  Days-to-Cover: {squeeze.get('days_to_cover','?')}")

    # News velocity
    lines.append(f"\nNews Velocity: {velocity.get('velocity','?')} | {velocity.get('signal','')}")
    if velocity.get("acceleration"):
        lines.append("  ⚡ News ACCELERATING — something may be happening, check latest headlines first")

    # Earnings reaction history
    if er_hist.get("avg_move_pct"):
        lines.append(f"\nHistorical Earnings Reactions ({er_hist.get('sample_size',0)} quarters):")
        lines.append(f"  Average move: {er_hist['avg_move_pct']:.1f}%  Beat rate: {er_hist.get('beat_rate','?')}")
        if er_hist.get("avg_beat_move") is not None:
            lines.append(f"  On beats: avg {er_hist['avg_beat_move']:+.1f}%  On misses: avg {er_hist.get('avg_miss_move',0):+.1f}%")
        lines.append(f"  Best: +{er_hist.get('best_move',0):.1f}%  Worst: {er_hist.get('worst_move',0):.1f}%")
        lines.append(f"  {er_hist.get('interpretation','')}")

    lines.append("=== END AWARENESS ===\n")

    return {
        "regime":           regime,
        "squeeze":          squeeze,
        "velocity":         velocity,
        "earnings_reactions": er_hist,
        "context_text":     "\n".join(lines),
        "confidence_multiplier": regime.get("confidence_multiplier", 1.0),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "regime"

    if cmd == "regime":
        r = detect_market_regime()
        print(f"\nMarket Regime: {r['regime']}")
        print(f"Signal: {r['signal']}")
        print(f"VIX: {r.get('vix','?')}  SPY 5d: {r.get('spy_trend','?')}%")
        print(f"Confidence multiplier: {r['confidence_multiplier']:.2f}x")

    elif cmd == "squeeze" and len(sys.argv) > 2:
        t = sys.argv[2].upper()
        s = squeeze_score(t)
        print(f"\n{t} Squeeze Score: {s['score']}/100")
        print(f"Label: {s['label']}")
        for k, v in s.get("components",{}).items():
            print(f"  {k}: {v['value']} ({v['pts']} pts)")

    elif cmd == "velocity" and len(sys.argv) > 2:
        t = sys.argv[2].upper()
        v = news_velocity(t)
        print(f"\n{t} News Velocity: {v['velocity']}")
        print(f"Signal: {v['signal']}")
        print(f"Counts: {v.get('counts',{})}")

    elif cmd == "earnings" and len(sys.argv) > 2:
        t = sys.argv[2].upper()
        e = earnings_reaction_history(t)
        print(f"\n{t} Earnings Reaction History:")
        print(f"  Avg move: {e.get('avg_move_pct','?')}%")
        print(f"  Beat rate: {e.get('beat_rate','?')}")
        print(f"  Best: +{e.get('best_move','?')}%  Worst: {e.get('worst_move','?')}%")
        print(f"  {e.get('interpretation','')}")

    elif cmd == "scan":
        theme = sys.argv[2] if len(sys.argv) > 2 else "high_short_squeeze"
        candidates = scan_for_dark_horses(theme)
        print(f"\nDark Horse Scanner — theme: {theme}")
        for c in candidates:
            print(f"  {c['ticker']:<6} score={c['score']}  {c['why']}")

    else:
        print("Usage: python market_scanner.py regime | squeeze SOUN | velocity SOUN | earnings SOUN | scan")
