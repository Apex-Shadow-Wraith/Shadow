---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L133"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# store_failure creates an Experiment with success=False, attempt_count=1.

## Connections
- [[.test_creates_correct_experiment()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store