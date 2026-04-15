---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Async Task Queue"
location: "L303"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Restore should recover module states from snapshot.

## Connections
- [[.test_restore_recovers_state()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue