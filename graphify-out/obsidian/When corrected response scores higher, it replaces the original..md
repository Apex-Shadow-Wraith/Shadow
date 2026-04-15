---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L140"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# When corrected response scores higher, it replaces the original.

## Connections
- [[.test_corrected_scores_higher_uses_corrected()]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue