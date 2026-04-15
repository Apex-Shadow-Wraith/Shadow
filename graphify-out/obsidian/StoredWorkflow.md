---
source_file: "modules\shadow\workflow_store.py"
type: "code"
community: "Workflow Store"
location: "L48"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Workflow_Store
---

# StoredWorkflow

## Connections
- [[._row_to_workflow()]] - `calls` [EXTRACTED]
- [[A complete stored workflow pattern.]] - `rationale_for` [EXTRACTED]
- [[All operations work when Grimoire is unavailable (SQLite-only).]] - `uses` [INFERRED]
- [[Edge cases and resilience tests.]] - `uses` [INFERRED]
- [[Empty store find_workflow returns empty list.]] - `uses` [INFERRED]
- [[Empty store get_popular_workflows returns empty list.]] - `uses` [INFERRED]
- [[Empty store stats returns valid zeroes.]] - `uses` [INFERRED]
- [[Return a mocked Grimoire instance.]] - `uses` [INFERRED]
- [[Return a temp DB path.]] - `uses` [INFERRED]
- [[Return sample workflow steps as dicts.]] - `uses` [INFERRED]
- [[SQLite DB is created on init._1]] - `uses` [INFERRED]
- [[TestAdaptWorkflow]] - `uses` [INFERRED]
- [[TestCleanupUnused]] - `uses` [INFERRED]
- [[TestEdgeCases_22]] - `uses` [INFERRED]
- [[TestFindWorkflow]] - `uses` [INFERRED]
- [[TestGetPopularWorkflows]] - `uses` [INFERRED]
- [[TestGetWorkflowStats]] - `uses` [INFERRED]
- [[TestRecordUsage]] - `uses` [INFERRED]
- [[TestStoreWorkflow]] - `uses` [INFERRED]
- [[Tests for Tool Chain Workflow Storage]] - `uses` [INFERRED]
- [[Tests for adapt_workflow method.]] - `uses` [INFERRED]
- [[Tests for cleanup_unused method.]] - `uses` [INFERRED]
- [[Tests for find_workflow method.]] - `uses` [INFERRED]
- [[Tests for get_popular_workflows method.]] - `uses` [INFERRED]
- [[Tests for get_workflow_stats method.]] - `uses` [INFERRED]
- [[Tests for record_usage method.]] - `uses` [INFERRED]
- [[Tests for store_workflow method.]] - `uses` [INFERRED]
- [[Workflow with a single step is valid.]] - `uses` [INFERRED]
- [[WorkflowStore with mocked Grimoire.]] - `uses` [INFERRED]
- [[WorkflowStore with no Grimoire (SQLite-only mode).]] - `uses` [INFERRED]
- [[Workflows with different tool sequences are not deduped.]] - `uses` [INFERRED]
- [[adapt_workflow preserves the tool sequence.]] - `uses` [INFERRED]
- [[adapt_workflow returns steps as list of dicts.]] - `uses` [INFERRED]
- [[cleanup_unused doesn't flag recently used workflows.]] - `uses` [INFERRED]
- [[cleanup_unused flags but never deletes.]] - `uses` [INFERRED]
- [[cleanup_unused flags workflows not used in N days.]] - `uses` [INFERRED]
- [[find_workflow filters by required_tools.]] - `uses` [INFERRED]
- [[find_workflow filters by task_type.]] - `uses` [INFERRED]
- [[find_workflow ranks by relevance  success_count.]] - `uses` [INFERRED]
- [[find_workflow returns matching workflows via SQLite fallback.]] - `uses` [INFERRED]
- [[find_workflow uses Grimoire semantic search when available.]] - `uses` [INFERRED]
- [[get_popular_workflows returns workflows ordered by success_count.]] - `uses` [INFERRED]
- [[get_workflow_stats returns accurate aggregate stats.]] - `uses` [INFERRED]
- [[record_usage increments success_count on success.]] - `uses` [INFERRED]
- [[record_usage returns False for nonexistent workflow.]] - `uses` [INFERRED]
- [[record_usage updates average_duration.]] - `uses` [INFERRED]
- [[record_usage failure doesn't decrement success_count.]] - `uses` [INFERRED]
- [[store_workflow also stores in Grimoire for semantic search.]] - `uses` [INFERRED]
- [[store_workflow creates a valid StoredWorkflow in SQLite.]] - `uses` [INFERRED]
- [[store_workflow deduplicates workflows with same tool sequence.]] - `uses` [INFERRED]
- [[store_workflow stores domain tags correctly.]] - `uses` [INFERRED]
- [[workflow_store.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Workflow_Store