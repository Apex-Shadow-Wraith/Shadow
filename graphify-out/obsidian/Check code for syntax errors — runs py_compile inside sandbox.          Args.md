---
source_file: "modules\omen\omen.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L980"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# Check code for syntax errors — runs py_compile inside sandbox.          Args:

## Connections
- [[._code_lint()]] - `rationale_for` [EXTRACTED]
- [[BaseModule]] - `uses` [INFERRED]
- [[CodeAnalyzer]] - `uses` [INFERRED]
- [[CodeSandbox]] - `uses` [INFERRED]
- [[ModelEvaluator]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Scratchpad]] - `uses` [INFERRED]
- [[TestGate]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)