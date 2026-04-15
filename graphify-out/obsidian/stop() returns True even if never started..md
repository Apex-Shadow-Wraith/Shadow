---
source_file: "tests\test_introspection_dashboard.py"
type: "rationale"
community: "Introspection Dashboard"
location: "L210"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Introspection_Dashboard
---

# stop() returns True even if never started.

## Connections
- [[.test_stop_when_not_started()]] - `rationale_for` [EXTRACTED]
- [[DashboardHandler]] - `uses` [INFERRED]
- [[IntrospectionDashboard]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Introspection_Dashboard