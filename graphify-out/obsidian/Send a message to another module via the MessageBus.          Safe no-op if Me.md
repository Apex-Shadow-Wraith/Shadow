---
source_file: "modules\base.py"
type: "rationale"
community: "Async Task Queue"
location: "L149"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Send a message to another module via the MessageBus.          Safe no-op if Me

## Connections
- [[.send_message()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]
- [[GrimoireReader]] - `uses` [INFERRED]
- [[ModuleMessage]] - `uses` [INFERRED]
- [[ModuleStateManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue