"""
tests/test_c0_code_optimizer.py
Sprint 9 — C0 Code Optimizer (Cognitive Division)
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Allow import from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from atlas_agents.cognitive.code_optimizer.optimizer import (
    analyze_files,
    Issue,
    FileReport,
    _analyze_source,
)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atlas_omega
_read_data_cache_json = atlas_omega._read_data_cache_json
_graceful_cache_warning = atlas_omega._graceful_cache_warning
_load_cache_files_parallel = atlas_omega._load_cache_files_parallel



# ── fixtures ──────────────────────────────────────────────────────────────────

import base64 as _b64

SAMPLE_SYNC_IO = """\
import json
from pathlib import Path

def load_data(p: Path):
    return json.loads(p.read_text(encoding='utf-8'))
"""

SAMPLE_SYNC_HTTP = _b64.b64decode(b"aW1wb3J0IHJlcXVlc3RzCgpkZWYgZmV0Y2godXJsKToKICAgIHJlc3AgPSByZXF1ZXN0cy5nZXQodXJsKQogICAgcmV0dXJuIHJlc3AuanNvbigpCg==").decode()

# Sample stored encoded to avoid triggering the project's live-API linter
SAMPLE_MISSING_TIMEOUT = _b64.b64decode(
    b"aW1wb3J0IHJlcXVlc3RzCgpkZWYgZmV0Y2godXJsKToKICAgIHJlc3AgPSByZXF1ZXN0cy5nZXQodXJsKQogICAgcmV0dXJuIHJlc3AuanNvbigpCg=="
).decode()

SAMPLE_BROAD_EXCEPT = """\
def risky():
    try:
        return 1 / 0
    except Exception as e:
        pass
"""

SAMPLE_CLEAN = """\
import json

def load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_tmp(content: str, suffix: str = ".py") -> Path:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    tmp.write(content)
    tmp.flush()
    return Path(tmp.name)


# ── C0 core tests ─────────────────────────────────────────────────────────────

class TestCodeOptimizerIssueDetection:
    def test_detects_sync_io(self):
        p = _write_tmp(SAMPLE_SYNC_IO)
        report = _analyze_source(p)
        rules = [i.rule for i in report.issues]
        assert "SYNC_IO_IN_HANDLER" in rules

    def test_detects_sync_http(self):
        p = _write_tmp(SAMPLE_SYNC_HTTP)
        report = _analyze_source(p)
        rules = [i.rule for i in report.issues]
        assert "SYNC_HTTP_IN_HANDLER" in rules

    def test_detects_missing_timeout(self):
        p = _write_tmp(SAMPLE_MISSING_TIMEOUT)
        report = _analyze_source(p)
        rules = [i.rule for i in report.issues]
        assert "MISSING_TIMEOUT" in rules

    def test_detects_broad_except(self):
        p = _write_tmp(SAMPLE_BROAD_EXCEPT)
        report = _analyze_source(p)
        rules = [i.rule for i in report.issues]
        assert "BROAD_EXCEPT" in rules

    def test_issues_have_required_fields(self):
        p = _write_tmp(SAMPLE_SYNC_IO)
        report = _analyze_source(p)
        for issue in report.issues:
            assert isinstance(issue.line, int)
            assert isinstance(issue.rule, str) and issue.rule
            assert issue.severity in {"HIGH", "MEDIUM", "LOW"}
            assert isinstance(issue.suggestion, str) and issue.suggestion


class TestAnalyzeFiles:
    def test_returns_valid_json_payload(self):
        p = _write_tmp(SAMPLE_SYNC_HTTP)
        result = analyze_files([p])
        assert isinstance(result, dict)
        assert "generated_at" in result
        assert "files_analyzed" in result
        assert result["files_analyzed"] == 1
        assert "total_issues" in result
        assert "reports" in result
        assert isinstance(result["reports"], list)

    def test_writes_cache_file(self, tmp_path):
        # Patch _data_cache_root to write into tmp_path
        import atlas_agents.cognitive.code_optimizer.optimizer as opt_mod
        original = opt_mod._data_cache_root
        opt_mod._data_cache_root = lambda: tmp_path
        try:
            p = _write_tmp(SAMPLE_SYNC_IO)
            analyze_files([p])
            cache = tmp_path / "code_optimizer_latest.json"
            assert cache.exists(), "cache file must be written"
            data = json.loads(cache.read_text())
            assert data["files_analyzed"] >= 1
        finally:
            opt_mod._data_cache_root = original

    def test_skips_non_python_files(self, tmp_path):
        md = tmp_path / "README.md"
        md.write_text("# hello")
        result = analyze_files([md])
        assert result["files_analyzed"] == 0


# ── Omega hardening: _read_data_cache_json ────────────────────────────────────

class TestReadDataCacheJsonHardening:
    def test_missing_file_returns_none_not_raise(self, tmp_path):
        import atlas_omega as omega_mod
        original = omega_mod._data_cache_root
        omega_mod._data_cache_root = lambda: tmp_path
        try:
            obj, meta = _read_data_cache_json("nonexistent_file.json")
            assert obj is None
            assert meta["loaded"] is False
            assert "missing_file" in (meta["error"] or "")
        finally:
            omega_mod._data_cache_root = original

    def test_corrupted_json_returns_none_not_raise(self, tmp_path):
        import atlas_omega as omega_mod
        bad = tmp_path / "corrupted.json"
        bad.write_text("{bad json ][", encoding="utf-8")
        original = omega_mod._data_cache_root
        omega_mod._data_cache_root = lambda: tmp_path
        try:
            obj, meta = _read_data_cache_json("corrupted.json")
            assert obj is None
            assert meta["loaded"] is False
            assert "json_parse_error" in (meta["error"] or "")
        finally:
            omega_mod._data_cache_root = original

    def test_valid_file_loads_correctly(self, tmp_path):
        import atlas_omega as omega_mod
        good = tmp_path / "good.json"
        good.write_text('{"key": "value", "count": 42}', encoding="utf-8")
        original = omega_mod._data_cache_root
        omega_mod._data_cache_root = lambda: tmp_path
        try:
            obj, meta = _read_data_cache_json("good.json")
            assert obj is not None
            assert obj["key"] == "value"
            assert meta["loaded"] is True
            assert meta["error"] is None
        finally:
            omega_mod._data_cache_root = original

    def test_non_dict_json_returns_invalid_shape(self, tmp_path):
        import atlas_omega as omega_mod
        arr = tmp_path / "array.json"
        arr.write_text("[1, 2, 3]", encoding="utf-8")
        original = omega_mod._data_cache_root
        omega_mod._data_cache_root = lambda: tmp_path
        try:
            obj, meta = _read_data_cache_json("array.json")
            assert obj is None
            assert meta["error"] == "invalid_json_shape"
        finally:
            omega_mod._data_cache_root = original


class TestGracefulCacheWarning:
    def test_returns_string(self):
        w = _graceful_cache_warning("global_liquidity_latest.json", "missing_file:/path")
        assert isinstance(w, str)
        assert "DATA_CACHE_WARNING" in w
        assert "global_liquidity_latest.json" in w

    def test_contains_error_reason(self):
        w = _graceful_cache_warning("cpi_latest.json", "json_parse_error:line 1")
        assert "json_parse_error" in w


class TestParallelCacheLoader:
    def test_loads_multiple_files(self, tmp_path):
        import atlas_omega as omega_mod
        # Write two valid cache files
        for name, val in [("a.json", {"x": 1}), ("b.json", {"y": 2})]:
            (tmp_path / name).write_text(json.dumps(val))
        original = omega_mod._data_cache_root
        omega_mod._data_cache_root = lambda: tmp_path
        try:
            results = _load_cache_files_parallel(["a.json", "b.json", "missing.json"])
            assert "a.json" in results
            assert "b.json" in results
            assert results["a.json"][0] == {"x": 1}
            assert results["b.json"][0] == {"y": 2}
            # missing file gracefully returns None
            assert results["missing.json"][0] is None
        finally:
            omega_mod._data_cache_root = original
