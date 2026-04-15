---
type: community
cohesion: 0.06
members: 89
---

# Execution Planner

**Cohesion:** 0.06 - loosely connected
**Members:** 89 nodes

## Members
- [[.__init__()_67]] - code - modules\shadow\execution_planner.py
- [[._adapt_existing_plan()]] - code - modules\shadow\execution_planner.py
- [[._build_steps()]] - code - modules\shadow\execution_planner.py
- [[._detect_circular_deps()]] - code - modules\shadow\execution_planner.py
- [[._dict_to_plan()]] - code - modules\shadow\execution_planner.py
- [[._find_reusable_plan()]] - code - modules\shadow\execution_planner.py
- [[._generate_new_plan()]] - code - modules\shadow\execution_planner.py
- [[._parse_plan_response()]] - code - modules\shadow\execution_planner.py
- [[._plans_are_similar()]] - code - modules\shadow\execution_planner.py
- [[._single_step_plan()]] - code - modules\shadow\execution_planner.py
- [[.adapt_plan()]] - code - modules\shadow\execution_planner.py
- [[.create_plan()]] - code - modules\shadow\execution_planner.py
- [[.evaluate_plan()]] - code - modules\shadow\execution_planner.py
- [[.get_planning_stats()]] - code - modules\shadow\execution_planner.py
- [[.search_reusable_plans()]] - code - modules\shadow\execution_planner.py
- [[.store_successful_plan()]] - code - modules\shadow\execution_planner.py
- [[.test_adapts_existing_plan_when_found()]] - code - tests\test_execution_planner.py
- [[.test_all_tools_available_feasible()]] - code - tests\test_execution_planner.py
- [[.test_checks_grimoire_for_reusable_plan()]] - code - tests\test_execution_planner.py
- [[.test_circular_dependency_detected()]] - code - tests\test_execution_planner.py
- [[.test_deduplicates_similar_plans()]] - code - tests\test_execution_planner.py
- [[.test_empty_available_tools()]] - code - tests\test_execution_planner.py
- [[.test_excessive_duration()]] - code - tests\test_execution_planner.py
- [[.test_execution_plan_has_all_fields()]] - code - tests\test_execution_planner.py
- [[.test_forward_reference_invalid()]] - code - tests\test_execution_planner.py
- [[.test_generates_new_plan_when_none_found()]] - code - tests\test_execution_planner.py
- [[.test_generates_plan_with_valid_steps()]] - code - tests\test_execution_planner.py
- [[.test_graceful_when_generate_fn_is_none()]] - code - tests\test_execution_planner.py
- [[.test_graceful_when_grimoire_is_none()]] - code - tests\test_execution_planner.py
- [[.test_initial_stats_are_zero()]] - code - tests\test_execution_planner.py
- [[.test_missing_tool_not_feasible()]] - code - tests\test_execution_planner.py
- [[.test_no_grimoire_returns_empty()_1]] - code - tests\test_execution_planner.py
- [[.test_no_grimoire_returns_empty()]] - code - tests\test_execution_planner.py
- [[.test_parsing_failure_single_step_fallback()]] - code - tests\test_execution_planner.py
- [[.test_plan_step_has_all_fields()]] - code - tests\test_execution_planner.py
- [[.test_preserves_task_description()]] - code - tests\test_execution_planner.py
- [[.test_produces_adapted_status()]] - code - tests\test_execution_planner.py
- [[.test_returns_matching_plans()]] - code - tests\test_execution_planner.py
- [[.test_returns_valid_data()]] - code - tests\test_execution_planner.py
- [[.test_single_step_valid()]] - code - tests\test_execution_planner.py
- [[.test_stores_in_grimoire()_1]] - code - tests\test_execution_planner.py
- [[.test_with_generate_fn_produces_new_steps()]] - code - tests\test_execution_planner.py
- [[.test_zero_steps_error()]] - code - tests\test_execution_planner.py
- [[A complete execution plan for a multi-tool task.]] - rationale - modules\shadow\execution_planner.py
- [[A single step in an execution plan.]] - rationale - modules\shadow\execution_planner.py
- [[Adapt a plan when execution diverges from expectations.          Takes the origi]] - rationale - modules\shadow\execution_planner.py
- [[Adapt an existing reusable plan to a new task.]] - rationale - modules\shadow\execution_planner.py
- [[Adapted plan gets a new ID and updated task description.]] - rationale - tests\test_execution_planner.py
- [[Check if two plans are similar enough to be considered duplicates.]] - rationale - modules\shadow\execution_planner.py
- [[Convert a list of step dicts into PlanStep objects.]] - rationale - modules\shadow\execution_planner.py
- [[Convert a stored dict back to an ExecutionPlan.]] - rationale - modules\shadow\execution_planner.py
- [[Create a minimal single-step fallback plan.]] - rationale - modules\shadow\execution_planner.py
- [[Create an execution plan for a task.          Checks Grimoire for a reusable pla]] - rationale - modules\shadow\execution_planner.py
- [[Detect circular dependencies in step references.          Returns a description]] - rationale - modules\shadow\execution_planner.py
- [[Empty tools list should produce a fallback plan gracefully.]] - rationale - tests\test_execution_planner.py
- [[Evaluate plan feasibility before execution.          Checks         - All requi]] - rationale - modules\shadow\execution_planner.py
- [[ExecutionPlan]] - code - modules\shadow\execution_planner.py
- [[ExecutionPlanner]] - code - modules\shadow\execution_planner.py
- [[Generate a brand new plan using the model.]] - rationale - modules\shadow\execution_planner.py
- [[Generate, evaluate, and store execution plans for multi-tool tasks.      Plans a]] - rationale - modules\shadow\execution_planner.py
- [[If model returns unparseable response, fall back to single step.]] - rationale - tests\test_execution_planner.py
- [[Parse JSON from model response, handling markdown fences.]] - rationale - modules\shadow\execution_planner.py
- [[PlanStep]] - code - modules\shadow\execution_planner.py
- [[Pre-Execution Planning Pass ============================== Before any multi-tool]] - rationale - modules\shadow\execution_planner.py
- [[Return a generate_fn that returns a JSON plan response.]] - rationale - tests\test_execution_planner.py
- [[Return planning statistics for the Growth Engine.          Returns]] - rationale - modules\shadow\execution_planner.py
- [[Search Grimoire for a reusable plan matching this task.]] - rationale - modules\shadow\execution_planner.py
- [[Search Grimoire for stored execution plans matching task type.          Args]] - rationale - modules\shadow\execution_planner.py
- [[Should not store a plan that's very similar to an existing one.]] - rationale - tests\test_execution_planner.py
- [[Step references a future step's output.]] - rationale - tests\test_execution_planner.py
- [[Store a successful plan in Grimoire as a reusable workflow.          Only stores]] - rationale - modules\shadow\execution_planner.py
- [[TestAdaptPlan]] - code - tests\test_execution_planner.py
- [[TestCreatePlan]] - code - tests\test_execution_planner.py
- [[TestDataClasses]] - code - tests\test_execution_planner.py
- [[TestEvaluatePlan]] - code - tests\test_execution_planner.py
- [[TestGetPlanningStats]] - code - tests\test_execution_planner.py
- [[TestSearchReusablePlans]] - code - tests\test_execution_planner.py
- [[TestStoreSuccessfulPlan]] - code - tests\test_execution_planner.py
- [[Tests for Pre-Execution Planning Pass.]] - rationale - tests\test_execution_planner.py
- [[When Grimoire has a matching plan, reuse it.]] - rationale - tests\test_execution_planner.py
- [[When Grimoire returns nothing, generate a new plan.]] - rationale - tests\test_execution_planner.py
- [[When model is available, adaptation generates new steps.]] - rationale - tests\test_execution_planner.py
- [[Without Grimoire, still generates plans via model.]] - rationale - tests\test_execution_planner.py
- [[Without a model, returns a single-step fallback plan.]] - rationale - tests\test_execution_planner.py
- [[_make_plan()]] - code - tests\test_execution_planner.py
- [[_make_step()]] - code - tests\test_execution_planner.py
- [[_mock_generate_fn()]] - code - tests\test_execution_planner.py
- [[execution_planner.py]] - code - modules\shadow\execution_planner.py
- [[test_execution_planner.py]] - code - tests\test_execution_planner.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Execution_Planner
SORT file.name ASC
```

## Connections to other communities
- 55 edges to [[_COMMUNITY_Async Task Queue]]
- 6 edges to [[_COMMUNITY_Base Module & Apex API]]
- 2 edges to [[_COMMUNITY_Adversarial Sparring]]
- 1 edge to [[_COMMUNITY_Workflow Store]]

## Top bridge nodes
- [[ExecutionPlanner]] - degree 122, connects to 2 communities
- [[_make_plan()]] - degree 17, connects to 1 community
- [[.store_successful_plan()]] - degree 8, connects to 1 community
- [[.search_reusable_plans()]] - degree 7, connects to 1 community
- [[._find_reusable_plan()]] - degree 5, connects to 1 community