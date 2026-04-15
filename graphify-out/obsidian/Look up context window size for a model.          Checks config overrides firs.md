---
source_file: "modules\shadow\context_manager.py"
type: "rationale"
community: "Context Compression"
location: "L546"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# Look up context window size for a model.          Checks config overrides firs

## Connections
- [[.get_model_context_limit()]] - `rationale_for` [EXTRACTED]
- [[ContextCompressor]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression