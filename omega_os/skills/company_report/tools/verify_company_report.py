"""
verify_company_report.py — Deterministic verifier for company_report output.

No external APIs. No API keys. Fully local and deterministic.
Call verify(text) -> VerifyResult from code, or run as CLI:
  python verify_company_report.py "...report text..."
  python verify_company_report.py --file report.txt
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field


# ── Required sections ─────────────────────────────────────────────────────────

REQUIRED_SECTIONS: tuple[str, ...] = (
    "executive summary",
)
# Note: The output_contracts layer checks the full required section list
# (Company Overview, Business Model, Key Risks, etc.).
# The verifier's job is trade bleed detection + minimum sanity check.

# ── Forbidden trade-plan terms ────────────────────────────────────────────────

FORBIDDEN_TRADE_TERMS: tuple[str, ...] = (
    "the setup",
    "your rules",
    "what breaks this",
    "how this plays out",
    "hold period",
    "action: buy",
    "action: sell",
    "action: avoid",
    "action: short",
    "rating: buy",
    "rating: sell",
    "rating: hold",
    "rating: avoid",
    "entry price",
    "stop loss",
    "take profit",
    "execution rules",
    "risk/reward",
    "position size",
    "position sizing",
    "trade rating",
    "tripwire",
    "hedge fund brief",
    "best contract",
    "best options contract",
    "options play",
)


@dataclass
class VerifyResult:
    passed: bool
    missing_sections: list[str] = field(default_factory=list)
    forbidden_found: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return "PASS: company_report output is valid."
        parts = []
        if self.missing_sections:
            parts.append(f"Missing sections: {self.missing_sections}")
        if self.forbidden_found:
            parts.append(f"Forbidden trade terms found: {self.forbidden_found}")
        if self.errors:
            parts.append(f"Errors: {self.errors}")
        return "FAIL: " + "; ".join(parts)


def verify(text: str) -> VerifyResult:
    """
    Verify that text is a valid company_report output.
    Returns VerifyResult with .passed, .missing_sections, .forbidden_found.
    """
    if not isinstance(text, str):
        return VerifyResult(passed=False, errors=["Input must be a string"])

    lowered = text.lower()

    missing = [s for s in REQUIRED_SECTIONS if s not in lowered]
    forbidden = [t for t in FORBIDDEN_TRADE_TERMS if t in lowered]

    passed = not missing and not forbidden
    return VerifyResult(
        passed=passed,
        missing_sections=missing,
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
    # Positional: join remaining args as text
    positional = [a for a in args if not a.startswith("-")]
    if positional:
        return " ".join(positional)
    return sys.stdin.read()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: python verify_company_report.py <text>")
        print("       python verify_company_report.py --file <path>")
        sys.exit(0)
    text = _load_text(args)
    result = verify(text)
    print(result.summary())
    sys.exit(0 if result.passed else 1)
