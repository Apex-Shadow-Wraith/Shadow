---
source_file: "tests\test_tool_evaluator.py"
type: "code"
community: "Tool Evaluator"
location: "L187"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Tool_Evaluator
---

# TestRecommendations

## Connections
- [[.test_all_pass_recommends_proceed()]] - `method` [EXTRACTED]
- [[.test_security_issue_recommends_abort()]] - `method` [EXTRACTED]
- [[.test_transient_error_recommends_retry()]] - `method` [EXTRACTED]
- [[.test_wrong_tool_recommends_replan()]] - `method` [EXTRACTED]
- [[EvaluationResult]] - `uses` [INFERRED]
- [[Tests for recommendation logic.]] - `rationale_for` [EXTRACTED]
- [[ToolResultEvaluator]] - `uses` [INFERRED]
- [[test_tool_evaluator.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Tool_Evaluator