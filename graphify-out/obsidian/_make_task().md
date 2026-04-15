---
source_file: "tests\test_task_queue.py"
type: "code"
community: "Async Task Queue"
location: "L33"
tags:
  - graphify/code
  - graphify/EXTRACTED
  - community/Async_Task_Queue
---

# _make_task()

## Connections
- [[.test_cleanup_keeps_recent()]] - `calls` [EXTRACTED]
- [[.test_cleanup_old_completed()]] - `calls` [EXTRACTED]
- [[.test_complete_task()]] - `calls` [EXTRACTED]
- [[.test_dequeue_marks_task_running()]] - `calls` [EXTRACTED]
- [[.test_dequeue_returns_highest_priority()]] - `calls` [EXTRACTED]
- [[.test_enqueue_returns_task_id()]] - `calls` [EXTRACTED]
- [[.test_fail_task()]] - `calls` [EXTRACTED]
- [[.test_fifo_within_same_priority()]] - `calls` [EXTRACTED]
- [[.test_full_priority_ordering()]] - `calls` [EXTRACTED]
- [[.test_get_queue_by_priority()]] - `calls` [EXTRACTED]
- [[.test_get_queue_depth()]] - `calls` [EXTRACTED]
- [[.test_get_running_count()]] - `calls` [EXTRACTED]
- [[.test_get_task_finds_across_states()]] - `calls` [EXTRACTED]
- [[.test_manual_preempt()]] - `calls` [EXTRACTED]
- [[.test_peek()]] - `calls` [EXTRACTED]
- [[.test_persist_and_recover()]] - `calls` [EXTRACTED]
- [[.test_preempt_does_not_affect_p2()]] - `calls` [EXTRACTED]
- [[.test_preempt_lower_priority_for_critical()]] - `calls` [EXTRACTED]
- [[.test_preempted_task_resumes()]] - `calls` [EXTRACTED]
- [[.test_priority_1_before_2()]] - `calls` [EXTRACTED]
- [[.test_priority_2_before_3()]] - `calls` [EXTRACTED]
- [[.test_priority_3_before_4()]] - `calls` [EXTRACTED]
- [[.test_running_tasks_requeued_on_recovery()]] - `calls` [EXTRACTED]
- [[Helper to create a QueuedTask.]] - `rationale_for` [EXTRACTED]
- [[create_task()]] - `calls` [INFERRED]
- [[test_task_queue.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/EXTRACTED #community/Async_Task_Queue