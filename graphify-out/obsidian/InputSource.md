---
source_file: "modules\shadow\task_chain.py"
type: "code"
community: "Ethics Engine (Cerberus)"
location: "L33"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Ethics_Engine_(Cerberus)
---

# InputSource

## Connections
- [[.create_chain()]] - `calls` [EXTRACTED]
- [[Build a simple 3-step chain definition.]] - `uses` [INFERRED]
- [[Cancelling a nonexistent chain raises KeyError.]] - `uses` [INFERRED]
- [[Cancelling marks pendingready steps as skipped.]] - `uses` [INFERRED]
- [[Chain aborts when a critical (non-parallel) step fails permanently.]] - `uses` [INFERRED]
- [[ChainStep and TaskChain survive to_dictfrom_dict round trip.]] - `uses` [INFERRED]
- [[Chains are saved to SQLite and recoverable.]] - `uses` [INFERRED]
- [[Create a TaskChainEngine with temp database.]] - `uses` [INFERRED]
- [[Create a mock ModuleRegistry with online modules.]] - `uses` [INFERRED]
- [[Create a simple chain and verify structure.]] - `uses` [INFERRED]
- [[Detect circular dependencies and raise ValueError.]] - `uses` [INFERRED]
- [[Enum]] - `inherits` [EXTRACTED]
- [[Failed steps are retried up to max_retries times.]] - `uses` [INFERRED]
- [[Falls back to single-step chain when LLM decomposition fails.]] - `uses` [INFERRED]
- [[Incomplete chains are recovered on engine startup.]] - `uses` [INFERRED]
- [[Independent steps can be in any order but before their dependents.]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Output from step N is available as input to step N+1.]] - `uses` [INFERRED]
- [[Reject depends_on referencing nonexistent step_ids.]] - `uses` [INFERRED]
- [[Reject empty chain description.]] - `uses` [INFERRED]
- [[Reject empty step list.]] - `uses` [INFERRED]
- [[Reject invalid priority values.]] - `uses` [INFERRED]
- [[Reject steps with invalid input_source.]] - `uses` [INFERRED]
- [[Reject steps with invalid module names.]] - `uses` [INFERRED]
- [[Reject steps without output_key.]] - `uses` [INFERRED]
- [[Reject steps without task_description.]] - `uses` [INFERRED]
- [[SafetyVerdict]] - `uses` [INFERRED]
- [[Single-step chain executes and completes.]] - `uses` [INFERRED]
- [[Single-step chain works correctly.]] - `uses` [INFERRED]
- [[Status report includes correct progress info.]] - `uses` [INFERRED]
- [[Steps are sorted so dependencies come before dependents.]] - `uses` [INFERRED]
- [[Steps in the same parallel_group run concurrently.]] - `uses` [INFERRED]
- [[TaskChain survives to_dictfrom_dict round trip.]] - `uses` [INFERRED]
- [[TestCancelChain]] - `uses` [INFERRED]
- [[TestChainPersistence]] - `uses` [INFERRED]
- [[TestChainStatus]] - `uses` [INFERRED]
- [[TestCreateChain]] - `uses` [INFERRED]
- [[TestExecuteChain]] - `uses` [INFERRED]
- [[TestPlanChainFromRequest]] - `uses` [INFERRED]
- [[Tests for LLM-based chain decomposition.]] - `uses` [INFERRED]
- [[Tests for TaskChainEngine — multi-module task orchestration.]] - `uses` [INFERRED]
- [[Tests for chain cancellation.]] - `uses` [INFERRED]
- [[Tests for chain creation, validation, and topological sort.]] - `uses` [INFERRED]
- [[Tests for chain execution logic.]] - `uses` [INFERRED]
- [[Tests for chain serialization and database recovery.]] - `uses` [INFERRED]
- [[Tests for chain status reporting.]] - `uses` [INFERRED]
- [[Where a chain step gets its input.]] - `rationale_for` [EXTRACTED]
- [[from_dict()_3]] - `calls` [EXTRACTED]
- [[list_chains filters by status.]] - `uses` [INFERRED]
- [[list_chains returns all chains.]] - `uses` [INFERRED]
- [[plan_chain_from_request decomposes a request using mocked LLM.]] - `uses` [INFERRED]
- [[task_chain.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Ethics_Engine_(Cerberus)