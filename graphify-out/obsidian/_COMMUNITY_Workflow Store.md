---
type: community
cohesion: 0.04
members: 128
---

# Workflow Store

**Cohesion:** 0.04 - loosely connected
**Members:** 128 nodes

## Members
- [[.__init__()_94]] - code - modules\shadow\workflow_store.py
- [[._find_duplicate()_1]] - code - modules\shadow\workflow_store.py
- [[._generate_name()]] - code - modules\shadow\workflow_store.py
- [[._grimoire_results_to_workflows()]] - code - modules\shadow\workflow_store.py
- [[._init_db()_8]] - code - modules\shadow\workflow_store.py
- [[._parse_steps()]] - code - modules\shadow\workflow_store.py
- [[._row_to_workflow()]] - code - modules\shadow\workflow_store.py
- [[._search_candidates()]] - code - modules\shadow\workflow_store.py
- [[._sqlite_search()]] - code - modules\shadow\workflow_store.py
- [[._store_in_grimoire()_1]] - code - modules\shadow\workflow_store.py
- [[._update_existing()_1]] - code - modules\shadow\workflow_store.py
- [[.adapt_workflow()]] - code - modules\shadow\workflow_store.py
- [[.cleanup_unused()]] - code - modules\shadow\workflow_store.py
- [[.close()_18]] - code - modules\shadow\workflow_store.py
- [[.find_workflow()]] - code - modules\shadow\workflow_store.py
- [[.get_popular_workflows()]] - code - modules\shadow\workflow_store.py
- [[.get_workflow_stats()]] - code - modules\shadow\workflow_store.py
- [[.record_usage()]] - code - modules\shadow\workflow_store.py
- [[.store_workflow()]] - code - modules\shadow\workflow_store.py
- [[.test_creates_valid_workflow_in_sqlite()]] - code - tests\test_workflow_store.py
- [[.test_deduplicates_same_tool_sequence()]] - code - tests\test_workflow_store.py
- [[.test_different_tools_not_deduped()]] - code - tests\test_workflow_store.py
- [[.test_doesnt_delete_anything()]] - code - tests\test_workflow_store.py
- [[.test_empty_store_returns_empty()]] - code - tests\test_workflow_store.py
- [[.test_empty_store_returns_empty()_1]] - code - tests\test_workflow_store.py
- [[.test_empty_store_stats()]] - code - tests\test_workflow_store.py
- [[.test_failure_doesnt_decrement()]] - code - tests\test_workflow_store.py
- [[.test_filters_by_required_tools()]] - code - tests\test_workflow_store.py
- [[.test_filters_by_task_type()]] - code - tests\test_workflow_store.py
- [[.test_find_with_grimoire()]] - code - tests\test_workflow_store.py
- [[.test_flags_old_workflows()]] - code - tests\test_workflow_store.py
- [[.test_graceful_without_grimoire()_1]] - code - tests\test_workflow_store.py
- [[.test_increments_success_count()]] - code - tests\test_workflow_store.py
- [[.test_nonexistent_workflow_returns_false()]] - code - tests\test_workflow_store.py
- [[.test_preserves_tool_sequence()]] - code - tests\test_workflow_store.py
- [[.test_ranks_by_success_count()]] - code - tests\test_workflow_store.py
- [[.test_recent_workflows_not_flagged()]] - code - tests\test_workflow_store.py
- [[.test_returns_accurate_counts()_1]] - code - tests\test_workflow_store.py
- [[.test_returns_adapted_steps_as_dicts()]] - code - tests\test_workflow_store.py
- [[.test_returns_matching_workflows()]] - code - tests\test_workflow_store.py
- [[.test_returns_most_used()]] - code - tests\test_workflow_store.py
- [[.test_single_step_workflow_valid()]] - code - tests\test_workflow_store.py
- [[.test_sqlite_db_created_on_init()_3]] - code - tests\test_workflow_store.py
- [[.test_stores_domain_tags()]] - code - tests\test_workflow_store.py
- [[.test_stores_in_grimoire()_2]] - code - tests\test_workflow_store.py
- [[.test_updates_average_duration()]] - code - tests\test_workflow_store.py
- [[A complete stored workflow pattern.]] - rationale - modules\shadow\workflow_store.py
- [[A single step in a stored workflow.]] - rationale - modules\shadow\workflow_store.py
- [[All operations work when Grimoire is unavailable (SQLite-only).]] - rationale - tests\test_workflow_store.py
- [[Close the database connection._10]] - rationale - modules\shadow\workflow_store.py
- [[Convert Grimoire recall results to StoredWorkflow objects.]] - rationale - modules\shadow\workflow_store.py
- [[Convert a database row to a StoredWorkflow object.]] - rationale - modules\shadow\workflow_store.py
- [[Convert list of dicts to WorkflowStep objects.]] - rationale - modules\shadow\workflow_store.py
- [[Create the workflows table if it doesn't exist.]] - rationale - modules\shadow\workflow_store.py
- [[Edge cases and resilience tests.]] - rationale - tests\test_workflow_store.py
- [[Empty store find_workflow returns empty list.]] - rationale - tests\test_workflow_store.py
- [[Empty store get_popular_workflows returns empty list.]] - rationale - tests\test_workflow_store.py
- [[Empty store stats returns valid zeroes.]] - rationale - tests\test_workflow_store.py
- [[Fallback search SQLite by description keywords and task_type.]] - rationale - modules\shadow\workflow_store.py
- [[Find existing workflow with the exact same tool sequence.]] - rationale - modules\shadow\workflow_store.py
- [[Flag workflows not used in N days. NEVER deletes.          Returns]] - rationale - modules\shadow\workflow_store.py
- [[Generate a human-readable name for a workflow.]] - rationale - modules\shadow\workflow_store.py
- [[Initialize WorkflowStore.          Args             grimoire Optional Grimoire]] - rationale - modules\shadow\workflow_store.py
- [[Record that a workflow was used.          On success increment success_count, u]] - rationale - modules\shadow\workflow_store.py
- [[Return a mocked Grimoire instance.]] - rationale - tests\test_workflow_store.py
- [[Return a temp DB path.]] - rationale - tests\test_workflow_store.py
- [[Return aggregate stats for Harbinger briefings.          Keys total_workflows,]] - rationale - modules\shadow\workflow_store.py
- [[Return most-used workflows, ordered by success_count descending.]] - rationale - modules\shadow\workflow_store.py
- [[Return sample workflow steps as dicts.]] - rationale - tests\test_workflow_store.py
- [[SQLite DB is created on init._1]] - rationale - tests\test_workflow_store.py
- [[Search for candidate workflows via Grimoire or SQLite fallback.]] - rationale - modules\shadow\workflow_store.py
- [[Search for matching workflows.          Uses Grimoire semantic search when avail]] - rationale - modules\shadow\workflow_store.py
- [[Store a successful workflow as a reusable pattern.          Deduplication if a]] - rationale - modules\shadow\workflow_store.py
- [[Store workflow in Grimoire for semantic search.]] - rationale - modules\shadow\workflow_store.py
- [[StoredWorkflow]] - code - modules\shadow\workflow_store.py
- [[Stores and retrieves reusable multi-tool workflow patterns.      Usage]] - rationale - modules\shadow\workflow_store.py
- [[Take an existing workflow and adapt it for a new similar task.          Preserve]] - rationale - modules\shadow\workflow_store.py
- [[TestAdaptWorkflow]] - code - tests\test_workflow_store.py
- [[TestCleanupUnused]] - code - tests\test_workflow_store.py
- [[TestEdgeCases_22]] - code - tests\test_workflow_store.py
- [[TestFindWorkflow]] - code - tests\test_workflow_store.py
- [[TestGetPopularWorkflows]] - code - tests\test_workflow_store.py
- [[TestGetWorkflowStats]] - code - tests\test_workflow_store.py
- [[TestRecordUsage]] - code - tests\test_workflow_store.py
- [[TestStoreWorkflow]] - code - tests\test_workflow_store.py
- [[Tests for Tool Chain Workflow Storage]] - rationale - tests\test_workflow_store.py
- [[Tests for adapt_workflow method.]] - rationale - tests\test_workflow_store.py
- [[Tests for cleanup_unused method.]] - rationale - tests\test_workflow_store.py
- [[Tests for find_workflow method.]] - rationale - tests\test_workflow_store.py
- [[Tests for get_popular_workflows method.]] - rationale - tests\test_workflow_store.py
- [[Tests for get_workflow_stats method.]] - rationale - tests\test_workflow_store.py
- [[Tests for record_usage method.]] - rationale - tests\test_workflow_store.py
- [[Tests for store_workflow method.]] - rationale - tests\test_workflow_store.py
- [[Tool Chain Workflow Storage ============================== When a multi-tool wor]] - rationale - modules\shadow\workflow_store.py
- [[Update an existing workflow on dedup match.]] - rationale - modules\shadow\workflow_store.py
- [[Workflow with a single step is valid.]] - rationale - tests\test_workflow_store.py
- [[WorkflowStep]] - code - modules\shadow\workflow_store.py
- [[WorkflowStore]] - code - modules\shadow\workflow_store.py
- [[WorkflowStore with mocked Grimoire.]] - rationale - tests\test_workflow_store.py
- [[WorkflowStore with no Grimoire (SQLite-only mode).]] - rationale - tests\test_workflow_store.py
- [[Workflows with different tool sequences are not deduped.]] - rationale - tests\test_workflow_store.py
- [[_sample_steps()]] - code - tests\test_workflow_store.py
- [[adapt_workflow preserves the tool sequence.]] - rationale - tests\test_workflow_store.py
- [[adapt_workflow returns steps as list of dicts.]] - rationale - tests\test_workflow_store.py
- [[cleanup_unused doesn't flag recently used workflows.]] - rationale - tests\test_workflow_store.py
- [[cleanup_unused flags but never deletes.]] - rationale - tests\test_workflow_store.py
- [[cleanup_unused flags workflows not used in N days.]] - rationale - tests\test_workflow_store.py
- [[find_workflow filters by required_tools.]] - rationale - tests\test_workflow_store.py
- [[find_workflow filters by task_type.]] - rationale - tests\test_workflow_store.py
- [[find_workflow ranks by relevance  success_count.]] - rationale - tests\test_workflow_store.py
- [[find_workflow returns matching workflows via SQLite fallback.]] - rationale - tests\test_workflow_store.py
- [[find_workflow uses Grimoire semantic search when available.]] - rationale - tests\test_workflow_store.py
- [[get_popular_workflows returns workflows ordered by success_count.]] - rationale - tests\test_workflow_store.py
- [[get_workflow_stats returns accurate aggregate stats.]] - rationale - tests\test_workflow_store.py
- [[mock_grimoire()_17]] - code - tests\test_workflow_store.py
- [[record_usage increments success_count on success.]] - rationale - tests\test_workflow_store.py
- [[record_usage returns False for nonexistent workflow.]] - rationale - tests\test_workflow_store.py
- [[record_usage updates average_duration.]] - rationale - tests\test_workflow_store.py
- [[record_usage failure doesn't decrement success_count.]] - rationale - tests\test_workflow_store.py
- [[store()_1]] - code - tests\test_workflow_store.py
- [[store_with_grimoire()_1]] - code - tests\test_workflow_store.py
- [[store_workflow also stores in Grimoire for semantic search.]] - rationale - tests\test_workflow_store.py
- [[store_workflow creates a valid StoredWorkflow in SQLite.]] - rationale - tests\test_workflow_store.py
- [[store_workflow deduplicates workflows with same tool sequence.]] - rationale - tests\test_workflow_store.py
- [[store_workflow stores domain tags correctly.]] - rationale - tests\test_workflow_store.py
- [[test_workflow_store.py]] - code - tests\test_workflow_store.py
- [[tmp_db()_6]] - code - tests\test_workflow_store.py
- [[workflow_store.py]] - code - modules\shadow\workflow_store.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Workflow_Store
SORT file.name ASC
```

## Connections to other communities
- 18 edges to [[_COMMUNITY_Data Pipeline & Embeddings]]
- 8 edges to [[_COMMUNITY_Module Lifecycle]]
- 2 edges to [[_COMMUNITY_Cross-Reference & Security]]
- 2 edges to [[_COMMUNITY_Morpheus Creative Pipeline]]
- 1 edge to [[_COMMUNITY_Experiment Store]]
- 1 edge to [[_COMMUNITY_Serendipity Detector]]
- 1 edge to [[_COMMUNITY_Code Analyzer (Omen)]]
- 1 edge to [[_COMMUNITY_Adversarial Sparring]]
- 1 edge to [[_COMMUNITY_Execution Planner]]

## Top bridge nodes
- [[store()_1]] - degree 12, connects to 7 communities
- [[.store_workflow()]] - degree 31, connects to 2 communities
- [[.record_usage()]] - degree 11, connects to 2 communities
- [[.cleanup_unused()]] - degree 7, connects to 2 communities
- [[.get_popular_workflows()]] - degree 9, connects to 1 community