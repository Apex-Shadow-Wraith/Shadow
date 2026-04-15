---
source_file: "tests\test_introspection_dashboard.py"
type: "rationale"
community: "Introspection Dashboard"
location: "L142"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Introspection_Dashboard
---

# Active LoRA comes from lora_manager.get_active().

## Connections
- [[.test_active_lora_from_manager()]] - `rationale_for` [EXTRACTED]
- [[DashboardHandler]] - `uses` [INFERRED]
- [[IntrospectionDashboard]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Introspection_Dashboard