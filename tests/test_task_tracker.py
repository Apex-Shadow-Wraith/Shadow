"""Tests for TaskTracker — SQLite-backed task persistence."""

import time
import uuid

import pytest

from modules.shadow.task_tracker import VALID_MODULES, VALID_STATUSES, TaskTracker


@pytest.fixture
def tracker(tmp_path):
    """Create a TaskTracker with a temp database."""
    db_path = tmp_path / "test_tasks.db"
    t = TaskTracker(db_path=db_path)
    t.initialize()
    yield t
    t.close()


# --- Creation ---


def test_create_task_returns_uuid(tracker):
    """Create a task and verify the returned ID is a valid uuid4."""
    task_id = tracker.create("Test task", "wraith")
    uuid.UUID(task_id, version=4)  # Raises if invalid


def test_create_task_fields(tracker):
    """Created task has correct defaults and stored values."""
    task_id = tracker.create("Deploy update", "omen", priority=2)
    task = tracker.get_status(task_id)

    assert task["task_id"] == task_id
    assert task["description"] == "Deploy update"
    assert task["assigned_module"] == "omen"
    assert task["priority"] == 2
    assert task["status"] == "queued"
    assert task["result"] is None
    assert isinstance(task["created_at"], float)
    assert isinstance(task["updated_at"], float)


def test_create_task_default_priority(tracker):
    """Default priority is 5."""
    task_id = tracker.create("Something", "wraith")
    task = tracker.get_status(task_id)
    assert task["priority"] == 5


def test_create_empty_description_fails(tracker):
    """Empty or whitespace-only descriptions are rejected."""
    with pytest.raises(ValueError, match="description must not be empty"):
        tracker.create("", "wraith")
    with pytest.raises(ValueError, match="description must not be empty"):
        tracker.create("   ", "wraith")


def test_create_invalid_module_fails(tracker):
    """Invalid module names are rejected."""
    with pytest.raises(ValueError, match="Invalid module"):
        tracker.create("Some task", "nonexistent_module")


def test_create_priority_bounds(tracker):
    """Priority must be 1-10."""
    with pytest.raises(ValueError, match="priority must be an integer"):
        tracker.create("Bad priority", "wraith", priority=0)
    with pytest.raises(ValueError, match="priority must be an integer"):
        tracker.create("Bad priority", "wraith", priority=11)
    with pytest.raises(ValueError, match="priority must be an integer"):
        tracker.create("Bad priority", "wraith", priority=-1)


def test_create_priority_not_float(tracker):
    """Priority must be an int, not float."""
    with pytest.raises(ValueError, match="priority must be an integer"):
        tracker.create("Float priority", "wraith", priority=3.5)


def test_duplicate_task_id_impossible(tracker):
    """Two creates always produce different IDs (uuid4 uniqueness)."""
    ids = {tracker.create(f"Task {i}", "wraith") for i in range(50)}
    assert len(ids) == 50


# --- Status transitions ---


def test_status_transition_queued_to_running_to_completed(tracker):
    """Normal lifecycle: queued → running → completed."""
    task_id = tracker.create("Lifecycle test", "omen")

    tracker.update_status(task_id, "running")
    assert tracker.get_status(task_id)["status"] == "running"

    tracker.update_status(task_id, "completed", result={"answer": 42})
    task = tracker.get_status(task_id)
    assert task["status"] == "completed"
    assert task["result"] == {"answer": 42}


def test_update_status_invalid_status(tracker):
    """Invalid status string raises ValueError."""
    task_id = tracker.create("Test", "wraith")
    with pytest.raises(ValueError, match="Invalid status"):
        tracker.update_status(task_id, "exploded")


def test_update_status_nonexistent_task(tracker):
    """Updating a missing task raises KeyError."""
    with pytest.raises(KeyError, match="Task not found"):
        tracker.update_status("nonexistent-id", "running")


def test_get_status_nonexistent(tracker):
    """Getting a missing task raises KeyError."""
    with pytest.raises(KeyError, match="Task not found"):
        tracker.get_status("does-not-exist")


def test_updated_at_changes(tracker):
    """updated_at advances when status changes."""
    task_id = tracker.create("Timing test", "wraith")
    t1 = tracker.get_status(task_id)["updated_at"]

    time.sleep(0.01)
    tracker.update_status(task_id, "running")
    t2 = tracker.get_status(task_id)["updated_at"]
    assert t2 > t1


# --- Cancel ---


def test_cancel_queued_task(tracker):
    """Cancelling a queued task succeeds."""
    task_id = tracker.create("Cancel me", "reaper")
    assert tracker.cancel(task_id) is True
    assert tracker.get_status(task_id)["status"] == "cancelled"


def test_cancel_running_task(tracker):
    """Cancelling a running task succeeds."""
    task_id = tracker.create("Running task", "reaper")
    tracker.update_status(task_id, "running")
    assert tracker.cancel(task_id) is True
    assert tracker.get_status(task_id)["status"] == "cancelled"


def test_cancel_completed_task_fails(tracker):
    """Cannot cancel a completed task."""
    task_id = tracker.create("Done task", "omen")
    tracker.update_status(task_id, "completed")
    assert tracker.cancel(task_id) is False
    assert tracker.get_status(task_id)["status"] == "completed"


def test_cancel_failed_task_fails(tracker):
    """Cannot cancel a failed task."""
    task_id = tracker.create("Failed task", "omen")
    tracker.update_status(task_id, "failed")
    assert tracker.cancel(task_id) is False


def test_cancel_nonexistent_task(tracker):
    """Cancelling a missing task raises KeyError."""
    with pytest.raises(KeyError):
        tracker.cancel("no-such-task")


# --- List ---


def test_list_all_tasks(tracker):
    """List without filter returns everything."""
    tracker.create("Task A", "wraith", priority=1)
    tracker.create("Task B", "omen", priority=3)
    tracker.create("Task C", "reaper", priority=2)

    tasks = tracker.list_tasks()
    assert len(tasks) == 3


def test_list_with_status_filter(tracker):
    """Filter returns only matching tasks."""
    id_a = tracker.create("Task A", "wraith")
    id_b = tracker.create("Task B", "omen")
    tracker.update_status(id_a, "running")

    queued = tracker.list_tasks(status_filter="queued")
    assert len(queued) == 1
    assert queued[0]["task_id"] == id_b

    running = tracker.list_tasks(status_filter="running")
    assert len(running) == 1
    assert running[0]["task_id"] == id_a


def test_list_invalid_status_filter(tracker):
    """Invalid status filter raises ValueError."""
    with pytest.raises(ValueError, match="Invalid status"):
        tracker.list_tasks(status_filter="exploded")


def test_list_empty(tracker):
    """List on empty DB returns empty list."""
    assert tracker.list_tasks() == []


def test_list_ordered_by_priority(tracker):
    """Tasks are ordered by priority ASC (1 first)."""
    tracker.create("Low", "wraith", priority=10)
    tracker.create("High", "wraith", priority=1)
    tracker.create("Medium", "wraith", priority=5)

    tasks = tracker.list_tasks()
    priorities = [t["priority"] for t in tasks]
    assert priorities == [1, 5, 10]


# --- Cleanup ---


def test_cleanup_removes_old_completed(tracker):
    """Cleanup deletes completed tasks older than threshold."""
    task_id = tracker.create("Old task", "wraith")
    tracker.update_status(task_id, "completed")

    # Backdate the created_at to 60 days ago
    old_time = time.time() - (60 * 86400)
    tracker._db.execute(
        "UPDATE shadow_tasks SET created_at = ? WHERE task_id = ?",
        (old_time, task_id),
    )
    tracker._db.commit()

    deleted = tracker.cleanup(older_than_days=30)
    assert deleted == 1
    assert tracker.list_tasks() == []


def test_cleanup_preserves_recent(tracker):
    """Cleanup does not delete tasks within the threshold."""
    task_id = tracker.create("Recent task", "wraith")
    tracker.update_status(task_id, "completed")

    deleted = tracker.cleanup(older_than_days=30)
    assert deleted == 0
    assert len(tracker.list_tasks()) == 1


def test_cleanup_preserves_queued_and_running(tracker):
    """Cleanup only targets completed/failed/cancelled tasks."""
    id_q = tracker.create("Queued", "wraith")
    id_r = tracker.create("Running", "omen")
    tracker.update_status(id_r, "running")

    # Backdate both
    old_time = time.time() - (60 * 86400)
    tracker._db.execute(
        "UPDATE shadow_tasks SET created_at = ? WHERE task_id IN (?, ?)",
        (old_time, id_q, id_r),
    )
    tracker._db.commit()

    deleted = tracker.cleanup(older_than_days=30)
    assert deleted == 0
    assert len(tracker.list_tasks()) == 2


def test_cleanup_mixed(tracker):
    """Cleanup removes old terminal tasks but keeps active and recent ones."""
    old_time = time.time() - (60 * 86400)

    # Old completed — should be deleted
    id_old = tracker.create("Old done", "wraith")
    tracker.update_status(id_old, "completed")
    tracker._db.execute(
        "UPDATE shadow_tasks SET created_at = ? WHERE task_id = ?",
        (old_time, id_old),
    )

    # Old failed — should be deleted
    id_fail = tracker.create("Old fail", "omen")
    tracker.update_status(id_fail, "failed")
    tracker._db.execute(
        "UPDATE shadow_tasks SET created_at = ? WHERE task_id = ?",
        (old_time, id_fail),
    )

    # Recent completed — should survive
    id_recent = tracker.create("Recent done", "reaper")
    tracker.update_status(id_recent, "completed")

    # Old queued — should survive (not terminal)
    id_queued = tracker.create("Old queued", "omen")
    tracker._db.execute(
        "UPDATE shadow_tasks SET created_at = ? WHERE task_id = ?",
        (old_time, id_queued),
    )

    tracker._db.commit()

    deleted = tracker.cleanup(older_than_days=30)
    assert deleted == 2
    remaining = tracker.list_tasks()
    remaining_ids = {t["task_id"] for t in remaining}
    assert id_recent in remaining_ids
    assert id_queued in remaining_ids


# --- All valid modules accepted ---


def test_all_valid_modules_accepted(tracker):
    """Every module codename is accepted."""
    for mod in sorted(VALID_MODULES):
        task_id = tracker.create(f"Test {mod}", mod)
        assert tracker.get_status(task_id)["assigned_module"] == mod


# --- Result JSON round-trip ---


def test_result_json_roundtrip(tracker):
    """Result dict survives JSON serialization/deserialization."""
    task_id = tracker.create("JSON test", "omen")
    payload = {"scores": [1, 2, 3], "nested": {"key": "value"}}
    tracker.update_status(task_id, "completed", result=payload)
    task = tracker.get_status(task_id)
    assert task["result"] == payload
