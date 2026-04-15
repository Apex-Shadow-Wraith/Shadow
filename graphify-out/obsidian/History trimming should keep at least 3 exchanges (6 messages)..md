---
source_file: "tests\test_context_manager.py"
type: "rationale"
community: "Context Compression"
location: "L305"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# History trimming should keep at least 3 exchanges (6 messages).

## Connections
- [[.test_drops_oldest_history_keeps_last_3()]] - `rationale_for` [EXTRACTED]
- [[ContextManager]] - `uses` [INFERRED]
- [[TokenBreakdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression