---
source_file: "tests\test_task_tracker.py"
type: "code"
community: "Code Analyzer (Omen)"
location: "L91"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# test_status_transition_queued_to_running_to_completed()

## Connections
- [[.create()_1]] - `calls` [INFERRED]
- [[.get_status()_2]] - `calls` [INFERRED]
- [[.update_status()]] - `calls` [INFERRED]
- [[Normal lifecycle queued → running → completed.]] - `rationale_for` [EXTRACTED]
- [[test_task_tracker.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Code_Analyzer_(Omen)