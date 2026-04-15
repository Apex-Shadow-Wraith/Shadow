---
source_file: "tests\test_task_queue.py"
type: "rationale"
community: "Async Task Queue"
location: "L40"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Helper to create a QueuedTask.

## Connections
- [[ModuleStatus]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[QueuedTask]] - `uses` [INFERRED]
- [[QueuedTaskStatus]] - `uses` [INFERRED]
- [[TaskChainEngine]] - `uses` [INFERRED]
- [[TaskKind]] - `uses` [INFERRED]
- [[TaskSource]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[_make_task()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue