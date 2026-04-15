---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L109"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Completing a task (busy→idle) should increment completed counter.

## Connections
- [[.test_busy_to_idle_increments_completed()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager