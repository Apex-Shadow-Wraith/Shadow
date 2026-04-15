---
source_file: "modules\omen\omen.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L1129"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Check the git repository state.          Args:             params: No require

## Connections
- [[._git_status()]] - `rationale_for` [EXTRACTED]
- [[BaseModule]] - `uses` [INFERRED]
- [[CodeAnalyzer]] - `uses` [INFERRED]
- [[CodeSandbox]] - `uses` [INFERRED]
- [[ModelEvaluator]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Scratchpad]] - `uses` [INFERRED]
- [[TestGate]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)