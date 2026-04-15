---
source_file: "tests\test_task_tracker.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L92"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Normal lifecycle: queued → running → completed.

## Connections
- [[TaskTracker]] - `uses` [INFERRED]
- [[test_status_transition_queued_to_running_to_completed()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)