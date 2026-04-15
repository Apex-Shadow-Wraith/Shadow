---
source_file: "tests\test_execution_planner.py"
type: "rationale"
community: "Execution Planner"
location: "L195"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Execution_Planner
---

# Without a model, returns a single-step fallback plan.

## Connections
- [[.test_graceful_when_generate_fn_is_none()]] - `rationale_for` [EXTRACTED]
- [[ExecutionPlan]] - `uses` [INFERRED]
- [[ExecutionPlanner]] - `uses` [INFERRED]
- [[PlanStep]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Execution_Planner