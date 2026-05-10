"""
Validate JSON caches under repo data_cache/.
Run: python -m atlas_core.validation.data_validator
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_cache_dir() -> Path:
    return repo_root() / "data_cache"


def validate_directory(cache: Path) -> tuple[int, list[str]]:
    if not cache.is_dir():
        return 0, [f"[warn] Missing directory: {cache}"]

    errors: list[str] = []
    count = 0
    for path in sorted(cache.glob("*.json")):
        count += 1
        try:
            text = path.read_text(encoding="utf-8")
            json.loads(text)
        except json.JSONDecodeError as e:
            errors.append(f"{path.name}: invalid JSON ({e})")
        except OSError as e:
            errors.append(f"{path.name}: read failed ({e})")
    return count, errors


def main(argv: list[str] | None = None) -> int:
    _ = argv
    cache = data_cache_dir()
    n_ok, errs = validate_directory(cache)
    if errs:
        for line in errs:
            print(line, file=sys.stderr)
        return 1
    print(f"OK: {n_ok} file(s) in {cache}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
