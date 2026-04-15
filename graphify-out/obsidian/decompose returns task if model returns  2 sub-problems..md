---
source_file: "tests\test_recursive_decomposer.py"
type: "rationale"
community: "ESV Bible Processor"
location: "L71"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/ESV_Bible_Processor
---

# decompose: returns [task] if model returns < 2 sub-problems.

## Connections
- [[.test_returns_task_if_cannot_decompose()]] - `rationale_for` [EXTRACTED]
- [[DecompositionResult]] - `uses` [INFERRED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[SubProblem]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/ESV_Bible_Processor