---
source_file: "modules\shadow\execution_planner.py"
type: "code"
community: "Execution Planner"
location: "L38"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Execution_Planner
---

# ExecutionPlan

## Connections
- [[._adapt_existing_plan()]] - `calls` [EXTRACTED]
- [[._dict_to_plan()]] - `calls` [EXTRACTED]
- [[._generate_new_plan()]] - `calls` [EXTRACTED]
- [[._single_step_plan()]] - `calls` [EXTRACTED]
- [[.adapt_plan()]] - `calls` [EXTRACTED]
- [[A complete execution plan for a multi-tool task.]] - `rationale_for` [EXTRACTED]
- [[Adapted plan gets a new ID and updated task description.]] - `uses` [INFERRED]
- [[Empty tools list should produce a fallback plan gracefully.]] - `uses` [INFERRED]
- [[If model returns unparseable response, fall back to single step.]] - `uses` [INFERRED]
- [[Return a generate_fn that returns a JSON plan response.]] - `uses` [INFERRED]
- [[Should not store a plan that's very similar to an existing one.]] - `uses` [INFERRED]
- [[Step references a future step's output.]] - `uses` [INFERRED]
- [[TestAdaptPlan]] - `uses` [INFERRED]
- [[TestCreatePlan]] - `uses` [INFERRED]
- [[TestDataClasses]] - `uses` [INFERRED]
- [[TestEvaluatePlan]] - `uses` [INFERRED]
- [[TestGetPlanningStats]] - `uses` [INFERRED]
- [[TestSearchReusablePlans]] - `uses` [INFERRED]
- [[TestStoreSuccessfulPlan]] - `uses` [INFERRED]
- [[Tests for Pre-Execution Planning Pass.]] - `uses` [INFERRED]
- [[When Grimoire has a matching plan, reuse it.]] - `uses` [INFERRED]
- [[When Grimoire returns nothing, generate a new plan.]] - `uses` [INFERRED]
- [[When model is available, adaptation generates new steps.]] - `uses` [INFERRED]
- [[Without Grimoire, still generates plans via model.]] - `uses` [INFERRED]
- [[Without a model, returns a single-step fallback plan.]] - `uses` [INFERRED]
- [[execution_planner.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Execution_Planner