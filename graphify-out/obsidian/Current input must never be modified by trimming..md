---
source_file: "tests\test_context_manager.py"
type: "rationale"
community: "Context Compression"
location: "L268"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# Current input must never be modified by trimming.

## Connections
- [[.test_preserves_current_input_always()]] - `rationale_for` [EXTRACTED]
- [[ContextManager]] - `uses` [INFERRED]
- [[TokenBreakdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression