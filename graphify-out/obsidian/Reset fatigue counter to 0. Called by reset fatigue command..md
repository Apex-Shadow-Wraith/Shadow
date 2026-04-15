---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L664"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Reset fatigue counter to 0. Called by /reset fatigue command.

## Connections
- [[.reset_fatigue()]] - `rationale_for` [EXTRACTED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine