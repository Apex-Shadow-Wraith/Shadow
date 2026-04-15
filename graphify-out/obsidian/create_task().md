---
source_file: "modules\shadow\task_queue.py"
type: "code"
community: "Async Task Queue"
location: "L380"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# create_task()

## Connections
- [[._step1_5_injection_screen()]] - `calls` [INFERRED]
- [[.start()_1]] - `calls` [INFERRED]
- [[.start()_3]] - `calls` [INFERRED]
- [[.submit_task()]] - `calls` [INFERRED]
- [[.test_create_task_custom()]] - `calls` [INFERRED]
- [[.test_create_task_defaults()]] - `calls` [INFERRED]
- [[.test_user_request_to_queue_to_chain()]] - `calls` [INFERRED]
- [[QueuedTask]] - `calls` [EXTRACTED]
- [[TaskKind]] - `calls` [EXTRACTED]
- [[TaskSource]] - `calls` [EXTRACTED]
- [[_make_task()]] - `calls` [INFERRED]
- [[task_queue.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Async_Task_Queue