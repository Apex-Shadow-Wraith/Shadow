---
source_file: "tests\test_experiment_store.py"
type: "rationale"
community: "Experiment Store"
location: "L210"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Experiment_Store
---

# Trigger 'tool_added:cuda_kernel' matches when tool is available.

## Connections
- [[.test_tool_added_trigger()]] - `rationale_for` [EXTRACTED]
- [[Experiment]] - `uses` [INFERRED]
- [[ExperimentStore]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Experiment_Store