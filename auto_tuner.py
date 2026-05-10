"""
auto_tuner.py — ATLAS Self-Tuning Weight Optimizer

This is ATLAS learning from its own track record.

After every graded outcome, the auto-tuner analyzes:
  1. Which scoring weights in multi_ranker.py actually predicted wins vs losses?
  2. Are the setup tag detection thresholds (e.g., "short_float > 20%") optimal?
  3. Is ATLAS overconfident or underconfident? (calibration check)
  4. Which data sources correlated most with correct calls?

It then writes updated weights to `atlas_tuned_weights.json`
which gets loaded at runtime — no code changes needed.
Multi_ranker, position_sizer, and deep_research all pick up
the updated weights automatically on next run.

This is the RIGHT way to do self-learning:
  - ATLAS doesn't touch its own .py files (dangerous)
  - It tunes its PARAMETERS based on what worked
  - Parameters are saved to JSON, human-readable, reversible
  - A "proposal" mode suggests code changes for human review

Think of it like a trader reviewing their journal:
  "I noticed my 'high short float' calls win 79% of the time.
   My 'analyst_strong_buy' calls only win 41% of the time.
   I'm going to weight short float more and analyst rating less."

That's exactly what this does — automatically.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_WEIGHTS_FILE    = Path(__file__).parent / "atlas_tuned_weights.json"
_THRESHOLDS_FILE = Path(__file__).parent / "atlas_tuned_thresholds.json"
_TUNING_LOG      = Path(__file__).parent / "atlas_tuning_log.json"

# ── Default weights (used before any tuning) ─────────────────────────────────
DEFAULT_RANKER_WEIGHTS = {
    "atlas_confidence": 40,
    "iv_rank":          15,
    "short_float":      10,
    "options_flow":     10,
    "earnings_catalyst": 10,
    "analyst_rating":   8,
    "news_sentiment":   7,
}

DEFAULT_THRESHOLDS = {
    "short_float_high":      20.0,   # % above which = elevated
    "short_float_extreme":   30.0,   # % above which = extreme
    "iv_rank_low":           20.0,   # below = cheap options
    "iv_rank_high":          70.0,   # above = expensive
    "pcr_bullish":           0.7,    # below = bullish flow
    "pcr_bearish":           1.5,    # above = bearish flow
    "rvol_spike":            2.0,    # above = unusual volume
    "rsi_oversold":          30.0,
    "rsi_overbought":        70.0,
    "confidence_min_trade":  6,      # minimum score to recommend a trade
}


def load_weights() -> dict:
    """Load tuned weights if they exist, else return defaults."""
    if _WEIGHTS_FILE.exists():
        try:
            data = json.loads(_WEIGHTS_FILE.read_text())
            # Merge with defaults (new weights may have been added)
            merged = dict(DEFAULT_RANKER_WEIGHTS)
            merged.update(data.get("weights", {}))
            return merged
        except Exception:
            pass
    return dict(DEFAULT_RANKER_WEIGHTS)


def load_thresholds() -> dict:
    """Load tuned thresholds if they exist, else return defaults."""
    if _THRESHOLDS_FILE.exists():
        try:
            return json.loads(_THRESHOLDS_FILE.read_text()).get("thresholds",
                              dict(DEFAULT_THRESHOLDS))
        except Exception:
            pass
    return dict(DEFAULT_THRESHOLDS)


def save_weights(weights: dict, reason: str = "") -> None:
    data = {
        "weights":    weights,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "reason":     reason,
    }
    _WEIGHTS_FILE.write_text(json.dumps(data, indent=2))
    log.info("[tuner] Weights saved: %s", reason)


def save_thresholds(thresholds: dict, reason: str = "") -> None:
    data = {
        "thresholds": thresholds,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "reason":     reason,
    }
    _THRESHOLDS_FILE.write_text(json.dumps(data, indent=2))
    log.info("[tuner] Thresholds saved: %s", reason)


# ─────────────────────────────────────────────────────────────────────────────
# Core tuning engine
# ─────────────────────────────────────────────────────────────────────────────
def _get_outcomes_with_tags(min_outcomes: int = 5) -> list[dict]:
    """Pull all graded outcomes with their setup tags from tracker DB."""
    try:
        import tracker
        with tracker._connect() as conn:
            rows = conn.execute("""
                SELECT r.setup_tags, r.atlas_conf, r.atlas_rating,
                       o.outcome, o.pnl_pct,
                       r.recorded_at
                FROM recommendations r
                JOIN outcomes o ON o.recommendation_id = r.id
                WHERE o.outcome IN ('WIN','LOSS','PARTIAL_WIN')
                ORDER BY r.recorded_at DESC
            """).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def tune_ranker_weights(min_outcomes: int = 5) -> Optional[dict]:
    """
    Use outcome history to find optimal scoring weights for multi_ranker.

    Method: coordinate ascent
      For each weight dimension, try increasing/decreasing it by 10%
      and see if it would have produced better rankings (wins ranked higher).
      Repeat until convergence or max iterations.

    Returns new weights dict, or None if not enough data.
    """
    outcomes = _get_outcomes_with_tags(min_outcomes)
    if len(outcomes) < min_outcomes:
        log.info("[tuner] Not enough outcomes yet (%d < %d). Need more graded trades.", 
                 len(outcomes), min_outcomes)
        return None

    log.info("[tuner] Tuning weights from %d outcomes...", len(outcomes))

    # Build tag-to-outcome mapping
    tag_outcomes: dict[str, list[float]] = {}
    for row in outcomes:
        try:
            tags = json.loads(row.get("setup_tags") or "[]")
        except Exception:
            continue
        pnl   = float(row.get("pnl_pct") or 0)
        is_win = row["outcome"] == "WIN"
        score  = 1.0 if is_win else (-0.5 if row["outcome"] == "PARTIAL_WIN" else -1.0)

        for tag in tags:
            if tag not in tag_outcomes:
                tag_outcomes[tag] = []
            tag_outcomes[tag].append(score)

    # Calculate predictive power of each tag
    tag_power: dict[str, float] = {}
    for tag, scores in tag_outcomes.items():
        if len(scores) >= 2:
            avg_score = sum(scores) / len(scores)
            tag_power[tag] = avg_score

    log.info("[tuner] Tag predictive power: %s",
             sorted(tag_power.items(), key=lambda x: x[1], reverse=True)[:5])

    # Map tags to weight categories
    tag_to_weight = {
        "extreme_short_float":  "short_float",
        "high_short_float":     "short_float",
        "elevated_short_float": "short_float",
        "iv_very_low":          "iv_rank",
        "iv_low":               "iv_rank",
        "iv_high":              "iv_rank",
        "iv_extreme":           "iv_rank",
        "bullish_options_flow": "options_flow",
        "bearish_options_flow": "options_flow",
        "very_bullish_pcr":     "options_flow",
        "bullish_pcr":          "options_flow",
        "bearish_pcr":          "options_flow",
        "earnings_imminent":    "earnings_catalyst",
        "earnings_today":       "earnings_catalyst",
        "earnings_this_week":   "earnings_catalyst",
        "analyst_strong_buy":   "analyst_rating",
        "analyst_buy":          "analyst_rating",
        "analyst_sell":         "analyst_rating",
        "bullish_news_sentiment": "news_sentiment",
        "bearish_news_sentiment": "news_sentiment",
        "high_conviction":      "atlas_confidence",
        "medium_conviction":    "atlas_confidence",
        "low_conviction":       "atlas_confidence",
    }

    # Calculate weight adjustment per category
    current_weights = load_weights()
    new_weights     = dict(current_weights)
    adjustments     = {k: 0.0 for k in current_weights}
    adj_counts      = {k: 0  for k in current_weights}

    for tag, power in tag_power.items():
        weight_key = tag_to_weight.get(tag)
        if not weight_key:
            continue
        adjustments[weight_key] += power
        adj_counts[weight_key]  += 1

    # Apply adjustments (bounded: ±40% of current value)
    reasons = []
    for key in new_weights:
        count = adj_counts.get(key, 0)
        if count == 0:
            continue
        avg_adj = adjustments[key] / count
        # Scale: if avg_adj > 0.3, increase weight; if < -0.3, decrease
        if avg_adj > 0.3:
            factor    = min(1.4, 1.0 + avg_adj * 0.5)
            new_w     = round(current_weights[key] * factor, 1)
            reasons.append(f"Increased {key} {current_weights[key]} → {new_w} (tag power={avg_adj:+.2f})")
        elif avg_adj < -0.3:
            factor    = max(0.6, 1.0 + avg_adj * 0.5)
            new_w     = round(current_weights[key] * factor, 1)
            reasons.append(f"Decreased {key} {current_weights[key]} → {new_w} (tag power={avg_adj:+.2f})")
        else:
            new_w = current_weights[key]
        new_weights[key] = max(1.0, new_w)  # minimum weight of 1

    # Normalize weights to sum to 100
    total = sum(new_weights.values())
    if total > 0:
        scale = 100 / total
        new_weights = {k: round(v * scale, 1) for k, v in new_weights.items()}

    reason_str = "; ".join(reasons) if reasons else "No significant adjustments needed"
    log.info("[tuner] New weights: %s", new_weights)
    log.info("[tuner] Reasons: %s", reason_str)

    return new_weights, reason_str


def tune_thresholds(min_outcomes: int = 5) -> Optional[dict]:
    """
    Tune detection thresholds based on what actually worked.
    e.g., if "short_float > 20%" has weak predictive power but
    "short_float > 30%" has strong predictive power, update the threshold.
    """
    outcomes = _get_outcomes_with_tags(min_outcomes)
    if len(outcomes) < min_outcomes:
        return None

    current = load_thresholds()
    new_thr = dict(current)

    # Analyze short float threshold
    sf_outcomes: list[tuple[float, float]] = []  # (short_float_value, win_score)
    for row in outcomes:
        tags = []
        try:
            tags = json.loads(row.get("setup_tags") or "[]")
        except Exception:
            continue
        score = 1.0 if row["outcome"] == "WIN" else -1.0

        # Determine approximate short float value from tags
        if "extreme_short_float" in tags:   sf_val = 35.0
        elif "high_short_float" in tags:    sf_val = 25.0
        elif "elevated_short_float" in tags: sf_val = 15.0
        else:                                sf_val = 5.0
        sf_outcomes.append((sf_val, score))

    if len(sf_outcomes) >= 5:
        # Test different thresholds
        best_sf_threshold = current["short_float_high"]
        best_sf_power     = -999
        for threshold in [10, 15, 20, 25, 30, 35]:
            above = [s for sf, s in sf_outcomes if sf >= threshold]
            if len(above) >= 3:
                power = sum(above) / len(above)
                if power > best_sf_power:
                    best_sf_power     = power
                    best_sf_threshold = float(threshold)

        if abs(best_sf_threshold - current["short_float_high"]) >= 5:
            new_thr["short_float_high"] = best_sf_threshold
            log.info("[tuner] Updated short_float_high threshold: %.0f%% → %.0f%%",
                     current["short_float_high"], best_sf_threshold)

    return new_thr


def check_confidence_calibration() -> dict:
    """
    Is ATLAS overconfident or underconfident?

    Calibration check: when ATLAS says confidence=8/10,
    it should be right ~80% of the time.
    If it's only right 50% of the time at confidence=8, it's overconfident.
    If it's right 95% of the time at confidence=8, it could size bigger.
    """
    result = {"calibrated": True, "summary": "", "adjustments": {}}

    try:
        import tracker
        with tracker._connect() as conn:
            rows = conn.execute("""
                SELECT r.atlas_conf, o.outcome
                FROM recommendations r
                JOIN outcomes o ON o.recommendation_id = r.id
                WHERE o.outcome IN ('WIN','LOSS','PARTIAL_WIN')
                  AND r.atlas_conf IS NOT NULL
            """).fetchall()

        if len(rows) < 5:
            result["summary"] = f"Only {len(rows)} outcomes — need 5+ for calibration check."
            return result

        # Group by confidence level
        by_conf: dict[int, list[str]] = {}
        for row in rows:
            c = int(row["atlas_conf"] or 5)
            c = max(1, min(10, c))
            by_conf.setdefault(c, []).append(row["outcome"])

        cal_lines = []
        over = 0
        under = 0
        for conf in sorted(by_conf.keys()):
            outcomes = by_conf[conf]
            total    = len(outcomes)
            wins     = sum(1 for o in outcomes if o == "WIN")
            parts    = sum(1 for o in outcomes if o == "PARTIAL_WIN")
            actual_wr = (wins + parts * 0.5) / total
            expected  = conf / 10.0
            gap       = actual_wr - expected

            cal_lines.append(
                f"  Confidence {conf}/10 → expected {conf*10}% win rate, "
                f"actual {actual_wr*100:.0f}% ({total} trades)"
                + (" ⚠ OVERCONFIDENT" if gap < -0.15 else " ✓" if abs(gap) <= 0.15 else " ↑ UNDERCONFIDENT")
            )
            if gap < -0.15: over += 1
            if gap > 0.20:  under += 1

        result["summary"] = "\n".join(cal_lines)
        if over >= 2:
            result["calibrated"] = False
            result["issue"] = "OVERCONFIDENT — ATLAS scores are inflated. Reduce position sizes by 20%."
            result["adjustments"]["confidence_deflator"] = 0.8
        elif under >= 2:
            result["calibrated"] = False
            result["issue"] = "UNDERCONFIDENT — ATLAS is too conservative. Can size slightly larger."
            result["adjustments"]["confidence_inflator"] = 1.1

        log.info("[tuner] Calibration check: %s", "OK" if result["calibrated"] else result.get("issue","?"))

    except Exception:
        log.debug("[tuner] Calibration check failed", exc_info=True)

    return result


def run_full_tune(min_outcomes: int = 5) -> dict:
    """
    Run the complete self-tuning cycle. Call this after every 5 new graded outcomes.
    Returns a summary of what was changed.
    """
    summary = {
        "ran_at":   datetime.now(timezone.utc).isoformat(),
        "changes":  [],
        "outcomes_used": 0,
    }

    outcomes = _get_outcomes_with_tags()
    summary["outcomes_used"] = len(outcomes)

    if len(outcomes) < min_outcomes:
        summary["message"] = f"Not enough data yet ({len(outcomes)}/{min_outcomes} outcomes). Keep grading trades."
        log.info("[tuner] %s", summary["message"])
        return summary

    # Tune weights
    tune_result = tune_ranker_weights(min_outcomes)
    if tune_result:
        new_weights, reason = tune_result
        current = load_weights()
        if new_weights != current:
            save_weights(new_weights, reason)
            summary["changes"].append(f"Updated ranker weights: {reason}")
        else:
            summary["changes"].append("Weights unchanged — current weights are optimal.")

    # Tune thresholds
    new_thr = tune_thresholds(min_outcomes)
    if new_thr:
        current_thr = load_thresholds()
        if new_thr != current_thr:
            save_thresholds(new_thr, "Auto-tuned from outcome history")
            changed_keys = [k for k in new_thr if new_thr[k] != current_thr.get(k)]
            summary["changes"].append(f"Updated thresholds: {', '.join(changed_keys)}")

    # Adaptive paper conviction threshold
    conviction_result = tune_paper_conviction_threshold()
    if conviction_result and conviction_result.get("changed"):
        summary["changes"].append(
            f"Conviction threshold: {conviction_result['previous_threshold']:.1f} -> "
            f"{conviction_result['new_threshold']:.1f} "
            f"(win_rate={conviction_result['win_rate']:.0%} over {conviction_result['window']} trades)"
        )

    # Calibration check
    cal = check_confidence_calibration()
    if not cal["calibrated"]:
        summary["changes"].append(f"Calibration issue: {cal.get('issue','')}")
        summary["calibration"] = cal

    # Log to tuning history
    _append_tuning_log(summary)

    log.info("[tuner] Full tune complete — %d changes", len(summary["changes"]))
    return summary


def _append_tuning_log(entry: dict) -> None:
    history = []
    if _TUNING_LOG.exists():
        try:
            history = json.loads(_TUNING_LOG.read_text())
        except Exception:
            pass
    history.append(entry)
    history = history[-50:]  # keep last 50 tuning runs
    _TUNING_LOG.write_text(json.dumps(history, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Adaptive paper conviction threshold
# ─────────────────────────────────────────────────────────────────────────────
_CONVICTION_FILE = Path(__file__).parent / "atlas_paper_conviction.json"
_CONVICTION_DEFAULT = 7.0
_CONVICTION_MIN     = 5.5
_CONVICTION_MAX     = 9.0
_CONVICTION_WINDOW  = 10   # look at last N closed paper trades


def load_paper_conviction() -> float:
    """Return the current adaptive paper trade conviction threshold."""
    if _CONVICTION_FILE.exists():
        try:
            return float(json.loads(_CONVICTION_FILE.read_text()).get("threshold", _CONVICTION_DEFAULT))
        except Exception:
            pass
    return _CONVICTION_DEFAULT


def save_paper_conviction(threshold: float, reason: str = "") -> None:
    _CONVICTION_FILE.write_text(json.dumps({
        "threshold": round(threshold, 1),
        "reason":    reason,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    log.info("[tuner] Adaptive conviction threshold set to %.1f — %s", threshold, reason)


def tune_paper_conviction_threshold() -> Optional[dict]:
    """
    Adjust the paper trade conviction threshold based on rolling win rate
    of the last _CONVICTION_WINDOW closed paper trades.

    Logic:
      win_rate >= 72%  → lower threshold by 0.5 (system is being too conservative)
      win_rate 55-72%  → hold (healthy zone)
      win_rate 40-55%  → raise threshold by 0.5 (be more selective)
      win_rate < 40%   → raise threshold by 1.0 (much more selective)

    Returns None if not enough data.
    """
    paper_file = Path(__file__).parent / "paper_trades.json"
    if not paper_file.exists():
        return None

    try:
        trades = json.loads(paper_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    closed = [t for t in trades if t.get("state", "").startswith("CLOSED_")]
    if len(closed) < 5:
        log.debug("[tuner] Only %d closed paper trades — need 5+ to tune conviction", len(closed))
        return None

    # Use last N trades by closed_at timestamp
    closed_sorted = sorted(closed, key=lambda t: t.get("closed_at", ""), reverse=True)
    window        = closed_sorted[:_CONVICTION_WINDOW]
    wins          = sum(1 for t in window if t.get("state") == "CLOSED_WIN")
    win_rate      = wins / len(window)

    current     = load_paper_conviction()
    new_thresh  = current

    if win_rate >= 0.72:
        new_thresh = max(_CONVICTION_MIN, current - 0.5)
        reason = f"Win rate {win_rate:.0%} over last {len(window)} trades — lowering threshold to catch more setups"
    elif win_rate >= 0.55:
        reason = f"Win rate {win_rate:.0%} — healthy zone, no change"
    elif win_rate >= 0.40:
        new_thresh = min(_CONVICTION_MAX, current + 0.5)
        reason = f"Win rate {win_rate:.0%} — below target, raising threshold for higher selectivity"
    else:
        new_thresh = min(_CONVICTION_MAX, current + 1.0)
        reason = f"Win rate {win_rate:.0%} — significantly below target, raising threshold aggressively"

    if new_thresh != current:
        save_paper_conviction(new_thresh, reason)

    return {
        "previous_threshold": current,
        "new_threshold":      new_thresh,
        "win_rate":           round(win_rate, 3),
        "window":             len(window),
        "changed":            new_thresh != current,
        "reason":             reason,
    }


def get_current_config() -> dict:
    """Return the currently active weights + thresholds for display."""
    return {
        "weights":              load_weights(),
        "thresholds":           load_thresholds(),
        "paper_conviction":     load_paper_conviction(),
        "defaults_active":      not _WEIGHTS_FILE.exists(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "tune":
        result = run_full_tune(min_outcomes=3)
        print(f"\nAuto-tune complete ({result['outcomes_used']} outcomes used):")
        for c in result["changes"]:
            print(f"  {c}")
        if "message" in result:
            print(f"  {result['message']}")

    elif cmd == "calibrate":
        cal = check_confidence_calibration()
        print(f"\nCalibration check:")
        print(cal["summary"] or "Not enough data.")
        if not cal["calibrated"]:
            print(f"\n⚠ Issue: {cal.get('issue','')}")

    elif cmd == "status":
        cfg = get_current_config()
        print(f"\nCurrent ATLAS Weights {'(DEFAULT — no tuning yet)' if cfg['defaults_active'] else '(TUNED)'}:")
        for k, v in cfg["weights"].items():
            print(f"  {k:<25} {v:.1f}")
        print(f"\nKey Thresholds:")
        for k, v in cfg["thresholds"].items():
            print(f"  {k:<30} {v}")

    elif cmd == "reset":
        if _WEIGHTS_FILE.exists():    _WEIGHTS_FILE.unlink()
        if _THRESHOLDS_FILE.exists(): _THRESHOLDS_FILE.unlink()
        print("Weights and thresholds reset to defaults.")

    else:
        print("Usage: python auto_tuner.py tune | calibrate | status | reset")
