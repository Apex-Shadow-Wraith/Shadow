---
source_file: "tests\test_execution_planner.py"
type: "rationale"
community: "Execution Planner"
location: "L114"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Execution_Planner
---

# When Grimoire has a matching plan, reuse it.

## Connections
- [[.test_checks_grimoire_for_reusable_plan()]] - `rationale_for` [EXTRACTED]
- [[ExecutionPlan]] - `uses` [INFERRED]
- [[ExecutionPlanner]] - `uses` [INFERRED]
- [[PlanStep]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Execution_Planner