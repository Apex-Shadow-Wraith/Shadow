---
source_file: "tests\test_base_module_capabilities.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L126"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Tests that state methods gracefully degrade when manager not wired.

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[TestStateAwarenessGracefulDegradation]] - `rationale_for` [EXTRACTED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API