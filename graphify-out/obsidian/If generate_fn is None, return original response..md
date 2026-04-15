---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L240"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# If generate_fn is None, return original response.

## Connections
- [[.test_no_generate_fn_returns_original()]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue