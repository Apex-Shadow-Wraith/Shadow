---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L188"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# Trigger 'model_changed' fires when model differs from experiment conditions.

## Connections
- [[.test_model_changed_trigger()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store