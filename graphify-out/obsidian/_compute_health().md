---
source_file: "modules\shadow\operational_state.py"
type: "code"
community: "Async Task Queue"
location: "L34"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Async_Task_Queue
---

# _compute_health()

## Connections
- [[.get_current_state()]] - `calls` [EXTRACTED]
- [[.record_cooldown()]] - `calls` [EXTRACTED]
- [[.test_overall_health_calculation()]] - `calls` [INFERRED]
- [[.update_after_task()]] - `calls` [EXTRACTED]
- [[Compute overall health from state dimensions.]] - `rationale_for` [EXTRACTED]
- [[_clamp()]] - `calls` [EXTRACTED]
- [[operational_state.py]] - `contains` [EXTRACTED]
- [[process_input()]] - `calls` [INFERRED]

#graphify/code #graphify/EXTRACTED #community/Async_Task_Queue