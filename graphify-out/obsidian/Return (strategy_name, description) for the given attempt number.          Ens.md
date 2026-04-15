---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L600"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Return (strategy_name, description) for the given attempt number.          Ens

## Connections
- [[.get_strategy_for_attempt()]] - `rationale_for` [EXTRACTED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine