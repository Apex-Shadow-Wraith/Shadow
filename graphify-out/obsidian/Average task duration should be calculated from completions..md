---
source_file: "tests\test_module_state.py"
type: "rationale"
community: "Module State Manager"
location: "L150"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_State_Manager
---

# Average task duration should be calculated from completions.

## Connections
- [[.test_avg_task_duration_calculated()]] - `rationale_for` [EXTRACTED]
- [[ModuleState]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_State_Manager