---
source_file: "tests\test_false_positive.py"
type: "rationale"
community: "Module Lifecycle"
location: "L195"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Lifecycle
---

# Cerberus without db_path returns empty calibration stats.

## Connections
- [[.test_no_db_path_returns_zeros()]] - `rationale_for` [EXTRACTED]
- [[Cerberus]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Lifecycle