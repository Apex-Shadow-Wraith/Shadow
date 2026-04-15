---
source_file: "modules\shadow\events.py"
type: "rationale"
community: "Async Task Queue"
location: "L75"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Pub/sub event system wrapping the MessageBus.      Modules subscribe to specific

## Connections
- [[EventSystem]] - `rationale_for` [EXTRACTED]
- [[MessageBus]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue