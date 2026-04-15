---
type: community
cohesion: 0.05
members: 79
---

# Tool Evaluator

**Cohesion:** 0.05 - loosely connected
**Members:** 79 nodes

## Members
- [[.__init__()_92]] - code - modules\shadow\tool_evaluator.py
- [[._check_content()]] - code - modules\shadow\tool_evaluator.py
- [[._check_critical()]] - code - modules\shadow\tool_evaluator.py
- [[._check_errors()]] - code - modules\shadow\tool_evaluator.py
- [[._check_size()]] - code - modules\shadow\tool_evaluator.py
- [[._check_transient()]] - code - modules\shadow\tool_evaluator.py
- [[._check_type()]] - code - modules\shadow\tool_evaluator.py
- [[._check_wrong_tool()]] - code - modules\shadow\tool_evaluator.py
- [[.evaluate()]] - code - modules\shadow\tool_evaluator.py
- [[.evaluate_chain_progress()]] - code - modules\shadow\tool_evaluator.py
- [[.format_evaluation_for_context()]] - code - modules\shadow\tool_evaluator.py
- [[.test_all_pass_recommends_proceed()]] - code - tests\test_tool_evaluator.py
- [[.test_empty_result()]] - code - tests\test_tool_evaluator.py
- [[.test_empty_steps_valid_default()]] - code - tests\test_tool_evaluator.py
- [[.test_error_field_in_result()]] - code - tests\test_tool_evaluator.py
- [[.test_expected_json_got_plain_text()]] - code - tests\test_tool_evaluator.py
- [[.test_expected_json_got_valid_json()]] - code - tests\test_tool_evaluator.py
- [[.test_expected_list_got_json_array()]] - code - tests\test_tool_evaluator.py
- [[.test_expected_list_got_non_list()]] - code - tests\test_tool_evaluator.py
- [[.test_expected_number_got_float()]] - code - tests\test_tool_evaluator.py
- [[.test_expected_number_got_number()]] - code - tests\test_tool_evaluator.py
- [[.test_expected_number_got_text()]] - code - tests\test_tool_evaluator.py
- [[.test_format_includes_issues()]] - code - tests\test_tool_evaluator.py
- [[.test_format_produces_readable_string()]] - code - tests\test_tool_evaluator.py
- [[.test_mixed_results()]] - code - tests\test_tool_evaluator.py
- [[.test_none_result()]] - code - tests\test_tool_evaluator.py
- [[.test_nonempty_meaningful_result()]] - code - tests\test_tool_evaluator.py
- [[.test_normal_sized_result()]] - code - tests\test_tool_evaluator.py
- [[.test_oversized_result()]] - code - tests\test_tool_evaluator.py
- [[.test_result_contains_expected_keywords()]] - code - tests\test_tool_evaluator.py
- [[.test_result_missing_expected_keywords()]] - code - tests\test_tool_evaluator.py
- [[.test_result_with_error_keyword()]] - code - tests\test_tool_evaluator.py
- [[.test_result_with_http_404()]] - code - tests\test_tool_evaluator.py
- [[.test_result_with_http_500()]] - code - tests\test_tool_evaluator.py
- [[.test_result_with_traceback()]] - code - tests\test_tool_evaluator.py
- [[.test_same_step_failed_three_times()]] - code - tests\test_tool_evaluator.py
- [[.test_security_issue_recommends_abort()]] - code - tests\test_tool_evaluator.py
- [[.test_three_successful_steps()]] - code - tests\test_tool_evaluator.py
- [[.test_transient_error_recommends_retry()]] - code - tests\test_tool_evaluator.py
- [[.test_valid_result_passes()]] - code - tests\test_tool_evaluator.py
- [[.test_very_short_result_for_content_task()]] - code - tests\test_tool_evaluator.py
- [[.test_whitespace_only_result()]] - code - tests\test_tool_evaluator.py
- [[.test_with_evaluation_result_objects()]] - code - tests\test_tool_evaluator.py
- [[.test_wrong_tool_recommends_replan()]] - code - tests\test_tool_evaluator.py
- [[Check for criticalsecurity issues.]] - rationale - modules\shadow\tool_evaluator.py
- [[Check for error keywords in output.]] - rationale - modules\shadow\tool_evaluator.py
- [[Check for transientrecoverable errors.]] - rationale - modules\shadow\tool_evaluator.py
- [[Check if output matches expected type.]] - rationale - modules\shadow\tool_evaluator.py
- [[Check if output suggests wrong tool was used.]] - rationale - modules\shadow\tool_evaluator.py
- [[Create a ToolResultEvaluator with default config.]] - rationale - tests\test_tool_evaluator.py
- [[Evaluate a tool's result against expectations.          Args             tool_n]] - rationale - modules\shadow\tool_evaluator.py
- [[Evaluate progress across a chain of completed steps.          Args]] - rationale - modules\shadow\tool_evaluator.py
- [[Evaluates tool results between chained calls.]] - rationale - modules\shadow\tool_evaluator.py
- [[EvaluationResult]] - code - modules\shadow\tool_evaluator.py
- [[Format an evaluation result as a string for context injection.          Args]] - rationale - modules\shadow\tool_evaluator.py
- [[Initialize evaluator with optional configuration.          Args             con]] - rationale - modules\shadow\tool_evaluator.py
- [[Result of evaluating a tool's output.]] - rationale - modules\shadow\tool_evaluator.py
- [[TestChainProgress]] - code - tests\test_tool_evaluator.py
- [[TestContentValidation]] - code - tests\test_tool_evaluator.py
- [[TestErrorDetection]] - code - tests\test_tool_evaluator.py
- [[TestFormatting]] - code - tests\test_tool_evaluator.py
- [[TestRecommendations_1]] - code - tests\test_tool_evaluator.py
- [[TestSizeValidation]] - code - tests\test_tool_evaluator.py
- [[TestTypeChecking]] - code - tests\test_tool_evaluator.py
- [[Tests for Tool Result Evaluation between chained calls.]] - rationale - tests\test_tool_evaluator.py
- [[Tests for content quality validation.]] - rationale - tests\test_tool_evaluator.py
- [[Tests for error keyword detection in tool output.]] - rationale - tests\test_tool_evaluator.py
- [[Tests for evaluate_chain_progress.]] - rationale - tests\test_tool_evaluator.py
- [[Tests for expected output type validation.]] - rationale - tests\test_tool_evaluator.py
- [[Tests for format_evaluation_for_context.]] - rationale - tests\test_tool_evaluator.py
- [[Tests for recommendation logic.]] - rationale - tests\test_tool_evaluator.py
- [[Tests for result size validation.]] - rationale - tests\test_tool_evaluator.py
- [[Tool Result Evaluation Between Chained Calls.  After every tool call in a multi-]] - rationale - modules\shadow\tool_evaluator.py
- [[ToolResultEvaluator]] - code - modules\shadow\tool_evaluator.py
- [[Validate content quality.]] - rationale - modules\shadow\tool_evaluator.py
- [[Validate result size.]] - rationale - modules\shadow\tool_evaluator.py
- [[evaluator()_2]] - code - tests\test_tool_evaluator.py
- [[test_tool_evaluator.py]] - code - tests\test_tool_evaluator.py
- [[tool_evaluator.py]] - code - modules\shadow\tool_evaluator.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Tool_Evaluator
SORT file.name ASC
```

## Connections to other communities
- 1 edge to [[_COMMUNITY_Behavioral Benchmark]]

## Top bridge nodes
- [[evaluator()_2]] - degree 4, connects to 1 community