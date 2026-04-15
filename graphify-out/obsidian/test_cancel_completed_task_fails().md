---
source_file: "tests\test_task_tracker.py"
type: "code"
community: "Code Analyzer (Omen)"
location: "L152"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# test_cancel_completed_task_fails()

## Connections
- [[.cancel()]] - `calls` [INFERRED]
- [[.create()_1]] - `calls` [INFERRED]
- [[.get_status()_2]] - `calls` [INFERRED]
- [[.update_status()]] - `calls` [INFERRED]
- [[Cannot cancel a completed task.]] - `rationale_for` [EXTRACTED]
- [[test_task_tracker.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Code_Analyzer_(Omen)