---
source_file: "modules\shadow\async_tasks.py"
type: "rationale"
community: "Async Task Queue"
location: "L57"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Start the background worker loop.

## Connections
- [[.start()_1]] - `rationale_for` [EXTRACTED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[QueuedTaskStatus]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue