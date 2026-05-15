"""
tests/test_omega_dashboard.py

Tests for omega_dashboard.py and its API endpoints.
All subsystem calls are mocked — no external credentials required.

omega_dashboard uses lazy __import__() internally, so we install stubs into
sys.modules only for the duration of each test and restore originals after.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# omega_dashboard uses lazy __import__() internally — safe to import without stubs
import omega_dashboard as _dash  # noqa: E402

# ─── Stub helpers ─────────────────────────────────────────────────────────────

_STUB_NAMES = (
    "omega_audit", "omega_connections", "omega_cadence",
    "omega_persistence", "omega_os_loader", "omega_google_workspace",
    "omega_sec_edgar",
)


def _make_stub(name: str, **attrs) -> ModuleType:
    m = ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def _build_stubs() -> dict[str, ModuleType]:
    conn = MagicMock()
    conn.name = "SEC EDGAR"; conn.slug = "sec_edgar"
    conn.status = "active"; conn.can_write = False; conn.is_destructive = False

    job = MagicMock()
    job.name = "Daily Brief"; job.slug = "daily_brief"
    job.frequency = "daily"; job.schedule_hint = "7am"; job.status = "planned"
    job.estimated_cost_usd = 0.02

    return {
        "omega_audit": _make_stub("omega_audit", run_audit=lambda: {
            "context": 20, "connections": 18, "capabilities": 22, "cadence": 15,
            "total": 75, "phase": "Beta",
            "strengths": ["Strong data layer"], "gaps": ["No cadence scheduled"],
            "next_steps": ["Schedule daily brief"],
        }),
        "omega_connections": _make_stub("omega_connections", get_registry=lambda: [conn]),
        "omega_cadence": _make_stub("omega_cadence", get_cadence_plan=lambda: [job]),
        "omega_persistence": _make_stub("omega_persistence",
            get_recent_reports=lambda limit=10: [{"id": "r1", "query": "NVDA"}],
            get_research_queue=lambda limit=10: [{"id": "t1", "topic": "macro"}],
            get_persistence_status=lambda: {
                "persistence_mode": "local_fallback", "supabase_configured": False,
            }),
        "omega_os_loader": _make_stub("omega_os_loader",
            list_skills=lambda: [{"name": "equity_deep_dive", "description": "Full equity report"}]),
        "omega_google_workspace": _make_stub("omega_google_workspace",
            get_google_workspace_status=lambda: {
                "configured": False, "enabled": False, "message": "not configured",
            }),
        "omega_sec_edgar": _make_stub("omega_sec_edgar", is_available=lambda: True),
    }


@pytest.fixture()
def dashboard_stubs():
    """Install subsystem stubs for the duration of one test, then restore."""
    originals = {k: sys.modules.get(k) for k in _STUB_NAMES}
    stubs = _build_stubs()
    sys.modules.update(stubs)
    yield stubs
    for name, original in originals.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


# ═══════════════════════════════════════════════════════════════════════════════
# 1. build_command_center_snapshot() — shape tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCommandCenterShape:
    @pytest.fixture(autouse=True)
    def _setup(self, dashboard_stubs):
        self.snap = _dash.build_command_center_snapshot()

    def test_returns_dict(self):
        assert isinstance(self.snap, dict)

    def test_omega_os_score_present(self):
        assert "omega_os_score" in self.snap

    def test_four_c_scores_present(self):
        assert "four_c_scores" in self.snap

    def test_four_c_scores_has_four_keys(self):
        fc = self.snap["four_c_scores"]
        assert set(fc) >= {"context", "connections", "capabilities", "cadence"}

    def test_phase_label_present(self):
        assert "phase_label" in self.snap

    def test_connection_status_present(self):
        assert "connection_status" in self.snap

    def test_connection_status_is_list(self):
        assert isinstance(self.snap["connection_status"], list)

    def test_cadence_status_present(self):
        assert "cadence_status" in self.snap

    def test_cadence_status_is_list(self):
        assert isinstance(self.snap["cadence_status"], list)

    def test_recent_reports_present(self):
        assert "recent_reports" in self.snap

    def test_research_queue_present(self):
        assert "research_queue" in self.snap

    def test_skills_summary_present(self):
        assert "skills_summary" in self.snap

    def test_google_workspace_status_present(self):
        assert "google_workspace_status" in self.snap

    def test_persistence_status_present(self):
        assert "persistence_status" in self.snap

    def test_sec_edgar_status_present(self):
        assert "sec_edgar_status" in self.snap

    def test_suggested_next_actions_present(self):
        assert "suggested_next_actions" in self.snap

    def test_suggested_next_actions_is_list(self):
        assert isinstance(self.snap["suggested_next_actions"], list)

    def test_system_health_present(self):
        assert "system_health" in self.snap

    def test_system_health_has_health_key(self):
        assert "health" in self.snap["system_health"]

    def test_snapshot_at_present(self):
        assert "snapshot_at" in self.snap

    def test_snapshot_type_is_command_center(self):
        assert self.snap["snapshot_type"] == "command_center"

    def test_json_serializable(self):
        json.dumps(self.snap)

    def test_omega_os_score_is_numeric(self):
        assert isinstance(self.snap["omega_os_score"], (int, float))

    def test_connection_status_entry_shape(self):
        conns = self.snap["connection_status"]
        assert len(conns) >= 1
        entry = conns[0]
        assert "name" in entry and "slug" in entry and "status" in entry

    def test_cadence_status_entry_shape(self):
        jobs = self.snap["cadence_status"]
        assert len(jobs) >= 1
        job = jobs[0]
        assert "name" in job and "slug" in job and "status" in job

    def test_sec_edgar_status_has_available_key(self):
        assert "available" in self.snap["sec_edgar_status"]

    def test_suggested_next_actions_max_5(self):
        assert len(self.snap["suggested_next_actions"]) <= 5

    def test_four_c_scores_are_numeric(self):
        fc = self.snap["four_c_scores"]
        for v in fc.values():
            assert isinstance(v, (int, float))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. build_omega_brain_snapshot() — shape tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestBrainSnapshotShape:
    @pytest.fixture(autouse=True)
    def _setup(self, dashboard_stubs):
        self.brain = _dash.build_omega_brain_snapshot()

    def test_returns_dict(self):
        assert isinstance(self.brain, dict)

    def test_context_categories_present(self):
        assert "context_categories" in self.brain

    def test_context_categories_is_list(self):
        assert isinstance(self.brain["context_categories"], list)

    def test_decisions_summary_present(self):
        assert "decisions_summary" in self.brain

    def test_decisions_summary_is_list(self):
        assert isinstance(self.brain["decisions_summary"], list)

    def test_audit_history_summary_present(self):
        assert "audit_history_summary" in self.brain

    def test_audit_history_summary_is_list(self):
        assert isinstance(self.brain["audit_history_summary"], list)

    def test_skills_available_present(self):
        assert "skills_available" in self.brain

    def test_skills_available_is_list(self):
        assert isinstance(self.brain["skills_available"], list)

    def test_memory_files_present(self):
        assert "memory_files" in self.brain

    def test_memory_files_is_list(self):
        assert isinstance(self.brain["memory_files"], list)

    def test_recommended_questions_present(self):
        assert "recommended_questions" in self.brain

    def test_recommended_questions_is_list(self):
        assert isinstance(self.brain["recommended_questions"], list)

    def test_recommended_questions_not_empty(self):
        assert len(self.brain["recommended_questions"]) > 0

    def test_recommended_questions_are_strings(self):
        for q in self.brain["recommended_questions"]:
            assert isinstance(q, str)

    def test_snapshot_at_present(self):
        assert "snapshot_at" in self.brain

    def test_snapshot_type_is_omega_brain(self):
        assert self.brain["snapshot_type"] == "omega_brain"

    def test_json_serializable(self):
        json.dumps(self.brain)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Graceful degradation — subsystems fail
# ═══════════════════════════════════════════════════════════════════════════════

class TestGracefulDegradation:
    def test_command_center_survives_audit_failure(self, dashboard_stubs):
        dashboard_stubs["omega_audit"].run_audit = MagicMock(side_effect=RuntimeError("boom"))
        snap = _dash.build_command_center_snapshot()
        assert "omega_os_score" in snap
        assert snap["four_c_scores"]["context"] == 0

    def test_command_center_survives_connections_failure(self, dashboard_stubs):
        dashboard_stubs["omega_connections"].get_registry = MagicMock(side_effect=RuntimeError)
        snap = _dash.build_command_center_snapshot()
        assert isinstance(snap["connection_status"], list)

    def test_command_center_survives_cadence_failure(self, dashboard_stubs):
        dashboard_stubs["omega_cadence"].get_cadence_plan = MagicMock(side_effect=RuntimeError)
        snap = _dash.build_command_center_snapshot()
        assert isinstance(snap["cadence_status"], list)

    def test_command_center_survives_persistence_failure(self, dashboard_stubs):
        dashboard_stubs["omega_persistence"].get_persistence_status = MagicMock(side_effect=RuntimeError)
        snap = _dash.build_command_center_snapshot()
        assert "persistence_status" in snap

    def test_command_center_survives_skills_failure(self, dashboard_stubs):
        dashboard_stubs["omega_os_loader"].list_skills = MagicMock(side_effect=RuntimeError)
        snap = _dash.build_command_center_snapshot()
        assert isinstance(snap["skills_summary"], list)

    def test_brain_survives_context_dir_missing(self, dashboard_stubs):
        with patch.object(_dash, "_CONTEXT_DIR", Path("/nonexistent/path")):
            brain = _dash.build_omega_brain_snapshot()
        assert isinstance(brain["context_categories"], list)

    def test_brain_survives_decisions_file_missing(self, dashboard_stubs):
        with patch.object(_dash, "_DECISIONS_DIR", Path("/nonexistent/decisions")):
            brain = _dash.build_omega_brain_snapshot()
        assert isinstance(brain["decisions_summary"], list)

    def test_brain_survives_audits_file_missing(self, dashboard_stubs):
        with patch.object(_dash, "_AUDITS_FILE", Path("/nonexistent/audits.md")):
            brain = _dash.build_omega_brain_snapshot()
        assert isinstance(brain["audit_history_summary"], list)

    def test_all_required_fields_present_on_full_degradation(self, dashboard_stubs):
        """All expected keys must exist even when every subsystem fails."""
        dashboard_stubs["omega_audit"].run_audit = MagicMock(side_effect=RuntimeError)
        dashboard_stubs["omega_connections"].get_registry = MagicMock(side_effect=RuntimeError)
        dashboard_stubs["omega_cadence"].get_cadence_plan = MagicMock(side_effect=RuntimeError)
        snap = _dash.build_command_center_snapshot()
        required = {
            "omega_os_score", "four_c_scores", "phase_label", "connection_status",
            "cadence_status", "recent_reports", "research_queue", "skills_summary",
            "google_workspace_status", "persistence_status", "sec_edgar_status",
            "suggested_next_actions", "system_health", "snapshot_at", "snapshot_type",
        }
        assert required <= set(snap)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. API endpoint registration
# ═══════════════════════════════════════════════════════════════════════════════

class TestApiEndpoints:
    def test_dashboard_route_registered(self):
        import api_server
        routes = [r.path for r in api_server.app.routes]
        assert "/omega-os/dashboard" in routes

    def test_brain_route_registered(self):
        import api_server
        routes = [r.path for r in api_server.app.routes]
        assert "/omega-os/brain" in routes

    def test_dashboard_route_is_get(self):
        import api_server
        for r in api_server.app.routes:
            if r.path == "/omega-os/dashboard":
                assert "GET" in r.methods
                return
        pytest.fail("/omega-os/dashboard route not found")

    def test_brain_route_is_get(self):
        import api_server
        for r in api_server.app.routes:
            if r.path == "/omega-os/brain":
                assert "GET" in r.methods
                return
        pytest.fail("/omega-os/brain route not found")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Security — no hardcoded secrets, routing purity
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurity:
    def _source(self) -> str:
        return (ROOT / "omega_dashboard.py").read_text(encoding="utf-8")

    def test_no_hardcoded_api_keys(self):
        source = self._source()
        bad_patterns = ["sk-", "sk_live_", "SG.", "ghp_", "xoxb-"]
        for pat in bad_patterns:
            assert pat not in source, f"Possible hardcoded secret: {pat}"

    def test_routing_purity_no_classify_intent(self):
        source = self._source()
        assert "classify_intent_route" not in source

    def test_routing_purity_no_query_router_import(self):
        source = self._source()
        assert "import query_router" not in source
        assert "from query_router" not in source

    def test_no_trading_credentials(self):
        source = self._source()
        assert "BROKER_API_KEY" not in source
        assert "stop_loss" not in source

    def test_py_compile_omega_dashboard(self):
        import py_compile
        py_compile.compile(str(ROOT / "omega_dashboard.py"), doraise=True)

    def test_py_compile_api_server(self):
        import py_compile
        py_compile.compile(str(ROOT / "api_server.py"), doraise=True)

    def test_importable_without_credentials(self):
        import importlib
        mod = importlib.import_module("omega_dashboard")
        assert hasattr(mod, "build_command_center_snapshot")
        assert hasattr(mod, "build_omega_brain_snapshot")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. System health roll-up logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestSystemHealth:
    def _health_for_score(self, score: int) -> str:
        four_c = {"total": score, "phase": "test", "strengths": [], "gaps": [], "next_steps": []}
        persistence = {"persistence_mode": "local_fallback", "supabase_configured": False}
        h = _dash._get_system_health(four_c, persistence)
        return h["health"]

    def test_health_excellent_at_85(self):
        assert self._health_for_score(85) == "excellent"

    def test_health_excellent_at_100(self):
        assert self._health_for_score(100) == "excellent"

    def test_health_good_at_70(self):
        assert self._health_for_score(70) == "good"

    def test_health_good_at_84(self):
        assert self._health_for_score(84) == "good"

    def test_health_needs_attention_at_50(self):
        assert self._health_for_score(50) == "needs_attention"

    def test_health_critical_at_49(self):
        assert self._health_for_score(49) == "critical"

    def test_health_critical_at_0(self):
        assert self._health_for_score(0) == "critical"

    def test_system_health_contains_omega_os_score(self):
        h = _dash._get_system_health({"total": 75}, {"persistence_mode": "local_fallback"})
        assert "omega_os_score" in h
