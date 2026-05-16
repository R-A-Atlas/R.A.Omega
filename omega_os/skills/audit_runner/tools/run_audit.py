"""
run_audit.py — R.A. Omega master audit orchestrator.

Runs both the competitive benchmark (ai_benchmarker) and product readiness
audit (product_readiness_audit) in sequence, then produces a single master
report with an overall score, letter grade, and prioritized fix list.

Saves dated report to atlas_vault/03-Outputs/omega_audit_YYYY-MM-DD.md
and prints a summary to stdout.

Overall score formula:
  60% product_readiness_pct  (how ready is the product)
  40% benchmark_score_normalized (how we compare vs competitors)

Verdict:
  90-100  PRODUCTION READY — ship it
  75-89   BETA READY — invite beta users
  60-74   ALPHA — internal testing only
  < 60    BUILDING — keep shipping

Usage:
    python omega_os/skills/audit_runner/tools/run_audit.py
    python omega_os/skills/audit_runner/tools/run_audit.py --json
    python omega_os/skills/audit_runner/tools/run_audit.py --no-save
    python omega_os/skills/audit_runner/tools/run_audit.py --quick  (skip benchmark)
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

BENCHMARK_PATH  = ROOT / "omega_os" / "skills" / "ai_benchmarker"        / "tools"
READINESS_PATH  = ROOT / "omega_os" / "skills" / "product_readiness_audit" / "tools"
VAULT_OUT       = ROOT / "atlas_vault" / "03-Outputs"

sys.path.insert(0, str(BENCHMARK_PATH))
sys.path.insert(0, str(READINESS_PATH))


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class MasterAuditReport:
    timestamp:          str
    readiness_score:    float    # 0–100
    readiness_grade:    str
    readiness_verdict:  str
    benchmark_score:    float    # 0–100 (our weighted score vs competitors)
    benchmark_grade:    str
    benchmark_rank:     int
    overall_score:      float    # weighted blend
    overall_grade:      str
    overall_verdict:    str
    top_advantages:     list[str]
    top_gaps:           list[str]
    priority_fixes:     list[tuple[str, str]]  # (category, fix)
    competitor_scores:  dict[str, float]
    category_scores:    dict[str, float]       # category → pct
    dimension_scores:   dict[str, int]         # dimension → omega score

    def to_dict(self) -> dict:
        return {
            "timestamp":         self.timestamp,
            "overall_score":     round(self.overall_score, 1),
            "overall_grade":     self.overall_grade,
            "overall_verdict":   self.overall_verdict,
            "readiness_score":   round(self.readiness_score, 1),
            "readiness_grade":   self.readiness_grade,
            "readiness_verdict": self.readiness_verdict,
            "benchmark_score":   round(self.benchmark_score, 1),
            "benchmark_grade":   self.benchmark_grade,
            "benchmark_rank":    self.benchmark_rank,
            "top_advantages":    self.top_advantages,
            "top_gaps":          self.top_gaps,
            "competitor_scores": {k: round(v, 1) for k, v in self.competitor_scores.items()},
            "category_scores":   {k: round(v, 1) for k, v in self.category_scores.items()},
            "priority_fixes":    [{"category": c, "fix": f} for c, f in self.priority_fixes[:15]],
        }


def _grade(score: float) -> str:
    if score >= 90: return "A"
    if score >= 82: return "A-"
    if score >= 75: return "B+"
    if score >= 65: return "B"
    if score >= 62: return "B-"
    if score >= 55: return "C+"
    if score >= 48: return "C"
    return "D"


def _verdict(score: float) -> str:
    if score >= 90: return "PRODUCTION READY — ship it"
    if score >= 75: return "BETA READY — invite beta users"
    if score >= 60: return "ALPHA — internal testing only"
    return "BUILDING — keep shipping"


# ── Runner ────────────────────────────────────────────────────────────────────

def run_audit(quick: bool = False, quiet: bool = False) -> MasterAuditReport:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Product readiness (always run)
    if not quiet:
        print("  Running product readiness audit...", flush=True)
    import readiness_check
    readiness = readiness_check.run_checks()

    # Competitive benchmark
    benchmark_score  = 0.0
    benchmark_grade  = "N/A"
    benchmark_rank   = 0
    top_advantages: list[str] = []
    top_gaps:       list[str] = []
    comp_scores:    dict[str, float] = {}
    dim_scores:     dict[str, int]   = {}

    if not quick:
        if not quiet:
            print("  Running competitive benchmark...", flush=True)
        import benchmark
        bench = benchmark.run_benchmark()
        benchmark_score = bench.omega_total
        benchmark_grade = bench.grade()
        benchmark_rank  = bench.omega_rank
        top_advantages  = bench.top_advantages
        top_gaps        = bench.top_gaps
        comp_scores     = bench.competitor_totals
        dim_scores      = {d.slug: d.omega_score for d in bench.dimensions}

    # Overall score: 60% readiness, 40% benchmark
    if quick:
        overall = readiness.pct
    else:
        overall = readiness.pct * 0.60 + benchmark_score * 0.40

    # Priority fixes from readiness
    priority_fixes = readiness.all_fixes()[:15]

    # Category scores as pct
    cat_scores = {cat.slug: round(cat.pct, 1) for cat in readiness.categories}

    return MasterAuditReport(
        timestamp         = ts,
        readiness_score   = round(readiness.pct, 1),
        readiness_grade   = readiness.grade(),
        readiness_verdict = readiness.verdict(),
        benchmark_score   = round(benchmark_score, 1),
        benchmark_grade   = benchmark_grade,
        benchmark_rank    = benchmark_rank,
        overall_score     = round(overall, 1),
        overall_grade     = _grade(overall),
        overall_verdict   = _verdict(overall),
        top_advantages    = top_advantages,
        top_gaps          = top_gaps,
        priority_fixes    = priority_fixes,
        competitor_scores = comp_scores,
        category_scores   = cat_scores,
        dimension_scores  = dim_scores,
    )


# ── Reporting ─────────────────────────────────────────────────────────────────

def _bar(score: float, width: int = 20) -> str:
    filled = int(score / 100 * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def print_master_report(r: MasterAuditReport) -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sep  = "=" * 72
    sep2 = "-" * 72

    print(sep)
    print("  R.A. OMEGA — MASTER AUDIT REPORT")
    print(f"  {r.timestamp}")
    print(sep)

    # Overall score banner
    print(f"\n  OVERALL SCORE:  {r.overall_score:.1f}/100  {_bar(r.overall_score)}  Grade {r.overall_grade}")
    print(f"  VERDICT:        {r.overall_verdict}")
    print()

    # Two-column breakdown
    print(f"  {'PRODUCT READINESS':<36}  {'VS COMPETITORS'}")
    print(f"  {sep2[:36]}  {sep2[:30]}")
    print(f"  Score:  {r.readiness_score:.1f}/100  {_bar(r.readiness_score, 14)}  {r.readiness_grade}"
          f"    Score: {r.benchmark_score:.1f}/100  Rank #{r.benchmark_rank}/5")
    print(f"  Verdict: {r.readiness_verdict:<27}  Grade: {r.benchmark_grade}")

    # Category breakdown
    print(f"\n  READINESS BY CATEGORY:")
    cat_order = ["auth", "ai", "billing", "ux", "data", "infra", "testing", "memory"]
    name_map  = {
        "auth": "Auth & Security", "ai": "Core AI Quality", "billing": "Billing",
        "ux": "UI/UX", "data": "Data Layer", "infra": "Infrastructure",
        "testing": "Test Coverage", "memory": "Memory & Personalization",
    }
    for slug in cat_order:
        pct  = r.category_scores.get(slug, 0)
        name = name_map.get(slug, slug)
        bar  = _bar(pct, 12)
        status = "OK" if pct >= 75 else "WARN" if pct >= 50 else "FAIL"
        print(f"    [{status:>4}]  {name:<28} {pct:>5.1f}%  {bar}")

    # Competitor comparison
    if r.competitor_scores:
        print(f"\n  COMPETITOR COMPARISON:")
        all_scores = {"R.A. Omega": r.benchmark_score, **r.competitor_scores}
        for name, score in sorted(all_scores.items(), key=lambda x: -x[1]):
            marker = "  <-- YOU" if name == "R.A. Omega" else ""
            print(f"    {name:<22} {score:>5.1f}/100  {_bar(score, 14)}{marker}")

    # Advantages and gaps
    if r.top_advantages:
        print(f"\n  OUR STRUCTURAL ADVANTAGES:")
        for adv in r.top_advantages:
            print(f"    + {adv}")

    if r.top_gaps:
        print(f"\n  GAPS TO CLOSE:")
        for gap in r.top_gaps:
            print(f"    - {gap}")

    # Priority fix list
    if r.priority_fixes:
        print(f"\n  PRIORITY FIX LIST (top {min(10, len(r.priority_fixes))}):")
        for i, (cat, fix) in enumerate(r.priority_fixes[:10], 1):
            print(f"    {i:>2}. [{cat}] {fix[:60]}")

    print(f"\n{sep}")
    print(f"  OVERALL: {r.overall_score:.1f}/100 (Grade {r.overall_grade}) — {r.overall_verdict}")
    print(f"  Report saved to atlas_vault/03-Outputs/")
    print(sep)


def save_report(r: MasterAuditReport) -> Path:
    """Save the master report as a dated Markdown file."""
    VAULT_OUT.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = VAULT_OUT / f"omega_audit_{date_str}.md"

    lines = [
        f"# R.A. Omega Audit Report — {r.timestamp}",
        f"",
        f"## Overall Score",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Overall Score | **{r.overall_score:.1f}/100** (Grade {r.overall_grade}) |",
        f"| Verdict | **{r.overall_verdict}** |",
        f"| Product Readiness | {r.readiness_score:.1f}/100 ({r.readiness_grade}) — {r.readiness_verdict} |",
        f"| Competitive Score | {r.benchmark_score:.1f}/100 (Grade {r.benchmark_grade}, Rank #{r.benchmark_rank}/5) |",
        f"",
        f"## Readiness by Category",
        f"",
        f"| Category | Score | Status |",
        f"|---|---|---|",
    ]
    cat_order = ["auth", "ai", "billing", "ux", "data", "infra", "testing", "memory"]
    name_map  = {
        "auth": "Auth & Security", "ai": "Core AI Quality", "billing": "Billing",
        "ux": "UI/UX", "data": "Data Layer", "infra": "Infrastructure",
        "testing": "Test Coverage", "memory": "Memory & Personalization",
    }
    for slug in cat_order:
        pct  = r.category_scores.get(slug, 0)
        name = name_map.get(slug, slug)
        status = "EXCELLENT" if pct >= 90 else "GOOD" if pct >= 70 else "FAIR" if pct >= 50 else "NEEDS WORK"
        lines.append(f"| {name} | {pct:.1f}% | {status} |")

    if r.competitor_scores:
        lines += [
            f"",
            f"## Competitive Position",
            f"",
            f"| Product | Score |",
            f"|---|---|",
        ]
        all_scores = {"**R.A. Omega**": r.benchmark_score, **r.competitor_scores}
        for name, score in sorted(all_scores.items(), key=lambda x: -x[1]):
            lines.append(f"| {name} | {score:.1f}/100 |")

    if r.top_advantages:
        lines += ["", "## Our Structural Advantages", ""]
        for adv in r.top_advantages:
            lines.append(f"- {adv}")

    if r.top_gaps:
        lines += ["", "## Gaps to Close", ""]
        for gap in r.top_gaps:
            lines.append(f"- {gap}")

    if r.priority_fixes:
        lines += ["", "## Priority Fix List", ""]
        for i, (cat, fix) in enumerate(r.priority_fixes[:15], 1):
            lines.append(f"{i}. **[{cat}]** {fix}")

    if r.dimension_scores:
        lines += ["", "## Benchmark Dimension Scores", "", "| Dimension | R.A. Omega | (out of 10) |", "|---|---|---|"]
        for slug, score in r.dimension_scores.items():
            lines.append(f"| {slug.replace('_', ' ').title()} | {score} | /10 |")

    lines += ["", "---", f"*Generated by audit_runner — {r.timestamp}*"]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="R.A. Omega master audit runner")
    parser.add_argument("--json",    action="store_true", help="Output JSON")
    parser.add_argument("--no-save", action="store_true", help="Do not save to vault")
    parser.add_argument("--quick",   action="store_true", help="Skip competitive benchmark (faster)")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not args.json:
        sep = "=" * 72
        print(sep)
        print("  R.A. OMEGA — MASTER AUDIT RUNNER")
        print(sep)

    report = run_audit(quick=args.quick, quiet=args.json)

    if not args.no_save:
        try:
            saved = save_report(report)
            if not args.json:
                print(f"  Saved: {saved.relative_to(ROOT)}")
        except Exception as e:
            if not args.json:
                print(f"  [~~] Could not save report: {e}")

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print()
        print_master_report(report)

    sys.exit(0)


if __name__ == "__main__":
    main()
