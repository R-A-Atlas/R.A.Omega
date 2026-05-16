"""Tests for omega_os/skills/api_contract_guard/tools/verify_contracts.py."""
import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
SCRIPT = ROOT / "omega_os/skills/api_contract_guard/tools/verify_contracts.py"


class TestVerifyContractsScript:
    def test_script_exists(self):
        assert SCRIPT.exists(), "verify_contracts.py must exist"

    def test_compiles_clean(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_runs_without_crash(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        # exit 0 (all pass) or 1 (some fail) are both OK — crash (non-0/1) is not
        assert result.returncode in (0, 1), (
            f"Unexpected exit {result.returncode}: {result.stderr[:300]}"
        )

    def test_json_flag_emits_valid_json(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        assert isinstance(data, list), "JSON output must be a list"

    def test_json_items_have_required_keys(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        for item in items:
            assert "check" in item, f"Missing 'check' key: {item}"
            assert "passed" in item, f"Missing 'passed' key: {item}"

    def test_health_scorer_check_present(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        data = json.loads(result.stdout)
        names = [item.get("check", "") for item in data]
        assert any("health_scorer" in n for n in names), (
            "health_scorer contract check must be present"
        )

    def test_output_contains_result_line(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert "RESULT" in result.stdout, "Output must contain RESULT line"


class TestVerifyContractsInterface:
    def test_run_all_function_present_in_source(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert "def run_all(" in source, "verify_contracts must define run_all()"

    def test_contract_result_class_present_in_source(self):
        source = SCRIPT.read_text(encoding="utf-8")
        assert "class ContractResult" in source

    def test_json_output_contains_passed_field(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        for item in items:
            assert "passed" in item

    def test_json_output_contains_check_field(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        for item in items:
            assert "check" in item
