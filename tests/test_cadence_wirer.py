"""Tests for omega_os/skills/cadence_wirer/tools/start_cadence.py."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
SCRIPT = ROOT / "omega_os/skills/cadence_wirer/tools/start_cadence.py"


class TestStartCadenceScript:
    def test_script_exists(self):
        assert SCRIPT.exists()

    def test_compiles_clean(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_dry_run_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--dry-run"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_dry_run_shows_real_runner(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--dry-run"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert "REAL" in result.stdout, "dry-run must show REAL for implemented runners"

    def test_dry_run_shows_stub_runner(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--dry-run"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert "STUB" in result.stdout, "dry-run must show STUB for unimplemented runners"

    def test_dry_run_shows_daily_market_brief(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--dry-run"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert "daily_market_brief" in result.stdout

    def test_without_env_var_prints_guidance(self):
        env = {k: v for k, v in os.environ.items() if k != "OMEGA_CADENCE_ENABLED"}
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0
        assert "OMEGA_CADENCE_ENABLED" in result.stdout

    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0


class TestStartCadenceFunctions:
    def _load_module(self):
        spec = importlib.util.spec_from_file_location("start_cadence", SCRIPT)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_start_cadence_if_enabled_importable(self):
        mod = self._load_module()
        assert callable(mod.start_cadence_if_enabled)

    def test_start_cadence_if_enabled_no_side_effects_without_env(self):
        mod = self._load_module()
        env_backup = os.environ.pop("OMEGA_CADENCE_ENABLED", None)
        try:
            # Should return without error and without starting scheduler
            mod.start_cadence_if_enabled()
        finally:
            if env_backup is not None:
                os.environ["OMEGA_CADENCE_ENABLED"] = env_backup

    def test_schedules_dict_has_all_7_jobs(self):
        mod = self._load_module()
        assert len(mod.SCHEDULES) == 7, f"Expected 7 schedules, got {len(mod.SCHEDULES)}"

    def test_runners_dict_has_real_runners(self):
        mod = self._load_module()
        assert "daily_market_brief" in mod.RUNNERS
        assert "weekly_omega_os_audit" in mod.RUNNERS

    def test_get_runner_returns_callable(self):
        mod = self._load_module()
        runner = mod._get_runner("daily_market_brief")
        assert callable(runner)

    def test_get_runner_stub_for_unknown(self):
        mod = self._load_module()
        runner = mod._get_runner("nonexistent_job")
        assert callable(runner)
        # Stub runner should not raise when called
        runner()

    def test_wired_in_api_server(self):
        api_path = ROOT / "api_server.py"
        text = api_path.read_text(encoding="utf-8", errors="replace")
        assert "start_cadence_if_enabled" in text, (
            "start_cadence_if_enabled must be called from api_server.py lifespan"
        )
