"""Tests for omega_os/skills/stub_completor/tools/stub_audit.py."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
SCRIPT = ROOT / "omega_os/skills/stub_completor/tools/stub_audit.py"
SKILLS = ROOT / "omega_os/skills"


class TestStubAuditScript:
    def test_script_exists(self):
        assert SCRIPT.exists()

    def test_compiles_clean(self):
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_runs_and_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

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
        assert len(items) > 0
        for item in items:
            assert "name" in item
            assert "is_full" in item
            assert "tools" in item
            assert "priority_score" in item

    def test_dev_session_guard_appears_as_full(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        entry = next((i for i in items if i["name"] == "dev_session_guard"), None)
        assert entry is not None, "dev_session_guard must appear in audit"
        assert entry["is_full"] is True, "dev_session_guard must be a full skill"

    def test_skills_with_no_tools_appear_as_stubs(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        stubs = [i for i in items if not i["is_full"]]
        # We know there are stub skills in this project
        assert len(stubs) > 0, "There must be some stub skills"

    def test_stubs_only_flag_works(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--stubs-only"],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_output_contains_full_and_stub_counts(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        assert "FULL" in result.stdout
        assert "STUB" in result.stdout

    def test_skill_count_matches_directory_count(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            cwd=ROOT, capture_output=True, text=True,
        )
        items = json.loads(result.stdout)
        dirs  = [d for d in SKILLS.iterdir() if d.is_dir()]
        assert len(items) == len(dirs), (
            f"Audit found {len(items)} skills, but {len(dirs)} skill dirs exist"
        )


class TestSkillEntryDataclass:
    def _load_module(self):
        import sys
        spec = importlib.util.spec_from_file_location("stub_audit", SCRIPT)
        mod  = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_skill_entry_is_full_with_tools(self):
        mod   = self._load_module()
        entry = mod.SkillEntry(
            name="test", has_skill_md=True, has_evals=True, has_contract=True,
            tools=["run_test.py"], cadence_refs=0, skill_refs=0, priority_score=2.0,
        )
        assert entry.is_full is True
        assert entry.is_stub is False

    def test_skill_entry_is_stub_without_tools(self):
        mod   = self._load_module()
        entry = mod.SkillEntry(
            name="test", has_skill_md=True, has_evals=False, has_contract=False,
            tools=[], cadence_refs=0, skill_refs=0, priority_score=0.0,
        )
        assert entry.is_stub is True
        assert entry.is_full is False
