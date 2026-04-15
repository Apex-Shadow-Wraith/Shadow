---
source_file: "tests\test_async_tasks.py"
type: "rationale"
community: "Async Task Queue"
location: "L261"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# After a failure, the worker should still process the next task.

## Connections
- [[.test_failed_task_doesnt_crash_worker()]] - `rationale_for` [EXTRACTED]
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue