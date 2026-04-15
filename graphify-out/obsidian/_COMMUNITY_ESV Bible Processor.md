---
type: community
cohesion: 0.04
members: 125
---

# ESV Bible Processor

**Cohesion:** 0.04 - loosely connected
**Members:** 125 nodes

## Members
- [[.__init__()_120]] - code - tests\test_recursive_decomposer.py
- [[._score_solution()]] - code - modules\shadow\recursive_decomposer.py
- [[._solve_direct()]] - code - modules\shadow\recursive_decomposer.py
- [[.decompose()]] - code - modules\shadow\recursive_decomposer.py
- [[.merge_solutions()]] - code - modules\shadow\recursive_decomposer.py
- [[.score_response()_2]] - code - tests\test_recursive_decomposer.py
- [[.should_decompose()]] - code - modules\shadow\recursive_decomposer.py
- [[.solve_with_decomposition()]] - code - modules\shadow\recursive_decomposer.py
- [[.test_all_sub_problems_fail_returns_best()]] - code - tests\test_recursive_decomposer.py
- [[.test_caps_at_five_sub_problems()]] - code - tests\test_recursive_decomposer.py
- [[.test_combines_sub_problem_solutions()]] - code - tests\test_recursive_decomposer.py
- [[.test_decomposition_helped_correctly_calculated()]] - code - tests\test_recursive_decomposer.py
- [[.test_decomposition_improves_score_uses_merged()]] - code - tests\test_recursive_decomposer.py
- [[.test_decomposition_no_improvement_uses_direct()]] - code - tests\test_recursive_decomposer.py
- [[.test_decomposition_result_has_all_fields()]] - code - tests\test_recursive_decomposer.py
- [[.test_depth_zero_max_depth_zero()]] - code - tests\test_recursive_decomposer.py
- [[.test_empty_sub_problems()]] - code - tests\test_recursive_decomposer.py
- [[.test_generate_fn_exception_returns_task()]] - code - tests\test_recursive_decomposer.py
- [[.test_generate_fn_failure_mid_recursion()]] - code - tests\test_recursive_decomposer.py
- [[.test_graceful_without_confidence_scorer()]] - code - tests\test_recursive_decomposer.py
- [[.test_high_confidence_no_decomposition()]] - code - tests\test_recursive_decomposer.py
- [[.test_high_confidence_returns_false()]] - code - tests\test_recursive_decomposer.py
- [[.test_low_confidence_complex_task_returns_true()]] - code - tests\test_recursive_decomposer.py
- [[.test_low_confidence_triggers_decomposition()]] - code - tests\test_recursive_decomposer.py
- [[.test_merge_without_generate_fn()]] - code - tests\test_recursive_decomposer.py
- [[.test_multiple_questions_returns_true()]] - code - tests\test_recursive_decomposer.py
- [[.test_multiple_sentences_returns_true()]] - code - tests\test_recursive_decomposer.py
- [[.test_no_generate_fn_returns_task()]] - code - tests\test_recursive_decomposer.py
- [[.test_parse_various_numbered_formats()]] - code - tests\test_recursive_decomposer.py
- [[.test_parsing_failure_returns_task()]] - code - tests\test_recursive_decomposer.py
- [[.test_respects_max_depth()]] - code - tests\test_recursive_decomposer.py
- [[.test_retry_engine_fallback_without_decomposer()]] - code - tests\test_recursive_decomposer.py
- [[.test_retry_engine_integration_mock()]] - code - tests\test_recursive_decomposer.py
- [[.test_returns_task_if_cannot_decompose()]] - code - tests\test_recursive_decomposer.py
- [[.test_simple_factual_question_returns_false()]] - code - tests\test_recursive_decomposer.py
- [[.test_single_sub_problem_returns_directly()]] - code - tests\test_recursive_decomposer.py
- [[.test_splits_task_into_sub_problems()]] - code - tests\test_recursive_decomposer.py
- [[.test_sub_problem_has_all_fields()]] - code - tests\test_recursive_decomposer.py
- [[.test_task_cannot_be_decomposed_solved_directly()]] - code - tests\test_recursive_decomposer.py
- [[.test_tracks_total_model_calls()]] - code - tests\test_recursive_decomposer.py
- [[A single node in the decomposition tree.]] - rationale - modules\shadow\recursive_decomposer.py
- [[All sub-problems fail → return direct solution.]] - rationale - tests\test_recursive_decomposer.py
- [[Ask the model to break a task into 2-5 independent sub-problems.          Args]] - rationale - modules\shadow\recursive_decomposer.py
- [[Clean a BeautifulSoup element for biblical text extraction.     Removes crossref]] - rationale - scripts\esv_processor.py
- [[Clean a study note paragraph tag into plain text.]] - rationale - scripts\esv_processor.py
- [[Collect all sibling elements between start_elem and end_elem (exclusive).     Re]] - rationale - scripts\esv_processor.py
- [[Combine sub-problem solutions into a coherent answer.          Args]] - rationale - modules\shadow\recursive_decomposer.py
- [[Complete result of a recursive decomposition pass.]] - rationale - modules\shadow\recursive_decomposer.py
- [[Correctly tracks total_model_calls across recursion.]] - rationale - tests\test_recursive_decomposer.py
- [[Create a mock generate_fn that returns canned responses in order.]] - rationale - tests\test_recursive_decomposer.py
- [[Decode a verse ID like '01001001' into (book, chapter, verse).     Used for both]] - rationale - scripts\esv_processor.py
- [[Decomposition doesn't improve → uses direct solution.]] - rationale - tests\test_recursive_decomposer.py
- [[Decomposition improves score → uses merged solution.]] - rationale - tests\test_recursive_decomposer.py
- [[DecompositionResult]] - code - modules\shadow\recursive_decomposer.py
- [[DecompositionResult has all required fields.]] - rationale - tests\test_recursive_decomposer.py
- [[Discover and group all book files from the epub.     Returns dict { book_number]] - rationale - scripts\esv_processor.py
- [[ESV Study Bible Epub Processor Parses the ESV Study Bible epub into structured J]] - rationale - scripts\esv_processor.py
- [[Extract all verse identities (book, chapter, verse) found in a section     by sc]] - rationale - scripts\esv_processor.py
- [[FakeConfidenceScorer]] - code - tests\test_recursive_decomposer.py
- [[High confidence on first try → no decomposition.]] - rationale - tests\test_recursive_decomposer.py
- [[High confidence → False regardless of task complexity.]] - rationale - tests\test_recursive_decomposer.py
- [[Integration tests with RetryEngine and data schema.]] - rationale - tests\test_recursive_decomposer.py
- [[Low confidence + complex task → True.]] - rationale - tests\test_recursive_decomposer.py
- [[Low confidence → decomposes and merges.]] - rationale - tests\test_recursive_decomposer.py
- [[Main entry point. Recursively decompose and solve.          Args             ta]] - rationale - modules\shadow\recursive_decomposer.py
- [[Mock confidence scorer that returns preset scores.]] - rationale - tests\test_recursive_decomposer.py
- [[Multiple question marks → True.]] - rationale - tests\test_recursive_decomposer.py
- [[Multiple sentences with low confidence → True.]] - rationale - tests\test_recursive_decomposer.py
- [[Parse a study note ID like 'n01024009' or 'n01001001-01002003'     into (chapter]] - rationale - scripts\esv_processor.py
- [[Parse all studynotes xhtml files for a single book.     Returns list of study no]] - rationale - scripts\esv_processor.py
- [[Parse all text xhtml files for a single book.     Returns list of pericope dicts]] - rationale - scripts\esv_processor.py
- [[Parses different numbering formats.]] - rationale - tests\test_recursive_decomposer.py
- [[Quick heuristic is this task worth decomposing          Args             task]] - rationale - modules\shadow\recursive_decomposer.py
- [[Recursive Decomposition Before Escalation ======================================]] - rationale - modules\shadow\recursive_decomposer.py
- [[Respects max_depth — stops recursing.]] - rationale - tests\test_recursive_decomposer.py
- [[RetryEngine can use decomposer for strategy 2 (concept test).]] - rationale - tests\test_recursive_decomposer.py
- [[RetryEngine falls back when decomposer is unavailable.]] - rationale - tests\test_recursive_decomposer.py
- [[Return genre string for a given book number (1-66).]] - rationale - scripts\esv_processor.py
- [[Score a solution's confidence.          Uses confidence_scorer if available, oth]] - rationale - modules\shadow\recursive_decomposer.py
- [[Simple factual question → False.]] - rationale - tests\test_recursive_decomposer.py
- [[Solve a task directly (single model call).          Returns             Tuple o]] - rationale - modules\shadow\recursive_decomposer.py
- [[SubProblem]] - code - modules\shadow\recursive_decomposer.py
- [[SubProblem has all required fields.]] - rationale - tests\test_recursive_decomposer.py
- [[Task that can't be decomposed → solved directly.]] - rationale - tests\test_recursive_decomposer.py
- [[TestDecompose]] - code - tests\test_recursive_decomposer.py
- [[TestEdgeCases_19]] - code - tests\test_recursive_decomposer.py
- [[TestIntegration]] - code - tests\test_recursive_decomposer.py
- [[TestMergeSolutions]] - code - tests\test_recursive_decomposer.py
- [[TestShouldDecompose]] - code - tests\test_recursive_decomposer.py
- [[TestSolveWithDecomposition]] - code - tests\test_recursive_decomposer.py
- [[Tests for Recursive Decomposition — confidence-gated depth control.]] - rationale - tests\test_recursive_decomposer.py
- [[Tests for the decompose() method.]] - rationale - tests\test_recursive_decomposer.py
- [[Tests for the merge_solutions() method.]] - rationale - tests\test_recursive_decomposer.py
- [[Tests for the should_decompose() method.]] - rationale - tests\test_recursive_decomposer.py
- [[Tests for the solve_with_decomposition() method.]] - rationale - tests\test_recursive_decomposer.py
- [[Works with no confidence_scorer (uses length heuristic).]] - rationale - tests\test_recursive_decomposer.py
- [[_parse_numbered_list()]] - code - modules\shadow\recursive_decomposer.py
- [[clean_note_text()]] - code - scripts\esv_processor.py
- [[clean_text_element()]] - code - scripts\esv_processor.py
- [[decode_verse_id()]] - code - scripts\esv_processor.py
- [[decompose caps output at 5 sub-problems.]] - rationale - tests\test_recursive_decomposer.py
- [[decompose generate_fn exception returns task.]] - rationale - tests\test_recursive_decomposer.py
- [[decompose no generate_fn returns task.]] - rationale - tests\test_recursive_decomposer.py
- [[decompose parsing failure returns task.]] - rationale - tests\test_recursive_decomposer.py
- [[decompose returns task if model returns  2 sub-problems.]] - rationale - tests\test_recursive_decomposer.py
- [[decompose splits task into 2-5 sub-problems.]] - rationale - tests\test_recursive_decomposer.py
- [[decomposition_helped is True only when merged beats direct.]] - rationale - tests\test_recursive_decomposer.py
- [[depth 0 with max_depth 0 → direct attempt only.]] - rationale - tests\test_recursive_decomposer.py
- [[discover_book_files()]] - code - scripts\esv_processor.py
- [[esv_processor.py]] - code - scripts\esv_processor.py
- [[extract_verses_from_section()]] - code - scripts\esv_processor.py
- [[generate_fn failure mid-recursion → return partial result.]] - rationale - tests\test_recursive_decomposer.py
- [[get_content_between()]] - code - scripts\esv_processor.py
- [[get_genre()]] - code - scripts\esv_processor.py
- [[main()_5]] - code - scripts\esv_processor.py
- [[make_generate_fn()_1]] - code - tests\test_recursive_decomposer.py
- [[merge_solutions combines sub-problem solutions.]] - rationale - tests\test_recursive_decomposer.py
- [[merge_solutions empty list returns empty string.]] - rationale - tests\test_recursive_decomposer.py
- [[merge_solutions no generate_fn → concatenates solutions.]] - rationale - tests\test_recursive_decomposer.py
- [[merge_solutions single sub-problem returns its solution directly.]] - rationale - tests\test_recursive_decomposer.py
- [[parse_studynotes_files()]] - code - scripts\esv_processor.py
- [[parse_text_files()]] - code - scripts\esv_processor.py
- [[parse_verse_range_from_id()]] - code - scripts\esv_processor.py
- [[recursive_decomposer.py]] - code - modules\shadow\recursive_decomposer.py
- [[test_recursive_decomposer.py]] - code - tests\test_recursive_decomposer.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/ESV_Bible_Processor
SORT file.name ASC
```

## Connections to other communities
- 83 edges to [[_COMMUNITY_Async Task Queue]]
- 5 edges to [[_COMMUNITY_Code Analyzer (Omen)]]
- 2 edges to [[_COMMUNITY_Module Lifecycle]]
- 1 edge to [[_COMMUNITY_Adversarial Sparring]]
- 1 edge to [[_COMMUNITY_Base Module & Apex API]]
- 1 edge to [[_COMMUNITY_Benchmark Generator]]

## Top bridge nodes
- [[.decompose()]] - degree 14, connects to 3 communities
- [[.solve_with_decomposition()]] - degree 23, connects to 2 communities
- [[._score_solution()]] - degree 5, connects to 2 communities
- [[FakeConfidenceScorer]] - degree 19, connects to 1 community
- [[TestDecompose]] - degree 11, connects to 1 community