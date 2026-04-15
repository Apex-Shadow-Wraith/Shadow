---
source_file: "tests\test_task_tracker.py"
type: "code"
community: "Code Analyzer (Omen)"
location: "L226"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# test_cleanup_removes_old_completed()

## Connections
- [[.cleanup()]] - `calls` [INFERRED]
- [[.create()_1]] - `calls` [INFERRED]
- [[.execute()_36]] - `calls` [INFERRED]
- [[.list_tasks()_1]] - `calls` [INFERRED]
- [[.update_status()]] - `calls` [INFERRED]
- [[Cleanup deletes completed tasks older than threshold.]] - `rationale_for` [EXTRACTED]
- [[test_task_tracker.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Code_Analyzer_(Omen)