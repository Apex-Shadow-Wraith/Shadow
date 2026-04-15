---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L383"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# get_pending_retries excludes experiments not queued for retry.

## Connections
- [[.test_excludes_non_queued()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store