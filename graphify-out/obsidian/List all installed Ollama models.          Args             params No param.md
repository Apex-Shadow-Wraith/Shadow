---
source_file: "modules\omen\omen.py"
type: "rationale"
community: "Code Analyzer (Omen)"
location: "L2827"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# List all installed Ollama models.          Args:             params: No param

## Connections
- [[._model_list()]] - `rationale_for` [EXTRACTED]
- [[BaseModule]] - `uses` [INFERRED]
- [[CodeAnalyzer]] - `uses` [INFERRED]
- [[CodeSandbox]] - `uses` [INFERRED]
- [[ModelEvaluator]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[Scratchpad]] - `uses` [INFERRED]
- [[TestGate]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Code_Analyzer_(Omen)