---
source_file: "tests\test_context_manager.py"
type: "rationale"
community: "Context Compression"
location: "L182"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# With a 500 token limit, a big history should trigger trimming.

## Connections
- [[.test_triggers_trim_when_over_limit()]] - `rationale_for` [EXTRACTED]
- [[ContextManager]] - `uses` [INFERRED]
- [[TokenBreakdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression