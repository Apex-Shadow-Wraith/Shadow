---
source_file: "modules\shadow\context_orchestrator.py"
type: "code"
community: "Context Orchestrator"
location: "L30"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Context_Orchestrator
---

# ContextPackage

## Connections
- [[.build_minimal_context()]] - `calls` [EXTRACTED]
- [[.build_optimal_context()]] - `calls` [EXTRACTED]
- [[.test_context_package_dataclass_defaults()]] - `calls` [INFERRED]
- [[Complete context package ready for an LLM call.]] - `rationale_for` [EXTRACTED]
- [[ContextOrchestrator accepts all components without error.]] - `uses` [INFERRED]
- [[ContextOrchestrator with all dependencies available.]] - `uses` [INFERRED]
- [[ContextOrchestrator(None) works — used by orchestrator fallback path.]] - `uses` [INFERRED]
- [[ContextPackage has sensible defaults for all fields.]] - `uses` [INFERRED]
- [[Each missing dependency skips its pipeline step without errors.]] - `uses` [INFERRED]
- [[Empty patterns returns empty string.]] - `uses` [INFERRED]
- [[Empty staged retrieval results produce empty grimoire_context.]] - `uses` [INFERRED]
- [[Empty task description doesn't crash.]] - `uses` [INFERRED]
- [[Estimate returns plausible token counts and percentages.]] - `uses` [INFERRED]
- [[Estimate works without ContextManager (uses defaults).]] - `uses` [INFERRED]
- [[Grimoire context is populated from staged retrieval results.]] - `uses` [INFERRED]
- [[If compressor raises, pipeline continues with raw history.]] - `uses` [INFERRED]
- [[If staged retrieval raises, pipeline continues.]] - `uses` [INFERRED]
- [[If tool loader raises, pipeline continues with empty tools.]] - `uses` [INFERRED]
- [[Minimal context doesn't search failure patterns.]] - `uses` [INFERRED]
- [[Minimal context doesn't trigger Grimoire search.]] - `uses` [INFERRED]
- [[Minimal context loads only core tools.]] - `uses` [INFERRED]
- [[Minimal context returns a package with no grimoire or failure patterns.]] - `uses` [INFERRED]
- [[Mock ContextCompressor.]] - `uses` [INFERRED]
- [[Mock ContextManager with token estimation and limits.]] - `uses` [INFERRED]
- [[Mock DynamicToolLoader.]] - `uses` [INFERRED]
- [[Mock FailurePatternDB.]] - `uses` [INFERRED]
- [[Mock Grimoire module.]] - `uses` [INFERRED]
- [[Mock StagedRetrieval.]] - `uses` [INFERRED]
- [[No conversation history returns package with empty messages.]] - `uses` [INFERRED]
- [[None conversation history handled gracefully.]] - `uses` [INFERRED]
- [[Pipeline attempts to load failure patterns.]] - `uses` [INFERRED]
- [[Pipeline calls compressor on conversation history.]] - `uses` [INFERRED]
- [[Pipeline calls staged retrieval with task description.]] - `uses` [INFERRED]
- [[Pipeline calls tool loader with target module.]] - `uses` [INFERRED]
- [[Profile returns valid stats after multiple builds.]] - `uses` [INFERRED]
- [[Profile returns zeros when no builds have happened.]] - `uses` [INFERRED]
- [[Result total_tokens should not exceed token_budget.]] - `uses` [INFERRED]
- [[Retrieval stats contain staged retrieval metadata.]] - `uses` [INFERRED]
- [[System prompt must never be trimmed, even with tiny budget.]] - `uses` [INFERRED]
- [[Task without module key loads tools with module_name=None.]] - `uses` [INFERRED]
- [[TestBuildMinimalContext]] - `uses` [INFERRED]
- [[TestBuildOptimalContext]] - `uses` [INFERRED]
- [[TestContextProfile]] - `uses` [INFERRED]
- [[TestEdgeCases_5]] - `uses` [INFERRED]
- [[TestGracefulDegradation_2]] - `uses` [INFERRED]
- [[TestOrchestratorIntegration]] - `uses` [INFERRED]
- [[Tests for ContextOrchestrator — unified context assembly pipeline.  Covers pipe]] - `uses` [INFERRED]
- [[Tests for build_minimal_context.]] - `uses` [INFERRED]
- [[Tests for build_optimal_context pipeline.]] - `uses` [INFERRED]
- [[Tests for edge cases and boundary conditions.]] - `uses` [INFERRED]
- [[Tests for get_context_profile and estimate_context_for_task.]] - `uses` [INFERRED]
- [[Tests for graceful degradation when dependencies are missing.]] - `uses` [INFERRED]
- [[Tests for orchestrator integration patterns.]] - `uses` [INFERRED]
- [[Token breakdown components sum to approximately total_tokens.]] - `uses` [INFERRED]
- [[Unknown model uses default token limit.]] - `uses` [INFERRED]
- [[Very long system prompt is preserved (never trimmed).]] - `uses` [INFERRED]
- [[When context exceeds budget, trimming occurs.]] - `uses` [INFERRED]
- [[With no tool loader, minimal context has empty tool_schemas.]] - `uses` [INFERRED]
- [[Works with all dependencies None — returns empty but valid package.]] - `uses` [INFERRED]
- [[Works with only ContextManager — token estimation works, rest empty.]] - `uses` [INFERRED]
- [[Works with only grimoirestaged_retrieval — retrieval works, rest defaults.]] - `uses` [INFERRED]
- [[Works with only tool_loader — tools loaded, rest defaults.]] - `uses` [INFERRED]
- [[_load_failure_patterns_from_results formats patterns correctly.]] - `uses` [INFERRED]
- [[build_optimal_context returns a ContextPackage with all fields populated.]] - `uses` [INFERRED]
- [[context_orchestrator.py]] - `contains` [EXTRACTED]
- [[set_failure_patterns stores patterns for later use.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Context_Orchestrator