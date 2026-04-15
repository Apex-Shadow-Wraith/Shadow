---
source_file: "tests\test_tool_loader.py"
type: "rationale"
community: "Async Task Queue"
location: "L41"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Registry with 3 modules: wraith (3 tools), omen (2 tools), grimoire (2 tools).

## Connections
- [[DynamicToolLoader]] - `uses` [INFERRED]
- [[_default_registry()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue