---
source_file: "tests\test_async_tasks.py"
type: "rationale"
community: "Async Task Queue"
location: "L532"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# If Grimoire storage fails, the worker should continue processing.

## Connections
- [[.test_grimoire_failure_does_not_crash_worker()]] - `rationale_for` [EXTRACTED]
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue