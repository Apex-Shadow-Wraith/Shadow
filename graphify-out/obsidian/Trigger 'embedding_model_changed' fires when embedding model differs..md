---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L243"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# Trigger 'embedding_model_changed' fires when embedding model differs.

## Connections
- [[.test_embedding_model_changed_trigger()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store