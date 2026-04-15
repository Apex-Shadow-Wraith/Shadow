---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L223"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# 12-attempt retry cycle with strategy rotation and Apex escalation-learning.

## Connections
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[RetryEngine]] - `rationale_for` [EXTRACTED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine