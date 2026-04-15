---
source_file: "tests\test_message_bus.py"
type: "code"
community: "Async Task Queue"
location: "L189"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Async_Task_Queue
---

# test_priority_ordering()

## Connections
- [[.receive()]] - `calls` [INFERRED]
- [[.send()]] - `calls` [INFERRED]
- [[Messages are delivered sorted by priority (1 first), then timestamp.]] - `rationale_for` [EXTRACTED]
- [[make_message()]] - `calls` [EXTRACTED]
- [[test_message_bus.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Async_Task_Queue