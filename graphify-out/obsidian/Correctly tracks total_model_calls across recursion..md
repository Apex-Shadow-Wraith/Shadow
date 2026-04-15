---
source_file: "tests\test_recursive_decomposer.py"
type: "rationale"
community: "ESV Bible Processor"
location: "L209"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/ESV_Bible_Processor
---

# Correctly tracks total_model_calls across recursion.

## Connections
- [[.test_tracks_total_model_calls()]] - `rationale_for` [EXTRACTED]
- [[DecompositionResult]] - `uses` [INFERRED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[SubProblem]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/ESV_Bible_Processor