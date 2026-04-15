---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L316"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# queue_for_retry returns False for non-existent experiment.

## Connections
- [[.test_returns_false_for_missing_id()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store