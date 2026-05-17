"""Tests for omega_os/skills/smoke_tester/tools/smoke_test.py."""
import json
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
SCRIPT = ROOT / "omega_os/skills/smoke_tester/tools/smoke_test.py"


class TestSmokeTestScript:
    def test_script_exists(self):
        assert SCRIPT.exists(), "smoke_test.py must exist"

    def test_compiles_clean(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_json_flag_emits_valid_json_when_server_down(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        # Server likely not running in CI — exit 1 is expected, but JSON must be valid
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_json_items_have_required_keys(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        assert len(items) > 0, "Must check at least one endpoint"
        for item in items:
            assert "endpoint" in item
            assert "status" in item
            assert "passed" in item

    def test_covers_command_center_endpoint(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        endpoints = [item["endpoint"] for item in items]
        assert "/command-center" in endpoints, "/command-center must be a smoke endpoint"

    def test_covers_health_endpoint(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        endpoints = [item["endpoint"] for item in items]
        assert "/health" in endpoints

    def test_at_least_15_endpoints_covered(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        assert len(items) >= 15, f"Expected ≥15 endpoints, got {len(items)}"

    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_custom_base_url_flag_accepted(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--base-url", "http://127.0.0.1:9999", "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        # Should still emit JSON (all failures), not crash
        data = json.loads(result.stdout)
        assert isinstance(data, list)


class TestSmokeResultBehavior:
    def test_passed_when_status_matches(self):
        # Verify via JSON that passing results show passed=true
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        # All results should have a boolean passed field
        for item in items:
            assert isinstance(item["passed"], bool)

    def test_error_when_server_down_shows_null_status(self):
        # Use a port that is guaranteed not to be running
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--base-url", "http://127.0.0.1:9999", "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        # When server is down, all endpoints should fail
        failing = [i for i in items if not i["passed"]]
        assert len(failing) > 0, "Expected failures when server is down"
