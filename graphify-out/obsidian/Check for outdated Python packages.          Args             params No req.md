---
source_file: "modules\omen\omen.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L1238"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Check for outdated Python packages.          Args:             params: No req

## Connections
- [[._dependency_check()]] - `rationale_for` [EXTRACTED]
- [[BaseModule]] - `uses` [INFERRED]
- [[CodeAnalyzer]] - `uses` [INFERRED]
- [[CodeSandbox]] - `uses` [INFERRED]
- [[ModelEvaluator]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Scratchpad]] - `uses` [INFERRED]
- [[TestGate]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)