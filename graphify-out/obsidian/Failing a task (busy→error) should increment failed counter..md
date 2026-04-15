---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L116"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Failing a task (busy→error) should increment failed counter.

## Connections
- [[.test_busy_to_error_increments_failed()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager