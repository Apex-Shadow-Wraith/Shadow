---
source_file: "modules\morpheus\experiment_store.py"
type: "code"
community: "Experiment Store"
location: "L27"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Experiment_Store
---

# Experiment

## Connections
- [[._row_to_experiment()]] - `calls` [EXTRACTED]
- [[.store_failure()]] - `calls` [EXTRACTED]
- [[A tracked experiment with retry trigger support.]] - `rationale_for` [EXTRACTED]
- [[Create a mock Grimoire module.]] - `uses` [INFERRED]
- [[Create an ExperimentStore with a mock Grimoire.]] - `uses` [INFERRED]
- [[Create an ExperimentStore with a temporary database.]] - `uses` [INFERRED]
- [[Deprioritized experiments are not returned by check_retry_triggers.]] - `uses` [INFERRED]
- [[Deprioritized experiments excluded by default.]] - `uses` [INFERRED]
- [[Deprioritized experiments included with include_deprioritized=True.]] - `uses` [INFERRED]
- [[Edge case and robustness tests.]] - `uses` [INFERRED]
- [[Experiment not returned when triggers are not met.]] - `uses` [INFERRED]
- [[Experiment with 0 retry_triggers never triggers retry.]] - `uses` [INFERRED]
- [[Failed retry updates attempt_history.]] - `uses` [INFERRED]
- [[Graceful handling when Grimoire raises an exception.]] - `uses` [INFERRED]
- [[Helper to create an Experiment with sensible defaults.]] - `uses` [INFERRED]
- [[No error when grimoire is None and experiment succeeds.]] - `uses` [INFERRED]
- [[Return a path to a temporary database file.]] - `uses` [INFERRED]
- [[SQLite DB is created if it doesn't exist.]] - `uses` [INFERRED]
- [[Successful retry updates status and stores in Grimoire.]] - `uses` [INFERRED]
- [[TestCheckRetryTriggers]] - `uses` [INFERRED]
- [[TestEdgeCases_8]] - `uses` [INFERRED]
- [[TestGetExperimentStats]] - `uses` [INFERRED]
- [[TestGetExperimentsByDomain]] - `uses` [INFERRED]
- [[TestGetPendingRetries]] - `uses` [INFERRED]
- [[TestQueueForRetry]] - `uses` [INFERRED]
- [[TestRecordRetryResult]] - `uses` [INFERRED]
- [[TestStoreExperiment]] - `uses` [INFERRED]
- [[TestStoreFailure]] - `uses` [INFERRED]
- [[Tests for ExperimentStore — Failed Experiment Knowledge Base with Retry Triggers]] - `uses` [INFERRED]
- [[Tests for check_retry_triggers.]] - `uses` [INFERRED]
- [[Tests for get_experiment_stats.]] - `uses` [INFERRED]
- [[Tests for get_experiments_by_domain.]] - `uses` [INFERRED]
- [[Tests for get_pending_retries.]] - `uses` [INFERRED]
- [[Tests for queue_for_retry.]] - `uses` [INFERRED]
- [[Tests for record_retry_result.]] - `uses` [INFERRED]
- [[Tests for store_experiment.]] - `uses` [INFERRED]
- [[Tests for store_failure.]] - `uses` [INFERRED]
- [[Trigger 'embedding_model_changed' fires when embedding model differs.]] - `uses` [INFERRED]
- [[Trigger 'knowledge_depthcuda5' matches when domain has 5+ entries.]] - `uses` [INFERRED]
- [[Trigger 'model_changed' does NOT fire when model is the same.]] - `uses` [INFERRED]
- [[Trigger 'model_changed' fires when model differs from experiment conditions.]] - `uses` [INFERRED]
- [[Trigger 'new_grimoire_knowledgecuda' matches when conditions include cuda.]] - `uses` [INFERRED]
- [[Trigger 'tool_addedcuda_kernel' matches when tool is available.]] - `uses` [INFERRED]
- [[_make_experiment()]] - `calls` [INFERRED]
- [[experiment_store.py]] - `contains` [EXTRACTED]
- [[get_experiment_stats returns accurate counts for all statuses.]] - `uses` [INFERRED]
- [[get_experiments_by_domain filters by domain tag.]] - `uses` [INFERRED]
- [[get_pending_retries excludes experiments not queued for retry.]] - `uses` [INFERRED]
- [[get_pending_retries returns queued experiments ordered by attempt_count.]] - `uses` [INFERRED]
- [[queue_for_retry does NOT deprioritize if same conditions (not genuinely differen]] - `uses` [INFERRED]
- [[queue_for_retry increments attempt_count.]] - `uses` [INFERRED]
- [[queue_for_retry returns False for non-existent experiment.]] - `uses` [INFERRED]
- [[queue_for_retry sets deprioritized after 3 failed attempts under different condi]] - `uses` [INFERRED]
- [[record_retry_result returns False for non-existent experiment.]] - `uses` [INFERRED]
- [[store_experiment persists to SQLite and returns the ID.]] - `uses` [INFERRED]
- [[store_experiment with success=False does not call Grimoire.]] - `uses` [INFERRED]
- [[store_experiment with success=True stores findings in Grimoire.]] - `uses` [INFERRED]
- [[store_failure creates an Experiment with success=False, attempt_count=1.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Experiment_Store