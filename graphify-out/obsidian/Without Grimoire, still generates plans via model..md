---
source_file: "tests\test_execution_planner.py"
type: "rationale"
community: "Execution Planner"
location: "L203"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Execution_Planner
---

# Without Grimoire, still generates plans via model.

## Connections
- [[.test_graceful_when_grimoire_is_none()]] - `rationale_for` [EXTRACTED]
- [[ExecutionPlan]] - `uses` [INFERRED]
- [[ExecutionPlanner]] - `uses` [INFERRED]
- [[PlanStep]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Execution_Planner