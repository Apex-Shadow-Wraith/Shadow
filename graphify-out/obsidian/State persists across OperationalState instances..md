---
source_file: "tests\test_operational_state.py"
type: "rationale"
community: "Async Task Queue"
location: "L307"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# State persists across OperationalState instances.

## Connections
- [[.test_state_survives_roundtrip()]] - `rationale_for` [EXTRACTED]
- [[OperationalState]] - `uses` [INFERRED]
- [[StateSnapshot]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue