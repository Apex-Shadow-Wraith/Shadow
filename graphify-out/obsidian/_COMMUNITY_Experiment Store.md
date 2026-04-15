---
type: community
cohesion: 0.04
members: 127
---

# Experiment Store

**Cohesion:** 0.04 - loosely connected
**Members:** 127 nodes

## Members
- [[.__init__()_28]] - code - modules\morpheus\experiment_store.py
- [[._all_different_conditions()]] - code - modules\morpheus\experiment_store.py
- [[._any_trigger_met()]] - code - modules\morpheus\experiment_store.py
- [[._create_tables()_1]] - code - modules\morpheus\experiment_store.py
- [[._row_to_experiment()]] - code - modules\morpheus\experiment_store.py
- [[._store_in_grimoire()]] - code - modules\morpheus\experiment_store.py
- [[._trigger_met()]] - code - modules\morpheus\experiment_store.py
- [[._update_experiment()]] - code - modules\morpheus\experiment_store.py
- [[.check_retry_triggers()]] - code - modules\morpheus\experiment_store.py
- [[.close()_4]] - code - modules\morpheus\experiment_store.py
- [[.get_experiment_stats()]] - code - modules\morpheus\experiment_store.py
- [[.get_experiments_by_domain()]] - code - modules\morpheus\experiment_store.py
- [[.get_pending_retries()]] - code - modules\morpheus\experiment_store.py
- [[.queue_for_retry()]] - code - modules\morpheus\experiment_store.py
- [[.record_retry_result()]] - code - modules\morpheus\experiment_store.py
- [[.store_experiment()]] - code - modules\morpheus\experiment_store.py
- [[.store_failure()]] - code - modules\morpheus\experiment_store.py
- [[.test_creates_correct_experiment()]] - code - tests\test_experiment_store.py
- [[.test_db_created_if_not_exists()]] - code - tests\test_experiment_store.py
- [[.test_deprioritized_excluded_by_default()]] - code - tests\test_experiment_store.py
- [[.test_deprioritized_included_when_requested()]] - code - tests\test_experiment_store.py
- [[.test_deprioritized_not_returned()]] - code - tests\test_experiment_store.py
- [[.test_deprioritizes_after_3_different_conditions()]] - code - tests\test_experiment_store.py
- [[.test_does_not_deprioritize_same_conditions()]] - code - tests\test_experiment_store.py
- [[.test_embedding_model_changed_trigger()]] - code - tests\test_experiment_store.py
- [[.test_excludes_non_queued()]] - code - tests\test_experiment_store.py
- [[.test_failure_does_not_store_in_grimoire()]] - code - tests\test_experiment_store.py
- [[.test_failure_updates_attempt_history()]] - code - tests\test_experiment_store.py
- [[.test_filters_correctly()]] - code - tests\test_experiment_store.py
- [[.test_grimoire_none_no_error()]] - code - tests\test_experiment_store.py
- [[.test_grimoire_unavailable_graceful()]] - code - tests\test_experiment_store.py
- [[.test_increments_attempt_count()]] - code - tests\test_experiment_store.py
- [[.test_knowledge_depth_trigger()]] - code - tests\test_experiment_store.py
- [[.test_model_changed_same_model()]] - code - tests\test_experiment_store.py
- [[.test_model_changed_trigger()]] - code - tests\test_experiment_store.py
- [[.test_new_grimoire_knowledge_trigger()]] - code - tests\test_experiment_store.py
- [[.test_persists_to_sqlite()]] - code - tests\test_experiment_store.py
- [[.test_returns_accurate_counts()]] - code - tests\test_experiment_store.py
- [[.test_returns_false_for_missing_id()]] - code - tests\test_experiment_store.py
- [[.test_returns_false_for_missing_id()_1]] - code - tests\test_experiment_store.py
- [[.test_returns_queued_ordered_correctly()]] - code - tests\test_experiment_store.py
- [[.test_success_stores_in_grimoire()]] - code - tests\test_experiment_store.py
- [[.test_success_updates_status_and_grimoire()]] - code - tests\test_experiment_store.py
- [[.test_tool_added_trigger()]] - code - tests\test_experiment_store.py
- [[.test_trigger_not_met()]] - code - tests\test_experiment_store.py
- [[.test_zero_retry_triggers_never_matches()]] - code - tests\test_experiment_store.py
- [[A tracked experiment with retry trigger support.]] - rationale - modules\morpheus\experiment_store.py
- [[Check if all attempts in history had different conditions.          Returns Fals]] - rationale - modules\morpheus\experiment_store.py
- [[Check if any of the experiment's retry triggers are met.]] - rationale - modules\morpheus\experiment_store.py
- [[Close the database connection._2]] - rationale - modules\morpheus\experiment_store.py
- [[Convenience method to store a failed experiment.          Args             hypo]] - rationale - modules\morpheus\experiment_store.py
- [[Convert a database row to an Experiment dataclass.]] - rationale - modules\morpheus\experiment_store.py
- [[Create a mock Grimoire module.]] - rationale - tests\test_experiment_store.py
- [[Create an ExperimentStore with a mock Grimoire.]] - rationale - tests\test_experiment_store.py
- [[Create an ExperimentStore with a temporary database.]] - rationale - tests\test_experiment_store.py
- [[Create the experiments table if it doesn't exist.]] - rationale - modules\morpheus\experiment_store.py
- [[Deprioritized experiments are not returned by check_retry_triggers.]] - rationale - tests\test_experiment_store.py
- [[Deprioritized experiments excluded by default.]] - rationale - tests\test_experiment_store.py
- [[Deprioritized experiments included with include_deprioritized=True.]] - rationale - tests\test_experiment_store.py
- [[Edge case and robustness tests.]] - rationale - tests\test_experiment_store.py
- [[Evaluate a single trigger against current conditions.]] - rationale - modules\morpheus\experiment_store.py
- [[Experiment]] - code - modules\morpheus\experiment_store.py
- [[Experiment not returned when triggers are not met.]] - rationale - tests\test_experiment_store.py
- [[Experiment with 0 retry_triggers never triggers retry.]] - rationale - tests\test_experiment_store.py
- [[ExperimentStore]] - code - modules\morpheus\experiment_store.py
- [[ExperimentStore — Failed Experiment Knowledge Base with Retry Triggers =========]] - rationale - modules\morpheus\experiment_store.py
- [[Failed retry updates attempt_history.]] - rationale - tests\test_experiment_store.py
- [[Filter experiments by domain tag.          Args             domain Domain tag]] - rationale - modules\morpheus\experiment_store.py
- [[Graceful handling when Grimoire raises an exception.]] - rationale - tests\test_experiment_store.py
- [[Helper to create an Experiment with sensible defaults.]] - rationale - tests\test_experiment_store.py
- [[No error when grimoire is None and experiment succeeds.]] - rationale - tests\test_experiment_store.py
- [[Queue an experiment for retry.          Increments attempt_count and adds to att]] - rationale - modules\morpheus\experiment_store.py
- [[Record the result of a retried experiment.          Args             experiment]] - rationale - modules\morpheus\experiment_store.py
- [[Return a path to a temporary database file.]] - rationale - tests\test_experiment_store.py
- [[Return aggregate statistics for reporting.          Returns             Dict wi]] - rationale - modules\morpheus\experiment_store.py
- [[Return experiments queued for retry, ordered by priority.          Fewer attempt]] - rationale - modules\morpheus\experiment_store.py
- [[SQLite DB is created if it doesn't exist.]] - rationale - tests\test_experiment_store.py
- [[SQLite-backed store for experiments with retry trigger logic.      Args]] - rationale - modules\morpheus\experiment_store.py
- [[Scan failed experiments and return those whose retry triggers are met.]] - rationale - modules\morpheus\experiment_store.py
- [[Store an experiment in SQLite.          If the experiment succeeded, also store]] - rationale - modules\morpheus\experiment_store.py
- [[Store experiment findings in Grimoire knowledge base.]] - rationale - modules\morpheus\experiment_store.py
- [[Successful retry updates status and stores in Grimoire.]] - rationale - tests\test_experiment_store.py
- [[TestCheckRetryTriggers]] - code - tests\test_experiment_store.py
- [[TestEdgeCases_8]] - code - tests\test_experiment_store.py
- [[TestGetExperimentStats]] - code - tests\test_experiment_store.py
- [[TestGetExperimentsByDomain]] - code - tests\test_experiment_store.py
- [[TestGetPendingRetries]] - code - tests\test_experiment_store.py
- [[TestQueueForRetry]] - code - tests\test_experiment_store.py
- [[TestRecordRetryResult]] - code - tests\test_experiment_store.py
- [[TestStoreExperiment]] - code - tests\test_experiment_store.py
- [[TestStoreFailure]] - code - tests\test_experiment_store.py
- [[Tests for ExperimentStore — Failed Experiment Knowledge Base with Retry Triggers]] - rationale - tests\test_experiment_store.py
- [[Tests for check_retry_triggers.]] - rationale - tests\test_experiment_store.py
- [[Tests for get_experiment_stats.]] - rationale - tests\test_experiment_store.py
- [[Tests for get_experiments_by_domain.]] - rationale - tests\test_experiment_store.py
- [[Tests for get_pending_retries.]] - rationale - tests\test_experiment_store.py
- [[Tests for queue_for_retry.]] - rationale - tests\test_experiment_store.py
- [[Tests for record_retry_result.]] - rationale - tests\test_experiment_store.py
- [[Tests for store_experiment.]] - rationale - tests\test_experiment_store.py
- [[Tests for store_failure.]] - rationale - tests\test_experiment_store.py
- [[Trigger 'embedding_model_changed' fires when embedding model differs.]] - rationale - tests\test_experiment_store.py
- [[Trigger 'knowledge_depthcuda5' matches when domain has 5+ entries.]] - rationale - tests\test_experiment_store.py
- [[Trigger 'model_changed' does NOT fire when model is the same.]] - rationale - tests\test_experiment_store.py
- [[Trigger 'model_changed' fires when model differs from experiment conditions.]] - rationale - tests\test_experiment_store.py
- [[Trigger 'new_grimoire_knowledgecuda' matches when conditions include cuda.]] - rationale - tests\test_experiment_store.py
- [[Trigger 'tool_addedcuda_kernel' matches when tool is available.]] - rationale - tests\test_experiment_store.py
- [[Update an experiment in the database.]] - rationale - modules\morpheus\experiment_store.py
- [[_make_experiment()]] - code - tests\test_experiment_store.py
- [[experiment_store.py]] - code - modules\morpheus\experiment_store.py
- [[get_experiment_stats returns accurate counts for all statuses.]] - rationale - tests\test_experiment_store.py
- [[get_experiments_by_domain filters by domain tag.]] - rationale - tests\test_experiment_store.py
- [[get_pending_retries excludes experiments not queued for retry.]] - rationale - tests\test_experiment_store.py
- [[get_pending_retries returns queued experiments ordered by attempt_count.]] - rationale - tests\test_experiment_store.py
- [[mock_grimoire()_6]] - code - tests\test_experiment_store.py
- [[queue_for_retry does NOT deprioritize if same conditions (not genuinely differen]] - rationale - tests\test_experiment_store.py
- [[queue_for_retry increments attempt_count.]] - rationale - tests\test_experiment_store.py
- [[queue_for_retry returns False for non-existent experiment.]] - rationale - tests\test_experiment_store.py
- [[queue_for_retry sets deprioritized after 3 failed attempts under different condi]] - rationale - tests\test_experiment_store.py
- [[record_retry_result returns False for non-existent experiment.]] - rationale - tests\test_experiment_store.py
- [[store()]] - code - tests\test_experiment_store.py
- [[store_experiment persists to SQLite and returns the ID.]] - rationale - tests\test_experiment_store.py
- [[store_experiment with success=False does not call Grimoire.]] - rationale - tests\test_experiment_store.py
- [[store_experiment with success=True stores findings in Grimoire.]] - rationale - tests\test_experiment_store.py
- [[store_failure creates an Experiment with success=False, attempt_count=1.]] - rationale - tests\test_experiment_store.py
- [[store_with_grimoire()]] - code - tests\test_experiment_store.py
- [[test_experiment_store.py]] - code - tests\test_experiment_store.py
- [[tmp_db()_2]] - code - tests\test_experiment_store.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Experiment_Store
SORT file.name ASC
```

## Connections to other communities
- 17 edges to [[_COMMUNITY_Data Pipeline & Embeddings]]
- 4 edges to [[_COMMUNITY_Module Lifecycle]]
- 2 edges to [[_COMMUNITY_Morpheus Creative Pipeline]]
- 1 edge to [[_COMMUNITY_Cross-Module Dreaming]]
- 1 edge to [[_COMMUNITY_Serendipity Detector]]
- 1 edge to [[_COMMUNITY_Workflow Store]]

## Top bridge nodes
- [[.store_failure()]] - degree 9, connects to 3 communities
- [[.store_experiment()]] - degree 30, connects to 1 community
- [[.check_retry_triggers()]] - degree 14, connects to 1 community
- [[.queue_for_retry()]] - degree 12, connects to 1 community
- [[.record_retry_result()]] - degree 10, connects to 1 community