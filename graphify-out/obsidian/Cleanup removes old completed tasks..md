---
source_file: "tests\test_task_queue.py"
type: "rationale"
community: "Async Task Queue"
location: "L345"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Cleanup removes old completed tasks.

## Connections
- [[.test_cleanup_old_completed()]] - `rationale_for` [EXTRACTED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[QueuedTask]] - `uses` [INFERRED]
- [[QueuedTaskStatus]] - `uses` [INFERRED]
- [[TaskChainEngine]] - `uses` [INFERRED]
- [[TaskKind]] - `uses` [INFERRED]
- [[TaskSource]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue