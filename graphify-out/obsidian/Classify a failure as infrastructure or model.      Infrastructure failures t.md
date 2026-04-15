---
source_file: "modules\shadow\retry_engine.py"
type: "rationale"
community: "Retry Engine"
location: "L69"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Retry_Engine
---

# Classify a failure as infrastructure or model.      Infrastructure failures: t

## Connections
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[classify_failure()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Retry_Engine