"""Tests for the Conversation Ingestor — Claude Code transcript mining."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.grimoire.conversation_ingestor import (
    CATEGORY_ARCHITECTURE,
    CATEGORY_BUG_FIX,
    CATEGORY_CONFIGURATION,
    CATEGORY_GENERAL,
    CATEGORY_IMPLEMENTATION,
    CATEGORY_TESTING,
    ConversationIngestor,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_grimoire():
    """Mock Grimoire that tracks remember() calls."""
    grim = MagicMock()
    grim.remember.return_value = "fake-uuid-1234"
    return grim


@pytest.fixture
def tmp_dirs(tmp_path):
    """Create temp transcript dir and manifest path."""
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    manifest_path = tmp_path / "manifest.json"
    return transcript_dir, manifest_path


@pytest.fixture
def ingestor(mock_grimoire, tmp_dirs):
    """ConversationIngestor with mocked Grimoire and temp paths."""
    transcript_dir, manifest_path = tmp_dirs
    config = {
        "transcript_dir": str(transcript_dir),
        "manifest_path": str(manifest_path),
    }
    return ConversationIngestor(mock_grimoire, config)


def _write_jsonl(path: Path, entries: list[dict]) -> str:
    """Write a list of dicts as JSONL to the given path, return str path."""
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return str(path.resolve())


# ---------------------------------------------------------------------------
# Test: scan_transcripts finds .jsonl and skips already-processed
# ---------------------------------------------------------------------------

class TestScanTranscripts:
    def test_finds_jsonl_files(self, ingestor, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        _write_jsonl(transcript_dir / "session1.jsonl", [{"role": "user", "content": "hi"}])
        _write_jsonl(transcript_dir / "session2.jsonl", [{"role": "user", "content": "hello"}])
        # Non-JSONL file should be ignored
        (transcript_dir / "notes.txt").write_text("not a transcript")

        found = ingestor.scan_transcripts()
        assert len(found) == 2
        assert all(f.endswith(".jsonl") for f in found)

    def test_skips_already_processed(self, ingestor, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        path1 = _write_jsonl(transcript_dir / "session1.jsonl", [{"role": "user", "content": "hi"}])
        _write_jsonl(transcript_dir / "session2.jsonl", [{"role": "user", "content": "hello"}])

        # Mark session1 as processed
        ingestor._manifest["processed_files"].append(path1)

        found = ingestor.scan_transcripts()
        assert len(found) == 1
        assert path1 not in found

    def test_empty_directory(self, ingestor):
        found = ingestor.scan_transcripts()
        assert found == []

    def test_nonexistent_directory(self, mock_grimoire, tmp_path):
        config = {
            "transcript_dir": str(tmp_path / "does_not_exist"),
            "manifest_path": str(tmp_path / "manifest.json"),
        }
        ing = ConversationIngestor(mock_grimoire, config)
        found = ing.scan_transcripts()
        assert found == []

    def test_scans_subdirectories(self, ingestor, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        subdir = transcript_dir / "project_a"
        subdir.mkdir()
        _write_jsonl(subdir / "session.jsonl", [{"role": "user", "content": "deep"}])

        found = ingestor.scan_transcripts()
        assert len(found) == 1


# ---------------------------------------------------------------------------
# Test: parse_transcript handles Claude Code JSONL format
# ---------------------------------------------------------------------------

class TestParseTranscript:
    def test_basic_parse(self, ingestor, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        entries = [
            {"role": "user", "content": "Fix the login bug please"},
            {"role": "assistant", "content": "I'll look into the authentication error."},
        ]
        path = _write_jsonl(transcript_dir / "session.jsonl", entries)

        exchanges = ingestor.parse_transcript(path)
        assert len(exchanges) == 2
        assert exchanges[0]["role"] == "user"
        assert exchanges[0]["content"] == "Fix the login bug please"
        assert exchanges[1]["role"] == "assistant"

    def test_content_blocks_format(self, ingestor, tmp_dirs):
        """Claude Code may store content as a list of blocks."""
        transcript_dir, _ = tmp_dirs
        entries = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Here is the fix."},
                    {"type": "text", "text": "It resolves the crash."},
                ],
            }
        ]
        path = _write_jsonl(transcript_dir / "session.jsonl", entries)

        exchanges = ingestor.parse_transcript(path)
        assert len(exchanges) == 1
        assert "Here is the fix." in exchanges[0]["content"]
        assert "It resolves the crash." in exchanges[0]["content"]

    def test_tool_calls_extracted(self, ingestor, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        entries = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "/foo/bar.py"}},
                    {"type": "text", "text": "Editing the file now."},
                ],
            }
        ]
        path = _write_jsonl(transcript_dir / "session.jsonl", entries)

        exchanges = ingestor.parse_transcript(path)
        assert len(exchanges) == 1
        assert len(exchanges[0]["tool_calls"]) == 1
        assert exchanges[0]["tool_calls"][0]["name"] == "Edit"

    def test_file_changes_detected(self, ingestor, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        entries = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "/new/file.py"}},
                ],
            }
        ]
        path = _write_jsonl(transcript_dir / "session.jsonl", entries)

        exchanges = ingestor.parse_transcript(path)
        assert "/new/file.py" in exchanges[0]["file_changes"]

    def test_missing_file(self, ingestor):
        exchanges = ingestor.parse_transcript("/nonexistent/path.jsonl")
        assert exchanges == []

    def test_skips_invalid_json_lines(self, ingestor, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        path = transcript_dir / "messy.jsonl"
        path.write_text(
            '{"role": "user", "content": "valid"}\n'
            'this is not json\n'
            '{"role": "assistant", "content": "also valid"}\n',
            encoding="utf-8",
        )

        exchanges = ingestor.parse_transcript(str(path.resolve()))
        assert len(exchanges) == 2

    def test_timestamp_preserved(self, ingestor, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        entries = [
            {"role": "user", "content": "hello", "timestamp": "2026-01-15T10:30:00Z"},
        ]
        path = _write_jsonl(transcript_dir / "session.jsonl", entries)

        exchanges = ingestor.parse_transcript(path)
        assert exchanges[0]["timestamp"] == "2026-01-15T10:30:00Z"


# ---------------------------------------------------------------------------
# Test: extract_knowledge filters noise and categorizes correctly
# ---------------------------------------------------------------------------

class TestExtractKnowledge:
    def test_filters_short_content(self, ingestor):
        exchanges = [
            {"role": "user", "content": "hi", "tool_calls": [], "file_changes": []},
            {"role": "assistant", "content": "hello there", "tool_calls": [], "file_changes": []},
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 0  # Both under 100 chars

    def test_categorizes_bug_fix(self, ingestor):
        exchanges = [
            {
                "role": "assistant",
                "content": "The error was caused by a null pointer in the authentication module. "
                           "I fixed the bug by adding a guard clause that checks for None before "
                           "accessing the user object. This prevents the crash on login.",
                "tool_calls": [],
                "file_changes": [],
            }
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 1
        assert entries[0]["category"] == CATEGORY_BUG_FIX

    def test_categorizes_architecture(self, ingestor):
        exchanges = [
            {
                "role": "assistant",
                "content": "We should consider a different approach for the data pipeline. "
                           "The current design uses synchronous processing which creates a "
                           "bottleneck. I'd suggest we refactor to an event-driven architecture "
                           "with async message queues for better throughput.",
                "tool_calls": [],
                "file_changes": [],
            }
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 1
        assert entries[0]["category"] == CATEGORY_ARCHITECTURE

    def test_categorizes_configuration(self, ingestor):
        exchanges = [
            {
                "role": "assistant",
                "content": "The configuration file needs to be updated with the new database "
                           "connection settings. I've modified the yaml config to include the "
                           "read replica endpoints and adjusted the connection pool size to "
                           "handle the increased traffic.",
                "tool_calls": [],
                "file_changes": [],
            }
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 1
        assert entries[0]["category"] == CATEGORY_CONFIGURATION

    def test_categorizes_testing(self, ingestor):
        exchanges = [
            {
                "role": "assistant",
                "content": "I've added comprehensive pytest tests for the new authentication "
                           "module. The test suite covers edge cases including expired tokens, "
                           "invalid signatures, and concurrent session handling. All assertions "
                           "are passing with full coverage.",
                "tool_calls": [],
                "file_changes": [],
            }
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 1
        assert entries[0]["category"] == CATEGORY_TESTING

    def test_categorizes_implementation(self, ingestor):
        exchanges = [
            {
                "role": "assistant",
                "content": "I'll create and implement the new caching layer module. This adds "
                           "support for both Redis and in-memory backends with a unified "
                           "interface. The feature includes TTL management and automatic "
                           "invalidation on write operations.",
                "tool_calls": [{"name": "Write", "input": {"file_path": "/cache.py"}}],
                "file_changes": ["/cache.py"],
            }
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 1
        assert entries[0]["category"] == CATEGORY_IMPLEMENTATION

    def test_filters_tool_output_noise(self, ingestor):
        exchanges = [
            {
                "role": "tool_result",
                "content": "short tool output here",
                "tool_calls": [],
                "file_changes": [],
            }
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 0

    def test_keeps_substantial_tool_output(self, ingestor):
        long_analysis = (
            "The test suite analysis reveals a significant regression in the authentication "
            "module. The error traces show that the session handler is not properly cleaning "
            "up expired tokens, which causes a cascading failure when the garbage collector "
            "runs. The fix involves adding a try/finally block around the session cleanup "
            "and implementing proper exception handling. " * 2
        )
        exchanges = [
            {
                "role": "tool_result",
                "content": long_analysis,
                "tool_calls": [],
                "file_changes": [],
            }
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 1

    def test_sanitizes_secrets(self, ingestor):
        exchanges = [
            {
                "role": "assistant",
                "content": "Found the API key issue. The key sk-ant-abc123XYZ was hardcoded "
                           "in the config instead of being loaded from the environment. "
                           "The ANTHROPIC_API_KEY = sk-secret123 line should be removed. "
                           "This is a critical security fix that prevents key leakage.",
                "tool_calls": [],
                "file_changes": [],
            }
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 1
        assert "sk-ant-abc123XYZ" not in entries[0]["content"]
        assert "[REDACTED]" in entries[0]["content"]

    def test_metadata_populated(self, ingestor):
        exchanges = [
            {
                "role": "assistant",
                "content": "x" * 150,  # Over threshold
                "timestamp": "2026-04-10T12:00:00Z",
                "tool_calls": [{"name": "Read", "input": {}}],
                "file_changes": ["foo.py"],
            }
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 1
        meta = entries[0]["metadata"]
        assert meta["timestamp"] == "2026-04-10T12:00:00Z"
        assert meta["role"] == "assistant"
        assert meta["has_tool_calls"] is True
        assert "foo.py" in meta["file_changes"]

    def test_filters_path_listings(self, ingestor):
        exchanges = [
            {
                "role": "assistant",
                "content": "src/foo.py\nsrc/bar.py\nsrc/baz.py\nlib/util.py\nlib/helper.py\n"
                           "tests/test_a.py\ntests/test_b.py\n" * 5,
                "tool_calls": [],
                "file_changes": [],
            }
        ]
        entries = ingestor.extract_knowledge(exchanges)
        assert len(entries) == 0


# ---------------------------------------------------------------------------
# Test: full ingest pipeline with mock Grimoire
# ---------------------------------------------------------------------------

class TestIngestPipeline:
    def test_end_to_end(self, ingestor, mock_grimoire, tmp_dirs):
        transcript_dir, manifest_path = tmp_dirs
        entries = [
            {"role": "user", "content": "Please fix the authentication error that crashes on login " * 3},
            {
                "role": "assistant",
                "content": "I found the bug causing the crash. The error was in the session "
                           "handler where it tried to access an expired token. I've added a "
                           "null check and proper error handling to fix this issue. " * 2,
            },
        ]
        _write_jsonl(transcript_dir / "session1.jsonl", entries)

        result = ingestor.ingest()

        assert result["files_processed"] == 1
        assert result["entries_created"] > 0
        assert result["errors"] == []
        assert mock_grimoire.remember.called

    def test_no_files_returns_zeros(self, ingestor):
        result = ingestor.ingest()
        assert result["files_processed"] == 0
        assert result["entries_created"] == 0
        assert result["errors"] == []

    def test_multiple_files(self, ingestor, mock_grimoire, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        for i in range(3):
            entries = [
                {
                    "role": "assistant",
                    "content": f"Fixed bug #{i} in the system. The error was caused by "
                               f"incorrect type handling in module {i}. Applied the fix "
                               f"and all tests are now passing correctly. " * 2,
                },
            ]
            _write_jsonl(transcript_dir / f"session{i}.jsonl", entries)

        result = ingestor.ingest()
        assert result["files_processed"] == 3

    def test_grimoire_remember_called_correctly(self, ingestor, mock_grimoire, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        entries = [
            {
                "role": "assistant",
                "content": "The approach we should take for the new design is an event-driven "
                           "architecture. This refactor will improve throughput by decoupling "
                           "the producer and consumer components. " * 2,
            },
        ]
        _write_jsonl(transcript_dir / "session.jsonl", entries)

        ingestor.ingest()

        call_kwargs = mock_grimoire.remember.call_args
        assert call_kwargs is not None
        _, kwargs = call_kwargs
        assert kwargs["source_module"] == "conversation_ingestor"
        assert kwargs["category"] == CATEGORY_ARCHITECTURE
        assert "transcript" in kwargs["tags"]
        assert "claude_code" in kwargs["tags"]

    def test_errors_collected_not_raised(self, ingestor, mock_grimoire, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        entries = [
            {
                "role": "assistant",
                "content": "Fixing the error in the authentication handler by adding proper "
                           "exception handling and input validation. " * 3,
            },
        ]
        _write_jsonl(transcript_dir / "session.jsonl", entries)

        mock_grimoire.remember.side_effect = RuntimeError("DB locked")

        result = ingestor.ingest()
        assert result["files_processed"] == 1
        assert result["entries_created"] == 0
        assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# Test: manifest tracking prevents re-ingestion
# ---------------------------------------------------------------------------

class TestManifestTracking:
    def test_processed_files_tracked(self, ingestor, mock_grimoire, tmp_dirs):
        transcript_dir, manifest_path = tmp_dirs
        entries = [
            {
                "role": "assistant",
                "content": "Fixed the critical bug in session management that caused crashes "
                           "on startup. The error was a race condition in initialization. " * 2,
            },
        ]
        _write_jsonl(transcript_dir / "session1.jsonl", entries)

        ingestor.ingest()

        # Second run should find nothing new
        result = ingestor.ingest()
        assert result["files_processed"] == 0

    def test_manifest_persisted_to_disk(self, mock_grimoire, tmp_dirs):
        transcript_dir, manifest_path = tmp_dirs
        entries = [
            {
                "role": "assistant",
                "content": "The fix for the broken test involves correcting the assertion "
                           "that was checking the wrong return type. " * 4,
            },
        ]
        _write_jsonl(transcript_dir / "session.jsonl", entries)

        config = {
            "transcript_dir": str(transcript_dir),
            "manifest_path": str(manifest_path),
        }
        ing1 = ConversationIngestor(mock_grimoire, config)
        ing1.ingest()

        # New instance should load the manifest and skip processed files
        ing2 = ConversationIngestor(mock_grimoire, config)
        result = ing2.ingest()
        assert result["files_processed"] == 0

    def test_new_files_processed_after_manifest_load(self, mock_grimoire, tmp_dirs):
        transcript_dir, manifest_path = tmp_dirs
        config = {
            "transcript_dir": str(transcript_dir),
            "manifest_path": str(manifest_path),
        }

        # First file + first run
        entries = [
            {
                "role": "assistant",
                "content": "Fixed error in the module by patching the broken handler that "
                           "was crashing on invalid input data. " * 3,
            },
        ]
        _write_jsonl(transcript_dir / "session1.jsonl", entries)
        ing = ConversationIngestor(mock_grimoire, config)
        ing.ingest()

        # Add a second file
        _write_jsonl(transcript_dir / "session2.jsonl", entries)
        ing2 = ConversationIngestor(mock_grimoire, config)
        result = ing2.ingest()
        assert result["files_processed"] == 1  # Only the new one


# ---------------------------------------------------------------------------
# Test: stats accuracy
# ---------------------------------------------------------------------------

class TestStats:
    def test_initial_stats(self, ingestor):
        stats = ingestor.get_stats()
        assert stats["total_files"] == 0
        assert stats["total_entries"] == 0
        assert stats["last_run"] is None
        assert stats["processed_files_count"] == 0

    def test_stats_after_ingestion(self, ingestor, mock_grimoire, tmp_dirs):
        transcript_dir, _ = tmp_dirs
        entries = [
            {
                "role": "assistant",
                "content": "I found and fixed the critical error in the payment processing "
                           "module. The bug was causing incorrect calculations. " * 3,
            },
        ]
        _write_jsonl(transcript_dir / "session.jsonl", entries)

        ingestor.ingest()

        stats = ingestor.get_stats()
        assert stats["total_files"] == 1
        assert stats["total_entries"] >= 1
        assert stats["last_run"] is not None
        assert stats["processed_files_count"] == 1

    def test_stats_accumulate(self, ingestor, mock_grimoire, tmp_dirs):
        transcript_dir, _ = tmp_dirs

        # First file
        entries = [
            {
                "role": "assistant",
                "content": "Fixed the bug that was causing the error in the routing module. "
                           "The crash was due to invalid state handling. " * 3,
            },
        ]
        _write_jsonl(transcript_dir / "session1.jsonl", entries)
        ingestor.ingest()

        # Second file
        _write_jsonl(transcript_dir / "session2.jsonl", entries)
        ingestor.ingest()

        stats = ingestor.get_stats()
        assert stats["total_files"] == 2
        assert stats["processed_files_count"] == 2
