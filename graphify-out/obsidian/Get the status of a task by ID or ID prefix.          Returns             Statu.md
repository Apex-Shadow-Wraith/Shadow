---
source_file: "modules\shadow\async_tasks.py"
type: "rationale"
community: "Async Task Queue"
location: "L146"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Get the status of a task by ID or ID prefix.          Returns:             Statu

## Connections
- [[.get_status()]] - `rationale_for` [EXTRACTED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[QueuedTaskStatus]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue