---
source_file: "tests\test_message_bus.py"
type: "code"
community: "Async Task Queue"
location: "L402"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Async_Task_Queue
---

# test_sqlite_persistence()

## Connections
- [[.close()_19]] - `calls` [INFERRED]
- [[.execute()_30]] - `calls` [EXTRACTED]
- [[.initialize()_31]] - `calls` [EXTRACTED]
- [[.receive()]] - `calls` [INFERRED]
- [[.reset()]] - `calls` [INFERRED]
- [[.send()]] - `calls` [INFERRED]
- [[.shutdown()_28]] - `calls` [EXTRACTED]
- [[MessageBus]] - `calls` [INFERRED]
- [[Messages persist in SQLite and can be recovered after bus restart.]] - `rationale_for` [EXTRACTED]
- [[make_message()]] - `calls` [EXTRACTED]
- [[make_registry()]] - `calls` [EXTRACTED]
- [[test_message_bus.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Async_Task_Queue