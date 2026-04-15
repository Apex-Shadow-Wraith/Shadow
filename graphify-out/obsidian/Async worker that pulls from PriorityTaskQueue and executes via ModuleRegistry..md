---
source_file: "modules\shadow\async_tasks.py"
type: "rationale"
community: "Async Task Queue"
location: "L33"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Async worker that pulls from PriorityTaskQueue and executes via ModuleRegistry.

## Connections
- [[AsyncTaskQueue]] - `rationale_for` [EXTRACTED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[QueuedTaskStatus]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue