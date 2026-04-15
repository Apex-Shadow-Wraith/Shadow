---
source_file: "modules\apex\apex.py"
type: "rationale"
community: "Apex API Providers"
location: "L37"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Apex_API_Providers
---

# SQLite-backed log of every Apex escalation.      Tracks what was escalated, wh

## Connections
- [[BaseModule]] - `uses` [INFERRED]
- [[EscalationLog]] - `rationale_for` [EXTRACTED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[TeachingExtractor]] - `uses` [INFERRED]
- [[ToolResult]] - `uses` [INFERRED]
- [[TrainingDataPipeline]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Apex_API_Providers