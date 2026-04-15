---
source_file: "modules\shadow\confidence_scorer.py"
type: "rationale"
community: "Async Task Queue"
location: "L169"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Evaluate response quality using rule-based checks.          Args:             ta

## Connections
- [[.score_response()_1]] - `rationale_for` [EXTRACTED]
- [[ConfidenceCalibrator]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue