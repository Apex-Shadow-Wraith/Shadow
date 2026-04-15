---
source_file: "tests\test_execution_planner.py"
type: "rationale"
community: "Execution Planner"
location: "L183"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Execution_Planner
---

# If model returns unparseable response, fall back to single step.

## Connections
- [[.test_parsing_failure_single_step_fallback()]] - `rationale_for` [EXTRACTED]
- [[ExecutionPlan]] - `uses` [INFERRED]
- [[ExecutionPlanner]] - `uses` [INFERRED]
- [[PlanStep]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Execution_Planner