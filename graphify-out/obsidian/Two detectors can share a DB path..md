---
source_file: "tests\test_drift_detector.py"
type: "rationale"
community: "Drift Detector"
location: "L297"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Drift_Detector
---

# Two detectors can share a DB path.

## Connections
- [[.test_concurrent_db_access()]] - `rationale_for` [EXTRACTED]
- [[DriftDetector]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Drift_Detector