---
source_file: "modules\shadow\task_queue.py"
type: "code"
community: "Async Task Queue"
location: "L63"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Async_Task_Queue
---

# QueuedTask

## Connections
- [[.test_queued_task_serialization()]] - `calls` [INFERRED]
- [[.to_dict()_5]] - `method` [EXTRACTED]
- [[A task waiting in or being processed by the priority queue.]] - `rationale_for` [EXTRACTED]
- [[All four priority levels dequeue in correct order.]] - `uses` [INFERRED]
- [[Cleanup keeps recently completed tasks.]] - `uses` [INFERRED]
- [[Cleanup removes old completed tasks.]] - `uses` [INFERRED]
- [[Complete a task with result data.]] - `uses` [INFERRED]
- [[Completing a nonexistent task raises KeyError.]] - `uses` [INFERRED]
- [[Create a PriorityTaskQueue with temp persistence.]] - `uses` [INFERRED]
- [[Create a mock ModuleRegistry.]] - `uses` [INFERRED]
- [[Critical task does NOT preempt P2 tasks (only P3+).]] - `uses` [INFERRED]
- [[Dequeue on empty queue returns None.]] - `uses` [INFERRED]
- [[Dequeue returns highest priority task first.]] - `uses` [INFERRED]
- [[Dequeued task has RUNNING status and started_at set.]] - `uses` [INFERRED]
- [[Enqueue returns the task_id.]] - `uses` [INFERRED]
- [[Enqueueing critical (P1) task auto-preempts running P3+ tasks.]] - `uses` [INFERRED]
- [[Explicit preempt() pauses a running task.]] - `uses` [INFERRED]
- [[Factory accepts custom parameters.]] - `uses` [INFERRED]
- [[Factory sets reasonable defaults.]] - `uses` [INFERRED]
- [[Fail a task with error description.]] - `uses` [INFERRED]
- [[Failing a nonexistent task raises KeyError.]] - `uses` [INFERRED]
- [[Helper to create a QueuedTask.]] - `uses` [INFERRED]
- [[Integration tests simulating the full flow.]] - `uses` [INFERRED]
- [[Peek on empty queue returns None.]] - `uses` [INFERRED]
- [[Peek returns next task without removing it.]] - `uses` [INFERRED]
- [[Preempted tasks resume when queue is empty.]] - `uses` [INFERRED]
- [[Preempting a nonexistent task raises KeyError.]] - `uses` [INFERRED]
- [[Priority 1 dequeues before priority 2.]] - `uses` [INFERRED]
- [[Priority 2 dequeues before priority 3.]] - `uses` [INFERRED]
- [[Priority 3 dequeues before priority 4.]] - `uses` [INFERRED]
- [[Priority breakdown is accurate.]] - `uses` [INFERRED]
- [[Queue depth reflects waiting tasks.]] - `uses` [INFERRED]
- [[Queue state survives saveload cycle.]] - `uses` [INFERRED]
- [[QueuedTask survives to_dictfrom_dict round trip.]] - `uses` [INFERRED]
- [[Running count reflects active tasks.]] - `uses` [INFERRED]
- [[Simulate user request → enqueue → dequeue → chain execution.]] - `uses` [INFERRED]
- [[Tasks that were running when saved are re-queued on recovery.]] - `uses` [INFERRED]
- [[Tasks with equal priority dequeue in FIFO order.]] - `uses` [INFERRED]
- [[TestCleanup_1]] - `uses` [INFERRED]
- [[TestCompleteAndFail]] - `uses` [INFERRED]
- [[TestCreateTaskFactory]] - `uses` [INFERRED]
- [[TestEnqueueDequeue]] - `uses` [INFERRED]
- [[TestPreemption]] - `uses` [INFERRED]
- [[TestPriorityOrdering]] - `uses` [INFERRED]
- [[TestQueueChainIntegration]] - `uses` [INFERRED]
- [[TestQueueInspection]] - `uses` [INFERRED]
- [[TestQueuePersistence]] - `uses` [INFERRED]
- [[Tests for PriorityTaskQueue — priority queue with preemption and persistence.]] - `uses` [INFERRED]
- [[Tests for basic queue operations.]] - `uses` [INFERRED]
- [[Tests for completed task cleanup.]] - `uses` [INFERRED]
- [[Tests for priority-based dequeue ordering.]] - `uses` [INFERRED]
- [[Tests for queue depth, peek, and status queries.]] - `uses` [INFERRED]
- [[Tests for queue state persistence and recovery.]] - `uses` [INFERRED]
- [[Tests for task completion and failure.]] - `uses` [INFERRED]
- [[Tests for task preemption.]] - `uses` [INFERRED]
- [[Tests for the create_task convenience factory.]] - `uses` [INFERRED]
- [[create_task()]] - `calls` [EXTRACTED]
- [[get_task finds tasks in any state.]] - `uses` [INFERRED]
- [[get_task returns None for nonexistent task.]] - `uses` [INFERRED]
- [[task_queue.py]] - `contains` [EXTRACTED]

#graphify/code #graphify/INFERRED #community/Async_Task_Queue