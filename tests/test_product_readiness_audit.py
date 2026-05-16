"""Tests for omega_os/skills/product_readiness_audit/tools/readiness_check.py."""
import json
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
SCRIPT = ROOT / "omega_os/skills/product_readiness_audit/tools/readiness_check.py"


class TestReadinessScript:
    def test_script_exists(self):
        assert SCRIPT.exists()

    def test_compiles_clean(self):
        r = subprocess.run([sys.executable, "-m", "py_compile", str(SCRIPT)],
                           cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    def test_runs_exits_zero(self):
        r = subprocess.run([sys.executable, str(SCRIPT)],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert r.returncode == 0, r.stderr[:300]

    def test_output_contains_result_line(self):
        r = subprocess.run([sys.executable, str(SCRIPT)],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert "RESULT:" in r.stdout

    def test_output_contains_verdict(self):
        r = subprocess.run([sys.executable, str(SCRIPT)],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        verdicts = ["PRODUCTION READY", "BETA READY", "ALPHA", "NOT READY"]
        assert any(v in r.stdout for v in verdicts)

    def test_json_output_is_valid(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert isinstance(data, dict)

    def test_json_has_required_keys(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        for key in ["total_score", "max_score", "pct", "grade", "verdict", "categories", "priority_fixes"]:
            assert key in data, f"Missing key: {key}"

    def test_json_has_eight_categories(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        cats = data.get("categories", [])
        assert len(cats) == 8, f"Expected 8 categories, got {len(cats)}"

    def test_json_max_score_is_100(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert data["max_score"] == 100

    def test_json_total_score_in_range(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert 0 <= data["total_score"] <= 100

    def test_category_filter_works(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--category", "auth"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert r.returncode == 0
        assert "Auth" in r.stdout or "auth" in r.stdout.lower()

    def test_priority_fixes_are_list(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert isinstance(data["priority_fixes"], list)

    def test_data_layer_scores_high(self):
        """Data layer should score well — we have atlas_memory.db, atlas_tracker.db, RAG."""
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        cats = {c["slug"]: c for c in data["categories"]}
        data_cat = cats.get("data", {})
        assert data_cat.get("pct", 0) >= 80, (
            f"Data layer scored {data_cat.get('pct', 0)}% — databases and RAG should give high score")

    def test_auth_redirect_check_passes(self):
        """Auth must redirect to /command-center — should pass since we fixed it."""
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        cats = {c["slug"]: c for c in data["categories"]}
        auth = cats.get("auth", {})
        redirect_check = next(
            (c for c in auth.get("checks", [])
             if "command-center" in c["label"].lower() or "redirect" in c["label"].lower()),
            None,
        )
        if redirect_check:
            assert redirect_check["passed"], (
                "Auth redirect check must pass — auth.html should redirect to /command-center")


class TestReadinessFunctions:
    def _import_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("readiness_check", SCRIPT)
        mod  = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_run_checks_returns_report(self):
        mod    = self._import_module()
        report = mod.run_checks()
        assert hasattr(report, "total_score")
        assert hasattr(report, "categories")
        assert hasattr(report, "verdict")

    def test_report_has_eight_categories(self):
        mod    = self._import_module()
        report = mod.run_checks()
        assert len(report.categories) == 8

    def test_max_score_is_100(self):
        mod    = self._import_module()
        report = mod.run_checks()
        assert report.max_score == 100

    def test_verdict_is_valid_string(self):
        mod     = self._import_module()
        report  = mod.run_checks()
        verdict = report.verdict()
        assert verdict in ("PRODUCTION READY", "BETA READY", "ALPHA / STAGING", "NOT READY")

    def test_all_fixes_returns_list_of_tuples(self):
        mod   = self._import_module()
        fixes = mod.run_checks().all_fixes()
        assert isinstance(fixes, list)
        for item in fixes:
            assert len(item) == 2, "all_fixes must return (category, fix) tuples"

    def test_category_filter_reduces_count(self):
        mod    = self._import_module()
        report = mod.run_checks(category_filter="auth")
        assert len(report.categories) == 1
        assert report.categories[0].slug == "auth"
