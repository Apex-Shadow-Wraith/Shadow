---
source_file: "tests\test_recursive_decomposer.py"
type: "code"
community: "ESV Bible Processor"
location: "L36"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/ESV_Bible_Processor
---

# FakeConfidenceScorer

## Connections
- [[.__init__()_120]] - `method` [EXTRACTED]
- [[.score_response()_2]] - `method` [EXTRACTED]
- [[.test_all_sub_problems_fail_returns_best()]] - `calls` [EXTRACTED]
- [[.test_decomposition_helped_correctly_calculated()]] - `calls` [EXTRACTED]
- [[.test_decomposition_improves_score_uses_merged()]] - `calls` [EXTRACTED]
- [[.test_decomposition_no_improvement_uses_direct()]] - `calls` [EXTRACTED]
- [[.test_depth_zero_max_depth_zero()]] - `calls` [EXTRACTED]
- [[.test_generate_fn_failure_mid_recursion()]] - `calls` [EXTRACTED]
- [[.test_high_confidence_no_decomposition()]] - `calls` [EXTRACTED]
- [[.test_low_confidence_triggers_decomposition()]] - `calls` [EXTRACTED]
- [[.test_respects_max_depth()]] - `calls` [EXTRACTED]
- [[.test_retry_engine_integration_mock()]] - `calls` [EXTRACTED]
- [[.test_task_cannot_be_decomposed_solved_directly()]] - `calls` [EXTRACTED]
- [[.test_tracks_total_model_calls()]] - `calls` [EXTRACTED]
- [[DecompositionResult]] - `uses` [INFERRED]
- [[Mock confidence scorer that returns preset scores.]] - `rationale_for` [EXTRACTED]
- [[RecursiveDecomposer]] - `uses` [INFERRED]
- [[SubProblem]] - `uses` [INFERRED]
- [[test_recursive_decomposer.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/ESV_Bible_Processor