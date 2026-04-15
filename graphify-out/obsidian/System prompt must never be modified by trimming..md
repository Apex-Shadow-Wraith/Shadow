---
source_file: "tests\test_context_manager.py"
type: "rationale"
community: "Context Compression"
location: "L249"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# System prompt must never be modified by trimming.

## Connections
- [[.test_preserves_system_prompt_always()]] - `rationale_for` [EXTRACTED]
- [[ContextManager]] - `uses` [INFERRED]
- [[TokenBreakdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression