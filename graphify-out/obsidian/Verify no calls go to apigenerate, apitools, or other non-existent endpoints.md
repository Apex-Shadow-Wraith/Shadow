---
source_file: "tests\test_omen.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L741"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Verify no calls go to /api/generate, /api/tools, or other non-existent endpoints

## Connections
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Omen]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API