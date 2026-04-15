---
source_file: "tests\test_confidence_calibration.py"
type: "rationale"
community: "Confidence Calibration"
location: "L172"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Confidence_Calibration
---

# get_calibration_by_type filters by task_type.

## Connections
- [[.test_filter_by_task_type()]] - `rationale_for` [EXTRACTED]
- [[CalibrationRecord]] - `uses` [INFERRED]
- [[ConfidenceCalibrator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Confidence_Calibration