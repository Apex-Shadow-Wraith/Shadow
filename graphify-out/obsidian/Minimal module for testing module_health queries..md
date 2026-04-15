---
source_file: "tests\test_shadow_module.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L19"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# Minimal module for testing module_health queries.

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[HealthMock]] - `rationale_for` [EXTRACTED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[ShadowModule]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools