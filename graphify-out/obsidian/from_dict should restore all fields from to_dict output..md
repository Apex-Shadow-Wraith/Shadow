---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L72"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# from_dict should restore all fields from to_dict output.

## Connections
- [[.test_from_dict_roundtrip()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager