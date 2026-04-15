---
source_file: "tests\test_message_bus.py"
type: "code"
community: "Async Task Queue"
location: "L516"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# test_full_flow_sentinel_to_omen()

## Connections
- [[.get_conversation()]] - `calls` [INFERRED]
- [[.get_message_status()]] - `calls` [INFERRED]
- [[.receive()]] - `calls` [INFERRED]
- [[.reply()]] - `calls` [INFERRED]
- [[.send()]] - `calls` [INFERRED]
- [[Full integration Sentinel sends request, Omen receives, replies, Sentinel gets]] - `rationale_for` [EXTRACTED]
- [[make_message()]] - `calls` [EXTRACTED]
- [[test_message_bus.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Async_Task_Queue