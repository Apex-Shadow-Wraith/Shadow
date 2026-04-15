---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L163"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# When corrected response scores lower, revert to original.

## Connections
- [[.test_corrected_scores_lower_reverts_to_original()]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue