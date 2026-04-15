---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L14"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Returns a configurable confidence score.

## Connections
- [[FakeConfidenceScorer_1]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue