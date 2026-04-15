---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L332"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Tests for daily counter reset.

## Connections
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]
- [[TestDailyReset]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager