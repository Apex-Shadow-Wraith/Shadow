---
source_file: "tests\test_execution_planner.py"
type: "rationale"
community: "Execution Planner"
location: "L43"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Execution_Planner
---

# Return a generate_fn that returns a JSON plan response.

## Connections
- [[ExecutionPlan]] - `uses` [INFERRED]
- [[ExecutionPlanner]] - `uses` [INFERRED]
- [[PlanStep]] - `uses` [INFERRED]
- [[_mock_generate_fn()]] - `rationale_for` [EXTRACTED]

#graphify/rationale #graphify/INFERRED #community/Execution_Planner