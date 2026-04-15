---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L97"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# store_experiment persists to SQLite and returns the ID.

## Connections
- [[.test_persists_to_sqlite()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store