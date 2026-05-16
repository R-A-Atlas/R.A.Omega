"""
health_scorer.py — Architecture health scorer (Option C).

Scores the codebase across 5 axes after chain mapping and bug fixes:
  1. Chain Integrity    — intent -> output_mode -> renderer -> skill -> contract
  2. Route Coverage     — API routes with test coverage
  3. Output Mode Depth  — each output mode has resolver + renderer + skill + contract
  4. Worker Completeness — omega_agents workers have info files + implementation stub
  5. Connection Wiring  — connections active or configured (not just planned)

Each axis scores 0-100. Overall = weighted average.
Ratings: EXCELLENT (90-100) | GOOD (75-89) | FAIR (50-74) | POOR (<50)

No external APIs. No LLM calls. No writes to source files.
Output written to atlas_vault/03-Outputs/health_score.md by default.

CLI:
  python health_scorer.py
  python health_scorer.py --json
  python health_scorer.py --output /path/to/report.md
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_ROOT))

# ── Axis weights (must sum to 1.0) ────────────────────────────────────────────
_WEIGHTS = {
    "chain_integrity":    0.30,
    "route_coverage":     0.25,
    "output_mode_depth":  0.20,
    "worker_completeness":0.15,
    "connection_wiring":  0.10,
}

_RATING = [
    (90, "EXCELLENT"),
    (75, "GOOD"),
    (50, "FAIR"),
    (0,  "POOR"),
]


def _rate(score: float) -> str:
    for threshold, label in _RATING:
        if score >= threshold:
            return label
    return "POOR"


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class AxisResult:
    name: str
    score: float              # 0-100
    weight: float
    rating: str
    passed: int
    total: int
    callouts: list[str] = field(default_factory=list)   # what's dragging score down

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class HealthResult:
    axes: list[AxisResult] = field(default_factory=list)
    report: str = ""

    @property
    def overall(self) -> float:
        return sum(a.weighted_score for a in self.axes)

    @property
    def overall_rating(self) -> str:
        return _rate(self.overall)

    def summary(self) -> str:
        return (
            f"{self.overall_rating}: {self.overall:.1f}/100 overall  |  "
            + "  ".join(f"{a.name}={a.score:.0f}" for a in self.axes)
        )


# ── Axis 1: Chain Integrity ───────────────────────────────────────────────────

def _score_chain_integrity() -> AxisResult:
    callouts: list[str] = []
    passed = total = 0

    try:
        sys.path.insert(0, str(_ROOT))
        from omega_os.skills.improve_system.tools.chain_mapper import (
            build_chain_map, _OMEGA_AGENT_INTENTS, _CHAT_INTENTS,
        )
        chains = build_chain_map()
    except Exception as exc:
        return AxisResult("chain_integrity", 0, _WEIGHTS["chain_integrity"],
                          "POOR", 0, 1, [f"Could not load chain_mapper: {exc}"])

    for c in chains:
        if c.via_omega or c.intent in _CHAT_INTENTS:
            continue   # OmegaAgent intents are a different path, not scored here
        total += 1
        if not c.broken_at:
            passed += 1
        else:
            callouts.append(
                f"{c.intent} -> broken at '{c.broken_at}' "
                f"(mode={c.output_mode}, renderer={c.renderer}, "
                f"skill={c.skill or 'none'}, contract={'yes' if c.has_contract else 'no'})"
            )
        if not c.has_tests:
            callouts.append(f"{c.intent} -> no test coverage found")

    score = (passed / total * 100) if total else 100.0
    return AxisResult("chain_integrity", round(score, 1), _WEIGHTS["chain_integrity"],
                      _rate(score), passed, total, callouts)


# ── Axis 2: Route Test Coverage ───────────────────────────────────────────────

def _score_route_coverage() -> AxisResult:
    callouts: list[str] = []
    api_path = _ROOT / "api_server.py"
    if not api_path.exists():
        return AxisResult("route_coverage", 0, _WEIGHTS["route_coverage"],
                          "POOR", 0, 1, ["api_server.py not found"])

    source = api_path.read_text(encoding="utf-8", errors="replace")
    route_re = re.compile(r'@app\.(?:get|post|put|patch|delete)\("([^"]+)"')
    routes = sorted(set(route_re.findall(source)))

    tests_dir = _ROOT / "tests"
    test_content = ""
    if tests_dir.is_dir():
        for tf in tests_dir.glob("*.py"):
            try:
                test_content += tf.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    passed = total = 0
    for route in routes:
        total += 1
        if "{" in route:
            base = route.split("{")[0].rstrip("/")
            covered = base and base in test_content
        else:
            covered = route in test_content
        if covered:
            passed += 1
        else:
            callouts.append(f"No test coverage: {route}")

    score = (passed / total * 100) if total else 100.0
    return AxisResult("route_coverage", round(score, 1), _WEIGHTS["route_coverage"],
                      _rate(score), passed, total, callouts)


# ── Axis 3: Output Mode Depth ─────────────────────────────────────────────────

def _score_output_mode_depth() -> AxisResult:
    callouts: list[str] = []
    passed = total = 0

    try:
        from output_modes import (
            OUTPUT_CHAT, OUTPUT_GENERAL_CHAT, OUTPUT_FINANCE_ANSWER,
            OUTPUT_COMPANY_REPORT, OUTPUT_DOCUMENT, OUTPUT_HTML_ARTIFACT,
            OUTPUT_MARKET_SNAPSHOT, OUTPUT_TRADE_PLAN,
            resolve_output_mode,
        )
        from output_contracts import OUTPUT_CONTRACTS
        from omega_pipeline import select_renderer_type
        from omega_skill_registry import get_skill_for_output_mode
    except Exception as exc:
        return AxisResult("output_mode_depth", 0, _WEIGHTS["output_mode_depth"],
                          "POOR", 0, 1, [f"Import failed: {exc}"])

    all_modes = [
        OUTPUT_CHAT, OUTPUT_GENERAL_CHAT, OUTPUT_FINANCE_ANSWER,
        OUTPUT_COMPANY_REPORT, OUTPUT_DOCUMENT, OUTPUT_HTML_ARTIFACT,
        OUTPUT_MARKET_SNAPSHOT, OUTPUT_TRADE_PLAN,
    ]

    for mode in all_modes:
        total += 1
        issues: list[str] = []

        renderer = select_renderer_type(mode, "")
        if not renderer or renderer == "unknown":
            issues.append("no renderer")

        skill = get_skill_for_output_mode(mode)
        if not skill:
            issues.append("no skill")

        if mode not in OUTPUT_CONTRACTS:
            issues.append("no contract")

        if issues:
            callouts.append(f"{mode}: {', '.join(issues)}")
        else:
            passed += 1

    score = (passed / total * 100) if total else 100.0
    return AxisResult("output_mode_depth", round(score, 1), _WEIGHTS["output_mode_depth"],
                      _rate(score), passed, total, callouts)


# ── Axis 4: Worker Completeness ───────────────────────────────────────────────

_REQUIRED_INFO_FILES = {"instructions.md", "memory.md", "past_errors.md", "plan.md", "safety_rules.md"}

def _score_worker_completeness() -> AxisResult:
    callouts: list[str] = []
    passed = total = 0

    agents_dir = _ROOT / "omega_agents"
    if not agents_dir.is_dir():
        return AxisResult("worker_completeness", 0, _WEIGHTS["worker_completeness"],
                          "POOR", 0, 1, ["omega_agents/ directory not found"])

    for worker_dir in sorted(agents_dir.iterdir()):
        if not worker_dir.is_dir() or worker_dir.name.startswith("."):
            continue
        total += 1
        issues: list[str] = []

        info_dir = worker_dir / "information"
        if info_dir.is_dir():
            present = {f.name for f in info_dir.glob("*.md")}
            missing = _REQUIRED_INFO_FILES - present
            if missing:
                issues.append(f"missing info files: {sorted(missing)}")
        else:
            issues.append("no information/ directory")

        impl_dir = worker_dir / "implementation"
        stubs = list(impl_dir.glob("run_*.py")) if impl_dir.is_dir() else []
        if not stubs:
            issues.append("no implementation/run_*.py stub")

        if issues:
            callouts.append(f"{worker_dir.name}: {'; '.join(issues)}")
        else:
            passed += 1

    score = (passed / total * 100) if total else 100.0
    return AxisResult("worker_completeness", round(score, 1), _WEIGHTS["worker_completeness"],
                      _rate(score), passed, total, callouts)


# ── Axis 5: Connection Wiring ─────────────────────────────────────────────────

_CRITICAL_CONNECTIONS = {"gemini", "supabase"}   # must be active for core system to work

def _score_connection_wiring() -> AxisResult:
    callouts: list[str] = []
    passed = total = 0

    try:
        from omega_connections import get_registry, STATUS_ACTIVE, STATUS_CONFIGURED
    except Exception as exc:
        return AxisResult("connection_wiring", 0, _WEIGHTS["connection_wiring"],
                          "POOR", 0, 1, [f"Could not load omega_connections: {exc}"])

    registry = get_registry()
    for conn in registry:
        total += 1
        if conn.status in (STATUS_ACTIVE, STATUS_CONFIGURED):
            passed += 1
            if conn.slug in _CRITICAL_CONNECTIONS and conn.status != STATUS_ACTIVE:
                callouts.append(f"{conn.slug}: critical connection is configured but not active")
        else:
            if conn.slug in _CRITICAL_CONNECTIONS:
                callouts.append(f"{conn.slug}: CRITICAL — not active (status={conn.status})")
            else:
                callouts.append(f"{conn.slug}: planned only — not yet wired")

    score = (passed / total * 100) if total else 0.0
    return AxisResult("connection_wiring", round(score, 1), _WEIGHTS["connection_wiring"],
                      _rate(score), passed, total, callouts)


# ── Report builder ────────────────────────────────────────────────────────────

def _build_report(result: HealthResult) -> str:
    bar_width = 30

    def bar(score: float) -> str:
        filled = int(score / 100 * bar_width)
        return "[" + "#" * filled + "-" * (bar_width - filled) + "]"

    lines = [
        "# Architecture Health Score",
        "",
        f"**Overall: {result.overall:.1f}/100 — {result.overall_rating}**",
        "",
        "## Axis Scores",
        "",
        f"{'Axis':<22} {'Score':>6}  {'Rating':<12} {'Bar'}",
        "-" * 65,
    ]

    for a in result.axes:
        lines.append(
            f"{a.name:<22} {a.score:>5.1f}%  {a.rating:<12} {bar(a.score)}  "
            f"({a.passed}/{a.total})"
        )

    lines += ["", "---", ""]

    for a in result.axes:
        rating_tag = f"[{a.rating}]"
        lines += [f"## {rating_tag} {a.name.replace('_', ' ').title()} — {a.score:.0f}/100", ""]

        if not a.callouts:
            lines.append("- All checks passed.")
        else:
            for c in a.callouts:
                lines.append(f"- {c}")
        lines.append("")

    lines += [
        "---",
        "",
        f"**Weighted breakdown:** "
        + ", ".join(
            f"{a.name}={a.score:.0f}x{int(a.weight*100)}%={a.weighted_score:.1f}"
            for a in result.axes
        ),
        f"**Overall: {result.overall:.1f}/100 — {result.overall_rating}**",
    ]

    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def score() -> HealthResult:
    """
    Run all 5 health axes and return a HealthResult.

    Returns:
        HealthResult with .axes, .overall, .overall_rating, .summary(), .report.
    """
    axes = [
        _score_chain_integrity(),
        _score_route_coverage(),
        _score_output_mode_depth(),
        _score_worker_completeness(),
        _score_connection_wiring(),
    ]
    result = HealthResult(axes=axes)
    result.report = _build_report(result)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    as_json = "--json" in args
    out_arg = None
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            out_arg = Path(args[idx + 1])

    result = score()

    if as_json:
        print(json.dumps({
            "overall":        round(result.overall, 1),
            "overall_rating": result.overall_rating,
            "axes": [
                {
                    "name":    a.name,
                    "score":   a.score,
                    "weight":  a.weight,
                    "rating":  a.rating,
                    "passed":  a.passed,
                    "total":   a.total,
                    "callouts": a.callouts,
                }
                for a in result.axes
            ],
        }, indent=2))
    else:
        print(result.report)

    out_path = out_arg or (_ROOT / "atlas_vault" / "03-Outputs" / "health_score.md")
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.report, encoding="utf-8")
        if not as_json:
            print(f"\nReport written to: {out_path}")
    except Exception as exc:
        print(f"Warning: could not write report -- {exc}", file=sys.stderr)

    sys.exit(0 if result.overall >= 75 else 1)
