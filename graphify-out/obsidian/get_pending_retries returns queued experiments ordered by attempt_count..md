---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L369"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# get_pending_retries returns queued experiments ordered by attempt_count.

## Connections
- [[.test_returns_queued_ordered_correctly()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store