---
source_file: "tests\test_model_evaluator.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L242"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# benchmark_model runs warmup + 8 prompts = 9 calls.

## Connections
- [[.test_with_warmup()]] - `rationale_for` [EXTRACTED]
- [[ModelEvaluator]] - `uses` [INFERRED]
- [[Omen]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)