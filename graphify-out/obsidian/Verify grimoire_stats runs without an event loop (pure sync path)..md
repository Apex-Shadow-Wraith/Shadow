---
source_file: "tests\test_standing_tasks.py"
type: "rationale"
community: "Module Registry & Tools"
location: "L305"
tags:
  - graphify/rationale
  - graphify/INFERRED
  - community/Module_Registry_&_Tools
---

# Verify grimoire_stats runs without an event loop (pure sync path).

## Connections
- [[ModuleRegistry]] - `uses` [INFERRED]
- [[ModuleStatus]] - `uses` [INFERRED]
- [[StandingTaskScheduler]] - `uses` [INFERRED]
- [[TestGrimoireStatsNoEventLoop]] - `rationale_for` [EXTRACTED]
- [[ToolResult]] - `uses` [INFERRED]

#graphify/rationale #graphify/INFERRED #community/Module_Registry_&_Tools