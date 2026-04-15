---
source_file: "modules\shadow\async_tasks.py"
type: "rationale"
community: "Async Task Queue"
location: "L1"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# AsyncTaskQueue — Async worker loop for background task execution. ==============

## Connections
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[QueuedTaskStatus]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[async_tasks.py]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue