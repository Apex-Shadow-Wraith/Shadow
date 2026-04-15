---
source_file: "tests\test_execution_planner.py"
type: "rationale"
community: "Execution Planner"
location: "L168"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Execution_Planner
---

# When Grimoire returns nothing, generate a new plan.

## Connections
- [[.test_generates_new_plan_when_none_found()]] - `rationale_for` [EXTRACTED]
- [[ExecutionPlan]] - `uses` [INFERRED]
- [[ExecutionPlanner]] - `uses` [INFERRED]
- [[PlanStep]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Execution_Planner