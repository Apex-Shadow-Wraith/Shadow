---
source_file: "tests\test_task_tracker.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L245"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Cleanup does not delete tasks within the threshold.

## Connections
- [[TaskTracker]] - `uses` [INFERRED]
- [[test_cleanup_preserves_recent()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)