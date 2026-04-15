---
source_file: "tests\test_lora_manager.py"
type: "rationale"
community: "Confidence Calibration"
location: "L332"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# When multiple adapters match a domain, the first registered is returned.

## Connections
- [[.test_multiple_adapters_same_domain()]] - `rationale_for` [EXTRACTED]
- [[LoRAAdapter]] - `uses` [INFERRED]
- [[LoRAManager]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration