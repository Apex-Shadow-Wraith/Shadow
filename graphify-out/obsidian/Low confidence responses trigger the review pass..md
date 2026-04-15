---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L99"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Low confidence responses trigger the review pass.

## Connections
- [[.test_low_confidence_triggers_review()]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue