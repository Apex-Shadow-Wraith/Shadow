---
source_file: "tests\test_async_wiring.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L331"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# /task <id> shows completed status after worker finishes.

## Connections
- [[.test_task_status_via_cli_after_completion()]] - `rationale_for` [EXTRACTED]
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API