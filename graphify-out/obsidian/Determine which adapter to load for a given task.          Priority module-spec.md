---
source_file: "modules\shadow\lora_manager.py"
type: "rationale"
community: "Confidence Calibration"
location: "L158"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Confidence_Calibration
---

# Determine which adapter to load for a given task.          Priority: module-spec

## Connections
- [[.get_adapter_for_task()]] - `rationale_for` [EXTRACTED]
- [[LoRAPerformanceTracker]] - `uses` [INFERRED]

#graphify/rationale #graphify/EXTRACTED #community/Confidence_Calibration