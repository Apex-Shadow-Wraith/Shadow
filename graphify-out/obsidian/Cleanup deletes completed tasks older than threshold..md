---
source_file: "tests\test_task_tracker.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L227"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Cleanup deletes completed tasks older than threshold.

## Connections
- [[TaskTracker]] - `uses` [INFERRED]
- [[test_cleanup_removes_old_completed()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)