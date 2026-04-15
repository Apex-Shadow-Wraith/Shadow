---
source_file: "tests\test_async_wiring.py"
type: "code"
community: "Async Task Queue"
location: "L290"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# TestTaskCompletion

## Connections
- [[.test_completed_task_has_result()]] - `method` [EXTRACTED]
- [[.test_submitted_task_completes()]] - `method` [EXTRACTED]
- [[.test_task_status_via_cli_after_completion()]] - `method` [EXTRACTED]
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[Verify that submitted tasks are processed by the worker.]] - `rationale_for` [EXTRACTED]
- [[test_async_wiring.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Async_Task_Queue