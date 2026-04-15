---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L669"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Return recent retry sessions for analytics.          Feeds into Growth Engine

## Connections
- [[.get_session_history()]] - `rationale_for` [EXTRACTED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine