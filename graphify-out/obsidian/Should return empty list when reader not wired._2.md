---
source_file: "tests\test_base_module_capabilities.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L76"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Should return empty list when reader not wired.

## Connections
- [[.test_browse_category_without_reader()]] - `rationale_for` [EXTRACTED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API