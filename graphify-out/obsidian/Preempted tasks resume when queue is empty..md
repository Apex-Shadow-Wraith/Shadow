---
source_file: "tests\test_task_queue.py"
type: "rationale"
community: "Async Task Queue"
location: "L202"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Preempted tasks resume when queue is empty.

## Connections
- [[.test_preempted_task_resumes()]] - `rationale_for` [EXTRACTED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[QueuedTask]] - `uses` [INFERRED]
- [[QueuedTaskStatus]] - `uses` [INFERRED]
- [[TaskChainEngine]] - `uses` [INFERRED]
- [[TaskKind]] - `uses` [INFERRED]
- [[TaskSource]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue