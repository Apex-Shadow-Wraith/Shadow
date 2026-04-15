---
source_file: "tests\test_introspection_dashboard.py"
type: "rationale"
community: "Introspection Dashboard"
location: "L116"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Introspection_Dashboard
---

# Recent tasks are fetched from confidence_scorer when task_tracker absent.

## Connections
- [[.test_recent_tasks_from_scorer()]] - `rationale_for` [EXTRACTED]
- [[DashboardHandler]] - `uses` [INFERRED]
- [[IntrospectionDashboard]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Introspection_Dashboard