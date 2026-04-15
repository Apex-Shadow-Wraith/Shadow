---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L408"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Concurrent queue operations should maintain consistency.

## Connections
- [[.test_concurrent_queue_operations()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager