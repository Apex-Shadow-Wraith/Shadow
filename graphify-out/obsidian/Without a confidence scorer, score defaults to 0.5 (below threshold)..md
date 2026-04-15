---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L249"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Without a confidence scorer, score defaults to 0.5 (below threshold).

## Connections
- [[.test_confidence_scorer_unavailable_reviews_by_task_type()]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue