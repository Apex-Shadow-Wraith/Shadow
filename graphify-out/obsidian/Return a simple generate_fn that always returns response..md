---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L27"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# Return a simple generate_fn that always returns *response*.

## Connections
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]
- [[make_generate_fn()_2]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue