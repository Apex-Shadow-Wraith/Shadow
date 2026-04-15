---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L258"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# queue_for_retry increments attempt_count.

## Connections
- [[.test_increments_attempt_count()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store