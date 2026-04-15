---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L199"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# Trigger 'model_changed' does NOT fire when model is the same.

## Connections
- [[.test_model_changed_same_model()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store