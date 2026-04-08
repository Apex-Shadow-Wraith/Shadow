"""Chunked Processing — split tasks exceeding the context window into sequential chunks.

Handles arbitrarily large inputs by splitting them into manageable chunks,
processing each with a running summary for continuity, then synthesizing
a final cohesive output.

NOTE: Chunked processing is a quality trade-off. Splitting input across
multiple model calls loses some cross-chunk coherence compared to a single
pass. Use only when input genuinely exceeds the context window.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Default context limits per model family (tokens)
_DEFAULT_CONTEXT_LIMITS: dict[str, int] = {
    "gemma4-26b": 128000,
    "phi4-mini": 128000,
    "gemma3": 128000,
    "llama3": 8192,
    "mistral": 32768,
}


@dataclass
class ChunkResult:
    """Result from processing a single chunk."""

    chunk_number: int
    input_segment: str
    output: str
    running_summary: str
    tokens_in_chunk: int
    duration_seconds: float


@dataclass
class ChunkedResult:
    """Aggregate result from chunked processing."""

    task: str
    chunks_processed: int
    chunk_results: list[ChunkResult]
    final_output: str
    running_summary: str
    total_input_tokens: int
    total_duration: float
    was_chunked: bool  # False if input fit in single pass


class ChunkedProcessor:
    """Split large tasks into sequential chunks with running summaries."""

    def __init__(
        self,
        generate_fn: Callable | None = None,
        context_manager: Any | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._generate_fn = generate_fn
        self._context_manager = context_manager
        config = config or {}

        self._chunk_overlap_tokens: int = config.get("chunk_overlap_tokens", 200)
        self._trigger_threshold: float = config.get("trigger_threshold", 0.8)
        self._summary_max_tokens: int = config.get("summary_max_tokens", 500)

        # Stats tracking
        self._tasks_chunked: int = 0
        self._total_chunks: int = 0
        self._total_summary_input_tokens: int = 0
        self._total_summary_output_tokens: int = 0

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        if not text:
            return 0
        if self._context_manager and hasattr(self._context_manager, "estimate_tokens"):
            return self._context_manager.estimate_tokens(text)
        # Fallback: ~4 chars per token
        return max(1, len(text) // 4)

    def _get_context_limit(self, model: str = "gemma4-26b") -> int:
        """Get context window size for a model."""
        if self._context_manager and hasattr(self._context_manager, "_model_limits"):
            limit = self._context_manager._model_limits.get(model)
            if limit:
                return limit
        return _DEFAULT_CONTEXT_LIMITS.get(model, 128000)

    # ------------------------------------------------------------------
    # Chunking decision
    # ------------------------------------------------------------------

    def needs_chunking(
        self,
        input_text: str,
        system_prompt: str = "",
        model: str = "gemma4-26b",
    ) -> bool:
        """Return True if the input exceeds the trigger threshold of the context window.

        Conservative: returns True at threshold boundary.
        """
        if not input_text:
            return False

        context_limit = self._get_context_limit(model)
        threshold = int(context_limit * self._trigger_threshold)

        total_tokens = self._estimate_tokens(system_prompt) + self._estimate_tokens(input_text)
        # Reserve space for response
        reserve = max(2048, int(context_limit * 0.1))
        total_tokens += reserve

        return total_tokens >= threshold

    # ------------------------------------------------------------------
    # Splitting
    # ------------------------------------------------------------------

    def split_into_chunks(
        self,
        text: str,
        max_chunk_tokens: int,
        overlap_tokens: int = 200,
    ) -> list[str]:
        """Split text into chunks that fit within max_chunk_tokens.

        Split priority:
        1. Paragraph boundaries (\\n\\n)
        2. Sentence boundaries (. ! ?)
        3. Word boundaries
        """
        if not text:
            return [""]

        total_tokens = self._estimate_tokens(text)
        if total_tokens <= max_chunk_tokens:
            return [text]

        # Approximate chars per token for splitting
        chars_per_token = len(text) / max(1, total_tokens)
        max_chunk_chars = int(max_chunk_tokens * chars_per_token)
        overlap_chars = int(overlap_tokens * chars_per_token)

        if max_chunk_chars <= 0:
            max_chunk_chars = 1000  # Safety floor

        chunks: list[str] = []
        pos = 0

        while pos < len(text):
            end = min(pos + max_chunk_chars, len(text))

            if end < len(text):
                # Try paragraph boundary
                split_point = self._find_split_point(
                    text, pos, end, "\n\n"
                )
                if split_point is None:
                    # Try sentence boundary
                    split_point = self._find_sentence_boundary(text, pos, end)
                if split_point is None:
                    # Try word boundary
                    split_point = self._find_split_point(
                        text, pos, end, " "
                    )
                if split_point is None:
                    # Hard split
                    split_point = end

                chunk_text = text[pos:split_point].strip()
                if chunk_text:
                    chunks.append(chunk_text)

                # Move forward, accounting for overlap
                pos = max(pos + 1, split_point - overlap_chars)
            else:
                chunk_text = text[pos:end].strip()
                if chunk_text:
                    chunks.append(chunk_text)
                break

        return chunks if chunks else [""]

    def _find_split_point(
        self, text: str, start: int, end: int, delimiter: str
    ) -> int | None:
        """Find the last occurrence of delimiter between start and end."""
        # Search in the last 30% of the chunk for a natural break
        search_start = start + int((end - start) * 0.7)
        idx = text.rfind(delimiter, search_start, end)
        if idx > start:
            return idx + len(delimiter)
        return None

    def _find_sentence_boundary(
        self, text: str, start: int, end: int
    ) -> int | None:
        """Find the last sentence boundary (. ! ?) in the chunk."""
        search_start = start + int((end - start) * 0.7)
        best = None
        for punct in (".", "!", "?"):
            idx = text.rfind(punct, search_start, end)
            if idx > start and (best is None or idx > best):
                best = idx
        if best is not None:
            return best + 1
        return None

    # ------------------------------------------------------------------
    # Running summary
    # ------------------------------------------------------------------

    def update_running_summary(
        self,
        previous_summary: str,
        new_output: str,
        chunk_number: int,
    ) -> str:
        """Update running summary incorporating new chunk output.

        Uses model if available, otherwise falls back to sentence extraction.
        """
        if self._generate_fn:
            try:
                prompt = (
                    f"You are summarizing a multi-part processing task.\n\n"
                    f"Previous summary (chunks 1-{chunk_number - 1}):\n"
                    f"{previous_summary}\n\n"
                    f"New output (chunk {chunk_number}):\n"
                    f"{new_output}\n\n"
                    f"Write a concise updated summary incorporating the new output. "
                    f"Keep under {self._summary_max_tokens} tokens. "
                    f"Focus on key facts, findings, and conclusions."
                )
                result = self._generate_fn(prompt)
                if result:
                    summary_tokens = self._estimate_tokens(result)
                    self._total_summary_input_tokens += self._estimate_tokens(prompt)
                    self._total_summary_output_tokens += summary_tokens
                    return result
            except Exception as e:
                logger.warning("Model summary failed, using fallback: %s", e)

        # Fallback: extract first 2 sentences from new output
        return self._fallback_summary(previous_summary, new_output, chunk_number)

    def _fallback_summary(
        self,
        previous_summary: str,
        new_output: str,
        chunk_number: int,
    ) -> str:
        """Concatenate first 2 sentences from each chunk output."""
        sentences = []
        current = ""
        for char in new_output:
            current += char
            if char in ".!?" and len(current.strip()) > 10:
                sentences.append(current.strip())
                current = ""
                if len(sentences) >= 2:
                    break

        if not sentences and new_output:
            # No sentence boundaries found — take first 200 chars
            sentences = [new_output[:200].strip()]

        new_summary_part = f"Chunk {chunk_number}: " + " ".join(sentences)

        if previous_summary:
            combined = f"{previous_summary}\n{new_summary_part}"
        else:
            combined = new_summary_part

        # Trim if over budget
        max_chars = self._summary_max_tokens * 4  # ~4 chars/token
        if len(combined) > max_chars:
            combined = combined[:max_chars]

        return combined

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def synthesize(self, running_summary: str, task: str) -> str:
        """Final synthesis pass — combine all chunk summaries into cohesive output."""
        if not self._generate_fn:
            return running_summary

        prompt = (
            f"Here is a summary of all processed segments:\n"
            f"{running_summary}\n\n"
            f"Original task: {task}\n\n"
            f"Provide the final cohesive answer."
        )
        try:
            result = self._generate_fn(prompt)
            return result if result else running_summary
        except Exception as e:
            logger.warning("Synthesis failed, returning raw summary: %s", e)
            return running_summary

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_chunked(
        self,
        task: str,
        input_text: str,
        system_prompt: str = "",
        model: str = "gemma4-26b",
    ) -> ChunkedResult:
        """Process a task, chunking if needed.

        If input fits in one pass, processes directly (was_chunked=False).
        Otherwise splits into chunks with running summaries.
        """
        start_time = time.time()

        # Empty input
        if not input_text:
            return ChunkedResult(
                task=task,
                chunks_processed=0,
                chunk_results=[],
                final_output="",
                running_summary="",
                total_input_tokens=0,
                total_duration=time.time() - start_time,
                was_chunked=False,
            )

        total_input_tokens = self._estimate_tokens(input_text)

        # Single pass if it fits
        if not self.needs_chunking(input_text, system_prompt, model):
            output = ""
            if self._generate_fn:
                try:
                    prompt = f"{system_prompt}\n\n{input_text}\n\nTask: {task}" if system_prompt else f"{input_text}\n\nTask: {task}"
                    output = self._generate_fn(prompt) or ""
                except Exception as e:
                    logger.error("Single-pass generation failed: %s", e)

            chunk_result = ChunkResult(
                chunk_number=1,
                input_segment=input_text,
                output=output,
                running_summary=output,
                tokens_in_chunk=total_input_tokens,
                duration_seconds=time.time() - start_time,
            )
            return ChunkedResult(
                task=task,
                chunks_processed=1,
                chunk_results=[chunk_result],
                final_output=output,
                running_summary=output,
                total_input_tokens=total_input_tokens,
                total_duration=time.time() - start_time,
                was_chunked=False,
            )

        # Multi-chunk processing
        context_limit = self._get_context_limit(model)
        system_tokens = self._estimate_tokens(system_prompt)
        summary_reserve = self._summary_max_tokens
        response_reserve = max(2048, int(context_limit * 0.1))
        overhead = 200  # Prompt template tokens

        max_chunk_tokens = context_limit - system_tokens - summary_reserve - response_reserve - overhead
        max_chunk_tokens = max(500, max_chunk_tokens)  # Safety floor

        chunks = self.split_into_chunks(
            input_text, max_chunk_tokens, self._chunk_overlap_tokens
        )

        chunk_results: list[ChunkResult] = []
        running_summary = ""

        for i, chunk in enumerate(chunks, 1):
            chunk_start = time.time()
            chunk_tokens = self._estimate_tokens(chunk)

            # Build prompt with running context
            parts = []
            if system_prompt:
                parts.append(system_prompt)
            if running_summary:
                parts.append(f"Previous segments summary:\n{running_summary}")
            parts.append(f"Process this segment:\n{chunk}")
            parts.append(f"\nTask: {task}")
            prompt = "\n\n".join(parts)

            # Generate
            output = ""
            if self._generate_fn:
                try:
                    output = self._generate_fn(prompt) or ""
                except Exception as e:
                    logger.error("Chunk %d generation failed: %s", i, e)
                    # Return partial result on failure
                    chunk_result = ChunkResult(
                        chunk_number=i,
                        input_segment=chunk,
                        output="",
                        running_summary=running_summary,
                        tokens_in_chunk=chunk_tokens,
                        duration_seconds=time.time() - chunk_start,
                    )
                    chunk_results.append(chunk_result)

                    self._tasks_chunked += 1
                    self._total_chunks += len(chunk_results)

                    return ChunkedResult(
                        task=task,
                        chunks_processed=len(chunk_results),
                        chunk_results=chunk_results,
                        final_output=running_summary,
                        running_summary=running_summary,
                        total_input_tokens=total_input_tokens,
                        total_duration=time.time() - start_time,
                        was_chunked=True,
                    )

            # Update running summary
            running_summary = self.update_running_summary(
                running_summary, output, i
            )

            chunk_result = ChunkResult(
                chunk_number=i,
                input_segment=chunk,
                output=output,
                running_summary=running_summary,
                tokens_in_chunk=chunk_tokens,
                duration_seconds=time.time() - chunk_start,
            )
            chunk_results.append(chunk_result)
            logger.info(
                "Chunk %d/%d processed (%d tokens, %.1fs)",
                i, len(chunks), chunk_tokens, chunk_result.duration_seconds,
            )

        # Final synthesis
        final_output = self.synthesize(running_summary, task)

        self._tasks_chunked += 1
        self._total_chunks += len(chunk_results)

        return ChunkedResult(
            task=task,
            chunks_processed=len(chunk_results),
            chunk_results=chunk_results,
            final_output=final_output,
            running_summary=running_summary,
            total_input_tokens=total_input_tokens,
            total_duration=time.time() - start_time,
            was_chunked=True,
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_chunking_stats(self) -> dict[str, Any]:
        """Return chunking statistics for context profiling."""
        avg_chunks = (
            self._total_chunks / self._tasks_chunked
            if self._tasks_chunked > 0
            else 0.0
        )
        avg_compression = 0.0
        if self._total_summary_input_tokens > 0:
            avg_compression = 1.0 - (
                self._total_summary_output_tokens / self._total_summary_input_tokens
            )

        return {
            "total_tasks_chunked": self._tasks_chunked,
            "avg_chunks_per_task": round(avg_chunks, 2),
            "avg_summary_compression": round(avg_compression, 3),
        }
