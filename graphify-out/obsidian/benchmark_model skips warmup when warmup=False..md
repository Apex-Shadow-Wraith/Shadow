---
source_file: "tests\test_model_evaluator.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L224"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# benchmark_model skips warmup when warmup=False.

## Connections
- [[.test_no_warmup()]] - `rationale_for` [EXTRACTED]
- [[ModelEvaluator]] - `uses` [INFERRED]
- [[Omen]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)