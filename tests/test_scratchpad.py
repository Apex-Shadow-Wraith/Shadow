"""Tests for Omen Scratchpad — file-based working memory."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from modules.omen.scratchpad import Scratchpad


@pytest.fixture
def scratch_dir(tmp_path):
    """Return a temp directory for scratchpads."""
    return str(tmp_path / "scratchpads")


@pytest.fixture
def pad(scratch_dir):
    """Return a Scratchpad instance with temp directory."""
    return Scratchpad(base_dir=scratch_dir)


@pytest.fixture
def pad_with_grimoire(scratch_dir):
    """Return a Scratchpad with a mock Grimoire."""
    grimoire = MagicMock()
    return Scratchpad(base_dir=scratch_dir, grimoire=grimoire), grimoire


# --- create ---

def test_create_returns_file_path(pad, scratch_dir):
    """create() returns the file path of the new scratchpad."""
    path = pad.create("task-1", "Test task")
    assert path != ""
    assert Path(path).exists()


def test_create_correct_structure(pad):
    """create() initializes JSON with correct fields."""
    pad.create("task-2", "Describe this")
    data = pad.read("task-2")
    assert data["task_id"] == "task-2"
    assert data["task_description"] == "Describe this"
    assert data["status"] == "active"
    assert data["entries"] == []
    assert "created_at" in data


def test_create_makes_base_dir(tmp_path):
    """create() creates base_dir if it doesn't exist."""
    deep = str(tmp_path / "a" / "b" / "c")
    pad = Scratchpad(base_dir=deep)
    pad.create("task-x")
    assert Path(deep).exists()


# --- write ---

def test_write_appends_entry(pad):
    """write() appends an entry to the scratchpad."""
    pad.create("t1")
    result = pad.write("t1", {
        "step": "analysis",
        "content": "Found 3 issues",
        "entry_type": "intermediate_result",
    })
    assert result is True
    data = pad.read("t1")
    assert len(data["entries"]) == 1
    assert data["entries"][0]["step"] == "analysis"
    assert data["entries"][0]["content"] == "Found 3 issues"
    assert data["entries"][0]["entry_type"] == "intermediate_result"
    assert "timestamp" in data["entries"][0]


def test_write_multiple_entries(pad):
    """write() accumulates multiple entries."""
    pad.create("t2")
    pad.write("t2", {"step": "step1", "content": "a", "entry_type": "thought"})
    pad.write("t2", {"step": "step2", "content": "b", "entry_type": "decision"})
    pad.write("t2", {"step": "step3", "content": "c", "entry_type": "code_draft"})
    data = pad.read("t2")
    assert len(data["entries"]) == 3


def test_write_nonexistent_returns_false(pad):
    """write() returns False for non-existent scratchpad."""
    result = pad.write("no-such-task", {"step": "x", "content": "y"})
    assert result is False


# --- read ---

def test_read_returns_full_contents(pad):
    """read() returns the full JSON dict."""
    pad.create("r1", "reading test")
    pad.write("r1", {"step": "a", "content": "hello", "entry_type": "thought"})
    data = pad.read("r1")
    assert data["task_id"] == "r1"
    assert len(data["entries"]) == 1


def test_read_nonexistent_returns_none(pad):
    """read() returns None for non-existent scratchpad."""
    assert pad.read("ghost") is None


# --- read_latest ---

def test_read_latest_returns_last_n(pad):
    """read_latest() returns only the last N entries."""
    pad.create("rl1")
    for i in range(5):
        pad.write("rl1", {"step": f"s{i}", "content": f"c{i}", "entry_type": "thought"})
    latest = pad.read_latest("rl1", n=2)
    assert len(latest) == 2
    assert latest[0]["step"] == "s3"
    assert latest[1]["step"] == "s4"


# --- format_for_context ---

def test_format_for_context_produces_readable_string(pad):
    """format_for_context() produces a readable formatted string."""
    pad.create("fc1")
    pad.write("fc1", {"step": "gather", "content": "collected data", "entry_type": "thought"})
    pad.write("fc1", {"step": "analyze", "content": "found pattern", "entry_type": "decision"})
    result = pad.format_for_context("fc1")
    assert result.startswith("Working memory:\n")
    assert "[Step 1: gather]" in result
    assert "[Step 2: analyze]" in result


def test_format_for_context_respects_max_tokens(pad):
    """format_for_context() truncates oldest entries first when over limit."""
    pad.create("fc2")
    for i in range(20):
        pad.write("fc2", {
            "step": f"step_{i}",
            "content": f"Content block number {i} with some padding text here",
            "entry_type": "thought",
        })
    result = pad.format_for_context("fc2", max_tokens=200)
    assert len(result) <= 200
    # Should keep the latest entries, not the oldest
    assert "step_19" in result


def test_format_for_context_empty_scratchpad(pad):
    """format_for_context() returns empty string for empty scratchpad."""
    pad.create("fc3")
    assert pad.format_for_context("fc3") == ""


def test_format_for_context_nonexistent(pad):
    """format_for_context() returns empty string for nonexistent scratchpad."""
    assert pad.format_for_context("nope") == ""


# --- close ---

def test_close_deletes_file(pad):
    """close() deletes the scratchpad file."""
    pad.create("cl1")
    result = pad.close("cl1")
    assert result is True
    assert pad.read("cl1") is None  # file deleted


def test_close_always_archives_to_grimoire(pad_with_grimoire):
    """close() always archives reasoning trace to Grimoire."""
    pad, grimoire = pad_with_grimoire
    pad.create("cl2", "archive test")
    pad.write("cl2", {"step": "x", "content": "y", "entry_type": "thought"})
    result = pad.close("cl2")
    assert result is True
    grimoire.store.assert_called_once()
    call_kwargs = grimoire.store.call_args
    assert call_kwargs.kwargs["category"] == "reasoning_trace"
    meta = call_kwargs.kwargs["metadata"]
    assert meta["source"] == "scratchpad"
    assert meta["task_id"] == "cl2"
    assert meta["entry_count"] == 1
    assert meta["status"] == "complete"


def test_close_deletes_file_after_archive(pad_with_grimoire):
    """close() deletes the file after archiving."""
    pad, grimoire = pad_with_grimoire
    pad.create("cl3")
    path = pad._path("cl3")
    assert path.exists()
    pad.close("cl3")
    assert not path.exists()


def test_close_nonexistent_returns_false(pad):
    """close() returns False for non-existent scratchpad."""
    assert pad.close("nope") is False


# --- cleanup_stale ---

def test_cleanup_stale_removes_old(pad):
    """cleanup_stale() removes scratchpads older than max_age_hours."""
    pad.create("old-task")
    # Manually backdate the created_at
    path = pad._path("old-task")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["created_at"] = time.time() - 100_000  # ~27 hours ago
    path.write_text(json.dumps(data), encoding="utf-8")

    cleaned = pad.cleanup_stale(max_age_hours=24)
    assert cleaned == 1
    assert not path.exists()


def test_cleanup_stale_doesnt_touch_recent(pad):
    """cleanup_stale() doesn't touch recent active scratchpads."""
    pad.create("fresh-task")
    cleaned = pad.cleanup_stale(max_age_hours=24)
    assert cleaned == 0
    assert pad._path("fresh-task").exists()


# --- list_active ---

def test_list_active_returns_active(pad):
    """list_active() returns active scratchpads."""
    pad.create("a1", "Alpha")
    pad.create("a2", "Beta")
    active = pad.list_active()
    assert len(active) == 2
    ids = {a["task_id"] for a in active}
    assert ids == {"a1", "a2"}


def test_list_active_excludes_completed(pad):
    """list_active() doesn't include completed scratchpads."""
    pad.create("keep")
    pad.create("done")
    pad.close("done")
    active = pad.list_active()
    assert len(active) == 1
    assert active[0]["task_id"] == "keep"


# --- concurrent / isolation ---

def test_concurrent_scratchpads_no_interference(pad):
    """Different tasks don't interfere with each other."""
    pad.create("job-a", "Job A")
    pad.create("job-b", "Job B")
    pad.write("job-a", {"step": "x", "content": "A stuff", "entry_type": "thought"})
    pad.write("job-b", {"step": "y", "content": "B stuff", "entry_type": "decision"})

    a = pad.read("job-a")
    b = pad.read("job-b")
    assert len(a["entries"]) == 1
    assert len(b["entries"]) == 1
    assert a["entries"][0]["content"] == "A stuff"
    assert b["entries"][0]["content"] == "B stuff"


# --- graceful without grimoire ---

def test_close_graceful_without_grimoire(pad):
    """close() works fine when grimoire is None (skips archive, still deletes)."""
    pad.create("nogrim")
    pad.write("nogrim", {"step": "a", "content": "b", "entry_type": "thought"})
    result = pad.close("nogrim")
    assert result is True
    assert not pad._path("nogrim").exists()


def test_cleanup_stale_archives_with_incomplete_status(tmp_path):
    """cleanup_stale() archives stale scratchpads with status 'incomplete'."""
    grimoire = MagicMock()
    pad = Scratchpad(base_dir=str(tmp_path / "sp"), grimoire=grimoire)
    pad.create("stale-task")
    # Backdate
    path = pad._path("stale-task")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["created_at"] = time.time() - 100_000
    path.write_text(json.dumps(data), encoding="utf-8")

    pad.cleanup_stale(max_age_hours=24)
    grimoire.store.assert_called_once()
    meta = grimoire.store.call_args.kwargs["metadata"]
    assert meta["status"] == "incomplete"
