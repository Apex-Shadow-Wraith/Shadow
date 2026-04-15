---
source_file: "tests\test_task_chain.py"
type: "rationale"
community: "Ethics Engine (Cerberus)"
location: "L210"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Ethics_Engine_(Cerberus)
---

# Detect circular dependencies and raise ValueError.

## Connections
- [[.test_create_chain_detects_circular_deps()]] - `rationale_for` [EXTRACTED]
- [[ChainStatus]] - `uses` [INFERRED]
- [[ChainStep]] - `uses` [INFERRED]
- [[InputSource]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[StepStatus]] - `uses` [INFERRED]
- [[TaskChain]] - `uses` [INFERRED]
- [[TaskChainEngine]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Ethics_Engine_(Cerberus)