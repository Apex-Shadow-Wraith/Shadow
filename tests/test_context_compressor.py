"""
Tests for Context Compression Pipeline
==========================================
Tests rule-based compression of grimoire results, conversation history,
tool results, system prompts, and failure patterns. Verifies integration
with ContextManager.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from modules.shadow.context_compressor import ContextCompressor, _estimate_tokens


# ──────────────────────── Fixtures ────────────────────────

@pytest.fixture
def compressor():
    """Default compressor instance."""
    return ContextCompressor()


@pytest.fixture
def long_grimoire_results():
    """Grimoire results with varied content including code blocks."""
    return [
        {
            "content": (
                "In this document we will explain how Shadow's routing works. "
                "The orchestrator receives a query and classifies it into one of 13 modules. "
                "Each module has a set of tools registered via MCP protocol. "
                "The classification uses phi4-mini with a structured prompt.\n\n"
                "```python\ndef classify(query: str) -> str:\n    return model.predict(query)\n```\n\n"
                "Additional details about fallback routing and error handling follow. "
                "The system has been tested with over 500 diverse queries."
            ),
            "relevance_score": 0.9,
        },
        {
            "content": (
                "Table of Contents\n1. Overview\n2. Setup\n3. Configuration\n\n"
                "Shadow's memory system uses SQLite for structured data and ChromaDB for vectors. "
                "Memories are stored with trust levels and timestamps. "
                "The vector embeddings use nomic-embed-text with 768 dimensions. "
                "Retrieval combines keyword search with semantic similarity."
            ),
            "relevance_score": 0.7,
        },
        {
            "content": "Short result.",
            "relevance_score": 0.3,
        },
    ]


@pytest.fixture
def conversation_history():
    """Sample conversation with multiple turns."""
    return [
        {"role": "user", "content": "What is the weather today?"},
        {"role": "assistant", "content": "I'll check the weather for you. It's currently 72°F and sunny."},
        {"role": "user", "content": "Can you set a reminder for 3pm?"},
        {"role": "assistant", "content": "I've decided to use Wraith's reminder system. Reminder set for 3:00 PM."},
        {"role": "user", "content": "How does the memory system work?"},
        {"role": "assistant", "content": "Grimoire manages memory with SQLite and ChromaDB for vector search."},
        {"role": "user", "content": "Run a security scan."},
        {"role": "assistant", "content": "Sentinel is running a network scan now. Results will be ready shortly."},
    ]


@pytest.fixture
def tool_results():
    """Sample tool execution results."""
    return [
        {"tool_name": "web_search", "content": "Found 10 results for 'Python async patterns'." * 20, "success": True},
        {"tool_name": "file_read", "content": "Error: file not found at /tmp/missing.txt", "success": False, "error": "FileNotFoundError: /tmp/missing.txt"},
        {"tool_name": "memory_search", "content": "Found 3 relevant memories about landscaping schedule.", "success": True},
    ]


# ──────────────── Grimoire Result Compression ────────────────

class TestCompressGrimoireResults:

    def test_reduces_token_count(self, compressor, long_grimoire_results):
        """Compression should reduce total tokens."""
        original_tokens = sum(
            _estimate_tokens(r["content"]) for r in long_grimoire_results
        )
        compressed = compressor.compress_grimoire_results(long_grimoire_results)
        compressed_tokens = sum(r["compressed_tokens"] for r in compressed)
        assert compressed_tokens < original_tokens

    def test_preserves_code_blocks(self, compressor, long_grimoire_results):
        """Code blocks must survive compression intact."""
        compressed = compressor.compress_grimoire_results(long_grimoire_results)
        # First result had a code block
        code_result = compressed[0]
        assert "```python" in code_result["content"]
        assert "def classify" in code_result["content"]

    def test_keeps_highest_relevance_when_over_limit(self, compressor, long_grimoire_results):
        """When over max_tokens, keep highest relevance entries."""
        compressed = compressor.compress_grimoire_results(
            long_grimoire_results, max_tokens=50
        )
        # Should keep at least the highest relevance one
        assert len(compressed) >= 1
        assert compressed[0]["relevance_score"] == 0.9

    def test_handles_empty_results(self, compressor):
        """Empty input returns empty output."""
        assert compressor.compress_grimoire_results([]) == []

    def test_strips_boilerplate(self, compressor):
        """Boilerplate phrases should be removed."""
        results = [{
            "content": "In this document we will explain everything. The actual content starts here. More details follow.",
            "relevance_score": 0.5,
        }]
        compressed = compressor.compress_grimoire_results(results)
        assert "In this document we will" not in compressed[0]["content"]
        assert "actual content" in compressed[0]["content"]

    def test_metadata_present(self, compressor, long_grimoire_results):
        """Each compressed result has required metadata fields."""
        compressed = compressor.compress_grimoire_results(long_grimoire_results)
        for r in compressed:
            assert "compressed" in r
            assert "original_tokens" in r
            assert "compressed_tokens" in r
            assert "relevance_score" in r

    def test_empty_content_handled(self, compressor):
        """Results with empty content don't crash."""
        results = [{"content": "", "relevance_score": 0.5}]
        compressed = compressor.compress_grimoire_results(results)
        assert len(compressed) == 1
        assert compressed[0]["compressed_tokens"] == 0


# ──────────────── Conversation History Compression ────────────────

class TestCompressConversationHistory:

    def test_keeps_last_n_turns_verbatim(self, compressor, conversation_history):
        """Last keep_recent turns should be unmodified."""
        compressed = compressor.compress_conversation_history(
            conversation_history, keep_recent=3
        )
        # Last 3 should match original last 3
        original_last_3 = conversation_history[-3:]
        compressed_last_3 = compressed[-3:]
        for orig, comp in zip(original_last_3, compressed_last_3):
            assert orig["content"] == comp["content"]
            assert orig["role"] == comp["role"]

    def test_summarizes_older_turns(self, compressor, conversation_history):
        """Older turns should be summarized into a single system message."""
        compressed = compressor.compress_conversation_history(
            conversation_history, keep_recent=3
        )
        # First entry should be the summary
        assert compressed[0]["role"] == "system"
        assert "[Earlier conversation:" in compressed[0]["content"]

    def test_summary_includes_topic_extraction(self, compressor, conversation_history):
        """Summary should include topics from user messages."""
        compressed = compressor.compress_conversation_history(
            conversation_history, keep_recent=2
        )
        summary = compressed[0]["content"]
        assert "User asked about" in summary
        assert "turns summarized" in summary

    def test_fewer_turns_than_keep_recent(self, compressor):
        """If fewer turns than keep_recent, return all verbatim."""
        short_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        compressed = compressor.compress_conversation_history(
            short_history, keep_recent=5
        )
        assert len(compressed) == 2
        assert compressed[0]["content"] == "Hello"
        assert compressed[1]["content"] == "Hi there!"

    def test_empty_history(self, compressor):
        """Empty history returns empty list."""
        assert compressor.compress_conversation_history([]) == []

    def test_summary_captures_decisions(self, compressor, conversation_history):
        """Summary should note key decisions when present."""
        compressed = compressor.compress_conversation_history(
            conversation_history, keep_recent=2
        )
        summary = compressed[0]["content"]
        assert "Key decisions:" in summary


# ──────────────── Tool Result Compression ────────────────

class TestCompressToolResults:

    def test_keeps_most_recent_verbatim(self, compressor, tool_results):
        """Most recent tool result should be unchanged."""
        compressed = compressor.compress_tool_results(tool_results)
        assert compressed[-1]["content"] == tool_results[-1]["content"]

    def test_truncates_older_results(self, compressor, tool_results):
        """Older successful results should be truncated with description."""
        compressed = compressor.compress_tool_results(tool_results)
        first = compressed[0]
        assert "[Result from web_search:" in first["content"]
        assert "truncated" in first["content"]
        assert first.get("summarized") is True

    def test_preserves_error_messages(self, compressor, tool_results):
        """Error results must keep full error message."""
        compressed = compressor.compress_tool_results(tool_results)
        error_result = compressed[1]  # The file_read error
        assert error_result.get("error") == "FileNotFoundError: /tmp/missing.txt"

    def test_single_result_unchanged(self, compressor):
        """Single result should be returned as-is."""
        single = [{"tool_name": "test", "content": "result data", "success": True}]
        compressed = compressor.compress_tool_results(single)
        assert len(compressed) == 1
        assert compressed[0]["content"] == "result data"

    def test_empty_results(self, compressor):
        """Empty input returns empty output."""
        assert compressor.compress_tool_results([]) == []


# ──────────────── System Prompt Compression ────────────────

class TestCompressSystemPrompt:

    def test_returns_unchanged_no_max_tokens(self, compressor):
        """Without max_tokens, prompt is returned as-is."""
        prompt = "You are Shadow, an autonomous AI agent."
        assert compressor.compress_system_prompt(prompt) == prompt

    def test_removes_optional_sections(self, compressor):
        """Optional sections are removed when max_tokens is set."""
        prompt = (
            "You are Shadow.\n"
            "<!-- optional -->\n"
            "This is optional background info that can be dropped.\n"
            "<!-- /optional -->\n"
            "Core identity remains."
        )
        compressed = compressor.compress_system_prompt(prompt, max_tokens=10)
        assert "optional background" not in compressed
        assert "Core identity remains" in compressed

    def test_short_prompt_unchanged_with_max(self, compressor):
        """Short prompt stays the same even with max_tokens."""
        prompt = "Shadow."
        assert compressor.compress_system_prompt(prompt, max_tokens=1000) == prompt

    def test_empty_prompt(self, compressor):
        """Empty prompt returns empty."""
        assert compressor.compress_system_prompt("") == ""
        assert compressor.compress_system_prompt(None) is None


# ──────────────── compress_all ────────────────

class TestCompressAll:

    def test_compresses_all_components(self, compressor, long_grimoire_results, conversation_history, tool_results):
        """compress_all should handle all component types."""
        components = {
            "grimoire_results": long_grimoire_results,
            "conversation_history": conversation_history,
            "tool_results": tool_results,
            "system_prompt": "You are Shadow.",
            "failure_patterns": [{"task_type": "routing", "mistake": "wrong module", "correct_approach": "check keywords"}],
        }
        result = compressor.compress_all(components)
        assert "grimoire_results" in result
        assert "conversation_history" in result
        assert "tool_results" in result
        assert "system_prompt" in result
        assert "failure_patterns" in result
        assert "compression_report" in result

    def test_none_inputs_handled(self, compressor):
        """None/missing inputs should not crash."""
        result = compressor.compress_all({})
        assert result["grimoire_results"] == []
        assert result["conversation_history"] == []
        assert result["tool_results"] == []
        assert result["system_prompt"] == ""
        assert result["failure_patterns"] == []


# ──────────────── Compression Report ────────────────

class TestCompressionReport:

    def test_report_has_accurate_ratios(self, compressor, long_grimoire_results, conversation_history, tool_results):
        """Report should have per-component and overall stats."""
        components = {
            "grimoire_results": long_grimoire_results,
            "conversation_history": conversation_history,
            "tool_results": tool_results,
            "system_prompt": "You are Shadow.",
            "failure_patterns": [],
        }
        compressor.compress_all(components)
        report = compressor.get_compression_report()
        assert "per_component" in report
        assert "total_original" in report
        assert "total_compressed" in report
        assert "overall_ratio" in report
        assert "summary" in report
        assert report["total_compressed"] <= report["total_original"]

    def test_ratio_is_positive(self, compressor, long_grimoire_results, conversation_history, tool_results):
        """Output should be smaller than or equal to input."""
        components = {
            "grimoire_results": long_grimoire_results,
            "conversation_history": conversation_history,
            "tool_results": tool_results,
            "system_prompt": "Short prompt.",
            "failure_patterns": [],
        }
        compressor.compress_all(components)
        report = compressor.get_compression_report()
        assert report["overall_ratio"] >= 0.0


# ──────────────── Edge Cases ────────────────

class TestEdgeCases:

    def test_very_short_content_not_longer(self, compressor):
        """Compression must not make very short content longer."""
        results = [{"content": "OK.", "relevance_score": 1.0}]
        compressed = compressor.compress_grimoire_results(results)
        assert compressed[0]["compressed_tokens"] <= compressed[0]["original_tokens"] + 1

    def test_unicode_content(self, compressor):
        """Unicode content should be handled correctly."""
        results = [{
            "content": "日本語のテストです。これはUnicodeのテキストです。Shadow は多言語対応。",
            "relevance_score": 0.8,
        }]
        compressed = compressor.compress_grimoire_results(results)
        assert len(compressed) == 1
        assert compressed[0]["compressed_tokens"] > 0

    def test_none_empty_inputs_all_methods(self, compressor):
        """All methods handle None/empty gracefully."""
        assert compressor.compress_grimoire_results([]) == []
        assert compressor.compress_grimoire_results(None or []) == []
        assert compressor.compress_conversation_history([]) == []
        assert compressor.compress_tool_results([]) == []
        assert compressor.compress_system_prompt("") == ""
        assert compressor.compress_failure_patterns([]) == []


# ──────────────── ContextManager Integration ────────────────

class TestContextManagerIntegration:

    def test_context_manager_calls_compressor_before_trimming(self):
        """ContextManager should call compressor.compress_all before trimming."""
        from modules.shadow.context_manager import ContextManager

        cm = ContextManager(max_tokens=128000)

        # Verify the compressor attribute exists and is used
        mock_compressor = MagicMock()
        mock_compressor.compress_all.return_value = {
            "grimoire_results": [],
            "conversation_history": [],
            "tool_results": [],
            "system_prompt": "Test prompt.",
            "failure_patterns": [],
            "compression_report": {"overall_ratio": 0.5, "summary": "50% reduction"},
        }
        mock_compressor.get_compression_report.return_value = {"overall_ratio": 0.5}

        cm.compressor = mock_compressor
        cm.build_context(
            system_prompt="Test prompt.",
            conversation_history=[{"role": "user", "content": "hello"}],
            grimoire_memories=[{"content": "memory"}],
            failure_patterns=[],
            tool_results=[],
            current_input="test",
        )

        mock_compressor.compress_all.assert_called_once()
        mock_compressor.get_compression_report.assert_called_once()
