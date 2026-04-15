---
source_file: "modules\shadow\context_manager.py"
type: "rationale"
community: "Context Compression"
location: "L569"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# Check if adding a new turn would push context over limit.          Returns Tru

## Connections
- [[.check_history_overflow()]] - `rationale_for` [EXTRACTED]
- [[ContextCompressor]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression