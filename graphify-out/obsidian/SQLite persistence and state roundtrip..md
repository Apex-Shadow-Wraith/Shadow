---
source_file: "tests\test_operational_state.py"
type: "rationale"
community: "Async Task Queue"
location: "L304"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# SQLite persistence and state roundtrip.

## Connections
- [[OperationalState]] - `uses` [INFERRED]
- [[StateSnapshot]] - `uses` [INFERRED]
- [[TestPersistence_2]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue