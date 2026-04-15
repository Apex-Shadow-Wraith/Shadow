---
source_file: "tests\test_failure_patterns.py"
type: "rationale"
community: "Base Module & Apex API"
location: "L780"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Base_Module_&_Apex_API
---

# Test failure patterns survive context trimming.

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[BrainType]] - `uses` [INFERRED]
- [[ContextManager]] - `uses` [INFERRED]
- [[FailurePatternDB]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[TaskClassification]] - `uses` [INFERRED]
- [[TaskType]] - `uses` [INFERRED]
- [[TestContextManagerFailurePatterns]] - `rationale_for` [EXTRACTED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Base_Module_&_Apex_API