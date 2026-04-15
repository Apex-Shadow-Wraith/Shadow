---
source_file: "tests\test_execution_planner.py"
type: "rationale"
community: "Execution Planner"
location: "L142"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Execution_Planner
---

# Adapted plan gets a new ID and updated task description.

## Connections
- [[.test_adapts_existing_plan_when_found()]] - `rationale_for` [EXTRACTED]
- [[ExecutionPlan]] - `uses` [INFERRED]
- [[ExecutionPlanner]] - `uses` [INFERRED]
- [[PlanStep]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Execution_Planner