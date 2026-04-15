---
source_file: "tests\test_introspection_dashboard.py"
type: "rationale"
community: "Introspection Dashboard"
location: "L170"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Introspection_Dashboard
---

# render_dashboard returns a non-empty HTML string.

## Connections
- [[.test_returns_html_string()]] - `rationale_for` [EXTRACTED]
- [[DashboardHandler]] - `uses` [INFERRED]
- [[IntrospectionDashboard]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Introspection_Dashboard