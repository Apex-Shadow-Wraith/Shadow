---
source_file: "tests\test_confidence_calibration.py"
type: "rationale"
community: "Confidence Calibration"
location: "L19"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# Create a calibrator with a temp database.

## Connections
- [[CalibrationRecord]] - `uses` [INFERRED]
- [[ConfidenceCalibrator]] - `uses` [INFERRED]
- [[calibrator()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration