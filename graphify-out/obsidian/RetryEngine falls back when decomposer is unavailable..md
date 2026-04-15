---
source_file: "tests\test_recursive_decomposer.py"
type: "rationale"
community: "ESV Bible Processor"
location: "L386"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/ESV_Bible_Processor
---

# RetryEngine falls back when decomposer is unavailable.

## Connections
- [[.test_retry_engine_fallback_without_decomposer()]] - `rationale_for` [EXTRACTED]
- [[DecompositionResult]] - `uses` [INFERRED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[SubProblem]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/ESV_Bible_Processor