---
source_file: "tests\test_context_manager.py"
type: "rationale"
community: "Context Compression"
location: "L460"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# An input that exceeds the limit alone should return an error, not crash.

## Connections
- [[.test_enormous_single_input_returns_error()]] - `rationale_for` [EXTRACTED]
- [[ContextManager]] - `uses` [INFERRED]
- [[TokenBreakdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression