---
source_file: "tests\test_self_review.py"
type: "rationale"
community: "Async Task Queue"
location: "L112"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# When issues are found, a corrected response is generated.

## Connections
- [[.test_issues_found_triggers_regeneration()]] - `rationale_for` [EXTRACTED]
- [[ReviewResult]] - `uses` [INFERRED]
- [[SelfReviewer]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Async_Task_Queue