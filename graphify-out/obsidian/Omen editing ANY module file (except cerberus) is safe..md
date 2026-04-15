---
source_file: "tests\test_emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L102"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Emergency_Shutdown
---

# Omen editing ANY module file (except cerberus) is safe.

## Connections
- [[.test_omen_editing_any_non_cerberus_module()]] - `rationale_for` [EXTRACTED]
- [[EmergencyShutdown]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Emergency_Shutdown