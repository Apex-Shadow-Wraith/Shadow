---
source_file: "tests\test_async_wiring.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L313"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# A completed task should have a retrievable result.

## Connections
- [[.test_completed_task_has_result()]] - `rationale_for` [EXTRACTED]
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API