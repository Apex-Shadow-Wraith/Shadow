---
source_file: "tests\test_sentinel.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L20"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Inject a fake psutil module so Sentinel's local imports work.

## Connections
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Sentinel]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[fake_psutil()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API