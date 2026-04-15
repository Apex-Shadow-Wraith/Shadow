---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L123"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# store_experiment with success=False does not call Grimoire.

## Connections
- [[.test_failure_does_not_store_in_grimoire()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store