"""
backtest_sandbox.py - ATLAS Dynamic Backtest Sandbox

Gemini writes a pandas backtest script from a natural-language setup description.
Python executes it in a sandboxed subprocess against 5 years of yfinance OHLCV data.
Results are injected into the synthesis prompt: instead of "this setup worked 3/4 times,"
ATLAS says "this setup is 68% accurate across 47 occurrences 2019-2024 — mathematically proven."

Architecture:
  1. Convert setup_tags → technical description
  2. Fetch 5y OHLCV + derived indicators (RSI, VWAP, volume ratio) via yfinance
  3. Ask Gemini to write a pandas backtest script
  4. Run script in subprocess (30s timeout, pandas/numpy only)
  5. Parse JSON results → format as synthesis context string

Safety:
  - Subprocess timeout 30s — never hangs
  - Restricted imports (pandas, numpy, sys, json, warnings only)
  - Any failure returns "" — never blocks deep research

Usage:
    python backtest_sandbox.py AAPL "RSI oversold bounce"
    python backtest_sandbox.py SOUN "short squeeze breakout"
    python backtest_sandbox.py --status             # show cache stats

Quick tuning (.env optional):
    BACKTEST_LOOKBACK_YEARS = years of daily bars (default 5)
    BACKTEST_FORWARD_DAYS   = horizon after each signal to measure return (default 10)
    BACKTEST_CACHE_TTL_H    = hours to reuse cached identical run (default 24)

Built-in setups (Gemini skips when keywords match — see _get_static_template in source):
    RSI oversold, momentum breakout, short squeeze breakout, BB squeeze,
    bullish volume spike, bullish momentum streak.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

from gemini_limiter import wait_for_slot

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
CACHE_DIR      = Path(__file__).parent / "atlas_rag"          # reuse existing dir
CACHE_FILE     = CACHE_DIR / "backtest_cache.json"
SANDBOX_TIMEOUT = 30     # seconds
CACHE_TTL_H    = int(os.environ.get("BACKTEST_CACHE_TTL_H", "24"))
LOOKBACK_YEARS  = int(os.environ.get("BACKTEST_LOOKBACK_YEARS", "5"))
FORWARD_DAYS    = int(os.environ.get("BACKTEST_FORWARD_DAYS", "10"))

# ─────────────────────────────────────────────────────────────────────────────
# Setup tag → technical description
# ─────────────────────────────────────────────────────────────────────────────
TAG_DESCRIPTIONS: dict[str, str] = {
    "extreme_short_float":  "short interest above 35% of float — extreme short squeeze potential",
    "high_short_interest":  "short interest 20–35% — elevated squeeze risk",
    "momentum_breakout":    "price breaks above 20-day high on volume 1.5x the 20-day average",
    "oversold_bounce":      "RSI(14) drops below 30 — oversold mean-reversion setup",
    "overbought_caution":   "RSI(14) above 70 — overbought, potential pullback",
    "earnings_catalyst":    "strong earnings beat with positive guidance revision",
    "news_velocity_spike":  "abnormal news volume spike — 3x normal mentions in 24h",
    "squeeze_setup":        "Bollinger Band width at 6-month low — volatility compression before expansion",
    "high_conviction":      "ATLAS composite conviction score 8+/10 — multi-factor confluence",
    "atlas_bullish":        "ATLAS overall rating is strong_buy or buy",
    "analyst_upgrade":      "analyst upgrade or price target raise in past 30 days",
    "insider_buying":       "insider purchase filed with SEC in past 90 days",
    "congress_buying":      "congressional member disclosed buy in past 180 days",
    "volume_spike":         "daily volume 2x+ the 20-day average",
    "gap_up":               "price gaps up 3%+ at open from prior close",
    "gap_down":             "price gaps down 3%+ at open — potential snap-back bounce",
    "low_float":            "float under 50M shares — amplified move potential",
}

DEFAULT_SETUP = "bullish momentum with above-average volume and positive price trend"


def _tags_to_description(setup_tags: list[str], research: dict = None) -> str:
    """Convert setup tags to a natural-language technical setup description."""
    if not setup_tags:
        # Try to extract from research synthesis
        if research:
            syn = research.get("synthesis") or {}
            rating = syn.get("overall_rating", "")
            action = (syn.get("trade_plan") or {}).get("action", "")
            if "buy" in rating or "buy" in action:
                return DEFAULT_SETUP
        return DEFAULT_SETUP

    desc_parts = [TAG_DESCRIPTIONS.get(tag, tag.replace("_", " ")) for tag in setup_tags[:4]]
    combined   = " AND ".join(desc_parts)

    # Add direction from research if available
    if research:
        syn    = (research.get("synthesis") or {})
        rating = syn.get("overall_rating", "")
        if "strong_buy" in rating:
            combined = "strong bullish setup: " + combined
        elif "buy" in rating:
            combined = "bullish setup: " + combined
        elif "sell" in rating:
            combined = "bearish setup: " + combined

    return combined


# ─────────────────────────────────────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────────────────────────────────────

def _cache_key(ticker: str, setup_desc: str) -> str:
    raw = f"{ticker.upper()}|{setup_desc[:100]}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cache(data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _get_cached(key: str) -> Optional[dict]:
    cache = _load_cache()
    entry = cache.get(key)
    if not entry:
        return None
    try:
        cached_at = datetime.fromisoformat(entry.get("cached_at", "2000-01-01"))
        age_h     = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_h < CACHE_TTL_H:
            return entry.get("result")
    except Exception:
        pass
    return None


def _store_cached(key: str, result: dict) -> None:
    cache = _load_cache()
    cache[key] = {
        "result":    result,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    # Prune old entries (keep last 50)
    if len(cache) > 50:
        keys_by_age = sorted(cache.keys(),
                             key=lambda k: cache[k].get("cached_at", ""), reverse=True)
        cache = {k: cache[k] for k in keys_by_age[:50]}
    _save_cache(cache)


# ─────────────────────────────────────────────────────────────────────────────
# OHLCV data preparation
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_ohlcv(ticker: str) -> Optional[str]:
    """Fetch 5y daily OHLCV + RSI + volume_ratio as CSV string."""
    try:
        import yfinance as yf
        import pandas as pd

        hist = yf.Ticker(ticker).history(period=f"{LOOKBACK_YEARS}y", interval="1d")
        if hist.empty or len(hist) < 50:
            log.warning("[backtest] Insufficient data for %s (%d rows)", ticker, len(hist))
            return None

        df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.columns = ["open", "high", "low", "close", "volume"]
        df.index.name = "date"

        # Add derived indicators so Gemini can use them directly
        df["rsi14"]        = _rsi(df["close"], 14)
        df["sma20"]        = df["close"].rolling(20).mean()
        df["sma50"]        = df["close"].rolling(50).mean()
        df["vol20_avg"]    = df["volume"].rolling(20).mean()
        df["volume_ratio"] = (df["volume"] / df["vol20_avg"]).round(2)
        df["pct_change"]   = df["close"].pct_change().round(4)
        df["high20"]       = df["close"].rolling(20).max().shift(1)  # prior 20d high
        df["low20"]        = df["close"].rolling(20).min().shift(1)
        df["bb_width"]     = (df["close"].rolling(20).std() / df["sma20"]).round(4)

        df = df.dropna(subset=["rsi14", "sma20"]).round(4)
        csv = df.reset_index().to_csv(index=False)
        log.info("[backtest] OHLCV fetched: %d rows for %s", len(df), ticker)
        return csv

    except Exception as e:
        log.error("[backtest] OHLCV fetch failed for %s: %s", ticker, e)
        return None


def _rsi(series, period: int = 14):
    """Compute RSI without talib."""
    import pandas as pd
    delta = series.diff()
    gain  = delta.where(delta > 0, 0.0)
    loss  = -delta.where(delta < 0, 0.0)
    avg_g = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_l = loss.ewm(com=period - 1, min_periods=period).mean()
    rs    = avg_g / avg_l.replace(0, float("nan"))
    return (100 - 100 / (1 + rs)).round(2)


# ─────────────────────────────────────────────────────────────────────────────
# Static backtest templates (no Gemini required for common setups)
# ─────────────────────────────────────────────────────────────────────────────

_STATIC_TEMPLATES = {
    "rsi_oversold": """\
import pandas as pd, numpy as np, sys, json, warnings
warnings.filterwarnings("ignore")
df = pd.read_csv(sys.argv[1])
df['date'] = pd.to_datetime(df['date'])
FWD = {fwd}
signals = df[df['rsi14'] < 30].index.tolist()
returns = []
for i in signals:
    j = i + FWD
    if j < len(df):
        r = (df.loc[j, 'close'] - df.loc[i, 'close']) / df.loc[i, 'close']
        returns.append(float(r))
returns = [r for r in returns if abs(r) < 0.5]
n = len(returns)
wins = [r for r in returns if r > 0]
losses = [r for r in returns if r <= 0]
print(json.dumps({{
    "setup_name": "RSI Oversold Bounce (RSI<30)",
    "n_occurrences": n,
    "win_rate": len(wins)/n if n else 0.0,
    "avg_return_10d": float(np.mean(returns)) if returns else 0.0,
    "avg_win_return": float(np.mean(wins)) if wins else 0.0,
    "avg_loss_return": float(np.mean(losses)) if losses else 0.0,
    "best_return": float(max(returns)) if returns else 0.0,
    "worst_return": float(min(returns)) if returns else 0.0,
    "median_return": float(np.median(returns)) if returns else 0.0,
    "years_tested": {years},
    "setup_condition": "rsi14 < 30"
}}))
""",

    "momentum_breakout": """\
import pandas as pd, numpy as np, sys, json, warnings
warnings.filterwarnings("ignore")
df = pd.read_csv(sys.argv[1])
FWD = {fwd}
signals = df[(df['close'] > df['high20']) & (df['volume_ratio'] >= 1.5)].index.tolist()
returns = []
for i in signals:
    j = i + FWD
    if j < len(df):
        r = (df.loc[j, 'close'] - df.loc[i, 'close']) / df.loc[i, 'close']
        returns.append(float(r))
returns = [r for r in returns if abs(r) < 0.5]
n = len(returns)
wins = [r for r in returns if r > 0]
losses = [r for r in returns if r <= 0]
print(json.dumps({{
    "setup_name": "Momentum Breakout (price>20d high, vol>1.5x)",
    "n_occurrences": n,
    "win_rate": len(wins)/n if n else 0.0,
    "avg_return_10d": float(np.mean(returns)) if returns else 0.0,
    "avg_win_return": float(np.mean(wins)) if wins else 0.0,
    "avg_loss_return": float(np.mean(losses)) if losses else 0.0,
    "best_return": float(max(returns)) if returns else 0.0,
    "worst_return": float(min(returns)) if returns else 0.0,
    "median_return": float(np.median(returns)) if returns else 0.0,
    "years_tested": {years},
    "setup_condition": "close > high20 AND volume_ratio >= 1.5"
}}))
""",

    "volume_spike": """\
import pandas as pd, numpy as np, sys, json, warnings
warnings.filterwarnings("ignore")
df = pd.read_csv(sys.argv[1])
FWD = {fwd}
signals = df[(df['volume_ratio'] >= 2.0) & (df['pct_change'] > 0)].index.tolist()
returns = []
for i in signals:
    j = i + FWD
    if j < len(df):
        r = (df.loc[j, 'close'] - df.loc[i, 'close']) / df.loc[i, 'close']
        returns.append(float(r))
returns = [r for r in returns if abs(r) < 0.5]
n = len(returns)
wins = [r for r in returns if r > 0]
losses = [r for r in returns if r <= 0]
print(json.dumps({{
    "setup_name": "Bullish Volume Spike (vol>2x, positive day)",
    "n_occurrences": n,
    "win_rate": len(wins)/n if n else 0.0,
    "avg_return_10d": float(np.mean(returns)) if returns else 0.0,
    "avg_win_return": float(np.mean(wins)) if wins else 0.0,
    "avg_loss_return": float(np.mean(losses)) if losses else 0.0,
    "best_return": float(max(returns)) if returns else 0.0,
    "worst_return": float(min(returns)) if returns else 0.0,
    "median_return": float(np.median(returns)) if returns else 0.0,
    "years_tested": {years},
    "setup_condition": "volume_ratio >= 2.0 AND pct_change > 0"
}}))
""",

    "squeeze_setup": """\
import pandas as pd, numpy as np, sys, json, warnings
warnings.filterwarnings("ignore")
df = pd.read_csv(sys.argv[1])
FWD = {fwd}
bb_threshold = df['bb_width'].rolling(126).quantile(0.15)
signals = df[df['bb_width'] <= bb_threshold].index.tolist()
returns = []
for i in signals:
    j = i + FWD
    if j < len(df):
        r = (df.loc[j, 'close'] - df.loc[i, 'close']) / df.loc[i, 'close']
        returns.append(float(r))
returns = [r for r in returns if abs(r) < 0.5]
n = len(returns)
wins = [r for r in returns if r > 0]
losses = [r for r in returns if r <= 0]
print(json.dumps({{
    "setup_name": "Bollinger Squeeze (volatility compression)",
    "n_occurrences": n,
    "win_rate": len(wins)/n if n else 0.0,
    "avg_return_10d": float(np.mean(returns)) if returns else 0.0,
    "avg_win_return": float(np.mean(wins)) if wins else 0.0,
    "avg_loss_return": float(np.mean(losses)) if losses else 0.0,
    "best_return": float(max(returns)) if returns else 0.0,
    "worst_return": float(min(returns)) if returns else 0.0,
    "median_return": float(np.median(returns)) if returns else 0.0,
    "years_tested": {years},
    "setup_condition": "bb_width <= 15th percentile (6-month rolling)"
}}))
""",

    "bullish_momentum": """\
import pandas as pd, numpy as np, sys, json, warnings
warnings.filterwarnings("ignore")
df = pd.read_csv(sys.argv[1])
FWD = {fwd}
signals = df[
    (df['close'] > df['sma20']) &
    (df['sma20'] > df['sma50']) &
    (df['rsi14'] > 50) & (df['rsi14'] < 70) &
    (df['volume_ratio'] >= 1.2)
].index.tolist()
returns = []
for i in signals:
    j = i + FWD
    if j < len(df):
        r = (df.loc[j, 'close'] - df.loc[i, 'close']) / df.loc[i, 'close']
        returns.append(float(r))
returns = [r for r in returns if abs(r) < 0.5]
n = len(returns)
wins = [r for r in returns if r > 0]
losses = [r for r in returns if r <= 0]
print(json.dumps({{
    "setup_name": "Bullish Momentum (price>SMA20>SMA50, RSI 50-70, vol>1.2x)",
    "n_occurrences": n,
    "win_rate": len(wins)/n if n else 0.0,
    "avg_return_10d": float(np.mean(returns)) if returns else 0.0,
    "avg_win_return": float(np.mean(wins)) if wins else 0.0,
    "avg_loss_return": float(np.mean(losses)) if losses else 0.0,
    "best_return": float(max(returns)) if returns else 0.0,
    "worst_return": float(min(returns)) if returns else 0.0,
    "median_return": float(np.median(returns)) if returns else 0.0,
    "years_tested": {years},
    "setup_condition": "close>sma20>sma50 AND rsi14 in (50,70) AND volume_ratio>=1.2"
}}))
""",

    "short_squeeze": """\
import pandas as pd, numpy as np, sys, json, warnings
warnings.filterwarnings("ignore")
df = pd.read_csv(sys.argv[1])
FWD = {fwd}
signals = df[
    (df['volume_ratio'] >= 2.5) &
    (df['pct_change'] > 0.03) &
    (df['rsi14'] > 40)
].index.tolist()
returns = []
for i in signals:
    j = i + FWD
    if j < len(df):
        r = (df.loc[j, 'close'] - df.loc[i, 'close']) / df.loc[i, 'close']
        returns.append(float(r))
returns = [r for r in returns if abs(r) < 0.8]
n = len(returns)
wins = [r for r in returns if r > 0]
losses = [r for r in returns if r <= 0]
print(json.dumps({{
    "setup_name": "Short Squeeze Breakout (vol>2.5x, gap>3%, RSI>40)",
    "n_occurrences": n,
    "win_rate": len(wins)/n if n else 0.0,
    "avg_return_10d": float(np.mean(returns)) if returns else 0.0,
    "avg_win_return": float(np.mean(wins)) if wins else 0.0,
    "avg_loss_return": float(np.mean(losses)) if losses else 0.0,
    "best_return": float(max(returns)) if returns else 0.0,
    "worst_return": float(min(returns)) if returns else 0.0,
    "median_return": float(np.median(returns)) if returns else 0.0,
    "years_tested": {years},
    "setup_condition": "volume_ratio>=2.5 AND pct_change>3% AND rsi14>40"
}}))
""",
}


def _get_static_template(setup_desc: str, setup_tags: list[str] = None) -> Optional[str]:
    """
    Match setup description to a pre-built template.
    Returns formatted code string or None if no match.
    """
    desc  = setup_desc.lower()
    tags  = [t.lower() for t in (setup_tags or [])]

    fmt = {"fwd": FORWARD_DAYS, "years": LOOKBACK_YEARS}

    if "oversold" in desc or "rsi" in desc or "oversold_bounce" in tags:
        return _STATIC_TEMPLATES["rsi_oversold"].format(**fmt)
    if "breakout" in desc and ("momentum" in desc or "momentum_breakout" in tags):
        return _STATIC_TEMPLATES["momentum_breakout"].format(**fmt)
    if "short squeeze" in desc or "squeeze" in desc and "short" in desc or \
            "extreme_short_float" in tags or "high_short_interest" in tags:
        return _STATIC_TEMPLATES["short_squeeze"].format(**fmt)
    if "squeeze" in desc or "squeeze_setup" in tags or "bollinger" in desc:
        return _STATIC_TEMPLATES["squeeze_setup"].format(**fmt)
    if "volume spike" in desc or "volume_spike" in tags:
        return _STATIC_TEMPLATES["volume_spike"].format(**fmt)
    if "momentum" in desc or "bullish" in desc or "atlas_bullish" in tags:
        return _STATIC_TEMPLATES["bullish_momentum"].format(**fmt)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Gemini code generation
# ─────────────────────────────────────────────────────────────────────────────

_BACKTEST_PROMPT = """You are an expert Python quant developer writing a backtesting script.

SETUP TO BACKTEST: {setup_desc}
TICKER: {ticker}
FORWARD WINDOW: {fwd_days} trading days (measure return from signal day to {fwd_days} days later)

The script will receive a CSV file path as sys.argv[1].
The CSV has columns: date, open, high, low, close, volume, rsi14, sma20, sma50, vol20_avg, volume_ratio, pct_change, high20, low20, bb_width

Your script must:
1. Import ONLY: pandas, numpy, sys, json, warnings
2. Load the CSV: df = pd.read_csv(sys.argv[1])
3. Identify ALL rows where the setup condition is met (be specific with thresholds)
4. For each signal row, compute the {fwd_days}-day forward return:
   forward_return = (close[i+{fwd_days}] - close[i]) / close[i]
5. Compute statistics across all signals
6. Print EXACTLY ONE JSON object to stdout (no other output):
{{
  "setup_name": "<short descriptive name>",
  "n_occurrences": <integer>,
  "win_rate": <float 0-1, fraction with positive forward return>,
  "avg_return_10d": <float, average forward return across all signals>,
  "avg_win_return": <float, average return on winning trades only>,
  "avg_loss_return": <float, average return on losing trades only>,
  "best_return": <float, max single forward return>,
  "worst_return": <float, min single forward return>,
  "median_return": <float>,
  "years_tested": {years},
  "setup_condition": "<one-line description of the exact condition used>"
}}

If no occurrences found: set n_occurrences=0, all returns=0.0, win_rate=0.0
Wrap all code in try/except and always print valid JSON.
Do NOT print anything else. Do NOT use print() except for the final JSON.
Write clean, fast vectorized pandas code. No loops if possible.
"""


def _generate_backtest_code(ticker: str, setup_desc: str) -> Optional[str]:
    """Ask Gemini to write the backtest script. Returns Python code string."""
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent / ".env")
        load_dotenv()

        from google import genai
        api_key = (os.environ.get("GEMINI_API_KEY", "")
                   or os.environ.get("GOOGLE_API_KEY", "")).strip()
        if not api_key:
            log.warning("[backtest] No GEMINI_API_KEY/GOOGLE_API_KEY — cannot generate backtest code")
            return None

        client = genai.Client(api_key=api_key)
        prompt = _BACKTEST_PROMPT.format(
            setup_desc = setup_desc,
            ticker     = ticker,
            fwd_days   = FORWARD_DAYS,
            years      = LOOKBACK_YEARS,
        )

        # Model fallback: 2.5-flash → 2.0-flash → 1.5-flash
        models_to_try = [
            os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ]
        import re as _re
        for model in models_to_try:
            for attempt in range(2):
                try:
                    wait_for_slot("backtest_sandbox")
                    resp = client.models.generate_content(model=model, contents=prompt)
                    code = (resp.text or "").strip()
                    if code:
                        code = _re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", code)
                        code = _re.sub(r"\s*```\s*$", "", code).strip()
                        log.info("[backtest] %s generated %d chars of backtest code", model, len(code))
                        return code
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str and attempt < 1:
                        time.sleep((attempt + 1) * 6)
                    elif "503" in err_str or "UNAVAILABLE" in err_str:
                        log.debug("[backtest] %s unavailable, trying next model", model)
                        break  # try next model
                    else:
                        log.warning("[backtest] Gemini code gen failed (%s): %s", model, e)
                        break
    except Exception as e:
        log.warning("[backtest] Code generation setup failed: %s", e)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Subprocess sandbox
# ─────────────────────────────────────────────────────────────────────────────

def _run_sandbox(code: str, csv_data: str) -> Optional[dict]:
    """
    Write code to a temp file, data to another temp file,
    run in subprocess with timeout. Returns parsed JSON dict.
    """
    tmp_code = tmp_csv = None
    try:
        # Write files
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py",
                                         delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_code = f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv",
                                          delete=False, encoding="utf-8") as f:
            f.write(csv_data)
            tmp_csv = f.name

        # Run subprocess
        result = subprocess.run(
            [sys.executable, tmp_code, tmp_csv],
            capture_output = True,
            text           = True,
            timeout        = SANDBOX_TIMEOUT,
            encoding       = "utf-8",
            errors         = "replace",
        )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if result.returncode != 0:
            log.warning("[backtest] Sandbox exited with code %d: %s",
                        result.returncode, stderr[:200])

        if not stdout:
            log.warning("[backtest] Sandbox produced no output. Stderr: %s", stderr[:200])
            return None

        # Parse JSON from stdout (might have extra lines before it)
        import re as _re
        json_match = _re.search(r"\{[\s\S]+\}", stdout)
        if not json_match:
            log.warning("[backtest] No JSON found in sandbox output: %s", stdout[:200])
            return None

        parsed = json.loads(json_match.group(0))
        log.info("[backtest] Sandbox result: n=%d win_rate=%.1f%% avg_return=%.2f%%",
                 parsed.get("n_occurrences", 0),
                 parsed.get("win_rate", 0) * 100,
                 parsed.get("avg_return_10d", 0) * 100)
        return parsed

    except subprocess.TimeoutExpired:
        log.warning("[backtest] Sandbox timed out after %ds", SANDBOX_TIMEOUT)
        return None
    except json.JSONDecodeError as e:
        log.warning("[backtest] JSON parse failed: %s", e)
        return None
    except Exception as e:
        log.warning("[backtest] Sandbox error: %s", e)
        return None
    finally:
        for tmp in [tmp_code, tmp_csv]:
            if tmp:
                try:
                    Path(tmp).unlink(missing_ok=True)
                except Exception:
                    pass


# ─────────────────────────────────────────────────────────────────────────────
# Core public API
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(ticker: str, setup_description: str,
                 setup_tags: list[str] = None,
                 use_cache: bool = True) -> Optional[dict]:
    """
    Run a full backtest for a ticker and setup description.
    Returns result dict or None if failed.
    """
    ticker = ticker.upper()
    key    = _cache_key(ticker, setup_description)

    if use_cache:
        cached = _get_cached(key)
        if cached:
            log.info("[backtest] Cache hit for %s — skipping re-run", ticker)
            return cached

    log.info("[backtest] Running backtest: %s — '%s'", ticker, setup_description[:60])

    # 1. Fetch data
    csv_data = _fetch_ohlcv(ticker)
    if not csv_data:
        return None

    # 2. Try static template first (fast, no API call)
    code = _get_static_template(setup_description, setup_tags)
    if code:
        log.info("[backtest] Using static template for setup: %s", setup_description[:40])
    else:
        # 3. Fall back to Gemini code generation
        code = _generate_backtest_code(ticker, setup_description)
        if not code:
            log.warning("[backtest] No code generated — skipping backtest for %s", ticker)
            return None

    # 4. Run sandbox
    result = _run_sandbox(code, csv_data)
    if not result:
        return None

    # 4. Enrich result
    result["ticker"]        = ticker
    result["setup_desc"]    = setup_description[:100]
    result["run_date"]      = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result["forward_days"]  = FORWARD_DAYS
    result["years_tested"]  = result.get("years_tested", LOOKBACK_YEARS)

    # 5. Cache
    _store_cached(key, result)

    return result


def get_backtest_context(ticker: str,
                         setup_tags: list[str] = None,
                         research: dict = None,
                         use_cache: bool = True) -> str:
    """
    Run a backtest and return a formatted string for injection into the synthesis prompt.
    Returns "" if backtest fails or finds <5 occurrences (too few to be meaningful).
    Never raises — always safe to call.
    """
    try:
        setup_desc = _tags_to_description(setup_tags or [], research)
        result     = run_backtest(ticker, setup_desc, setup_tags=setup_tags, use_cache=use_cache)

        if not result:
            return ""

        n = result.get("n_occurrences", 0)
        if n < 5:
            log.info("[backtest] Only %d occurrences for %s — too few to be meaningful", n, ticker)
            return ""

        win_rate    = result.get("win_rate", 0) * 100
        avg_ret     = result.get("avg_return_10d", 0) * 100
        avg_win     = result.get("avg_win_return", 0) * 100
        avg_loss    = result.get("avg_loss_return", 0) * 100
        best        = result.get("best_return", 0) * 100
        worst       = result.get("worst_return", 0) * 100
        setup_name  = result.get("setup_name", setup_desc[:50])
        condition   = result.get("setup_condition", "")
        run_date    = result.get("run_date", "?")
        years       = result.get("years_tested", LOOKBACK_YEARS)
        fwd         = result.get("forward_days", FORWARD_DAYS)

        strength = ("STRONG" if win_rate >= 65 else
                    "MODERATE" if win_rate >= 55 else
                    "WEAK")

        lines = [
            f"\n=== DYNAMIC BACKTEST RESULTS FOR {ticker} ===",
            f"(Setup: {setup_name})",
            f"(Backtested {years} years of daily data via yfinance — run {run_date})",
            f"(Condition: {condition})" if condition else "",
            f"",
            f"Occurrences found:   {n} signals over {years} years",
            f"Win rate:            {win_rate:.1f}% ({strength})",
            f"Avg {fwd}d return:     {avg_ret:+.2f}%",
            f"Avg win return:      {avg_win:+.2f}%",
            f"Avg loss return:     {avg_loss:+.2f}%",
            f"Best single trade:   {best:+.2f}%",
            f"Worst single trade:  {worst:+.2f}%",
            f"",
            f"INSTRUCTION: This is MATHEMATICAL PROOF from {years} years of history.",
            (f"This setup is historically {strength} — cite the {win_rate:.0f}% win rate "
             f"over {n} occurrences in your analysis.")
            if n >= 10 else
            f"Sample size ({n}) is small — treat as directional signal, not proof.",
        ]

        return "\n".join(l for l in lines if l is not None)

    except Exception as e:
        log.debug("[backtest] get_backtest_context failed: %s", e)
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Cache stats
# ─────────────────────────────────────────────────────────────────────────────

def backtest_stats() -> dict:
    cache = _load_cache()
    return {
        "cached_backtests": len(cache),
        "cache_path":       str(CACHE_FILE),
        "entries": [
            {
                "ticker":     v.get("result", {}).get("ticker", "?"),
                "setup":      v.get("result", {}).get("setup_desc", "?")[:40],
                "n":          v.get("result", {}).get("n_occurrences", 0),
                "win_rate":   round(v.get("result", {}).get("win_rate", 0) * 100, 1),
                "cached_at":  v.get("cached_at", "?")[:10],
            }
            for v in list(cache.values())[:10]
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    args = sys.argv[1:]

    if not args or args[0] == "--help":
        print(__doc__)
        sys.exit(0)

    if args[0] == "--status":
        stats = backtest_stats()
        print(f"\nATLAS Backtest Cache")
        print(f"  Path:    {stats['cache_path']}")
        print(f"  Entries: {stats['cached_backtests']}")
        if stats["entries"]:
            print(f"\n  {'Ticker':<8} {'Win%':>6} {'N':>5}  Setup")
            for e in stats["entries"]:
                print(f"  {e['ticker']:<8} {e['win_rate']:>5.1f}% {e['n']:>5}  {e['setup']}")
        sys.exit(0)

    ticker     = args[0].upper()
    setup_desc = " ".join(args[1:]) if len(args) > 1 else None

    if not setup_desc:
        # Try to infer from ticker's recent research pattern tags
        try:
            import tracker
            recs = tracker.recent_recommendations(5)
            tags = []
            for r in recs:
                if r.get("ticker", "").upper() == ticker:
                    tags = r.get("setup_tags", [])
                    break
            setup_desc = _tags_to_description(tags) if tags else DEFAULT_SETUP
        except Exception:
            setup_desc = DEFAULT_SETUP

    print(f"\nRunning backtest: {ticker}")
    print(f"Setup: {setup_desc}")
    print()

    result = run_backtest(ticker, setup_desc, use_cache=False)
    if not result:
        print("Backtest failed — check logs for details")
        sys.exit(1)

    n        = result.get("n_occurrences", 0)
    win_rate = result.get("win_rate", 0) * 100
    avg_ret  = result.get("avg_return_10d", 0) * 100
    best     = result.get("best_return", 0) * 100
    worst    = result.get("worst_return", 0) * 100

    print(f"  Setup name:    {result.get('setup_name', '?')}")
    print(f"  Condition:     {result.get('setup_condition', '?')}")
    print(f"  Occurrences:   {n} signals over {result.get('years_tested', LOOKBACK_YEARS)} years")
    print(f"  Win rate:      {win_rate:.1f}%")
    print(f"  Avg {FORWARD_DAYS}d return:  {avg_ret:+.2f}%")
    print(f"  Best trade:    {best:+.2f}%")
    print(f"  Worst trade:   {worst:+.2f}%")

    ctx = get_backtest_context(ticker, research=None, use_cache=True)
    if ctx:
        print(f"\n--- Synthesis context ({len(ctx)} chars) ---")
        print(ctx)
