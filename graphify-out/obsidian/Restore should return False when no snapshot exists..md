---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Async Task Queue"
location: "L326"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Restore should return False when no snapshot exists.

## Connections
- [[.test_restore_missing_file()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue