---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L227"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# If generate_fn raises, return original response gracefully.

## Connections
- [[.test_generate_fn_failure_returns_original()]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue