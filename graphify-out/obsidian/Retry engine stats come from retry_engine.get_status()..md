---
source_file: "tests\test_introspection_dashboard.py"
type: "rationale"
community: "Introspection Dashboard"
location: "L150"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Introspection_Dashboard
---

# Retry engine stats come from retry_engine.get_status().

## Connections
- [[.test_retry_engine_from_orchestrator()]] - `rationale_for` [EXTRACTED]
- [[DashboardHandler]] - `uses` [INFERRED]
- [[IntrospectionDashboard]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Introspection_Dashboard