---
source_file: "tests\test_context_manager.py"
type: "rationale"
community: "Context Compression"
location: "L443"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# Even with huge inputs, the assembled context must fit.

## Connections
- [[.test_output_fits_within_max_tokens()]] - `rationale_for` [EXTRACTED]
- [[ContextManager]] - `uses` [INFERRED]
- [[TokenBreakdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression