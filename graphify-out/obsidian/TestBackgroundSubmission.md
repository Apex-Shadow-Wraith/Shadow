---
source_file: "tests\test_async_wiring.py"
type: "code"
community: "Introspection Dashboard"
location: "L166"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Introspection_Dashboard
---

# TestBackgroundSubmission

## Connections
- [[.test_should_run_async_false_without_queue()]] - `method` [EXTRACTED]
- [[.test_should_run_async_with_background_flag()]] - `method` [EXTRACTED]
- [[.test_submit_task_returns_id_immediately()]] - `method` [EXTRACTED]
- [[AsyncTaskQueue]] - `uses` [INFERRED]
- [[BaseModule]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[PriorityTaskQueue]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[Verify _should_run_async returns True and task is routed to queue.]] - `rationale_for` [EXTRACTED]
- [[test_async_wiring.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Introspection_Dashboard