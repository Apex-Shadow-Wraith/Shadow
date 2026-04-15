---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L624"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Check whether escalation to Apex is warranted.          Returns True only if:

## Connections
- [[.should_escalate()]] - `rationale_for` [EXTRACTED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine