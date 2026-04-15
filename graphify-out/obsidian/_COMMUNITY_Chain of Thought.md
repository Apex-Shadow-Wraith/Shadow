---
type: community
cohesion: 0.06
members: 94
---

# Chain of Thought

**Cohesion:** 0.06 - loosely connected
**Members:** 94 nodes

## Members
- [[.__init__()_56]] - code - modules\shadow\chain_of_thought.py
- [[.__init__()_104]] - code - tests\test_chain_of_thought.py
- [[.__init__()_105]] - code - tests\test_chain_of_thought.py
- [[._build_complex_steps()]] - code - modules\shadow\chain_of_thought.py
- [[._build_moderate_steps()]] - code - modules\shadow\chain_of_thought.py
- [[._build_simple_steps()]] - code - modules\shadow\chain_of_thought.py
- [[._execute_pipeline()]] - code - modules\shadow\chain_of_thought.py
- [[.estimate_complexity()]] - code - modules\shadow\chain_of_thought.py
- [[.get_reasoning_stats()]] - code - modules\shadow\chain_of_thought.py
- [[.reason()]] - code - modules\shadow\chain_of_thought.py
- [[.reason_custom()]] - code - modules\shadow\chain_of_thought.py
- [[.score()]] - code - tests\test_chain_of_thought.py
- [[.score()_1]] - code - tests\test_chain_of_thought.py
- [[.test_analysis_keyword_triggers_complex()]] - code - tests\test_chain_of_thought.py
- [[.test_auto_routes_correctly()]] - code - tests\test_chain_of_thought.py
- [[.test_code_keywords_trigger_complex()]] - code - tests\test_chain_of_thought.py
- [[.test_context_in_step1_prompt()]] - code - tests\test_chain_of_thought.py
- [[.test_correct_step_count_and_durations()]] - code - tests\test_chain_of_thought.py
- [[.test_custom_empty_steps_returns_error()]] - code - tests\test_chain_of_thought.py
- [[.test_custom_previous_output_substitution()]] - code - tests\test_chain_of_thought.py
- [[.test_custom_three_steps()]] - code - tests\test_chain_of_thought.py
- [[.test_each_step_receives_previous_output()]] - code - tests\test_chain_of_thought.py
- [[.test_early_exit_skips_remaining_steps()]] - code - tests\test_chain_of_thought.py
- [[.test_empty_context_no_error()]] - code - tests\test_chain_of_thought.py
- [[.test_final_output_is_last_step_response()]] - code - tests\test_chain_of_thought.py
- [[.test_four_steps_execute_in_order()]] - code - tests\test_chain_of_thought.py
- [[.test_generate_called_once_per_step()]] - code - tests\test_chain_of_thought.py
- [[.test_generate_failure_stops_chain()]] - code - tests\test_chain_of_thought.py
- [[.test_long_task_is_complex()]] - code - tests\test_chain_of_thought.py
- [[.test_medium_question_is_moderate()]] - code - tests\test_chain_of_thought.py
- [[.test_moderate_passes_understanding_to_execute()]] - code - tests\test_chain_of_thought.py
- [[.test_none_generate_fn_returns_error()]] - code - tests\test_chain_of_thought.py
- [[.test_short_simple_question()]] - code - tests\test_chain_of_thought.py
- [[.test_shortcut_rate_tracked()]] - code - tests\test_chain_of_thought.py
- [[.test_simple_auto_detected()]] - code - tests\test_chain_of_thought.py
- [[.test_single_step_only()]] - code - tests\test_chain_of_thought.py
- [[.test_stats_after_multiple_calls()]] - code - tests\test_chain_of_thought.py
- [[.test_stats_empty_history()]] - code - tests\test_chain_of_thought.py
- [[.test_step1_never_skipped()]] - code - tests\test_chain_of_thought.py
- [[.test_task_stored_in_result()]] - code - tests\test_chain_of_thought.py
- [[.test_tokens_estimated_per_step()]] - code - tests\test_chain_of_thought.py
- [[.test_two_steps()]] - code - tests\test_chain_of_thought.py
- [[.test_used_shortcut_false_when_no_early_exit()]] - code - tests\test_chain_of_thought.py
- [[.test_used_shortcut_set_correctly()]] - code - tests\test_chain_of_thought.py
- [[2 steps understand + execute.]] - rationale - tests\test_chain_of_thought.py
- [[A single step in the chain-of-thought pipeline.]] - rationale - modules\shadow\chain_of_thought.py
- [[All 4 steps execute in order for complex tasks.]] - rationale - tests\test_chain_of_thought.py
- [[Break complex reasoning into explicit sequential steps.      Each step is a SEPA]] - rationale - modules\shadow\chain_of_thought.py
- [[Build a 1-step pipeline (direct attempt).]] - rationale - modules\shadow\chain_of_thought.py
- [[Build a 2-step pipeline (understand + execute).]] - rationale - modules\shadow\chain_of_thought.py
- [[Build the full 4-step pipeline.]] - rationale - modules\shadow\chain_of_thought.py
- [[Chain-of-Thought Scaffolding — Structured Multi-Step Reasoning =================]] - rationale - modules\shadow\chain_of_thought.py
- [[ChainOfThought]] - code - modules\shadow\chain_of_thought.py
- [[ChainResult]] - code - modules\shadow\chain_of_thought.py
- [[Complete result of a chain-of-thought reasoning pass.]] - rationale - modules\shadow\chain_of_thought.py
- [[Complexity auto-detection from task text.]] - rationale - tests\test_chain_of_thought.py
- [[Context string properly passed through.]] - rationale - tests\test_chain_of_thought.py
- [[Estimate task complexity from text characteristics.          Args             t]] - rationale - modules\shadow\chain_of_thought.py
- [[Execute a sequence of reasoning steps.          Each step is a separate model ca]] - rationale - modules\shadow\chain_of_thought.py
- [[Generate function that always raises.]] - rationale - tests\test_chain_of_thought.py
- [[High confidence after a step can skip remaining steps.]] - rationale - tests\test_chain_of_thought.py
- [[Initialize the chain-of-thought scaffolding.          Args             generate]] - rationale - modules\shadow\chain_of_thought.py
- [[Main entry point for chain-of-thought reasoning.          Args             task]] - rationale - modules\shadow\chain_of_thought.py
- [[Model call behavior and error handling.]] - rationale - tests\test_chain_of_thought.py
- [[Only 1 step for simple tasks.]] - rationale - tests\test_chain_of_thought.py
- [[ReasoningStep]] - code - modules\shadow\chain_of_thought.py
- [[Result dataclass has correct metadata.]] - rationale - tests\test_chain_of_thought.py
- [[Return statistics from reasoning history.          Returns             Dict wit]] - rationale - modules\shadow\chain_of_thought.py
- [[Returns a generate function that counts calls.]] - rationale - tests\test_chain_of_thought.py
- [[Run a custom step pipeline for domain-specific reasoning.          Args]] - rationale - modules\shadow\chain_of_thought.py
- [[Scorer that returns a fixed confidence value.]] - rationale - tests\test_chain_of_thought.py
- [[Scorer that returns increasing confidence per call.]] - rationale - tests\test_chain_of_thought.py
- [[Simple mock that echoes back a summary of the prompt.]] - rationale - tests\test_chain_of_thought.py
- [[TestChainResult]] - code - tests\test_chain_of_thought.py
- [[TestComplexPipeline]] - code - tests\test_chain_of_thought.py
- [[TestContextHandling]] - code - tests\test_chain_of_thought.py
- [[TestCustomPipeline]] - code - tests\test_chain_of_thought.py
- [[TestEarlyExit]] - code - tests\test_chain_of_thought.py
- [[TestEstimateComplexity]] - code - tests\test_chain_of_thought.py
- [[TestGenerateFunction]] - code - tests\test_chain_of_thought.py
- [[TestModeratePipeline]] - code - tests\test_chain_of_thought.py
- [[TestReasoningStats]] - code - tests\test_chain_of_thought.py
- [[TestSimplePipeline]] - code - tests\test_chain_of_thought.py
- [[Tests for Chain-of-Thought Scaffolding ========================================]] - rationale - tests\test_chain_of_thought.py
- [[_MockConfidenceScorer]] - code - tests\test_chain_of_thought.py
- [[_SteppedConfidenceScorer]] - code - tests\test_chain_of_thought.py
- [[_counting_generate()]] - code - tests\test_chain_of_thought.py
- [[_estimate_tokens()]] - code - modules\shadow\chain_of_thought.py
- [[_failing_generate()]] - code - tests\test_chain_of_thought.py
- [[_mock_generate()]] - code - tests\test_chain_of_thought.py
- [[chain_of_thought.py]] - code - modules\shadow\chain_of_thought.py
- [[get_reasoning_stats returns valid data.]] - rationale - tests\test_chain_of_thought.py
- [[reason_custom with user-defined steps.]] - rationale - tests\test_chain_of_thought.py
- [[test_chain_of_thought.py]] - code - tests\test_chain_of_thought.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Chain_of_Thought
SORT file.name ASC
```

## Connections to other communities
- 56 edges to [[_COMMUNITY_Async Task Queue]]
- 5 edges to [[_COMMUNITY_Base Module & Apex API]]
- 1 edge to [[_COMMUNITY_Module Lifecycle]]

## Top bridge nodes
- [[ChainOfThought]] - degree 131, connects to 2 communities
- [[._execute_pipeline()]] - degree 9, connects to 1 community