---
source_file: "tests\test_message_bus.py"
type: "code"
community: "Async Task Queue"
location: "L242"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# test_ttl_expiration()

## Connections
- [[.cleanup_expired()_1]] - `calls` [INFERRED]
- [[.receive()]] - `calls` [INFERRED]
- [[.send()]] - `calls` [INFERRED]
- [[Messages past their TTL are cleaned up.]] - `rationale_for` [EXTRACTED]
- [[make_message()]] - `calls` [EXTRACTED]
- [[test_message_bus.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Async_Task_Queue