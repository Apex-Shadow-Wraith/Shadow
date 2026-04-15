---
source_file: "modules\shadow\confidence_calibration.py"
type: "rationale"
community: "Confidence Calibration"
location: "L372"
tags:
  - graphify/rationale
  - graphify/EXTRACTED
  - community/Confidence_Calibration
---

# Return True if calibration error > 0.15 or > 100 new records since last check.

## Connections
- [[.should_recalibrate()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/EXTRACTED #community/Confidence_Calibration