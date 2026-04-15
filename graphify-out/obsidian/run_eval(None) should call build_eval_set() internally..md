---
source_file: "tests\test_embedding_evaluator.py"
type: "rationale"
community: "Embedding Evaluator"
location: "L238"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Embedding_Evaluator
---

# run_eval(None) should call build_eval_set() internally.

## Connections
- [[.test_auto_builds_eval_set_when_none()]] - `rationale_for` [EXTRACTED]
- [[EmbeddingEvaluator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Embedding_Evaluator