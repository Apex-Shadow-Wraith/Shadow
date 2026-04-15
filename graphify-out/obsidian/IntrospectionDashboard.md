---
source_file: "modules\shadow\introspection_dashboard.py"
type: "code"
community: "Introspection Dashboard"
location: "L55"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Introspection_Dashboard
---

# IntrospectionDashboard

## Connections
- [[.__init__()_69]] - `method` [EXTRACTED]
- [[._get_active_lora()]] - `method` [EXTRACTED]
- [[._get_confidence()]] - `method` [EXTRACTED]
- [[._get_context_window()]] - `method` [EXTRACTED]
- [[._get_grimoire_stats()]] - `method` [EXTRACTED]
- [[._get_module_states()]] - `method` [EXTRACTED]
- [[._get_operational_state()]] - `method` [EXTRACTED]
- [[._get_recent_tasks()]] - `method` [EXTRACTED]
- [[._get_retry_engine()]] - `method` [EXTRACTED]
- [[.get_dashboard_data()]] - `method` [EXTRACTED]
- [[.render_dashboard()]] - `method` [EXTRACTED]
- [[.setUp()]] - `calls` [INFERRED]
- [[.start()_2]] - `method` [EXTRACTED]
- [[.stop()_2]] - `method` [EXTRACTED]
- [[.test_active_lora_from_manager()]] - `calls` [INFERRED]
- [[.test_api_state_returns_json()]] - `calls` [INFERRED]
- [[.test_confidence_from_calibrator()]] - `calls` [INFERRED]
- [[.test_context_window_from_profiler()]] - `calls` [INFERRED]
- [[.test_graceful_when_no_orchestrator()]] - `calls` [INFERRED]
- [[.test_grimoire_stats_from_module()]] - `calls` [INFERRED]
- [[.test_health_includes_uptime()]] - `calls` [INFERRED]
- [[.test_module_states_from_registry()]] - `calls` [INFERRED]
- [[.test_operational_state_from_orchestrator()]] - `calls` [INFERRED]
- [[.test_port_configurable()]] - `calls` [INFERRED]
- [[.test_recent_tasks_from_scorer()]] - `calls` [INFERRED]
- [[.test_retry_engine_from_orchestrator()]] - `calls` [INFERRED]
- [[.test_returns_valid_dict_with_all_sections()]] - `calls` [INFERRED]
- [[.test_start_and_stop()]] - `calls` [INFERRED]
- [[.test_stop_when_not_started()]] - `calls` [INFERRED]
- [[.test_timestamp_is_recent()]] - `calls` [INFERRED]
- [[apistate returns valid JSON with all sections.]] - `uses` [INFERRED]
- [[Active LoRA comes from lora_manager.get_active().]] - `uses` [INFERRED]
- [[All sections return safe defaults when orchestrator is None.]] - `uses` [INFERRED]
- [[Confidence section comes from confidence_calibrator.]] - `uses` [INFERRED]
- [[Context window stats come from context_profiler.get_usage_stats().]] - `uses` [INFERRED]
- [[Dashboard can start and stop without error.]] - `uses` [INFERRED]
- [[Dashboard data contains every expected top-level key.]] - `uses` [INFERRED]
- [[Dashboard uses dark theme with Shadow's color scheme.]] - `uses` [INFERRED]
- [[Grimoire stats come from grimoire module's get_stats().]] - `uses` [INFERRED]
- [[HTML contains setInterval for auto-refresh.]] - `uses` [INFERRED]
- [[HTMLJS references all 13 module codenames.]] - `uses` [INFERRED]
- [[Health check returns status and uptime.]] - `uses` [INFERRED]
- [[Module states are populated from orchestrator.registry.list_modules().]] - `uses` [INFERRED]
- [[Operational state values come from orchestrator.operational_state.]] - `uses` [INFERRED]
- [[Port is configurable via constructor.]] - `uses` [INFERRED]
- [[Real-time web dashboard for Shadow's internal state.      Runs a lightweight HTT]] - `rationale_for` [EXTRACTED]
- [[Recent tasks are fetched from confidence_scorer when task_tracker absent.]] - `uses` [INFERRED]
- [[Retry engine stats come from retry_engine.get_status().]] - `uses` [INFERRED]
- [[Test apihealth returns correct data.]] - `uses` [INFERRED]
- [[TestGetDashboardData]] - `uses` [INFERRED]
- [[TestHealthEndpoint]] - `uses` [INFERRED]
- [[TestRenderDashboard]] - `uses` [INFERRED]
- [[TestStartStopLifecycle]] - `uses` [INFERRED]
- [[Tests for get_dashboard_data().]] - `uses` [INFERRED]
- [[Tests for render_dashboard().]] - `uses` [INFERRED]
- [[Tests for start() and stop().]] - `uses` [INFERRED]
- [[Tests for the Real-Time Introspection Dashboard.]] - `uses` [INFERRED]
- [[Timestamp should be close to current time.]] - `uses` [INFERRED]
- [[introspection_dashboard.py]] - `contains` [EXTRACTED]
- [[render_dashboard returns a non-empty HTML string.]] - `uses` [INFERRED]
- [[start() returns False if the server can't bind.]] - `uses` [INFERRED]
- [[stop() returns True even if never started.]] - `uses` [INFERRED]
- [[test_start_failure_returns_false()]] - `calls` [INFERRED]

#graphify/code #graphify/INFERRED #community/Introspection_Dashboard