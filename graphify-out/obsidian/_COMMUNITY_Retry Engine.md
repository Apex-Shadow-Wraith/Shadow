---
type: community
cohesion: 0.05
members: 115
---

# Retry Engine

**Cohesion:** 0.05 - loosely connected
**Members:** 115 nodes

## Members
- [[._build_attempts_summary()]] - code - modules\shadow\retry_engine.py
- [[._build_strategy_context()]] - code - modules\shadow\retry_engine.py
- [[._extract_common_failures()]] - code - modules\shadow\retry_engine.py
- [[._is_impossibility()]] - code - modules\shadow\retry_engine.py
- [[._record_session()]] - code - modules\shadow\retry_engine.py
- [[._send_progress()]] - code - modules\shadow\retry_engine.py
- [[._session_to_dict()]] - code - modules\shadow\retry_engine.py
- [[.attempt_task()]] - code - modules\shadow\retry_engine.py
- [[.escalate_to_apex()]] - code - modules\shadow\retry_engine.py
- [[.get_session_history()]] - code - modules\shadow\retry_engine.py
- [[.get_strategy_for_attempt()]] - code - modules\shadow\retry_engine.py
- [[.reset_fatigue()]] - code - modules\shadow\retry_engine.py
- [[.should_escalate()]] - code - modules\shadow\retry_engine.py
- [[reset fatigue resets the fatigue counter to 0.]] - rationale - tests\test_retry_engine.py
- [[12-attempt retry cycle with strategy rotation and Apex escalation-learning.]] - rationale - modules\shadow\retry_engine.py
- [[After escalation, a local re-verification attempt is made.]] - rationale - tests\test_retry_engine.py
- [[After escalation, three entries are stored answer, teaching, failure_pattern.]] - rationale - tests\test_retry_engine.py
- [[All 12 strategy categories are used before declaring exhaustion.]] - rationale - tests\test_retry_engine.py
- [[Attempt]] - code - modules\shadow\retry_engine.py
- [[Build a human-readable summary of all attempts for Apex.]] - rationale - modules\shadow\retry_engine.py
- [[Build the full context dict for an attempt.]] - rationale - modules\shadow\retry_engine.py
- [[Check if an error indicates hardwaresoftware impossibility.]] - rationale - modules\shadow\retry_engine.py
- [[Check whether escalation to Apex is warranted.          Returns True only if]] - rationale - modules\shadow\retry_engine.py
- [[Classify a failure as infrastructure or model.      Infrastructure failures t]] - rationale - modules\shadow\retry_engine.py
- [[Classify failures as infrastructure vs model to avoid inflating fatigue.]] - rationale - modules\shadow\retry_engine.py
- [[Convert a RetrySession to a serializable dict.]] - rationale - modules\shadow\retry_engine.py
- [[Create an evaluate_fn that succeeds on a specific attempt number.      Args]] - rationale - tests\test_retry_engine.py
- [[Each failed attempt records its failure_type classification.]] - rationale - tests\test_retry_engine.py
- [[Each failed attempt uses a different strategy category.]] - rationale - tests\test_retry_engine.py
- [[Escalate to Apex after exhausting local strategies.          Steps         1]] - rationale - modules\shadow\retry_engine.py
- [[Escalation sends the original task and failure summary to Apex.]] - rationale - tests\test_retry_engine.py
- [[Exceptions in execute_fn are caught and recorded as failures.]] - rationale - tests\test_retry_engine.py
- [[Extract a summary of what went wrong across all attempts.]] - rationale - modules\shadow\retry_engine.py
- [[FailureType]] - code - modules\shadow\retry_engine.py
- [[First attempt succeeds — returns immediately, no retries.]] - rationale - tests\test_retry_engine.py
- [[Fresh RetryEngine instance.]] - rationale - tests\test_retry_engine.py
- [[Full session tracking all retry attempts for a task.]] - rationale - modules\shadow\retry_engine.py
- [[Grimoire search failure is handled gracefully.]] - rationale - tests\test_retry_engine.py
- [[Hardware impossibility detected in error causes early exit.]] - rationale - tests\test_retry_engine.py
- [[Infrastructure failures (tool_loader empty) do NOT increment fatigue.]] - rationale - tests\test_retry_engine.py
- [[Main entry point. Tries up to 12 strategies before giving up.          Args]] - rationale - modules\shadow\retry_engine.py
- [[Mock execute function that always raises.]] - rationale - tests\test_retry_engine.py
- [[Mock execute function that returns a basic result.]] - rationale - tests\test_retry_engine.py
- [[Model failures (bad LLM output) DO increment fatigue.]] - rationale - tests\test_retry_engine.py
- [[No progress notifications when task succeeds before attempt 4.]] - rationale - tests\test_retry_engine.py
- [[Only model failures increment fatigue, not infrastructure failures.]] - rationale - tests\test_retry_engine.py
- [[Previous failure patterns are loaded from Grimoire before first attempt.]] - rationale - tests\test_retry_engine.py
- [[Progress notifications fire at attempts 4, 8, and 12.]] - rationale - tests\test_retry_engine.py
- [[Record a session in the history buffer.]] - rationale - modules\shadow\retry_engine.py
- [[Record of a single retry attempt.]] - rationale - modules\shadow\retry_engine.py
- [[Reset fatigue counter to 0. Called by reset fatigue command.]] - rationale - modules\shadow\retry_engine.py
- [[Retry Engine — 12-Attempt Strategy Rotation with Apex Escalation-Learning =====]] - rationale - modules\shadow\retry_engine.py
- [[RetryEngine]] - code - modules\shadow\retry_engine.py
- [[RetrySession]] - code - modules\shadow\retry_engine.py
- [[Return (strategy_name, description) for the given attempt number.          Ens]] - rationale - modules\shadow\retry_engine.py
- [[Return recent retry sessions for analytics.          Feeds into Growth Engine]] - rationale - modules\shadow\retry_engine.py
- [[Send progress notifications at milestone attempts.]] - rationale - modules\shadow\retry_engine.py
- [[Session history records completed sessions with all attempts.]] - rationale - tests\test_retry_engine.py
- [[Task succeeds on the 5th attempt after 4 failures.]] - rationale - tests\test_retry_engine.py
- [[Tests for RetryEngine — 12-Attempt Strategy Rotation with Apex Escalation-Learni]] - rationale - tests\test_retry_engine.py
- [[The teaching follow-up asks Apex to explain its approach vs our failures.]] - rationale - tests\test_retry_engine.py
- [[Tool execution errors should be classified as infrastructure, not model.]] - rationale - tests\test_retry_engine.py
- [[Verify there are exactly 12 strategy categories.]] - rationale - tests\test_retry_engine.py
- [[When tool_loader returns empty on first attempt, skip ALL remaining retries.]] - rationale - tests\test_retry_engine.py
- [[classify_failure defaults to model failure for non-infrastructure errors.]] - rationale - tests\test_retry_engine.py
- [[classify_failure identifies infrastructure errors from error strings.]] - rationale - tests\test_retry_engine.py
- [[classify_failure reads tool_loader_empty from result dict.]] - rationale - tests\test_retry_engine.py
- [[classify_failure()]] - code - modules\shadow\retry_engine.py
- [[engine()_3]] - code - tests\test_retry_engine.py
- [[escalate_to_apex works when given a dict instead of RetrySession.]] - rationale - tests\test_retry_engine.py
- [[fatigue_counter()]] - code - modules\shadow\retry_engine.py
- [[get_strategy_for_attempt never returns a repeated strategy within a session.]] - rationale - tests\test_retry_engine.py
- [[make_evaluate_fn()]] - code - tests\test_retry_engine.py
- [[mock_execute_fn()]] - code - tests\test_retry_engine.py
- [[mock_execute_fn_error()]] - code - tests\test_retry_engine.py
- [[retry_engine.py]] - code - modules\shadow\retry_engine.py
- [[should_escalate returns False when fewer than 12 attempts have been made.]] - rationale - tests\test_retry_engine.py
- [[should_escalate returns True for hardware impossibility even before 12.]] - rationale - tests\test_retry_engine.py
- [[should_escalate returns True for network impossibility.]] - rationale - tests\test_retry_engine.py
- [[should_escalate returns True when all 12 attempts are exhausted.]] - rationale - tests\test_retry_engine.py
- [[should_escalate works with dict representation of session.]] - rationale - tests\test_retry_engine.py
- [[test_all_12_categories_used()]] - code - tests\test_retry_engine.py
- [[test_classify_failure_from_result_dict()]] - code - tests\test_retry_engine.py
- [[test_classify_failure_infrastructure_markers()]] - code - tests\test_retry_engine.py
- [[test_classify_failure_model_markers()]] - code - tests\test_retry_engine.py
- [[test_classify_failure_tool_execution_errors()]] - code - tests\test_retry_engine.py
- [[test_different_strategies_each_attempt()]] - code - tests\test_retry_engine.py
- [[test_early_exit_on_tool_loader_empty()]] - code - tests\test_retry_engine.py
- [[test_escalation_sends_to_apex()]] - code - tests\test_retry_engine.py
- [[test_escalation_teaching_followup()]] - code - tests\test_retry_engine.py
- [[test_escalation_with_dict_session()]] - code - tests\test_retry_engine.py
- [[test_execute_fn_exception_handled()]] - code - tests\test_retry_engine.py
- [[test_failure_patterns_loaded_from_grimoire()]] - code - tests\test_retry_engine.py
- [[test_failure_type_recorded_in_attempts()]] - code - tests\test_retry_engine.py
- [[test_first_attempt_succeeds()]] - code - tests\test_retry_engine.py
- [[test_get_strategy_never_repeats()]] - code - tests\test_retry_engine.py
- [[test_grimoire_search_failure_graceful()]] - code - tests\test_retry_engine.py
- [[test_hardware_impossibility_early_exit()]] - code - tests\test_retry_engine.py
- [[test_infrastructure_failure_no_fatigue()]] - code - tests\test_retry_engine.py
- [[test_local_reverification()]] - code - tests\test_retry_engine.py
- [[test_mixed_failure_types_fatigue()]] - code - tests\test_retry_engine.py
- [[test_model_failure_increments_fatigue()]] - code - tests\test_retry_engine.py
- [[test_no_notifications_on_early_success()]] - code - tests\test_retry_engine.py
- [[test_progress_notifications()]] - code - tests\test_retry_engine.py
- [[test_reset_fatigue_command()]] - code - tests\test_retry_engine.py
- [[test_retry_engine.py]] - code - tests\test_retry_engine.py
- [[test_session_history()]] - code - tests\test_retry_engine.py
- [[test_should_escalate_false_before_12()]] - code - tests\test_retry_engine.py
- [[test_should_escalate_impossibility_network()]] - code - tests\test_retry_engine.py
- [[test_should_escalate_true_at_12()]] - code - tests\test_retry_engine.py
- [[test_should_escalate_true_for_hardware_impossibility()]] - code - tests\test_retry_engine.py
- [[test_should_escalate_with_dict()]] - code - tests\test_retry_engine.py
- [[test_strategy_categories_count()]] - code - tests\test_retry_engine.py
- [[test_succeed_on_fifth_attempt()]] - code - tests\test_retry_engine.py
- [[test_three_grimoire_entries_stored()]] - code - tests\test_retry_engine.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Retry_Engine
SORT file.name ASC
```

## Connections to other communities
- 82 edges to [[_COMMUNITY_Async Task Queue]]
- 30 edges to [[_COMMUNITY_Base Module & Apex API]]
- 3 edges to [[_COMMUNITY_Module Lifecycle]]

## Top bridge nodes
- [[.escalate_to_apex()]] - degree 15, connects to 3 communities
- [[RetryEngine]] - degree 118, connects to 2 communities
- [[Attempt]] - degree 52, connects to 2 communities
- [[RetrySession]] - degree 52, connects to 2 communities
- [[FailureType]] - degree 42, connects to 2 communities