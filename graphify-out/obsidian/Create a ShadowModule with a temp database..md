---
source_file: "tests\test_shadow_module.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L48"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# Create a ShadowModule with a temp database.

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[ShadowModule]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[shadow_module()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools