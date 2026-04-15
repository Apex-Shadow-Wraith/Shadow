---
source_file: "tests\test_async_wiring.py"
type: "code"
community: "Async Task Queue"
location: "L247"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# TestTasksCommand

## Connections
- [[.test_tasks_command_empty_queue()]] - `method` [EXTRACTED]
- [[.test_tasks_command_shows_live_tasks()]] - `method` [EXTRACTED]
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[Verify tasks CLI command connects to the live ATQ.]] - `rationale_for` [EXTRACTED]
- [[test_async_wiring.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Async_Task_Queue