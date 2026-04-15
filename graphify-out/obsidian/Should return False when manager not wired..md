---
source_file: "tests\test_base_module_capabilities.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L129"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Should return False when manager not wired.

## Connections
- [[.test_is_module_available_without_manager()]] - `rationale_for` [EXTRACTED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API