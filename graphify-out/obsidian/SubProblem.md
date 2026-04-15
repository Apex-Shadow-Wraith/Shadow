---
source_file: "modules\shadow\recursive_decomposer.py"
type: "code"
community: "ESV Bible Processor"
location: "L36"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/ESV_Bible_Processor
---

# SubProblem

## Connections
- [[.solve_with_decomposition()]] - `calls` [EXTRACTED]
- [[.test_combines_sub_problem_solutions()]] - `calls` [INFERRED]
- [[.test_merge_without_generate_fn()]] - `calls` [INFERRED]
- [[.test_single_sub_problem_returns_directly()]] - `calls` [INFERRED]
- [[.test_sub_problem_has_all_fields()]] - `calls` [INFERRED]
- [[A single node in the decomposition tree.]] - `rationale_for` [EXTRACTED]
- [[All sub-problems fail → return direct solution.]] - `uses` [INFERRED]
- [[Correctly tracks total_model_calls across recursion.]] - `uses` [INFERRED]
- [[Create a mock generate_fn that returns canned responses in order.]] - `uses` [INFERRED]
- [[Decomposition doesn't improve → uses direct solution.]] - `uses` [INFERRED]
- [[Decomposition improves score → uses merged solution.]] - `uses` [INFERRED]
- [[DecompositionResult has all required fields.]] - `uses` [INFERRED]
- [[FakeConfidenceScorer]] - `uses` [INFERRED]
- [[High confidence on first try → no decomposition.]] - `uses` [INFERRED]
- [[High confidence → False regardless of task complexity.]] - `uses` [INFERRED]
- [[Integration tests with RetryEngine and data schema.]] - `uses` [INFERRED]
- [[Low confidence + complex task → True.]] - `uses` [INFERRED]
- [[Low confidence → decomposes and merges.]] - `uses` [INFERRED]
- [[Mock confidence scorer that returns preset scores.]] - `uses` [INFERRED]
- [[Multiple question marks → True.]] - `uses` [INFERRED]
- [[Multiple sentences with low confidence → True.]] - `uses` [INFERRED]
- [[Parses different numbering formats.]] - `uses` [INFERRED]
- [[Respects max_depth — stops recursing.]] - `uses` [INFERRED]
- [[RetryEngine can use decomposer for strategy 2 (concept test).]] - `uses` [INFERRED]
- [[RetryEngine falls back when decomposer is unavailable.]] - `uses` [INFERRED]
- [[Simple factual question → False.]] - `uses` [INFERRED]
- [[SubProblem has all required fields.]] - `uses` [INFERRED]
- [[Task that can't be decomposed → solved directly.]] - `uses` [INFERRED]
- [[TestDecompose]] - `uses` [INFERRED]
- [[TestEdgeCases_19]] - `uses` [INFERRED]
- [[TestIntegration]] - `uses` [INFERRED]
- [[TestMergeSolutions]] - `uses` [INFERRED]
- [[TestShouldDecompose]] - `uses` [INFERRED]
- [[TestSolveWithDecomposition]] - `uses` [INFERRED]
- [[Tests for Recursive Decomposition — confidence-gated depth control.]] - `uses` [INFERRED]
- [[Tests for the decompose() method.]] - `uses` [INFERRED]
- [[Tests for the merge_solutions() method.]] - `uses` [INFERRED]
- [[Tests for the should_decompose() method.]] - `uses` [INFERRED]
- [[Tests for the solve_with_decomposition() method.]] - `uses` [INFERRED]
- [[Works with no confidence_scorer (uses length heuristic).]] - `uses` [INFERRED]
- [[decompose caps output at 5 sub-problems.]] - `uses` [INFERRED]
- [[decompose generate_fn exception returns task.]] - `uses` [INFERRED]
- [[decompose no generate_fn returns task.]] - `uses` [INFERRED]
- [[decompose parsing failure returns task.]] - `uses` [INFERRED]
- [[decompose returns task if model returns  2 sub-problems.]] - `uses` [INFERRED]
- [[decompose splits task into 2-5 sub-problems.]] - `uses` [INFERRED]
- [[decomposition_helped is True only when merged beats direct.]] - `uses` [INFERRED]
- [[depth 0 with max_depth 0 → direct attempt only.]] - `uses` [INFERRED]
- [[generate_fn failure mid-recursion → return partial result.]] - `uses` [INFERRED]
- [[merge_solutions combines sub-problem solutions.]] - `uses` [INFERRED]
- [[merge_solutions empty list returns empty string.]] - `uses` [INFERRED]
- [[merge_solutions no generate_fn → concatenates solutions.]] - `uses` [INFERRED]
- [[merge_solutions single sub-problem returns its solution directly.]] - `uses` [INFERRED]
- [[recursive_decomposer.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/ESV_Bible_Processor