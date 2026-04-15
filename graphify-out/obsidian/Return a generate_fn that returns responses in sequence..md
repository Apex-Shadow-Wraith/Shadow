---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L39"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Return a generate_fn that returns responses in sequence.

## Connections
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]
- [[make_sequenced_generate_fn()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue