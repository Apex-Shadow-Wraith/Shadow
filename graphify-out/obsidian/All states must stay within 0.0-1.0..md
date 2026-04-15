---
source_file: "tests\test_operational_state.py"
type: "rationale"
community: "Async Task Queue"
location: "L157"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# All states must stay within 0.0-1.0.

## Connections
- [[.test_states_clamped_to_bounds()]] - `rationale_for` [EXTRACTED]
- [[OperationalState]] - `uses` [INFERRED]
- [[StateSnapshot]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue