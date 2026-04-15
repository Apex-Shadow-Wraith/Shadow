---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L159"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# Trigger 'new_grimoire_knowledge:cuda' matches when conditions include cuda.

## Connections
- [[.test_new_grimoire_knowledge_trigger()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store