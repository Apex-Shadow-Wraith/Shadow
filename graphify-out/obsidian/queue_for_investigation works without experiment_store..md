---
source_file: "tests\test_serendipity_detector.py"
type: "rationale"
community: "Serendipity Detector"
location: "L357"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Serendipity_Detector
---

# queue_for_investigation works without experiment_store.

## Connections
- [[.test_graceful_when_experiment_store_unavailable()]] - `rationale_for` [EXTRACTED]
- [[SerendipityDetector]] - `uses` [INFERRED]
- [[SerendipityFinding]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Serendipity_Detector