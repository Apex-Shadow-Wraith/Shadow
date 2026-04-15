---
source_file: "tests\test_execution_planner.py"
type: "rationale"
community: "Execution Planner"
location: "L354"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Execution_Planner
---

# Should not store a plan that's very similar to an existing one.

## Connections
- [[.test_deduplicates_similar_plans()]] - `rationale_for` [EXTRACTED]
- [[ExecutionPlan]] - `uses` [INFERRED]
- [[ExecutionPlanner]] - `uses` [INFERRED]
- [[PlanStep]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Execution_Planner