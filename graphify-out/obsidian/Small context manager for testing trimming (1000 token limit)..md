---
source_file: "tests\test_context_manager.py"
type: "rationale"
community: "Context Compression"
location: "L25"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# Small context manager for testing trimming (1000 token limit).

## Connections
- [[ContextManager]] - `uses` [INFERRED]
- [[TokenBreakdown]] - `uses` [INFERRED]
- [[small_cm()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression