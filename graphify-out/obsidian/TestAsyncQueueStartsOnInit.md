---
source_file: "tests\test_async_wiring.py"
type: "code"
community: "Async Task Queue"
location: "L108"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# TestAsyncQueueStartsOnInit

## Connections
- [[.test_async_task_queue_property_accessible()]] - `method` [EXTRACTED]
- [[.test_orchestrator_has_async_task_queue_after_startup()]] - `method` [EXTRACTED]
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[Verify the startup() path in main.py initializes the ATQ.]] - `rationale_for` [EXTRACTED]
- [[test_async_wiring.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Async_Task_Queue