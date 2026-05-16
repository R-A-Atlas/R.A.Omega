"""
chain_mapper.py — Intent-to-output chain mapper + dead wire scanner.

Two tools in one:

  A. Chain Mapper: For every known intent, traces the full pipeline:
       intent -> output_mode -> renderer -> skill -> contract -> tests
     Shows exactly where each chain breaks.

  B. Dead Wire Scanner: Finds things defined but never connected:
       - Intents that fall through to chat (no explicit routing rule)
       - Output modes missing a renderer or contract
       - API routes with no test coverage
       - Skills registered but unreachable from any output_mode chain

No external APIs. No LLM calls. No writes to source files.

CLI:
  python chain_mapper.py              # full report (A + B)
  python chain_mapper.py --chains     # Option A only
  python chain_mapper.py --wires      # Option B only
  python chain_mapper.py --json       # JSON output
  python chain_mapper.py --output /path/to/report.md
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_ROOT))

# Intents that legitimately fall through to chat — not dead wires
_CHAT_INTENTS = {"CASUAL", "GENERAL_CHAT"}

# Scan intents route via OmegaAgent (POST /omega), not through resolve_output_mode.
# Falling through to chat for these is expected, not a bug.
_OMEGA_AGENT_INTENTS = {
    "CRYPTO_MARKET_SCAN", "EQUITIES_MARKET_SCAN", "OPTIONS_FLOW_MARKET_SCAN",
    "INSIDER_TRADES_MARKET_SCAN", "TREASURY_YIELD_MARKET_SCAN",
    "CPI_INFLATION_MARKET_SCAN", "FED_WATCH_MARKET_SCAN", "WATCH_MARKET_SCAN",
    "EARNINGS_MARKET_SCAN", "FOREX_MARKET_SCAN", "COMMODITIES_MARKET_SCAN",
    "SUPPLY_CHAIN_MARKET_SCAN", "ENERGY_MARKET_SCAN", "CLIMATE_RISK_MARKET_SCAN",
    "TARIFFS_MARKET_SCAN", "JOBS_MARKET_SCAN", "CONGRESS_TRADES_MARKET_SCAN",
    "DARK_POOL_SCAN", "PENNY_STOCK_SCAN", "REAL_ESTATE_SCAN",
    "PERSONAL_WEALTH_SCAN", "TAX_LEGAL_SCAN", "BUSINESS_SCAN",
    "ALTERNATIVE_ASSET_SCAN", "GLOBAL_LIQUIDITY_SCAN", "GROWTH_MARKETING_SCAN",
    "INTELLIGENCE_SYNTHESIS", "SECTOR_ROTATION_SCAN", "SENTIMENT_DIVERGENCE_SCAN",
    "MACRO_RISK_SCAN",
}


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ChainLink:
    intent: str
    output_mode: str
    renderer: str
    skill: str
    has_contract: bool
    has_tests: bool
    broken_at: str       # "" = fully connected; field name where chain breaks
    via_omega: bool = False

    @property
    def is_broken(self) -> bool:
        return bool(self.broken_at)

    @property
    def status(self) -> str:
        if self.via_omega:
            return "omega"
        if self.is_broken:
            return "broken"
        return "ok"


@dataclass
class DeadWire:
    category: str   # unrouted_intent | missing_renderer | missing_contract |
                    # untested_route  | dead_skill
    target: str
    detail: str
    severity: str = "warning"   # error | warning | info


@dataclass
class ChainMapResult:
    chains: list[ChainLink] = field(default_factory=list)
    dead_wires: list[DeadWire] = field(default_factory=list)
    report: str = ""

    @property
    def total_intents(self) -> int:
        return len(self.chains)

    @property
    def broken_chains(self) -> int:
        return sum(1 for c in self.chains if c.is_broken and not c.via_omega)

    @property
    def total_dead_wires(self) -> int:
        return len(self.dead_wires)

    @property
    def passed(self) -> bool:
        errors = [w for w in self.dead_wires if w.severity == "error"]
        return self.broken_chains == 0 and len(errors) == 0

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"{status}: {self.total_intents} intents mapped, "
            f"{self.broken_chains} broken chains, "
            f"{self.total_dead_wires} dead wires"
        )


# ── Intent loader ─────────────────────────────────────────────────────────────

def _load_all_intents() -> list[str]:
    try:
        import query_router as qr
        intents = sorted({
            v for k, v in vars(qr).items()
            if k.startswith("INTENT_") and isinstance(v, str)
        })
        return intents if intents else _FALLBACK_INTENTS
    except Exception:
        return _FALLBACK_INTENTS

_FALLBACK_INTENTS = sorted({
    "MARKET_DEEP_DIVE", "GENERAL_FINANCE", "CASUAL", "GENERAL_CHAT",
    "COMPANY_RESEARCH", "DOCUMENT_GENERATION", "HTML_ARTIFACT",
    "MARKET_DATA", "TRADING_ANALYSIS",
} | _OMEGA_AGENT_INTENTS)


# ── Chain resolution helpers ──────────────────────────────────────────────────

def _resolve_mode(intent: str) -> str:
    try:
        from output_modes import resolve_output_mode
        return resolve_output_mode("", intent)
    except Exception:
        return "unknown"


def _get_renderer(output_mode: str) -> str:
    try:
        from omega_pipeline import select_renderer_type
        r = select_renderer_type(output_mode, "")
        return r if r else "unknown"
    except Exception:
        return "unknown"


def _get_skill(output_mode: str) -> str:
    try:
        from omega_skill_registry import get_skill_for_output_mode
        return get_skill_for_output_mode(output_mode) or ""
    except Exception:
        return ""


def _has_contract(output_mode: str) -> bool:
    try:
        from output_contracts import OUTPUT_CONTRACTS
        return output_mode in OUTPUT_CONTRACTS
    except Exception:
        return False


def _has_tests(intent: str, output_mode: str) -> bool:
    tests_dir = _ROOT / "tests"
    if not tests_dir.is_dir():
        return False
    needles = {intent, output_mode}
    for tf in tests_dir.glob("*.py"):
        try:
            content = tf.read_text(encoding="utf-8", errors="replace")
            if any(n in content for n in needles):
                return True
        except Exception:
            pass
    return False


# ── Option A: Chain Mapper ────────────────────────────────────────────────────

def build_chain_map() -> list[ChainLink]:
    chains: list[ChainLink] = []
    for intent in _load_all_intents():
        via_omega = intent in _OMEGA_AGENT_INTENTS

        output_mode = _resolve_mode(intent)
        renderer    = _get_renderer(output_mode)
        skill       = _get_skill(output_mode)
        contract    = _has_contract(output_mode)
        tests       = _has_tests(intent, output_mode)

        broken_at = ""
        if not via_omega:
            if output_mode in ("unknown", "chat") and intent not in _CHAT_INTENTS:
                broken_at = "output_mode"
            elif renderer == "unknown":
                broken_at = "renderer"
            elif not skill:
                broken_at = "skill"
            elif not contract:
                broken_at = "contract"

        chains.append(ChainLink(
            intent=intent,
            output_mode=output_mode,
            renderer=renderer,
            skill=skill,
            has_contract=contract,
            has_tests=tests,
            broken_at=broken_at,
            via_omega=via_omega,
        ))
    return chains


# ── Option B: Dead Wire Scanner ───────────────────────────────────────────────

def _scan_unrouted_intents(chains: list[ChainLink]) -> list[DeadWire]:
    wires: list[DeadWire] = []
    for c in chains:
        if c.via_omega or c.intent in _CHAT_INTENTS:
            continue
        if c.output_mode in ("chat", "unknown") and c.intent not in _CHAT_INTENTS:
            wires.append(DeadWire(
                "unrouted_intent",
                c.intent,
                "No explicit rule in resolve_output_mode() — falls through to chat",
                severity="error",
            ))
    return wires


def _scan_output_mode_gaps() -> list[DeadWire]:
    wires: list[DeadWire] = []
    try:
        from output_modes import (
            OUTPUT_CHAT, OUTPUT_GENERAL_CHAT, OUTPUT_FINANCE_ANSWER,
            OUTPUT_COMPANY_REPORT, OUTPUT_DOCUMENT, OUTPUT_HTML_ARTIFACT,
            OUTPUT_MARKET_SNAPSHOT, OUTPUT_TRADE_PLAN,
        )
        all_modes = [
            OUTPUT_CHAT, OUTPUT_GENERAL_CHAT, OUTPUT_FINANCE_ANSWER,
            OUTPUT_COMPANY_REPORT, OUTPUT_DOCUMENT, OUTPUT_HTML_ARTIFACT,
            OUTPUT_MARKET_SNAPSHOT, OUTPUT_TRADE_PLAN,
        ]
    except Exception:
        return []

    for mode in all_modes:
        if _get_renderer(mode) == "unknown":
            wires.append(DeadWire(
                "missing_renderer", mode,
                "Defined in output_modes.py but select_renderer_type() returns unknown",
                severity="error",
            ))
        if not _has_contract(mode):
            wires.append(DeadWire(
                "missing_contract", mode,
                "No entry in OUTPUT_CONTRACTS — quality firewall has no rules for this mode",
                severity="warning",
            ))
    return wires


def _scan_routes_without_tests() -> list[DeadWire]:
    api_path = _ROOT / "api_server.py"
    if not api_path.exists():
        return []

    source = api_path.read_text(encoding="utf-8", errors="replace")
    route_re = re.compile(r'@app\.(?:get|post|put|patch|delete)\("([^"]+)"')
    routes = sorted(set(route_re.findall(source)))

    # Read all test content once
    tests_dir = _ROOT / "tests"
    test_content = ""
    if tests_dir.is_dir():
        for tf in tests_dir.glob("*.py"):
            try:
                test_content += tf.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    wires: list[DeadWire] = []
    for route in routes:
        if "{" in route:
            # Path-param routes: check if base path appears in tests
            base = route.split("{")[0].rstrip("/")
            if base and base not in test_content:
                wires.append(DeadWire(
                    "untested_route", route,
                    f"No test references base path '{base}'",
                    severity="warning",
                ))
        elif route not in test_content:
            wires.append(DeadWire(
                "untested_route", route,
                "No test file references this path",
                severity="warning",
            ))
    return wires


def _scan_dead_skills(chains: list[ChainLink]) -> list[DeadWire]:
    try:
        from omega_skill_registry import list_skills
        registered = {s["name"] for s in list_skills()}
    except Exception:
        return []

    reachable = {c.skill for c in chains if c.skill}
    dead = registered - reachable
    return [
        DeadWire(
            "dead_skill", name,
            "In skill registry but no output_mode chain leads to it",
            severity="warning",
        )
        for name in sorted(dead)
    ]


def scan_dead_wires(chains: list[ChainLink]) -> list[DeadWire]:
    wires: list[DeadWire] = []
    wires += _scan_unrouted_intents(chains)
    wires += _scan_output_mode_gaps()
    wires += _scan_routes_without_tests()
    wires += _scan_dead_skills(chains)
    return wires


# ── Report builder ────────────────────────────────────────────────────────────

def _build_report(result: ChainMapResult, include_chains: bool, include_wires: bool) -> str:
    lines = [
        "# Chain Mapper + Dead Wire Scan",
        "",
        f"**Result:** {result.summary()}",
        "",
    ]

    if include_chains:
        lines += ["## A. Intent Chain Map", ""]
        ok      = [c for c in result.chains if c.status == "ok"]
        broken  = [c for c in result.chains if c.status == "broken"]
        omega   = [c for c in result.chains if c.status == "omega"]

        if broken:
            lines += ["### Broken Chains", ""]
            for c in broken:
                lines.append(
                    f"- [BROKEN at {c.broken_at}] `{c.intent}` -> "
                    f"`{c.output_mode}` / `{c.renderer}` / "
                    f"skill={c.skill or '(none)'} / "
                    f"contract={'YES' if c.has_contract else 'NO'}"
                )
            lines.append("")

        lines += ["### Fully Connected Chains", ""]
        for c in ok:
            tests_tag = "tested" if c.has_tests else "no tests"
            lines.append(
                f"- [OK] `{c.intent}` -> `{c.output_mode}` / "
                f"`{c.renderer}` / skill=`{c.skill}` [{tests_tag}]"
            )
        lines.append("")

        lines += [
            f"### OmegaAgent Intents ({len(omega)}) — routed via POST /omega",
            "",
            "These intents bypass resolve_output_mode() and go directly to OmegaAgent.",
            "Chat fallback for these is expected, not a bug.",
            "",
        ]
        for c in omega:
            lines.append(f"- `{c.intent}`")
        lines.append("")

    if include_wires:
        lines += ["## B. Dead Wire Scan", ""]

        categories = [
            ("unrouted_intent",  "Unrouted Intents (no explicit rule in resolve_output_mode)"),
            ("missing_renderer", "Output Modes Missing Renderer"),
            ("missing_contract", "Output Modes Missing Contract"),
            ("untested_route",   "API Routes Without Test Coverage"),
            ("dead_skill",       "Dead Skills (registered but unreachable)"),
        ]

        found_any = False
        for cat, label in categories:
            items = [w for w in result.dead_wires if w.category == cat]
            if not items:
                continue
            found_any = True
            lines += [f"### {label}", ""]
            for w in items:
                sev = "ERROR" if w.severity == "error" else "WARN"
                lines.append(f"- [{sev}] `{w.target}` — {w.detail}")
            lines.append("")

        if not found_any:
            lines += ["All wires connected — no dead wires found.", ""]

    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def run(include_chains: bool = True, include_wires: bool = True) -> ChainMapResult:
    """
    Run the chain mapper and/or dead wire scanner.

    Args:
        include_chains: Run Option A (intent chain map).
        include_wires:  Run Option B (dead wire scan).

    Returns:
        ChainMapResult with .chains, .dead_wires, .report, .passed, .summary().
    """
    chains     = build_chain_map() if include_chains or include_wires else []
    dead_wires = scan_dead_wires(chains) if include_wires else []

    result = ChainMapResult(chains=chains, dead_wires=dead_wires)
    result.report = _build_report(result, include_chains, include_wires)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]
    as_json       = "--json"   in args
    chains_only   = "--chains" in args
    wires_only    = "--wires"  in args
    out_arg       = None
    if "--output" in args:
        idx = args.index("--output")
        if idx + 1 < len(args):
            out_arg = Path(args[idx + 1])

    include_chains = not wires_only
    include_wires  = not chains_only

    result = run(include_chains=include_chains, include_wires=include_wires)

    if as_json:
        print(json.dumps({
            "passed":        result.passed,
            "summary":       result.summary(),
            "broken_chains": result.broken_chains,
            "total_dead_wires": result.total_dead_wires,
            "chains": [
                {
                    "intent":       c.intent,
                    "output_mode":  c.output_mode,
                    "renderer":     c.renderer,
                    "skill":        c.skill,
                    "has_contract": c.has_contract,
                    "has_tests":    c.has_tests,
                    "broken_at":    c.broken_at,
                    "via_omega":    c.via_omega,
                }
                for c in result.chains
            ],
            "dead_wires": [
                {
                    "category": w.category,
                    "target":   w.target,
                    "detail":   w.detail,
                    "severity": w.severity,
                }
                for w in result.dead_wires
            ],
        }, indent=2))
    else:
        print(result.report)

    out_path = out_arg or (_ROOT / "atlas_vault" / "03-Outputs" / "chain_map.md")
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.report, encoding="utf-8")
        if not as_json:
            print(f"\nReport written to: {out_path}")
    except Exception as exc:
        print(f"Warning: could not write report — {exc}", file=sys.stderr)

    sys.exit(0 if result.passed else 1)
