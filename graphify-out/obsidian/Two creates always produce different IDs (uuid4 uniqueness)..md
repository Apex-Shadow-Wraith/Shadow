---
source_file: "tests\test_task_tracker.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L83"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Two creates always produce different IDs (uuid4 uniqueness).

## Connections
- [[TaskTracker]] - `uses` [INFERRED]
- [[test_duplicate_task_id_impossible()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)