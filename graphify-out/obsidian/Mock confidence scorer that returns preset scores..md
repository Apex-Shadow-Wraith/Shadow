---
source_file: "tests\test_recursive_decomposer.py"
type: "rationale"
community: "ESV Bible Processor"
location: "L37"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/ESV_Bible_Processor
---

# Mock confidence scorer that returns preset scores.

## Connections
- [[DecompositionResult]] - `uses` [INFERRED]
- [[FakeConfidenceScorer]] - `rationale_for` [EXTRACTED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[SubProblem]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/ESV_Bible_Processor