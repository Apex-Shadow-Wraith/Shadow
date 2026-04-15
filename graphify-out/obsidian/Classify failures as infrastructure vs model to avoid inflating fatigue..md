---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L38"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Classify failures as infrastructure vs model to avoid inflating fatigue.

## Connections
- [[FailureType]] - `rationale_for` [EXTRACTED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine