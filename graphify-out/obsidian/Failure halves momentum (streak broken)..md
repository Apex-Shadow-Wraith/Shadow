---
source_file: "tests\test_operational_state.py"
type: "rationale"
community: "Async Task Queue"
location: "L101"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Failure halves momentum (streak broken).

## Connections
- [[.test_failure_breaks_momentum()]] - `rationale_for` [EXTRACTED]
- [[OperationalState]] - `uses` [INFERRED]
- [[StateSnapshot]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue