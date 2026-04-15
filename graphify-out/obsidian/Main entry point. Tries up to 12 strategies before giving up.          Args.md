---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L261"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Main entry point. Tries up to 12 strategies before giving up.          Args:

## Connections
- [[.attempt_task()]] - `rationale_for` [EXTRACTED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine