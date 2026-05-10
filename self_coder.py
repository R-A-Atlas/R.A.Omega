"""
self_coder.py — ATLAS Self-Improvement Engine

This is the closest thing to an AI editing its own code — safely.

The approach:
  1. ATLAS reviews all its LOSS and PARTIAL_WIN outcomes
  2. For each loss, it asks: "what data was available? what did we miss?"
  3. It identifies systematic blind spots (e.g., "we missed IV crush 3 times")
  4. It uses Gemini to generate a specific code patch that would fix the pattern
  5. The patch is saved to proposed_updates/ for HUMAN REVIEW
  6. The human reads it, says "yes" or "no", and applies it
  7. ATLAS learns which proposals got accepted → improves future proposals

Why we don't auto-apply:
  - Financial code that auto-modifies itself could have catastrophic bugs
  - Human oversight is a feature, not a limitation
  - The proposal quality improves over time as ATLAS tracks acceptance rates

The result is a genuine AI coding assistant for itself:
  ATLAS identifies "I keep losing on biotech earnings plays" and
  proposes a new setup_tag detection rule for "biotech_fda_within_7_days"
  or a refined IV crush warning in the synthesis prompt.
"""

from __future__ import annotations

import json
import logging
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

from gemini_limiter import wait_for_slot

_WORKSPACE    = Path(__file__).parent
_PROPOSALS_DIR = _WORKSPACE / "proposed_updates"
_LESSONS_FILE  = _WORKSPACE / "atlas_lessons_learned.json"

_PROPOSALS_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 1. LOSS PATTERN ANALYZER
# ─────────────────────────────────────────────────────────────────────────────
def analyze_losses(min_losses: int = 3) -> dict:
    """
    Analyze all LOSS outcomes and find systematic patterns.
    Returns a dict of patterns with counts and examples.

    Common patterns we look for:
      - IV crush: we recommended options before earnings, IV collapsed
      - Gap-and-crap: stock gapped up but we were still long
      - Wrong regime: we played longs in a bear market
      - Missed catalyst: we missed an upcoming FDA/earnings date
      - Data conflict ignored: cross-reference showed conflict but we ignored it
      - Overconfident on single source: data had LOW confidence tag but we rated high
    """
    patterns: dict[str, dict] = {}

    try:
        import tracker
        with tracker._connect() as conn:
            rows = conn.execute("""
                SELECT r.ticker, r.setup_tags, r.atlas_conf, r.atlas_rating,
                       r.synthesis_excerpt, r.recorded_at,
                       o.outcome, o.pnl_pct, o.notes
                FROM recommendations r
                JOIN outcomes o ON o.recommendation_id = r.id
                WHERE o.outcome IN ('LOSS', 'PARTIAL_WIN')
                ORDER BY r.recorded_at DESC
                LIMIT 50
            """).fetchall()

        if len(rows) < min_losses:
            log.info("[self_coder] Not enough losses yet (%d). Keep trading and grading.", len(rows))
            return {"loss_count": len(rows), "patterns": {}}

        for row in rows:
            try:
                tags = json.loads(row.get("setup_tags") or "[]")
            except Exception:
                tags = []

            notes  = (row.get("notes") or "").lower()
            synth  = (row.get("synthesis_excerpt") or "").lower()
            ticker = row.get("ticker","?")
            pnl    = float(row.get("pnl_pct") or 0)

            def _record(pattern_id: str, label: str, example: str) -> None:
                if pattern_id not in patterns:
                    patterns[pattern_id] = {"label": label, "count": 0, "examples": [], "tickers": []}
                patterns[pattern_id]["count"] += 1
                if len(patterns[pattern_id]["examples"]) < 3:
                    patterns[pattern_id]["examples"].append(example)
                if ticker not in patterns[pattern_id]["tickers"]:
                    patterns[pattern_id]["tickers"].append(ticker)

            # IV Crush detection
            if any(t in tags for t in ["iv_high","iv_extreme"]) and \
               any(t in tags for t in ["earnings_imminent","earnings_today","earnings_this_week"]):
                _record("iv_crush", "IV Crush on Earnings Options",
                        f"{ticker}: high IV + near earnings → options bought at peak IV. pnl={pnl:.1f}%")

            # High short float losses (squeeze didn't happen)
            if any(t in tags for t in ["high_short_float","extreme_short_float"]) and pnl < -10:
                _record("squeeze_no_trigger", "Short Squeeze Setup With No Catalyst",
                        f"{ticker}: high SF but no catalyst triggered squeeze. pnl={pnl:.1f}%")

            # Low confidence, big loss
            conf = int(row.get("atlas_conf") or 5)
            if conf <= 4 and pnl < -15:
                _record("low_conf_big_loss", "Low Confidence Trade With Large Loss",
                        f"{ticker}: conf={conf}/10 but traded anyway. pnl={pnl:.1f}%")

            # Overconfident
            if conf >= 8 and pnl < -10:
                _record("overconfident", "High Confidence Rating With Loss",
                        f"{ticker}: conf={conf}/10 but lost {pnl:.1f}%")

            # Negative news ignored
            if "bearish_news_sentiment" in tags and "LONG" in (row.get("atlas_rating") or ""):
                _record("bearish_news_ignored", "Bearish News Sentiment With Long Recommendation",
                        f"{ticker}: bearish news tags but still recommended long")

            # Analyst sell ignored
            if "analyst_sell" in tags and "LONG" in (row.get("atlas_rating") or ""):
                _record("analyst_sell_ignored", "Analyst Sell With Long Play",
                        f"{ticker}: analyst sell tag but recommended long")

        # Sort by count
        patterns = dict(sorted(patterns.items(), key=lambda x: x[1]["count"], reverse=True))
        log.info("[self_coder] Found %d loss patterns from %d losses", len(patterns), len(rows))

    except Exception:
        log.debug("[self_coder] Loss analysis failed", exc_info=True)

    return {"loss_count": len(rows) if "rows" in dir() else 0, "patterns": patterns}


# ─────────────────────────────────────────────────────────────────────────────
# 2. CODE IMPROVEMENT PROPOSAL GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

PATCH_TEMPLATES: dict[str, dict] = {
    "iv_crush": {
        "target_file": "deep_research.py",
        "title": "Add IV Crush Warning to Earnings Options Synthesis Prompt",
        "description": "ATLAS missed IV crush on options held through earnings. The synthesis prompt should explicitly warn about IV collapse risk when IV is high AND earnings are imminent.",
        "search_for": "historical win rates from the ATLAS pattern library",
        "insert_before": "The sector macro wind",
        "code": textwrap.dedent("""\
            - **IV CRUSH ALERT**: This ticker has BOTH high IV rank AND imminent earnings.
              If recommending options: (1) strongly prefer debit spreads over naked calls/puts
              to cap the IV crush loss. (2) Consider selling premium instead of buying it.
              (3) If buying options, enter AFTER earnings or use a strangle/straddle.
              This pattern has historically caused losses. Be explicit about IV crush risk.
        """),
    },

    "squeeze_no_trigger": {
        "target_file": "tracker.py",
        "title": "Add Catalyst_Required Tag for High-Short-Float Setups",
        "description": "High short float positions lost because there was no squeeze trigger/catalyst. Add a check: if short float is high but there's no news/catalyst tag, add a 'needs_catalyst' tag.",
        "search_for": "def detect_setup_tags",
        "code": textwrap.dedent("""\
            # Squeeze needs a catalyst — if no catalyst is present, flag it
            has_catalyst = any(t in tags for t in [
                "earnings_imminent", "earnings_today", "earnings_this_week",
                "bullish_news_sentiment", "bullish_options_flow", "very_bullish_pcr"
            ])
            is_squeeze_candidate = any(t in tags for t in [
                "high_short_float", "extreme_short_float"
            ])
            if is_squeeze_candidate and not has_catalyst:
                tags.append("squeeze_no_catalyst")  # adds to synthesis: needs a trigger!
        """),
    },

    "low_conf_big_loss": {
        "target_file": "deep_research.py",
        "title": "Enforce Minimum Confidence Gate in Position Sizer",
        "description": "Trades with confidence < 5 caused big losses. The position sizer should return zero size (no trade) when atlas_conf < configured minimum.",
        "search_for": "size_from_research",
        "code": textwrap.dedent("""\
            # Enforce minimum confidence gate
            thresholds = {}
            try:
                import auto_tuner
                thresholds = auto_tuner.load_thresholds()
            except Exception:
                pass
            min_conf = thresholds.get("confidence_min_trade", 6)
            atlas_conf = research.get("atlas_conf") or research.get("confidence_score") or 5
            if int(atlas_conf) < min_conf:
                return {"shares": 0, "contracts": 0,
                        "summary": f"BLOCKED: confidence {atlas_conf}/10 below minimum {min_conf}/10. No trade.",
                        "reason": "below_confidence_gate"}
        """),
    },

    "overconfident": {
        "target_file": "auto_tuner.py",
        "title": "Run Calibration Check After Every 5 Outcomes",
        "description": "ATLAS is overconfident on high-confidence ratings. Auto_tuner should auto-run calibration check and emit a warning if calibration drift is detected.",
        "is_config_change": True,
        "config_file": "atlas_tuned_thresholds.json",
        "config_change": {"confidence_deflator": 0.85},
        "code": "# Confidence deflator set to 0.85 in atlas_tuned_thresholds.json",
    },

    "bearish_news_ignored": {
        "target_file": "deep_research.py",
        "title": "Add Bearish News Contradiction Warning to Synthesis Prompt",
        "description": "Bearish news sentiment was present but we still went long. Add an explicit warning to the synthesis prompt when news sentiment contradicts the trade direction.",
        "search_for": "Use the sector macro wind",
        "code": textwrap.dedent("""\
            - If news sentiment is BEARISH but you are considering a LONG position:
              explicitly acknowledge this contradiction and reduce confidence by 1-2 points.
              Only recommend long if there is a very strong override catalyst.
        """),
    },
}


def generate_proposal(pattern_id: str, pattern_data: dict,
                      gemini_client=None) -> Optional[dict]:
    """
    Generate a code improvement proposal for a given loss pattern.
    Uses Gemini if available for dynamic proposals, falls back to templates.
    """
    template = PATCH_TEMPLATES.get(pattern_id)
    count    = pattern_data.get("count", 0)
    examples = pattern_data.get("examples", [])

    if template:
        proposal = {
            "id":            f"{pattern_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}",
            "pattern_id":    pattern_id,
            "count":         count,
            "label":         pattern_data.get("label", "?"),
            "title":         template["title"],
            "description":   template["description"],
            "target_file":   template.get("target_file","?"),
            "proposed_code": template.get("code",""),
            "is_config_change": template.get("is_config_change", False),
            "examples":      examples,
            "generated_at":  datetime.now(timezone.utc).isoformat(),
            "status":        "PENDING_REVIEW",
            "priority":      "HIGH" if count >= 3 else "MEDIUM",
        }
    elif gemini_client:
        # Dynamic Gemini-generated proposal
        prompt = f"""You are improving the ATLAS trading analysis system.

ATLAS has lost money on this pattern {count} times:
Pattern: {pattern_data.get("label","?")}
Examples:
{chr(10).join(f"  - {e}" for e in examples[:3])}

ATLAS's code is organized into these files:
- deep_research.py (main analysis + AI synthesis)
- tracker.py (setup tag detection, win-rate tracking)
- market_scanner.py (hyper-awareness: squeeze, gaps, regime)
- auto_tuner.py (weight optimization)
- position_sizer.py (position sizing with Kelly criterion)
- web_scraper.py (data gathering)

Propose ONE specific code change to fix this pattern. Be concrete:
1. Which file to modify
2. Exact code to add or change (Python)
3. Why this will prevent the loss pattern

Keep the code change under 20 lines. Focus on the most impactful single fix.
Return JSON with keys: title, target_file, description, proposed_code"""

        try:
            wait_for_slot("self_coder")
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            raw = response.text.strip()
            if raw.startswith("```json"):
                raw = raw[7:]
            if raw.endswith("```"):
                raw = raw[:-3]
            data = json.loads(raw.strip())

            proposal = {
                "id":            f"{pattern_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}",
                "pattern_id":    pattern_id,
                "count":         count,
                "label":         pattern_data.get("label","?"),
                "title":         data.get("title","AI-generated proposal"),
                "description":   data.get("description",""),
                "target_file":   data.get("target_file","?"),
                "proposed_code": data.get("proposed_code",""),
                "examples":      examples,
                "generated_at":  datetime.now(timezone.utc).isoformat(),
                "status":        "PENDING_REVIEW",
                "source":        "gemini_generated",
                "priority":      "HIGH" if count >= 3 else "MEDIUM",
            }
        except Exception:
            log.debug("[self_coder] Gemini proposal failed", exc_info=True)
            return None
    else:
        # No template, no Gemini — skip
        return None

    return proposal


def save_proposal(proposal: dict) -> Path:
    """Save proposal to proposed_updates/ directory."""
    filename = f"{proposal['id']}.json"
    path     = _PROPOSALS_DIR / filename
    path.write_text(json.dumps(proposal, indent=2))
    log.info("[self_coder] Saved proposal: %s", filename)
    return path


def list_proposals(status: str = None) -> list[dict]:
    """List all saved proposals, optionally filtered by status."""
    proposals = []
    for f in sorted(_PROPOSALS_DIR.glob("*.json")):
        try:
            p = json.loads(f.read_text())
            if status is None or p.get("status") == status:
                proposals.append(p)
        except Exception:
            continue
    return proposals


def accept_proposal(proposal_id: str) -> bool:
    """
    Mark a proposal as ACCEPTED and log it to lessons_learned.
    NOTE: Does NOT auto-apply the code. You apply it yourself.
    """
    for f in _PROPOSALS_DIR.glob(f"{proposal_id}*.json"):
        try:
            p = json.loads(f.read_text())
            p["status"]      = "ACCEPTED"
            p["accepted_at"] = datetime.now(timezone.utc).isoformat()
            f.write_text(json.dumps(p, indent=2))
            _log_lesson(p, accepted=True)
            log.info("[self_coder] Accepted proposal: %s", proposal_id)
            return True
        except Exception:
            pass
    return False


def reject_proposal(proposal_id: str, reason: str = "") -> bool:
    """Mark a proposal as REJECTED."""
    for f in _PROPOSALS_DIR.glob(f"{proposal_id}*.json"):
        try:
            p = json.loads(f.read_text())
            p["status"]      = "REJECTED"
            p["rejected_at"] = datetime.now(timezone.utc).isoformat()
            p["reject_reason"] = reason
            f.write_text(json.dumps(p, indent=2))
            _log_lesson(p, accepted=False)
            log.info("[self_coder] Rejected proposal: %s  reason: %s", proposal_id, reason)
            return True
        except Exception:
            pass
    return False


def _log_lesson(proposal: dict, accepted: bool) -> None:
    """Track which proposals were accepted/rejected so ATLAS improves future proposals."""
    lessons = []
    if _LESSONS_FILE.exists():
        try:
            lessons = json.loads(_LESSONS_FILE.read_text())
        except Exception:
            pass
    lessons.append({
        "pattern_id":  proposal.get("pattern_id"),
        "title":       proposal.get("title"),
        "accepted":    accepted,
        "reason":      proposal.get("reject_reason",""),
        "logged_at":   datetime.now(timezone.utc).isoformat(),
    })
    lessons = lessons[-100:]
    _LESSONS_FILE.write_text(json.dumps(lessons, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# 3. GENERATE LESSONS LEARNED HTML REPORT
# ─────────────────────────────────────────────────────────────────────────────
def render_lessons_html() -> str:
    """Generate a human-readable HTML report of what ATLAS has learned."""
    patterns   = analyze_losses(min_losses=1)
    proposals  = list_proposals()
    pending    = [p for p in proposals if p["status"] == "PENDING_REVIEW"]
    accepted   = [p for p in proposals if p["status"] == "ACCEPTED"]
    rejected   = [p for p in proposals if p["status"] == "REJECTED"]

    rows_html = ""
    for pid, pdata in patterns.get("patterns", {}).items():
        count    = pdata["count"]
        label    = pdata["label"]
        examples = "<br>".join(pdata.get("examples",[])[:2])
        color    = "#ff4444" if count >= 3 else "#ffaa00" if count >= 2 else "#aaa"
        rows_html += f"""
        <tr>
          <td style="color:{color};font-weight:bold">{count}x</td>
          <td>{label}</td>
          <td style="font-size:0.8em;color:#aaa">{examples}</td>
          <td>{'✅ Has proposal' if pid in PATCH_TEMPLATES else '⏳ Generating...'}</td>
        </tr>"""

    proposal_cards = ""
    for p in pending[:5]:
        proposal_cards += f"""
        <div class="proposal-card">
          <div class="p-header">
            <span class="priority-{p.get('priority','MEDIUM').lower()}">{p.get('priority','?')}</span>
            <b>{p.get('title','?')}</b>
            <span class="p-id">ID: {p.get('id','?')[:20]}...</span>
          </div>
          <div class="p-desc">{p.get('description','')}</div>
          <div class="p-file">File: <code>{p.get('target_file','?')}</code> | Pattern: {p.get('count',0)} occurrences</div>
          <pre class="p-code">{p.get('proposed_code','')}</pre>
          <div class="p-actions">
            <code>python self_coder.py accept {p.get('id','')[:20]}</code>
            &nbsp;&nbsp;|&nbsp;&nbsp;
            <code>python self_coder.py reject {p.get('id','')[:20]} "reason"</code>
          </div>
        </div>"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>ATLAS Self-Learning Report</title>
<style>
  body {{ background:#0a0e1a; color:#e0e6f0; font-family:'Segoe UI',sans-serif; padding:24px; }}
  h1 {{ color:#7ec8e3; border-bottom:1px solid #334; padding-bottom:8px; }}
  h2 {{ color:#a8d8ea; margin-top:32px; }}
  table {{ width:100%; border-collapse:collapse; margin:12px 0; }}
  th {{ background:#141c2e; color:#7ec8e3; padding:10px; text-align:left; }}
  td {{ padding:8px 10px; border-bottom:1px solid #1e2a3a; vertical-align:top; }}
  .proposal-card {{ background:#101828; border:1px solid #2a3a5e; border-radius:8px;
                    padding:16px; margin:12px 0; }}
  .p-header {{ display:flex; align-items:center; gap:12px; margin-bottom:8px; }}
  .p-desc {{ color:#aaa; margin:8px 0; font-size:0.9em; }}
  .p-file {{ color:#7ec8e3; font-size:0.85em; margin:4px 0; }}
  .p-code {{ background:#060d1a; padding:12px; border-radius:4px; font-size:0.8em;
             overflow-x:auto; border-left:3px solid #7ec8e3; white-space:pre-wrap; }}
  .p-actions {{ margin-top:10px; font-size:0.8em; color:#7ec8e3; }}
  .p-id {{ color:#555; font-size:0.8em; margin-left:auto; }}
  .priority-high {{ background:#ff4444; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.8em; }}
  .priority-medium {{ background:#ff8800; color:#fff; padding:2px 8px; border-radius:4px; font-size:0.8em; }}
  .stat-box {{ display:inline-block; background:#141c2e; border-radius:8px; padding:16px 24px;
               margin:8px; text-align:center; }}
  .stat-num {{ font-size:2em; font-weight:bold; color:#7ec8e3; display:block; }}
  .stat-label {{ color:#aaa; font-size:0.85em; }}
</style>
</head>
<body>
<h1>🧠 ATLAS Self-Learning Report</h1>
<p style="color:#aaa">Generated: {now} — ATLAS is analyzing its own mistakes and proposing fixes</p>

<div>
  <div class="stat-box">
    <span class="stat-num">{patterns.get('loss_count',0)}</span>
    <span class="stat-label">Losses Analyzed</span>
  </div>
  <div class="stat-box">
    <span class="stat-num">{len(patterns.get('patterns',{}))}</span>
    <span class="stat-label">Patterns Found</span>
  </div>
  <div class="stat-box">
    <span class="stat-num">{len(pending)}</span>
    <span class="stat-label">Pending Proposals</span>
  </div>
  <div class="stat-box">
    <span class="stat-num">{len(accepted)}</span>
    <span class="stat-label">Accepted & Fixed</span>
  </div>
</div>

<h2>Loss Pattern Analysis</h2>
<table>
  <tr><th>Frequency</th><th>Pattern</th><th>Examples</th><th>Fix Status</th></tr>
  {rows_html if rows_html else '<tr><td colspan="4" style="color:#555;text-align:center">No patterns detected yet — keep grading trades</td></tr>'}
</table>

<h2>Pending Code Improvement Proposals</h2>
<p style="color:#aaa;font-size:0.9em">
  ATLAS generated these fixes. Review, then run the accept/reject commands shown below each proposal.
  You apply the actual code change yourself — ATLAS will not auto-modify files.
</p>
{proposal_cards if proposal_cards else '<p style="color:#555">No pending proposals — run: python self_coder.py analyze</p>'}

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Master run — analyze losses + generate proposals
# ─────────────────────────────────────────────────────────────────────────────
def run_self_analysis(gemini_client=None, min_losses: int = 2) -> dict:
    """
    Full self-analysis cycle:
    1. Analyze loss patterns
    2. Generate proposals for top patterns
    3. Save proposals to proposed_updates/
    4. Return summary
    """
    result = {
        "ran_at":    datetime.now(timezone.utc).isoformat(),
        "patterns":  {},
        "proposals_generated": [],
    }

    analysis = analyze_losses(min_losses=min_losses)
    result["patterns"]   = analysis.get("patterns", {})
    result["loss_count"] = analysis.get("loss_count", 0)

    top_patterns = list(result["patterns"].items())[:5]

    for pattern_id, pattern_data in top_patterns:
        if pattern_data["count"] < min_losses:
            continue
        proposal = generate_proposal(pattern_id, pattern_data, gemini_client)
        if proposal:
            path = save_proposal(proposal)
            result["proposals_generated"].append({
                "id":       proposal["id"],
                "title":    proposal["title"],
                "file":     str(path.name),
                "priority": proposal.get("priority","?"),
            })

    # Write HTML report
    html = render_lessons_html()
    report_path = _WORKSPACE / "reports" / "ATLAS_SELF_LEARNING.html"
    report_path.write_text(html, encoding="utf-8")
    result["report_path"] = str(report_path)

    log.info("[self_coder] Analysis complete: %d patterns, %d proposals",
             len(result["patterns"]), len(result["proposals_generated"]))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    cmd = sys.argv[1] if len(sys.argv) > 1 else "analyze"

    if cmd == "analyze":
        result = run_self_analysis(min_losses=1)
        print(f"\nSelf-Analysis Complete:")
        print(f"  Losses analyzed: {result['loss_count']}")
        print(f"  Patterns found:  {len(result['patterns'])}")
        print(f"  Proposals saved: {len(result['proposals_generated'])}")
        for p in result["proposals_generated"]:
            print(f"    [{p['priority']}] {p['title']}")
        if result.get("report_path"):
            print(f"\nFull report: {result['report_path']}")

    elif cmd == "list":
        status = sys.argv[2] if len(sys.argv) > 2 else None
        proposals = list_proposals(status)
        print(f"\nProposals ({len(proposals)} total):")
        for p in proposals:
            print(f"  [{p['status']}] {p['id'][:24]}  {p['title'][:60]}")

    elif cmd == "accept" and len(sys.argv) > 2:
        pid = sys.argv[2]
        if accept_proposal(pid):
            print(f"Proposal {pid} marked as ACCEPTED. Apply the code change manually.")
        else:
            print(f"Proposal {pid} not found.")

    elif cmd == "reject" and len(sys.argv) > 2:
        pid    = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) > 3 else ""
        if reject_proposal(pid, reason):
            print(f"Proposal {pid} rejected.")
        else:
            print(f"Proposal {pid} not found.")

    elif cmd == "patterns":
        analysis = analyze_losses(min_losses=1)
        print(f"\nLoss Patterns ({analysis['loss_count']} losses):")
        for pid, pdata in analysis["patterns"].items():
            print(f"  {pdata['count']}x  {pdata['label']}")
            for ex in pdata.get("examples",[])[:2]:
                print(f"       {ex}")

    else:
        print("Usage: python self_coder.py analyze | list [status] | accept <id> | reject <id> [reason] | patterns")
