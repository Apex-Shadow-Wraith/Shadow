---
source_file: "tests\test_confidence_calibration.py"
type: "rationale"
community: "Confidence Calibration"
location: "L163"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Well-calibrated: calibrate returns value close to input.

## Connections
- [[.test_calibrate_well_calibrated_minimal_change()]] - `rationale_for` [EXTRACTED]
- [[CalibrationRecord]] - `uses` [INFERRED]
- [[ConfidenceCalibrator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration