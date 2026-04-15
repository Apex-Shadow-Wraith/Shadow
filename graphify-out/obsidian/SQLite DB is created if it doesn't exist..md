---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L445"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# SQLite DB is created if it doesn't exist.

## Connections
- [[.test_db_created_if_not_exists()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store