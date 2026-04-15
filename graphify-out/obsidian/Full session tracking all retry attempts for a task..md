---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L206"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Full session tracking all retry attempts for a task.

## Connections
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[RetrySession]] - `rationale_for` [EXTRACTED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine