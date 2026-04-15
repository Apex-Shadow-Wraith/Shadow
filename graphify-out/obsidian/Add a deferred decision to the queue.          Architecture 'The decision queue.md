---
source_file: "modules\harbinger\harbinger.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L519"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Add a deferred decision to the queue.          Architecture: 'The decision queue

## Connections
- [[._decision_queue_add()]] - `rationale_for` [EXTRACTED]
- [[BaseModule]] - `uses` [INFERRED]
- [[DailySafetyReport]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[TelegramDelivery]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API