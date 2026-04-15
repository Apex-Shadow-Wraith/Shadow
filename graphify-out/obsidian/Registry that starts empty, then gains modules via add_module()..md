---
source_file: "tests\test_tool_loader.py"
type: "rationale"
community: "Async Task Queue"
location: "L228"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Registry that starts empty, then gains modules via add_module().

## Connections
- [[DynamicToolLoader]] - `uses` [INFERRED]
- [[_DeferredRegistry]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue