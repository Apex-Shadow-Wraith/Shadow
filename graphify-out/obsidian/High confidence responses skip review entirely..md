---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L86"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# High confidence responses skip review entirely.

## Connections
- [[.test_high_confidence_returns_original_no_review()]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue