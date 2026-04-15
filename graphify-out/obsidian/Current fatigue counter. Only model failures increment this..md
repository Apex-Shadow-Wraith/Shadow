---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Async Task Queue"
location: "L660"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Current fatigue counter. Only model failures increment this.

## Connections
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue