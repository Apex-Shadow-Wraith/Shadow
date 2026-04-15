---
source_file: "tests\test_lora_manager.py"
type: "rationale"
community: "Confidence Calibration"
location: "L318"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Graceful empty state when directory doesn't exist.

## Connections
- [[.test_no_adapters_directory()]] - `rationale_for` [EXTRACTED]
- [[LoRAAdapter]] - `uses` [INFERRED]
- [[LoRAManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration