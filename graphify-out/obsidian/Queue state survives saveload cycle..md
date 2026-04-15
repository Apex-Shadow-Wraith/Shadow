---
source_file: "tests\test_task_queue.py"
type: "rationale"
community: "Async Task Queue"
location: "L378"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Queue state survives save/load cycle.

## Connections
- [[.test_persist_and_recover()]] - `rationale_for` [EXTRACTED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[QueuedTask]] - `uses` [INFERRED]
- [[QueuedTaskStatus]] - `uses` [INFERRED]
- [[TaskChainEngine]] - `uses` [INFERRED]
- [[TaskKind]] - `uses` [INFERRED]
- [[TaskSource]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue