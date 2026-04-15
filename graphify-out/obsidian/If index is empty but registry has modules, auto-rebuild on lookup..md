---
source_file: "tests\test_tool_loader.py"
type: "rationale"
community: "Async Task Queue"
location: "L307"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# If index is empty but registry has modules, auto-rebuild on lookup.

## Connections
- [[.test_auto_refresh_on_empty_index()]] - `rationale_for` [EXTRACTED]
- [[DynamicToolLoader]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue