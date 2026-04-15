---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L201"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Should return None for capabilities no module has.

## Connections
- [[.test_returns_none_for_unknown_capability()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager