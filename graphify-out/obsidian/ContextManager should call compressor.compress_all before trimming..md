---
source_file: "tests\test_context_compressor.py"
type: "rationale"
community: "Context Compression"
location: "L372"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# ContextManager should call compressor.compress_all before trimming.

## Connections
- [[.test_context_manager_calls_compressor_before_trimming()]] - `rationale_for` [EXTRACTED]
- [[ContextCompressor]] - `uses` [INFERRED]
- [[ContextManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression