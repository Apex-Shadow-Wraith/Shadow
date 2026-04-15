---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L185"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Review never exceeds max_cycles (default 2).

## Connections
- [[.test_max_two_cycles_enforced()]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue