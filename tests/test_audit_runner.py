"""Tests for omega_os/skills/audit_runner/tools/run_audit.py."""
import json
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
SCRIPT = ROOT / "omega_os/skills/audit_runner/tools/run_audit.py"


class TestAuditRunnerScript:
    def test_script_exists(self):
        assert SCRIPT.exists()

    def test_compiles_clean(self):
        r = subprocess.run([sys.executable, "-m", "py_compile", str(SCRIPT)],
                           cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    def test_quick_no_save_exits_zero(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--quick", "--no-save"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert r.returncode == 0, r.stderr[:300]

    def test_quick_json_no_save_is_valid_json(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--quick", "--no-save", "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert isinstance(data, dict)

    def test_json_has_overall_score(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--quick", "--no-save", "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert "overall_score" in data
        assert isinstance(data["overall_score"], (int, float))

    def test_json_has_required_keys(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--quick", "--no-save", "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        for key in ["overall_score", "overall_grade", "overall_verdict",
                    "readiness_score", "priority_fixes", "category_scores"]:
            assert key in data, f"Missing key: {key}"

    def test_overall_score_in_range(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--quick", "--no-save", "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert 0 <= data["overall_score"] <= 100

    def test_overall_grade_is_letter(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--quick", "--no-save", "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert data["overall_grade"] in ("A", "A-", "B+", "B", "B-", "C+", "C", "D")

    def test_overall_verdict_is_valid(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--quick", "--no-save", "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        verdicts = ["PRODUCTION READY", "BETA READY", "ALPHA", "BUILDING"]
        assert any(v in data["overall_verdict"] for v in verdicts)

    def test_full_run_no_save_exits_zero(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--no-save"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90)
        assert r.returncode == 0, r.stderr[:300]

    def test_full_run_produces_output(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--no-save"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90)
        assert "OVERALL" in r.stdout
        assert "VERDICT" in r.stdout

    def test_full_run_json_has_benchmark_score(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--no-save", "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=90)
        data = json.loads(r.stdout)
        assert "benchmark_score" in data
        assert data["benchmark_score"] > 0

    def test_report_saved_to_vault(self, tmp_path):
        """--no-save skips vault; default saves to atlas_vault/03-Outputs/."""
        vault = ROOT / "atlas_vault" / "03-Outputs"
        r = subprocess.run([sys.executable, str(SCRIPT), "--quick"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        assert r.returncode == 0
        audit_files = list(vault.glob("omega_audit_*.md"))
        assert len(audit_files) >= 1, "Expected at least one omega_audit_*.md in vault outputs"

    def test_saved_report_is_markdown(self):
        vault = ROOT / "atlas_vault" / "03-Outputs"
        files = sorted(vault.glob("omega_audit_*.md"))
        if files:
            content = files[-1].read_text(encoding="utf-8")
            assert "Overall Score" in content
            assert "Priority Fix" in content


class TestAuditRunnerFunctions:
    def _import_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("run_audit", SCRIPT)
        mod  = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_grade_function_covers_all_ranges(self):
        mod = self._import_module()
        assert mod._grade(95) == "A"
        assert mod._grade(83) == "A-"
        assert mod._grade(76) == "B+"
        assert mod._grade(65) == "B"
        assert mod._grade(50) == "C"
        assert mod._grade(30) == "D"

    def test_verdict_function_covers_all_ranges(self):
        mod = self._import_module()
        assert "PRODUCTION READY" in mod._verdict(92)
        assert "BETA READY"       in mod._verdict(80)
        assert "ALPHA"            in mod._verdict(65)
        assert "BUILDING"         in mod._verdict(50)

    def test_run_audit_quick_returns_report(self):
        mod    = self._import_module()
        report = mod.run_audit(quick=True)
        assert hasattr(report, "overall_score")
        assert hasattr(report, "overall_grade")
        assert hasattr(report, "priority_fixes")
        assert 0 <= report.overall_score <= 100
