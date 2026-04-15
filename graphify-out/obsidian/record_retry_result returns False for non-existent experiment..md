---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L361"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# record_retry_result returns False for non-existent experiment.

## Connections
- [[.test_returns_false_for_missing_id()_1]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store