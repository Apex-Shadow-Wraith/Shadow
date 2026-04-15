---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L378"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Concurrent state updates should not corrupt data.

## Connections
- [[.test_concurrent_updates_no_corruption()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager