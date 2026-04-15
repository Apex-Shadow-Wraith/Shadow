---
source_file: "modules\cerberus\emergency_shutdown.py"
type: "rationale"
community: "Emergency Shutdown"
location: "L302"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Emergency_Shutdown
---

# Execute emergency shutdown. Message sends FIRST, then halt.          Order is no

## Connections
- [[.initiate_shutdown()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Emergency_Shutdown