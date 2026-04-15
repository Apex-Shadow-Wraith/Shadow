---
source_file: "tests\test_async_wiring.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L383"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# no rush' should trigger async.

## Connections
- [[.test_no_rush_triggers_async()]] - `rationale_for` [EXTRACTED]
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API