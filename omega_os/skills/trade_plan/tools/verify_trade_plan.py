"""
verify_trade_plan.py — Deterministic verifier for trade_plan output.

No external APIs. No API keys. Fully local and deterministic.
Call verify(text) -> VerifyResult from code, or run as CLI:
  python verify_trade_plan.py "...trade plan text..."
  python verify_trade_plan.py --file plan.txt
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field


# ── Required sections ─────────────────────────────────────────────────────────

REQUIRED_SECTIONS: tuple[str, ...] = (
    "entry",
    "risk",
)

# "Stop loss" OR "invalidation" counts as the stop mechanism — either is acceptable.
_STOP_MECHANISM_ALIASES: tuple[str, ...] = ("stop loss", "invalidation")

# Optional but expected in a complete trade plan
RECOMMENDED_SECTIONS: tuple[str, ...] = (
    "target",
    "risk/reward",
    "options play",
)

# ── Forbidden patterns (naked options, no-stop plans) ────────────────────────

FORBIDDEN_PATTERNS: tuple[str, ...] = (
    "naked call",
    "naked put",
    "unlimited risk",
    "no stop",
    "stop loss: none",
    "stop loss: n/a",
)


@dataclass
class VerifyResult:
    passed: bool
    missing_sections: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)
    forbidden_found: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            rec_note = ""
            if self.missing_recommended:
                rec_note = f" (missing recommended: {self.missing_recommended})"
            return f"PASS: trade_plan output is valid.{rec_note}"
        parts = []
        if self.missing_sections:
            parts.append(f"Missing required sections: {self.missing_sections}")
        if self.forbidden_found:
            parts.append(f"Forbidden patterns found: {self.forbidden_found}")
        if self.errors:
            parts.append(f"Errors: {self.errors}")
        return "FAIL: " + "; ".join(parts)


def verify(text: str) -> VerifyResult:
    """
    Verify that text is a valid trade_plan output.
    Returns VerifyResult with .passed, .missing_sections, .forbidden_found.
    """
    if not isinstance(text, str):
        return VerifyResult(passed=False, errors=["Input must be a string"])

    lowered = text.lower()

    missing = [s for s in REQUIRED_SECTIONS if s not in lowered]

    # Check stop mechanism: "stop loss" OR "invalidation" must be present
    has_stop_mechanism = any(alias in lowered for alias in _STOP_MECHANISM_ALIASES)
    if not has_stop_mechanism:
        missing.append("stop loss")

    missing_rec = [s for s in RECOMMENDED_SECTIONS if s not in lowered]
    forbidden = [p for p in FORBIDDEN_PATTERNS if p in lowered]

    passed = not missing and not forbidden
    return VerifyResult(
        passed=passed,
        missing_sections=missing,
        missing_recommended=missing_rec,
        forbidden_found=forbidden,
    )


def _load_text(args: list[str]) -> str:
    if "--file" in args:
        idx = args.index("--file")
        if idx + 1 >= len(args):
            print("ERROR: --file requires a path argument", file=sys.stderr)
            sys.exit(1)
        path = args[idx + 1]
        with open(path, encoding="utf-8") as f:
            return f.read()
    positional = [a for a in args if not a.startswith("-")]
    if positional:
        return " ".join(positional)
    return sys.stdin.read()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: python verify_trade_plan.py <text>")
        print("       python verify_trade_plan.py --file <path>")
        sys.exit(0)
    text = _load_text(args)
    result = verify(text)
    print(result.summary())
    sys.exit(0 if result.passed else 1)
