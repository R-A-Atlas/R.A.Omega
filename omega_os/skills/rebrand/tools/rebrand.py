"""
rebrand.py — Hunts and replaces every user-visible "ATLAS" reference with "R.A. Omega".

Rules:
  CHANGE:  user-visible text in HTML, AI response strings, titles, labels, descriptions
  SKIP:    Python identifiers, JS function/variable names, CSS class names,
           file names, import paths, database names, API header names,
           internal constants (ATLAS_API_DEFAULT, __ATLAS_SB_CONFIG__, etc.)
           — changing those would break the codebase

Never touches: deep_research.py, gemini_limiter.py
Touches atlas_omega.py ONLY to change user-visible response strings (not logic).

Usage:
    python omega_os/skills/rebrand/tools/rebrand.py          # audit
    python omega_os/skills/rebrand/tools/rebrand.py --fix    # apply
    python omega_os/skills/rebrand/tools/rebrand.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# ── What to change in each file ──────────────────────────────────────────────
# Each entry: (file, old_string, new_string, context_note)
PATCHES: list[tuple[str, str, str, str]] = [

    # atlas_omega.py — casual response fallback (user-visible AI reply text only)
    ("atlas_omega.py",
     "\"Hey there! I'm ATLAS, your financial intelligence assistant. \"",
     "\"Hey there! I'm R.A. Omega, your financial intelligence assistant. \"",
     "casual reply fallback text"),

    ("atlas_omega.py",
     "\"Ask me about stocks, real estate, debt, crypto, or anything money-related!\"",
     "\"Ask me about stocks, real estate, debt, crypto, or anything money-related!\"",
     "no change needed — already brand-neutral"),

    ("atlas_omega.py",
     "\"You are ATLAS, a friendly AI financial intelligence assistant. \"",
     "\"You are R.A. Omega, a friendly AI financial intelligence assistant. \"",
     "Gemini system prompt for casual replies"),

    # omega_brain_network.html — visible text nodes
    ("omega_brain_network.html",
     "the ATLAS architecture.",
     "the R.A. Omega architecture.",
     "visible description text"),

    ("omega_brain_network.html",
     "label: 'ATLAS Core'",
     "label: 'Omega Core'",
     "brain network node label"),

    ("omega_brain_network.html",
     "id: 'atlas_core'",
     "id: 'omega_core'",
     "brain network node id (also updates references)"),

    ("omega_brain_network.html",
     "'atlas_core'",
     "'omega_core'",
     "node id references in connections/edges"),

    # ra_omega_app.html — any residual ATLAS text (welcome, footer, etc.)
    ("ra_omega_app.html",
     "ATLAS",
     "R.A. Omega",
     "any remaining ATLAS text in app UI"),

    # auth.html — comment only, safe to update
    ("auth.html",
     "/* Brand accent: #18C6C8 — ATLAS cyan",
     "/* Brand accent: #18C6C8 — R.A. Omega cyan",
     "CSS comment (cosmetic)"),
]

# Files that must NEVER be touched
PROTECTED = {"deep_research.py", "gemini_limiter.py"}


@dataclass
class PatchResult:
    file: str
    old: str
    new: str
    note: str
    applied: bool = False
    already_done: bool = False
    skipped: bool = False
    error: str = ""


def audit_and_fix(fix: bool = False) -> list[PatchResult]:
    results: list[PatchResult] = []

    seen: dict[str, str] = {}   # file → current content (avoid re-reading)

    for fname, old, new, note in PATCHES:
        if fname in PROTECTED:
            results.append(PatchResult(fname, old, new, note, skipped=True,
                                       error="protected file"))
            continue
        if old == new:
            results.append(PatchResult(fname, old, new, note, already_done=True))
            continue

        path = ROOT / fname
        if not path.exists():
            results.append(PatchResult(fname, old, new, note, skipped=True,
                                       error="file not found"))
            continue

        if fname not in seen:
            seen[fname] = path.read_text(encoding="utf-8", errors="replace")

        content = seen[fname]

        if old not in content:
            # Check if new string is already there (patch already applied)
            if new in content:
                results.append(PatchResult(fname, old, new, note, already_done=True))
            else:
                results.append(PatchResult(fname, old, new, note, skipped=True,
                                           error="old string not found"))
            continue

        count = content.count(old)
        if fix:
            seen[fname] = content.replace(old, new)
            path.write_text(seen[fname], encoding="utf-8")
            results.append(PatchResult(fname, old, new, note, applied=True))
        else:
            results.append(PatchResult(fname, old, new, note,
                                       error=f"found {count}x — run --fix to apply"))

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="R.A. Omega rebrand tool")
    parser.add_argument("--fix",  action="store_true", help="Apply all patches")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    results = audit_and_fix(fix=args.fix)

    applied      = [r for r in results if r.applied]
    already_done = [r for r in results if r.already_done]
    needs_fix    = [r for r in results if not r.applied and not r.already_done and not r.skipped]
    skipped      = [r for r in results if r.skipped]

    if args.json:
        print(json.dumps({
            "applied":      len(applied),
            "already_done": len(already_done),
            "needs_fix":    len(needs_fix),
            "skipped":      len(skipped),
            "patches": [
                {"file": r.file, "note": r.note, "status":
                 "applied" if r.applied else
                 "already_done" if r.already_done else
                 "needs_fix" if not r.skipped else "skipped",
                 "error": r.error}
                for r in results
            ]
        }, indent=2))
        return

    sep = "=" * 64
    print(sep)
    print("  R.A. OMEGA — REBRAND PATROL")
    print(sep)

    if applied:
        print(f"\n  APPLIED ({len(applied)}):")
        for r in applied:
            print(f"    [DONE]  {r.file} — {r.note}")

    if already_done:
        print(f"\n  ALREADY CORRECT ({len(already_done)}):")
        for r in already_done:
            print(f"    [OK]    {r.file} — {r.note}")

    if needs_fix:
        print(f"\n  NEEDS FIX ({len(needs_fix)}):")
        for r in needs_fix:
            print(f"    [WARN]  {r.file} — {r.note}")
            print(f"            {r.error}")

    if skipped:
        print(f"\n  SKIPPED ({len(skipped)}):")
        for r in skipped:
            print(f"    [SKIP]  {r.file} — {r.error}")

    print(f"\n{'-'*64}")
    print(f"  {len(applied)} applied | {len(already_done)} already correct | "
          f"{len(needs_fix)} pending | {len(skipped)} skipped")

    if needs_fix and not args.fix:
        print(f"\n  Run with --fix to apply all pending patches.")
    elif applied:
        print(f"\n  Rebrand complete. Restart server to see changes.")
    else:
        print(f"\n  Nothing to do.")
    print(sep)


if __name__ == "__main__":
    main()
