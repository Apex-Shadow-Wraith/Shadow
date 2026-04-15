---
source_file: "tests\test_cross_module_dreaming.py"
type: "rationale"
community: "Cross-Module Dreaming"
location: "L242"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Cross-Module_Dreaming
---

# store_dream() should call experiment_store.store_failure().

## Connections
- [[.test_store_dream_saves_to_experiment_store()]] - `rationale_for` [EXTRACTED]
- [[CrossModuleDreamer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Cross-Module_Dreaming