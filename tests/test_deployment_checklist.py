"""Tests for omega_os/skills/deployment_checklist/tools/deploy_check.py."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
SCRIPT = ROOT / "omega_os/skills/deployment_checklist/tools/deploy_check.py"


class TestDeployCheckScript:
    def test_script_exists(self):
        assert SCRIPT.exists()

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
        assert result.returncode in (0, 1)

    def test_output_contains_result_line(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert "RESULT" in result.stdout

    def test_strict_flag_accepted(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--strict"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode in (0, 1)

    def test_auth_disabled_causes_blocker(self):
        env = {**os.environ, "ATLAS_DISABLE_AUTH": "true"}
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True, env=env,
        )
        assert result.returncode == 1, "ATLAS_DISABLE_AUTH=true must be a hard blocker"
        assert "ATLAS_DISABLE_AUTH" in result.stdout

    def test_auth_disabled_false_no_blocker_for_that_check(self):
        env = {**os.environ, "ATLAS_DISABLE_AUTH": "false"}
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True, env=env,
        )
        # Other checks may still fail — just verify auth check passes
        assert "ATLAS_DISABLE_AUTH=false" in result.stdout or "auth guard active" in result.stdout

    def test_ok_and_fail_markers_in_output(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        output = result.stdout
        assert "[OK]" in output or "[!!]" in output or "[~~]" in output


class TestDeployCheckFunctions:
    def _load_module(self):
        spec = importlib.util.spec_from_file_location("deploy_check", SCRIPT)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_check_auth_disabled_returns_list(self):
        mod = self._load_module()
        blockers = mod.check_auth_disabled()
        assert isinstance(blockers, list)

    def test_atlas_disable_auth_true_returns_blocker(self):
        mod = self._load_module()
        os.environ["ATLAS_DISABLE_AUTH"] = "true"
        try:
            blockers = mod.check_auth_disabled()
            assert len(blockers) > 0
        finally:
            os.environ.pop("ATLAS_DISABLE_AUTH", None)

    def test_check_api_server_compiles_passes(self):
        mod = self._load_module()
        blockers = mod.check_api_server_compiles()
        assert blockers == [], f"api_server.py must compile: {blockers}"

    def test_check_env_not_staged_returns_list(self):
        mod = self._load_module()
        blockers = mod.check_env_not_staged()
        assert isinstance(blockers, list)

    def test_load_local_dotenv_reads_values_without_overriding(self, tmp_path):
        mod = self._load_module()
        env_file = tmp_path / ".env"
        env_file.write_text(
            "SUPABASE_URL=https://example.supabase.co\n"
            "GEMINI_API_KEY=from-file\n"
            "EXISTING_VALUE=from-file\n",
            encoding="utf-8",
        )
        old_existing = os.environ.get("EXISTING_VALUE")
        old_supabase = os.environ.get("SUPABASE_URL")
        old_gemini = os.environ.get("GEMINI_API_KEY")
        os.environ.pop("SUPABASE_URL", None)
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ["EXISTING_VALUE"] = "from-env"
        try:
            assert mod._load_local_dotenv(env_file) is True
            assert os.environ["SUPABASE_URL"] == "https://example.supabase.co"
            assert os.environ["GEMINI_API_KEY"] == "from-file"
            assert os.environ["EXISTING_VALUE"] == "from-env"
        finally:
            for key, old in {
                "EXISTING_VALUE": old_existing,
                "SUPABASE_URL": old_supabase,
                "GEMINI_API_KEY": old_gemini,
            }.items():
                if old is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old
