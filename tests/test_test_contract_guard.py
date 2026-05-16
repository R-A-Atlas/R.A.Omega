"""Tests for omega_os/skills/test_contract_guard/tools/test_fragility_scan.py."""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT   = Path(__file__).parent.parent
SCRIPT = ROOT / "omega_os/skills/test_contract_guard/tools/test_fragility_scan.py"


class TestFragilityScanScript:
    def test_script_exists(self):
        assert SCRIPT.exists()

    def test_compiles_clean(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_runs_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_output_contains_result_line(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert "RESULT" in result.stdout

    def test_json_output_is_valid_list(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_json_items_have_required_keys(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        for item in items:
            assert "file" in item
            assert "line" in item
            assert "pattern" in item
            assert "severity" in item

    def test_fix_hints_flag_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--fix-hints"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_high_only_flag_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--high-only"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_high_only_filters_to_high_severity(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--high-only", "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        for item in items:
            assert item["severity"] == "high", (
                f"--high-only must only return high severity, got: {item['severity']}"
            )


class TestFragilePatternDetection:
    def _load_module(self):
        import sys
        spec = importlib.util.spec_from_file_location("test_fragility_scan", SCRIPT)
        mod  = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    def _write_test_file(self, content: str) -> Path:
        p = Path(tempfile.mktemp(suffix=".py", prefix="test_frag_"))
        p.write_text(content, encoding="utf-8")
        return p

    def test_scan_tests_returns_list(self):
        mod = self._load_module()
        result = mod.scan_tests()
        assert isinstance(result, list)

    def test_fragile_match_dataclass_fields(self):
        mod = self._load_module()
        m = mod.FragileMatch(
            file="test_foo.py",
            line=42,
            pattern_name="hex_color_assertion",
            matched_text='assert "#18C6C8" in html',
            suggestion="Use CSS variable",
            severity="high",
        )
        assert m.file == "test_foo.py"
        assert m.severity == "high"

    def test_patterns_list_has_six_entries(self):
        mod = self._load_module()
        assert len(mod.PATTERNS) == 6, f"Expected 6 patterns, got {len(mod.PATTERNS)}"

    def test_all_patterns_have_required_fields(self):
        mod = self._load_module()
        for name, regex, severity, suggestion in mod.PATTERNS:
            assert name, "Pattern must have a name"
            assert regex, "Pattern must have a regex"
            assert severity in ("high", "medium", "low"), f"Invalid severity: {severity}"
            assert suggestion, "Pattern must have a suggestion"

    def test_implementation_detail_string_is_high_severity(self):
        mod = self._load_module()
        high_patterns = [p for p in mod.PATTERNS if p[0] == "implementation_detail_string"]
        assert len(high_patterns) == 1
        assert high_patterns[0][2] == "high"

    def test_hex_color_assertion_is_high_severity(self):
        mod = self._load_module()
        high_patterns = [p for p in mod.PATTERNS if p[0] == "hex_color_assertion"]
        assert len(high_patterns) == 1
        assert high_patterns[0][2] == "high"
