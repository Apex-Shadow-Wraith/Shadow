---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L375"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Tests for concurrent access.

## Connections
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]
- [[TestThreadSafety]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager