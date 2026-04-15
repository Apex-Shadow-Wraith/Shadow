---
source_file: "tests\test_task_tracker.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L255"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Cleanup only targets completed/failed/cancelled tasks.

## Connections
- [[TaskTracker]] - `uses` [INFERRED]
- [[test_cleanup_preserves_queued_and_running()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)