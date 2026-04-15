---
source_file: "tests\test_base_module_capabilities.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L133"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Should return 'unknown' when manager not wired.

## Connections
- [[.test_get_module_status_without_manager()]] - `rationale_for` [EXTRACTED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API