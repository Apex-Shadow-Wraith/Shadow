"""Tests for the Real-Time Introspection Dashboard."""

import json
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from modules.shadow.introspection_dashboard import (
    IntrospectionDashboard,
    DashboardHandler,
    MODULE_CODENAMES,
)


class TestGetDashboardData(unittest.TestCase):
    """Tests for get_dashboard_data()."""

    def test_returns_valid_dict_with_all_sections(self):
        """Dashboard data contains every expected top-level key."""
        dash = IntrospectionDashboard()
        data = dash.get_dashboard_data()
        expected_keys = {
            "timestamp", "module_states", "operational_state",
            "context_window", "confidence", "recent_tasks",
            "grimoire_stats", "active_lora", "retry_engine",
        }
        self.assertEqual(set(data.keys()), expected_keys)

    def test_timestamp_is_recent(self):
        """Timestamp should be close to current time."""
        dash = IntrospectionDashboard()
        data = dash.get_dashboard_data()
        self.assertAlmostEqual(data["timestamp"], time.time(), delta=2)

    def test_graceful_when_no_orchestrator(self):
        """All sections return safe defaults when orchestrator is None."""
        dash = IntrospectionDashboard(orchestrator=None)
        data = dash.get_dashboard_data()
        # module_states should list all 13 modules
        self.assertEqual(len(data["module_states"]), 13)
        for name in MODULE_CODENAMES:
            self.assertIn(name, data["module_states"])
            self.assertEqual(data["module_states"][name]["status"], "unknown")
        # operational_state defaults
        self.assertEqual(data["operational_state"]["frustration"], 0.0)
        self.assertEqual(data["operational_state"]["overall_health"], 0.0)
        # confidence defaults
        self.assertEqual(data["confidence"]["direction"], "unknown")
        # recent_tasks empty
        self.assertEqual(data["recent_tasks"], [])
        # grimoire defaults
        self.assertEqual(data["grimoire_stats"]["total_entries"], 0)
        # lora default
        self.assertEqual(data["active_lora"], "none")
        # retry default
        self.assertEqual(data["retry_engine"]["active_sessions"], 0)

    def test_module_states_from_registry(self):
        """Module states are populated from orchestrator.registry.list_modules()."""
        orch = MagicMock()
        orch.registry.list_modules.return_value = [
            {"name": "omen", "status": "busy", "current_task": "code generation"},
            {"name": "shadow", "status": "idle"},
        ]
        dash = IntrospectionDashboard(orchestrator=orch)
        data = dash.get_dashboard_data()
        self.assertEqual(data["module_states"]["omen"]["status"], "busy")
        self.assertEqual(data["module_states"]["omen"]["current_task"], "code generation")
        self.assertEqual(data["module_states"]["shadow"]["status"], "idle")
        # Missing modules default to unknown
        self.assertEqual(data["module_states"]["cerberus"]["status"], "unknown")

    def test_operational_state_from_orchestrator(self):
        """Operational state values come from orchestrator.operational_state."""
        orch = MagicMock()
        snapshot = MagicMock()
        snapshot.frustration = 0.12
        snapshot.confidence_momentum = 0.85
        snapshot.curiosity = 0.3
        snapshot.fatigue = 0.2
        snapshot.overall_health = 0.91
        orch.operational_state.get_current_state.return_value = snapshot
        dash = IntrospectionDashboard(orchestrator=orch)
        data = dash.get_dashboard_data()
        self.assertAlmostEqual(data["operational_state"]["frustration"], 0.12)
        self.assertAlmostEqual(data["operational_state"]["confidence_momentum"], 0.85)
        self.assertAlmostEqual(data["operational_state"]["overall_health"], 0.91)

    def test_context_window_from_profiler(self):
        """Context window stats come from context_profiler.get_usage_stats()."""
        orch = MagicMock()
        orch.context_profiler.get_usage_stats.return_value = {
            "last_usage_percent": 52.3,
            "avg_usage_percent": 48.1,
            "tokens_used": 67000,
            "token_limit": 128000,
        }
        dash = IntrospectionDashboard(orchestrator=orch)
        data = dash.get_dashboard_data()
        self.assertAlmostEqual(data["context_window"]["last_usage_percent"], 52.3)
        self.assertEqual(data["context_window"]["tokens_used"], 67000)

    def test_confidence_from_calibrator(self):
        """Confidence section comes from confidence_calibrator."""
        orch = MagicMock()
        orch.confidence_calibrator.get_calibration_summary.return_value = {
            "calibration_error": 0.08,
            "direction": "well_calibrated",
        }
        dash = IntrospectionDashboard(orchestrator=orch)
        data = dash.get_dashboard_data()
        self.assertAlmostEqual(data["confidence"]["calibration_error"], 0.08)
        self.assertEqual(data["confidence"]["direction"], "well_calibrated")

    def test_recent_tasks_from_scorer(self):
        """Recent tasks are fetched from confidence_scorer when task_tracker absent."""
        orch = MagicMock()
        orch._task_tracker = None
        orch.confidence_scorer.get_scoring_history.return_value = [
            {"task": "lint code", "module": "omen", "confidence": 0.85, "duration": 2.3, "success": True},
        ]
        dash = IntrospectionDashboard(orchestrator=orch)
        data = dash.get_dashboard_data()
        self.assertEqual(len(data["recent_tasks"]), 1)
        self.assertEqual(data["recent_tasks"][0]["module"], "omen")

    def test_grimoire_stats_from_module(self):
        """Grimoire stats come from grimoire module's get_stats()."""
        orch = MagicMock()
        grimoire_mod = MagicMock()
        grimoire_mod.get_stats.return_value = {
            "total_entries": 18610,
            "recent_queries": 45,
            "avg_relevance": 0.72,
        }
        orch.registry.get_module.return_value = grimoire_mod
        dash = IntrospectionDashboard(orchestrator=orch)
        data = dash.get_dashboard_data()
        self.assertEqual(data["grimoire_stats"]["total_entries"], 18610)

    def test_active_lora_from_manager(self):
        """Active LoRA comes from lora_manager.get_active()."""
        orch = MagicMock()
        orch.lora_manager.get_active.return_value = "ethics_lora"
        dash = IntrospectionDashboard(orchestrator=orch)
        data = dash.get_dashboard_data()
        self.assertEqual(data["active_lora"], "ethics_lora")

    def test_retry_engine_from_orchestrator(self):
        """Retry engine stats come from retry_engine.get_status()."""
        orch = MagicMock()
        orch.retry_engine.get_status.return_value = {
            "active_sessions": 2,
            "recent_escalations": 1,
        }
        dash = IntrospectionDashboard(orchestrator=orch)
        data = dash.get_dashboard_data()
        self.assertEqual(data["retry_engine"]["active_sessions"], 2)
        self.assertEqual(data["retry_engine"]["recent_escalations"], 1)


class TestRenderDashboard(unittest.TestCase):
    """Tests for render_dashboard()."""

    def setUp(self):
        self.dash = IntrospectionDashboard()
        self.html = self.dash.render_dashboard()

    def test_returns_html_string(self):
        """render_dashboard returns a non-empty HTML string."""
        self.assertIsInstance(self.html, str)
        self.assertIn("<!DOCTYPE html>", self.html)
        self.assertIn("</html>", self.html)

    def test_contains_auto_refresh_javascript(self):
        """HTML contains setInterval for auto-refresh."""
        self.assertIn("setInterval", self.html)
        self.assertIn("fetch(\"/api/state\")", self.html)
        self.assertIn("5000", self.html)

    def test_contains_all_13_module_names(self):
        """HTML/JS references all 13 module codenames."""
        for name in MODULE_CODENAMES:
            self.assertIn(name, self.html)

    def test_dark_theme_css(self):
        """Dashboard uses dark theme with Shadow's color scheme."""
        self.assertIn("#0a0a0a", self.html)  # dark background
        self.assertIn("#d4af37", self.html)  # gold accent


class TestStartStopLifecycle(unittest.TestCase):
    """Tests for start() and stop()."""

    def test_start_and_stop(self):
        """Dashboard can start and stop without error."""
        dash = IntrospectionDashboard(port=18377)
        try:
            result = dash.start()
            self.assertTrue(result)
            self.assertIsNotNone(dash._server)
            self.assertIsNotNone(dash._thread)
            self.assertTrue(dash._thread.daemon)
            self.assertIsNotNone(dash._start_time)
        finally:
            dash.stop()
            self.assertIsNone(dash._server)

    def test_stop_when_not_started(self):
        """stop() returns True even if never started."""
        dash = IntrospectionDashboard()
        self.assertTrue(dash.stop())

    def test_port_configurable(self):
        """Port is configurable via constructor."""
        dash = IntrospectionDashboard(port=9999)
        self.assertEqual(dash.port, 9999)

    @patch("modules.shadow.introspection_dashboard.HTTPServer", side_effect=OSError("port in use"))
    def test_start_failure_returns_false(self, _mock):
        """start() returns False if the server can't bind."""
        dash = IntrospectionDashboard()
        self.assertFalse(dash.start())


class TestHealthEndpoint(unittest.TestCase):
    """Test /api/health returns correct data."""

    def test_health_includes_uptime(self):
        """Health check returns status and uptime."""
        dash = IntrospectionDashboard(port=18378)
        try:
            dash.start()
            time.sleep(0.1)
            import urllib.request
            resp = urllib.request.urlopen(f"http://localhost:18378/api/health")
            data = json.loads(resp.read())
            self.assertEqual(data["status"], "ok")
            self.assertIn("uptime", data)
            self.assertGreaterEqual(data["uptime"], 0)
        finally:
            dash.stop()

    def test_api_state_returns_json(self):
        """/api/state returns valid JSON with all sections."""
        dash = IntrospectionDashboard(port=18379)
        try:
            dash.start()
            time.sleep(0.1)
            import urllib.request
            resp = urllib.request.urlopen(f"http://localhost:18379/api/state")
            data = json.loads(resp.read())
            self.assertIn("module_states", data)
            self.assertIn("timestamp", data)
        finally:
            dash.stop()


if __name__ == "__main__":
    unittest.main()
