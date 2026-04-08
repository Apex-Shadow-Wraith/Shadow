"""Tests for ChunkedProcessor — chunked processing for large tasks."""

from __future__ import annotations

import pytest

from modules.shadow.chunked_processor import (
    ChunkedProcessor,
    ChunkedResult,
    ChunkResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_generate(prompt: str) -> str:
    """Simple mock generate function."""
    return f"Response to: {prompt[:80]}..."


def _failing_generate(prompt: str) -> str:
    """Generate function that always raises."""
    raise RuntimeError("Model unavailable")


def _make_long_text(chars: int = 600_000) -> str:
    """Create a long text with paragraph structure."""
    paragraph = "This is a test paragraph with enough content to be meaningful. " * 10
    paragraphs = []
    while len("\n\n".join(paragraphs)) < chars:
        paragraphs.append(paragraph)
    return "\n\n".join(paragraphs)


def _make_long_text_no_paragraphs(chars: int = 600_000) -> str:
    """Create a long text with sentences but no paragraph breaks."""
    sentence = "This is a sentence with meaningful content. "
    result = ""
    while len(result) < chars:
        result += sentence
    return result


class FakeContextManager:
    """Minimal context manager stub for testing."""

    def __init__(self, max_tokens: int = 128000) -> None:
        self._model_limits = {"gemma4-26b": max_tokens, "phi4-mini": max_tokens}

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)


# ===========================================================================
# Chunking decision tests
# ===========================================================================


class TestNeedsChunking:
    """Tests for needs_chunking()."""

    def test_short_input_no_chunking(self):
        proc = ChunkedProcessor()
        assert proc.needs_chunking("Hello world") is False

    def test_long_input_needs_chunking(self):
        proc = ChunkedProcessor()
        long_text = "x" * 500_000  # ~125K tokens at 4 chars/token
        assert proc.needs_chunking(long_text) is True

    def test_threshold_boundary_conservative(self):
        """At exactly the threshold, should return True (conservative)."""
        proc = ChunkedProcessor(
            config={"trigger_threshold": 0.8}
        )
        # 128K context * 0.8 = 102,400 token threshold
        # Need total tokens (input + reserve) >= 102,400
        # Reserve is max(2048, 12800) = 12,800
        # So input needs ~89,600 tokens = ~358,400 chars
        threshold_text = "x" * 360_000
        assert proc.needs_chunking(threshold_text) is True

    def test_empty_input_no_chunking(self):
        proc = ChunkedProcessor()
        assert proc.needs_chunking("") is False

    def test_with_context_manager(self):
        cm = FakeContextManager(max_tokens=1000)
        proc = ChunkedProcessor(context_manager=cm)
        # 1000 * 0.8 = 800 threshold, text of 4000 chars = 1000 tokens + reserve
        long_text = "x" * 4000
        assert proc.needs_chunking(long_text, model="gemma4-26b") is True


# ===========================================================================
# Splitting tests
# ===========================================================================


class TestSplitIntoChunks:
    """Tests for split_into_chunks()."""

    def test_splits_on_paragraph_boundaries(self):
        proc = ChunkedProcessor()
        text = ("Paragraph one. " * 50 + "\n\n" + "Paragraph two. " * 50)
        chunks = proc.split_into_chunks(text, max_chunk_tokens=100)
        assert len(chunks) >= 2
        # Chunks should not start/end mid-word
        for chunk in chunks:
            assert chunk == chunk.strip()

    def test_splits_on_sentences_when_no_paragraphs(self):
        proc = ChunkedProcessor()
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. " * 100
        chunks = proc.split_into_chunks(text, max_chunk_tokens=200)
        assert len(chunks) >= 2

    def test_overlap_between_adjacent_chunks(self):
        proc = ChunkedProcessor()
        text = _make_long_text(10_000)
        chunks = proc.split_into_chunks(text, max_chunk_tokens=500, overlap_tokens=100)
        assert len(chunks) >= 2
        # Check that adjacent chunks share some content
        for i in range(len(chunks) - 1):
            tail = chunks[i][-100:]  # Last 100 chars of chunk i
            head = chunks[i + 1][:200]  # First 200 chars of chunk i+1
            # With overlap, there should be some shared words
            tail_words = set(tail.split())
            head_words = set(head.split())
            assert tail_words & head_words, f"No overlap between chunk {i} and {i+1}"

    def test_single_long_paragraph_splits_on_words(self):
        proc = ChunkedProcessor()
        text = "word " * 5000  # No paragraph or sentence breaks
        chunks = proc.split_into_chunks(text, max_chunk_tokens=500)
        assert len(chunks) >= 2

    def test_returns_at_least_one_chunk(self):
        proc = ChunkedProcessor()
        assert len(proc.split_into_chunks("", max_chunk_tokens=100)) >= 1
        assert len(proc.split_into_chunks("short", max_chunk_tokens=100)) >= 1

    def test_small_input_single_chunk(self):
        proc = ChunkedProcessor()
        chunks = proc.split_into_chunks("Hello world", max_chunk_tokens=1000)
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"


# ===========================================================================
# Processing tests
# ===========================================================================


class TestProcessChunked:
    """Tests for process_chunked()."""

    def test_short_input_single_pass(self):
        proc = ChunkedProcessor(generate_fn=_mock_generate)
        result = proc.process_chunked("summarize", "Short text.")
        assert result.was_chunked is False
        assert result.chunks_processed == 1
        assert result.final_output != ""

    def test_long_input_multiple_chunks(self):
        proc = ChunkedProcessor(generate_fn=_mock_generate)
        long_text = _make_long_text(600_000)
        result = proc.process_chunked("summarize", long_text)
        assert result.was_chunked is True
        assert result.chunks_processed > 1

    def test_running_summary_updated_each_chunk(self):
        proc = ChunkedProcessor(generate_fn=_mock_generate)
        long_text = _make_long_text(600_000)
        result = proc.process_chunked("summarize", long_text)
        # Each chunk result should have a non-empty running summary
        for cr in result.chunk_results:
            assert cr.running_summary != ""

    def test_final_synthesis_produces_output(self):
        proc = ChunkedProcessor(generate_fn=_mock_generate)
        long_text = _make_long_text(600_000)
        result = proc.process_chunked("summarize", long_text)
        assert result.final_output != ""
        assert result.running_summary != ""

    def test_chunked_result_correct_count(self):
        proc = ChunkedProcessor(generate_fn=_mock_generate)
        long_text = _make_long_text(600_000)
        result = proc.process_chunked("summarize", long_text)
        assert result.chunks_processed == len(result.chunk_results)
        assert isinstance(result, ChunkedResult)


# ===========================================================================
# Summary tests
# ===========================================================================


class TestUpdateRunningSummary:
    """Tests for update_running_summary()."""

    def test_incorporates_new_content(self):
        proc = ChunkedProcessor()
        summary = proc.update_running_summary("", "First chunk output.", 1)
        assert "First chunk" in summary or "Chunk 1" in summary

    def test_stays_under_max_tokens(self):
        proc = ChunkedProcessor(config={"summary_max_tokens": 50})
        long_output = "This is a sentence. " * 100
        summary = proc.update_running_summary("Previous stuff. " * 50, long_output, 5)
        # 50 tokens * 4 chars = 200 chars max
        assert len(summary) <= 200

    def test_synthesize_with_mock(self):
        proc = ChunkedProcessor(generate_fn=_mock_generate)
        result = proc.synthesize("Summary of all chunks.", "original task")
        assert result != ""


# ===========================================================================
# Edge case tests
# ===========================================================================


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_input_returns_empty_result(self):
        proc = ChunkedProcessor(generate_fn=_mock_generate)
        result = proc.process_chunked("summarize", "")
        assert result.chunks_processed == 0
        assert result.final_output == ""
        assert result.was_chunked is False

    def test_very_long_input_completes(self):
        proc = ChunkedProcessor(generate_fn=_mock_generate)
        long_text = _make_long_text(120_000)
        result = proc.process_chunked("analyze", long_text)
        assert result.chunks_processed >= 1
        assert isinstance(result, ChunkedResult)

    def test_generate_fn_failure_mid_chunk(self):
        """If generate_fn fails mid-chunk, return partial result."""
        call_count = 0

        def _fail_on_second(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise RuntimeError("Model crashed")
            return "First chunk output."

        proc = ChunkedProcessor(generate_fn=_fail_on_second)
        long_text = _make_long_text(600_000)
        result = proc.process_chunked("summarize", long_text)
        # Should return partial result, not raise
        assert isinstance(result, ChunkedResult)
        assert result.was_chunked is True

    def test_no_context_manager_uses_default(self):
        proc = ChunkedProcessor(context_manager=None)
        # Should default to 128K limit
        limit = proc._get_context_limit("gemma4-26b")
        assert limit == 128000

    def test_get_chunking_stats_valid(self):
        proc = ChunkedProcessor(generate_fn=_mock_generate)
        stats = proc.get_chunking_stats()
        assert "total_tasks_chunked" in stats
        assert "avg_chunks_per_task" in stats
        assert "avg_summary_compression" in stats
        assert stats["total_tasks_chunked"] == 0

        # Process something to update stats
        long_text = _make_long_text(600_000)
        proc.process_chunked("test", long_text)
        stats = proc.get_chunking_stats()
        assert stats["total_tasks_chunked"] == 1
        assert stats["avg_chunks_per_task"] > 0

    def test_no_generate_fn(self):
        """Processor without generate_fn should still work (empty outputs)."""
        proc = ChunkedProcessor(generate_fn=None)
        result = proc.process_chunked("test", "Short text.")
        assert isinstance(result, ChunkedResult)
