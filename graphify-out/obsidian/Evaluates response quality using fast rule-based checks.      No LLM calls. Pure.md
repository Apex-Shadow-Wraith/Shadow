---
source_file: "modules\shadow\confidence_scorer.py"
type: "rationale"
community: "Async Task Queue"
location: "L88"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Evaluates response quality using fast rule-based checks.      No LLM calls. Pure

## Connections
- [[ConfidenceCalibrator]] - `uses` [INFERRED]
- [[ConfidenceScorer]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue