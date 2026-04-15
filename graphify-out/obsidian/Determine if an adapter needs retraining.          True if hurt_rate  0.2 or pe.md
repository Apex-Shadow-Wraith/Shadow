---
source_file: "modules\shadow\lora_tracker.py"
type: "rationale"
community: "Confidence Calibration"
location: "L230"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Confidence_Calibration
---

# Determine if an adapter needs retraining.          True if hurt_rate > 0.2 or pe

## Connections
- [[._check_needs_retrain()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Confidence_Calibration