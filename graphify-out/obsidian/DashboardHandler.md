---
source_file: "modules\shadow\introspection_dashboard.py"
type: "code"
community: "Introspection Dashboard"
location: "L24"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Introspection_Dashboard
---

# DashboardHandler

## Connections
- [[._respond()]] - `method` [EXTRACTED]
- [[.do_GET()]] - `method` [EXTRACTED]
- [[.log_message()]] - `method` [EXTRACTED]
- [[apistate returns valid JSON with all sections.]] - `uses` [INFERRED]
- [[Active LoRA comes from lora_manager.get_active().]] - `uses` [INFERRED]
- [[All sections return safe defaults when orchestrator is None.]] - `uses` [INFERRED]
- [[BaseHTTPRequestHandler]] - `inherits` [EXTRACTED]
- [[Confidence section comes from confidence_calibrator.]] - `uses` [INFERRED]
- [[Context window stats come from context_profiler.get_usage_stats().]] - `uses` [INFERRED]
- [[Dashboard can start and stop without error.]] - `uses` [INFERRED]
- [[Dashboard data contains every expected top-level key.]] - `uses` [INFERRED]
- [[Dashboard uses dark theme with Shadow's color scheme.]] - `uses` [INFERRED]
- [[Grimoire stats come from grimoire module's get_stats().]] - `uses` [INFERRED]
- [[HTML contains setInterval for auto-refresh.]] - `uses` [INFERRED]
- [[HTMLJS references all 13 module codenames.]] - `uses` [INFERRED]
- [[HTTP request handler for the introspection dashboard.]] - `rationale_for` [EXTRACTED]
- [[Health check returns status and uptime.]] - `uses` [INFERRED]
- [[Module states are populated from orchestrator.registry.list_modules().]] - `uses` [INFERRED]
- [[Operational state values come from orchestrator.operational_state.]] - `uses` [INFERRED]
- [[Port is configurable via constructor.]] - `uses` [INFERRED]
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

#graphify/code #graphify/INFERRED #community/Introspection_Dashboard