---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L432"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Escalate to Apex after exhausting local strategies.          Steps:         1

## Connections
- [[.escalate_to_apex()]] - `rationale_for` [EXTRACTED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine