---
source_file: "tests\test_base_module_capabilities.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L142"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Tests that state methods properly delegate to ModuleStateManager.

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[TestStateAwarenessDelegation]] - `rationale_for` [EXTRACTED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API