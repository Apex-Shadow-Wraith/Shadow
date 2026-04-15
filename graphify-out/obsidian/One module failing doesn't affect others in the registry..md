---
source_file: "tests\test_effectiveness.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L307"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# One module failing doesn't affect others in the registry.

## Connections
- [[.test_other_modules_unaffected_by_failure()]] - `rationale_for` [EXTRACTED]
- [[BaseModule]] - `uses` [INFERRED]
- [[Grimoire]] - `uses` [INFERRED]
- [[GrowthEngine]] - `uses` [INFERRED]
- [[Harbinger]] - `uses` [INFERRED]
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Morpheus]] - `uses` [INFERRED]
- [[Orchestrator]] - `uses` [INFERRED]
- [[PromptInjectionDetector]] - `uses` [INFERRED]
- [[TaskTracker]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools