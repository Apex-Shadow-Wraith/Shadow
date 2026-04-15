---
type: community
cohesion: 0.02
members: 140
---

# Context Orchestrator

**Cohesion:** 0.02 - loosely connected
**Members:** 140 nodes

## Members
- [[._calculate_token_breakdown()]] - code - modules\shadow\context_orchestrator.py
- [[._estimate_tokens()_1]] - code - modules\shadow\context_orchestrator.py
- [[._get_token_budget()]] - code - modules\shadow\context_orchestrator.py
- [[._load_failure_patterns()]] - code - modules\shadow\context_orchestrator.py
- [[._load_failure_patterns_from_results()]] - code - modules\shadow\context_orchestrator.py
- [[._record_build_stats()]] - code - modules\shadow\context_orchestrator.py
- [[._trim_to_budget()]] - code - modules\shadow\context_orchestrator.py
- [[.build_minimal_context()]] - code - modules\shadow\context_orchestrator.py
- [[.build_optimal_context()]] - code - modules\shadow\context_orchestrator.py
- [[.estimate_context_for_task()]] - code - modules\shadow\context_orchestrator.py
- [[.get_context_profile()]] - code - modules\shadow\context_orchestrator.py
- [[.set_failure_patterns()]] - code - modules\shadow\context_orchestrator.py
- [[.test_all_dependencies_none()]] - code - tests\test_context_orchestrator.py
- [[.test_calls_compressor()]] - code - tests\test_context_orchestrator.py
- [[.test_calls_dynamic_tool_loader()]] - code - tests\test_context_orchestrator.py
- [[.test_calls_failure_pattern_search()]] - code - tests\test_context_orchestrator.py
- [[.test_calls_staged_retrieval()]] - code - tests\test_context_orchestrator.py
- [[.test_compressor_exception_handled()]] - code - tests\test_context_orchestrator.py
- [[.test_context_package_dataclass_defaults()]] - code - tests\test_context_orchestrator.py
- [[.test_doesnt_call_failure_patterns()]] - code - tests\test_context_orchestrator.py
- [[.test_doesnt_call_grimoire()]] - code - tests\test_context_orchestrator.py
- [[.test_empty_task_description()]] - code - tests\test_context_orchestrator.py
- [[.test_estimate_no_context_manager()]] - code - tests\test_context_orchestrator.py
- [[.test_estimate_returns_reasonable_values()]] - code - tests\test_context_orchestrator.py
- [[.test_fallback_when_unavailable()]] - code - tests\test_context_orchestrator.py
- [[.test_grimoire_context_populated()]] - code - tests\test_context_orchestrator.py
- [[.test_load_failure_patterns_from_results()]] - code - tests\test_context_orchestrator.py
- [[.test_load_failure_patterns_from_results_empty()]] - code - tests\test_context_orchestrator.py
- [[.test_loads_core_tools_only()]] - code - tests\test_context_orchestrator.py
- [[.test_missing_dependency_skips_gracefully()]] - code - tests\test_context_orchestrator.py
- [[.test_model_not_in_config_uses_default()]] - code - tests\test_context_orchestrator.py
- [[.test_no_conversation_history()]] - code - tests\test_context_orchestrator.py
- [[.test_no_tool_loader_returns_empty()]] - code - tests\test_context_orchestrator.py
- [[.test_none_conversation_history()]] - code - tests\test_context_orchestrator.py
- [[.test_only_context_manager_available()]] - code - tests\test_context_orchestrator.py
- [[.test_only_grimoire_available()]] - code - tests\test_context_orchestrator.py
- [[.test_only_tool_loader_available()]] - code - tests\test_context_orchestrator.py
- [[.test_orchestrator_initializes_with_available_components()]] - code - tests\test_context_orchestrator.py
- [[.test_produces_valid_context_package()]] - code - tests\test_context_orchestrator.py
- [[.test_profile_empty_when_no_builds()]] - code - tests\test_context_orchestrator.py
- [[.test_profile_valid_after_multiple_builds()]] - code - tests\test_context_orchestrator.py
- [[.test_respects_token_budget()]] - code - tests\test_context_orchestrator.py
- [[.test_retrieval_stats_populated()]] - code - tests\test_context_orchestrator.py
- [[.test_returns_small_context_package()]] - code - tests\test_context_orchestrator.py
- [[.test_set_failure_patterns()]] - code - tests\test_context_orchestrator.py
- [[.test_staged_retrieval_empty_results()]] - code - tests\test_context_orchestrator.py
- [[.test_staged_retrieval_exception_handled()]] - code - tests\test_context_orchestrator.py
- [[.test_system_prompt_never_trimmed()]] - code - tests\test_context_orchestrator.py
- [[.test_task_with_no_module()]] - code - tests\test_context_orchestrator.py
- [[.test_token_breakdown_sums_approximately()]] - code - tests\test_context_orchestrator.py
- [[.test_tool_loader_exception_handled()]] - code - tests\test_context_orchestrator.py
- [[.test_trims_when_over_budget()]] - code - tests\test_context_orchestrator.py
- [[.test_very_long_system_prompt()]] - code - tests\test_context_orchestrator.py
- [[Assemble the optimal context window for an LLM call.          Pipeline]] - rationale - modules\shadow\context_orchestrator.py
- [[Calculate token counts per component.]] - rationale - modules\shadow\context_orchestrator.py
- [[Complete context package ready for an LLM call.]] - rationale - modules\shadow\context_orchestrator.py
- [[Context Orchestrator — Unified Context Assembly Pipeline =======================]] - rationale - modules\shadow\context_orchestrator.py
- [[ContextOrchestrator accepts all components without error.]] - rationale - tests\test_context_orchestrator.py
- [[ContextOrchestrator with all dependencies available.]] - rationale - tests\test_context_orchestrator.py
- [[ContextOrchestrator(None) works — used by orchestrator fallback path.]] - rationale - tests\test_context_orchestrator.py
- [[ContextPackage]] - code - modules\shadow\context_orchestrator.py
- [[ContextPackage has sensible defaults for all fields.]] - rationale - tests\test_context_orchestrator.py
- [[Each missing dependency skips its pipeline step without errors.]] - rationale - tests\test_context_orchestrator.py
- [[Empty patterns returns empty string.]] - rationale - tests\test_context_orchestrator.py
- [[Empty staged retrieval results produce empty grimoire_context.]] - rationale - tests\test_context_orchestrator.py
- [[Empty task description doesn't crash.]] - rationale - tests\test_context_orchestrator.py
- [[Estimate returns plausible token counts and percentages.]] - rationale - tests\test_context_orchestrator.py
- [[Estimate tokens for text using ContextManager or fallback heuristic.]] - rationale - modules\shadow\context_orchestrator.py
- [[Estimate works without ContextManager (uses defaults).]] - rationale - tests\test_context_orchestrator.py
- [[Format pre-fetched failure patterns for context inclusion.]] - rationale - modules\shadow\context_orchestrator.py
- [[Get the effective token budget for a model.]] - rationale - modules\shadow\context_orchestrator.py
- [[Grimoire context is populated from staged retrieval results.]] - rationale - tests\test_context_orchestrator.py
- [[If compressor raises, pipeline continues with raw history.]] - rationale - tests\test_context_orchestrator.py
- [[If staged retrieval raises, pipeline continues.]] - rationale - tests\test_context_orchestrator.py
- [[If tool loader raises, pipeline continues with empty tools.]] - rationale - tests\test_context_orchestrator.py
- [[Lightweight context for simplefast tasks.          No Grimoire search, no failu]] - rationale - modules\shadow\context_orchestrator.py
- [[Minimal context doesn't search failure patterns.]] - rationale - tests\test_context_orchestrator.py
- [[Minimal context doesn't trigger Grimoire search.]] - rationale - tests\test_context_orchestrator.py
- [[Minimal context loads only core tools.]] - rationale - tests\test_context_orchestrator.py
- [[Minimal context returns a package with no grimoire or failure patterns.]] - rationale - tests\test_context_orchestrator.py
- [[Mock ContextCompressor.]] - rationale - tests\test_context_orchestrator.py
- [[Mock ContextManager with token estimation and limits.]] - rationale - tests\test_context_orchestrator.py
- [[Mock DynamicToolLoader.]] - rationale - tests\test_context_orchestrator.py
- [[Mock FailurePatternDB.]] - rationale - tests\test_context_orchestrator.py
- [[Mock Grimoire module.]] - rationale - tests\test_context_orchestrator.py
- [[Mock StagedRetrieval.]] - rationale - tests\test_context_orchestrator.py
- [[No conversation history returns package with empty messages.]] - rationale - tests\test_context_orchestrator.py
- [[None conversation history handled gracefully.]] - rationale - tests\test_context_orchestrator.py
- [[Pipeline attempts to load failure patterns.]] - rationale - tests\test_context_orchestrator.py
- [[Pipeline calls compressor on conversation history.]] - rationale - tests\test_context_orchestrator.py
- [[Pipeline calls staged retrieval with task description.]] - rationale - tests\test_context_orchestrator.py
- [[Pipeline calls tool loader with target module.]] - rationale - tests\test_context_orchestrator.py
- [[Profile returns valid stats after multiple builds.]] - rationale - tests\test_context_orchestrator.py
- [[Profile returns zeros when no builds have happened.]] - rationale - tests\test_context_orchestrator.py
- [[Quick estimate WITHOUT actually building the context.          Returns estimated]] - rationale - modules\shadow\context_orchestrator.py
- [[Record build stats for profiling.]] - rationale - modules\shadow\context_orchestrator.py
- [[Result total_tokens should not exceed token_budget.]] - rationale - tests\test_context_orchestrator.py
- [[Retrieval stats contain staged retrieval metadata.]] - rationale - tests\test_context_orchestrator.py
- [[Search FailurePatternDB and format patterns for context.]] - rationale - modules\shadow\context_orchestrator.py
- [[Set pre-fetched failure patterns (called by orchestrator after async fetch).]] - rationale - modules\shadow\context_orchestrator.py
- [[Stats from the last N builds for Growth Engine and Harbinger.]] - rationale - modules\shadow\context_orchestrator.py
- [[System prompt must never be trimmed, even with tiny budget.]] - rationale - tests\test_context_orchestrator.py
- [[Task without module key loads tools with module_name=None.]] - rationale - tests\test_context_orchestrator.py
- [[TestBuildMinimalContext]] - code - tests\test_context_orchestrator.py
- [[TestBuildOptimalContext]] - code - tests\test_context_orchestrator.py
- [[TestContextProfile]] - code - tests\test_context_orchestrator.py
- [[TestEdgeCases_5]] - code - tests\test_context_orchestrator.py
- [[TestGracefulDegradation_2]] - code - tests\test_context_orchestrator.py
- [[TestOrchestratorIntegration]] - code - tests\test_context_orchestrator.py
- [[Tests for ContextOrchestrator — unified context assembly pipeline.  Covers pipe]] - rationale - tests\test_context_orchestrator.py
- [[Tests for build_minimal_context.]] - rationale - tests\test_context_orchestrator.py
- [[Tests for build_optimal_context pipeline.]] - rationale - tests\test_context_orchestrator.py
- [[Tests for edge cases and boundary conditions.]] - rationale - tests\test_context_orchestrator.py
- [[Tests for get_context_profile and estimate_context_for_task.]] - rationale - tests\test_context_orchestrator.py
- [[Tests for graceful degradation when dependencies are missing.]] - rationale - tests\test_context_orchestrator.py
- [[Tests for orchestrator integration patterns.]] - rationale - tests\test_context_orchestrator.py
- [[Token breakdown components sum to approximately total_tokens.]] - rationale - tests\test_context_orchestrator.py
- [[Trim context components to fit within token budget.          Priority order (tri]] - rationale - modules\shadow\context_orchestrator.py
- [[Unknown model uses default token limit.]] - rationale - tests\test_context_orchestrator.py
- [[Very long system prompt is preserved (never trimmed).]] - rationale - tests\test_context_orchestrator.py
- [[When context exceeds budget, trimming occurs.]] - rationale - tests\test_context_orchestrator.py
- [[With no tool loader, minimal context has empty tool_schemas.]] - rationale - tests\test_context_orchestrator.py
- [[Works with all dependencies None — returns empty but valid package.]] - rationale - tests\test_context_orchestrator.py
- [[Works with only ContextManager — token estimation works, rest empty.]] - rationale - tests\test_context_orchestrator.py
- [[Works with only grimoirestaged_retrieval — retrieval works, rest defaults.]] - rationale - tests\test_context_orchestrator.py
- [[Works with only tool_loader — tools loaded, rest defaults.]] - rationale - tests\test_context_orchestrator.py
- [[_load_failure_patterns_from_results formats patterns correctly.]] - rationale - tests\test_context_orchestrator.py
- [[build_optimal_context returns a ContextPackage with all fields populated.]] - rationale - tests\test_context_orchestrator.py
- [[context_orchestrator.py]] - code - modules\shadow\context_orchestrator.py
- [[full_orchestrator()]] - code - tests\test_context_orchestrator.py
- [[mock_compressor()]] - code - tests\test_context_orchestrator.py
- [[mock_context_manager()]] - code - tests\test_context_orchestrator.py
- [[mock_failure_pattern_db()]] - code - tests\test_context_orchestrator.py
- [[mock_grimoire()_2]] - code - tests\test_context_orchestrator.py
- [[mock_staged_retrieval()]] - code - tests\test_context_orchestrator.py
- [[mock_tool_loader()]] - code - tests\test_context_orchestrator.py
- [[sample_history()_1]] - code - tests\test_context_orchestrator.py
- [[sample_task()]] - code - tests\test_context_orchestrator.py
- [[set_failure_patterns stores patterns for later use.]] - rationale - tests\test_context_orchestrator.py
- [[test_context_orchestrator.py]] - code - tests\test_context_orchestrator.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Context_Orchestrator
SORT file.name ASC
```

## Connections to other communities
- 94 edges to [[_COMMUNITY_Async Task Queue]]
- 4 edges to [[_COMMUNITY_Context Compression]]
- 3 edges to [[_COMMUNITY_Base Module & Apex API]]
- 1 edge to [[_COMMUNITY_Module Lifecycle]]
- 1 edge to [[_COMMUNITY_Module Registry & Tools]]

## Top bridge nodes
- [[.build_optimal_context()]] - degree 41, connects to 5 communities
- [[.build_minimal_context()]] - degree 12, connects to 2 communities
- [[._estimate_tokens()_1]] - degree 6, connects to 2 communities
- [[._get_token_budget()]] - degree 6, connects to 2 communities
- [[._load_failure_patterns_from_results()]] - degree 5, connects to 2 communities