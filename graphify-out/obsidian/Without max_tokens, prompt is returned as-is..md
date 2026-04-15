---
source_file: "tests\test_context_compressor.py"
type: "rationale"
community: "Context Compression"
location: "L242"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Context_Compression
---

# Without max_tokens, prompt is returned as-is.

## Connections
- [[.test_returns_unchanged_no_max_tokens()]] - `rationale_for` [EXTRACTED]
- [[ContextCompressor]] - `uses` [INFERRED]
- [[ContextManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Context_Compression