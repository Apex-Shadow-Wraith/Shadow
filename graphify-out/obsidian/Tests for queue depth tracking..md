---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L350"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Tests for queue depth tracking.

## Connections
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]
- [[TestQueueManagement]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager