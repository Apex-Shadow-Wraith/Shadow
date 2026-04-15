---
source_file: "tests\test_operational_state.py"
type: "rationale"
community: "Async Task Queue"
location: "L31"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Helper to build a task_result dict.

## Connections
- [[OperationalState]] - `uses` [INFERRED]
- [[StateSnapshot]] - `uses` [INFERRED]
- [[_task()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue