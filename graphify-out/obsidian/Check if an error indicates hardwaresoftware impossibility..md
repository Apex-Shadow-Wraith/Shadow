---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L773"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Check if an error indicates hardware/software impossibility.

## Connections
- [[._is_impossibility()]] - `rationale_for` [EXTRACTED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine