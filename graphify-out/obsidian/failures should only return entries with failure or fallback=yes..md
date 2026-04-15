---
source_file: "tests\test_operational_history.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L264"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# /failures should only return entries with failure or fallback=yes.

## Connections
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API