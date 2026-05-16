"""Tests for omega_os/skills/ai_benchmarker/tools/benchmark.py."""
import json
import subprocess
import sys
from pathlib import Path

ROOT   = Path(__file__).parent.parent
SCRIPT = ROOT / "omega_os/skills/ai_benchmarker/tools/benchmark.py"
TOOLS  = ROOT / "omega_os/skills/improve_system/tools"


class TestBenchmarkScript:
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

    def test_json_output_is_valid(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert isinstance(data, dict)

    def test_json_has_omega_total(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert "omega_total" in data
        assert isinstance(data["omega_total"], (int, float))

    def test_json_has_all_four_competitors(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        totals = data.get("competitor_totals", {})
        for name in ["ChatGPT", "Claude", "Gemini", "Perplexity"]:
            assert name in totals, f"Missing competitor: {name}"

    def test_omega_scores_above_60(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert data["omega_total"] > 60, (
            f"R.A. Omega scored {data['omega_total']}/100 — sanity check fails")

    def test_json_has_nine_dimensions(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        dims = data.get("dimensions", [])
        assert len(dims) == 9, f"Expected 9 dimensions, got {len(dims)}"

    def test_json_has_advantages_and_gaps(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--json"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        data = json.loads(r.stdout)
        assert "top_advantages" in data
        assert "top_gaps" in data

    def test_output_contains_rank(self):
        r = subprocess.run([sys.executable, str(SCRIPT)],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert "Rank #" in r.stdout

    def test_output_contains_result_line(self):
        r = subprocess.run([sys.executable, str(SCRIPT)],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        assert "RESULT:" in r.stdout

    def test_dimension_weights_sum_to_100(self):
        # Import and verify weights are defined correctly in the script
        source = SCRIPT.read_text(encoding="utf-8")
        # DIMENSIONS list defines (slug, name, weight, desc) tuples
        import re
        weights = [int(m) for m in re.findall(r',\s*(\d+),\s*"[^"]+"\)', source)]
        assert sum(weights) == 100, f"Weights sum to {sum(weights)}, expected 100"


class TestBenchmarkFunctions:
    def _import_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("benchmark", SCRIPT)
        mod  = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        sys.path.insert(0, str(TOOLS))
        spec.loader.exec_module(mod)
        return mod

    def test_competitors_dict_has_four_entries(self):
        mod = self._import_module()
        assert len(mod.COMPETITORS) == 4

    def test_each_competitor_has_all_dimensions(self):
        mod  = self._import_module()
        slugs = [s for s, _, _, _ in mod.DIMENSIONS]
        for name, profile in mod.COMPETITORS.items():
            for slug in slugs:
                assert slug in profile, f"Competitor {name} missing dimension {slug}"

    def test_run_benchmark_returns_report(self):
        mod    = self._import_module()
        report = mod.run_benchmark()
        assert hasattr(report, "omega_total")
        assert hasattr(report, "competitor_totals")
        assert hasattr(report, "omega_rank")
        assert hasattr(report, "dimensions")

    def test_report_rank_is_int_in_range(self):
        mod    = self._import_module()
        report = mod.run_benchmark()
        assert isinstance(report.omega_rank, int)
        assert 1 <= report.omega_rank <= 5

    def test_benchmark_report_grade_method(self):
        mod    = self._import_module()
        report = mod.run_benchmark()
        grade  = report.grade()
        assert grade in ("A", "A-", "B+", "B", "B-", "C+", "C", "D")
