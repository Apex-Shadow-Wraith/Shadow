---
source_file: "tests\test_execution_planner.py"
type: "rationale"
community: "Execution Planner"
location: "L212"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Execution_Planner
---

# Empty tools list should produce a fallback plan gracefully.

## Connections
- [[.test_empty_available_tools()]] - `rationale_for` [EXTRACTED]
- [[ExecutionPlan]] - `uses` [INFERRED]
- [[ExecutionPlanner]] - `uses` [INFERRED]
- [[PlanStep]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Execution_Planner