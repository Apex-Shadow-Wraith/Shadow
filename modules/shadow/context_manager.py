"""
Context Window Manager — Token Estimation and Priority-Based Trimming
========================================================================
Shadow needs to know how much context he's using and automatically trim
to prevent overflow and degradation. This module handles:

- Fast token estimation without external tokenizer dependencies
- Priority-based context assembly and trimming
- Model-specific context window limits
- Usage reporting and diagnostics

The rule: Shadow's identity (system prompt) and the current request are
NEVER trimmed. Everything else has a priority order for removal.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.context_manager")


@dataclass
class TokenBreakdown:
    """Token usage breakdown for each context component."""
    system_prompt_tokens: int = 0
    history_tokens: int = 0
    memory_tokens: int = 0
    failure_pattern_tokens: int = 0
    tool_result_tokens: int = 0
    input_tokens: int = 0
    total_tokens: int = 0

    def as_dict(self) -> dict[str, int]:
        """Return breakdown as a dictionary."""
        return {
            "system_prompt_tokens": self.system_prompt_tokens,
            "history_tokens": self.history_tokens,
            "memory_tokens": self.memory_tokens,
            "failure_pattern_tokens": self.failure_pattern_tokens,
            "tool_result_tokens": self.tool_result_tokens,
            "input_tokens": self.input_tokens,
            "total_tokens": self.total_tokens,
        }


# Default context limits for known models
_DEFAULT_MODEL_LIMITS: dict[str, int] = {
    "gemma4:26b": 256000,
    "qwen3.5:35b-a3b": 262144,
    "qwen3.5-35b-a3b": 262144,
    "phi4-mini": 16384,
    "nomic-embed-text": 8192,
}

# Default unknown model limit
_DEFAULT_CONTEXT_LIMIT = 128000


class ContextManager:
    """Manages context window usage with priority-based trimming.

    Ensures Shadow never overflows the model's context window by
    estimating token counts and trimming low-priority components
    when the total exceeds the effective limit.
    """

    def __init__(
        self,
        max_tokens: int = 128000,
        reserve_tokens: int = 4096,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._max_tokens = max_tokens
        self._reserve_tokens = reserve_tokens
        self._effective_limit = max_tokens - reserve_tokens
        self._config = config or {}

        # Calibration ratios — can be tuned via calibrate()
        self._english_ratio = 4.0   # 1 token ≈ 4 chars for English
        self._code_ratio = 3.5      # 1 token ≈ 3.5 chars for code

        # Load model limits from config, falling back to defaults
        self._model_limits = dict(_DEFAULT_MODEL_LIMITS)
        config_limits = self._config.get("context_limits", {}).get("model_context_limits", {})
        self._model_limits.update(config_limits)

        # Override reserve from config if present
        config_reserve = self._config.get("context_limits", {}).get("reserve_tokens")
        if config_reserve is not None:
            self._reserve_tokens = config_reserve
            self._effective_limit = self._max_tokens - self._reserve_tokens

        # Context compressor — compress before trimming
        self.compressor = None
        try:
            from modules.shadow.context_compressor import ContextCompressor
            self.compressor = ContextCompressor(self._config.get("compressor", {}))
        except Exception:
            logger.debug("ContextCompressor not available, skipping compression")

        # Last build stats for reporting
        self._last_breakdown: TokenBreakdown | None = None
        self._last_trimmed: bool = False
        self._last_trimmed_components: list[str] = []

    @property
    def max_tokens(self) -> int:
        """Maximum tokens for the model's context window."""
        return self._max_tokens

    @property
    def reserve_tokens(self) -> int:
        """Tokens reserved for the response."""
        return self._reserve_tokens

    @property
    def effective_limit(self) -> int:
        """Usable tokens (max - reserve)."""
        return self._effective_limit

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count without an external tokenizer.

        Uses character-based heuristics:
        - English text: ~4 characters per token
        - Code: ~3.5 characters per token (more special chars/operators)

        Detects code by checking for common code patterns.
        """
        if not text:
            return 0

        char_count = len(text)

        # Detect if this looks like code
        if self._is_code(text):
            return max(1, int(char_count / self._code_ratio))
        return max(1, int(char_count / self._english_ratio))

    def _is_code(self, text: str) -> bool:
        """Heuristic: does this text look like code?"""
        code_indicators = 0
        # Check for common code patterns
        if re.search(r'[{}\[\]();]', text):
            code_indicators += 1
        if re.search(r'(def |class |import |from |function |const |let |var )', text):
            code_indicators += 1
        if re.search(r'(->|=>|::|&&|\|\|)', text):
            code_indicators += 1
        if text.count('\n') > 3 and text.count('    ') > 2:
            code_indicators += 1
        return code_indicators >= 2

    def estimate_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        """Estimate tokens for a list of chat messages.

        Each message has overhead (~4 tokens for role/formatting).
        """
        total = 0
        for msg in messages:
            total += 4  # role + formatting overhead
            total += self.estimate_tokens(msg.get("content", ""))
        return total

    def calibrate(self, text: str, actual_tokens: int) -> dict[str, float]:
        """Calibrate estimation ratios against actual token counts.

        Run this against Ollama's reported token count to improve accuracy.

        Args:
            text: The text that was tokenized.
            actual_tokens: Ollama's reported token count for this text.

        Returns:
            Updated ratios and the error percentage.
        """
        if actual_tokens <= 0 or not text:
            return {"english_ratio": self._english_ratio, "code_ratio": self._code_ratio, "error_pct": 0.0}

        char_count = len(text)
        actual_ratio = char_count / actual_tokens

        if self._is_code(text):
            self._code_ratio = (self._code_ratio + actual_ratio) / 2.0
        else:
            self._english_ratio = (self._english_ratio + actual_ratio) / 2.0

        estimated = self.estimate_tokens(text)
        error_pct = abs(estimated - actual_tokens) / actual_tokens * 100

        logger.info(
            "Calibration: actual=%d, estimated=%d, error=%.1f%%, "
            "english_ratio=%.2f, code_ratio=%.2f",
            actual_tokens, estimated, error_pct,
            self._english_ratio, self._code_ratio,
        )

        return {
            "english_ratio": self._english_ratio,
            "code_ratio": self._code_ratio,
            "error_pct": error_pct,
        }

    def build_context(
        self,
        system_prompt: str,
        conversation_history: list[dict[str, str]],
        grimoire_memories: list[dict[str, Any]],
        failure_patterns: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
        current_input: str,
    ) -> dict[str, Any]:
        """Assemble the full context and trim if necessary.

        Args:
            system_prompt: Shadow's identity prompt (never trimmed).
            conversation_history: Past conversation turns.
            grimoire_memories: Relevant memories from Grimoire.
            failure_patterns: Failure patterns for retry cycle.
            tool_results: Results from tool executions.
            current_input: The current user request (never trimmed).

        Returns:
            Dictionary with:
            - messages: list of chat messages ready for the model
            - token_breakdown: TokenBreakdown dict
            - trimmed: whether trimming occurred
            - trimmed_components: list of what was trimmed
        """
        # Compress before checking if we fit
        if self.compressor:
            compressed = self.compressor.compress_all({
                "grimoire_results": grimoire_memories,
                "conversation_history": conversation_history,
                "tool_results": tool_results,
                "system_prompt": system_prompt,
                "failure_patterns": failure_patterns,
            })
            grimoire_memories = compressed["grimoire_results"]
            conversation_history = compressed["conversation_history"]
            tool_results = compressed["tool_results"]
            system_prompt = compressed["system_prompt"]
            failure_patterns = compressed["failure_patterns"]
            report = self.compressor.get_compression_report()
            logger.info("Context compressed: %.0f%% reduction", report.get("overall_ratio", 0) * 100)

        # Calculate tokens for each component
        breakdown = TokenBreakdown()
        breakdown.system_prompt_tokens = self.estimate_tokens(system_prompt) + 4
        breakdown.input_tokens = self.estimate_tokens(current_input) + 4
        breakdown.history_tokens = self.estimate_messages_tokens(conversation_history)
        breakdown.memory_tokens = self._estimate_component_tokens(grimoire_memories)
        breakdown.failure_pattern_tokens = self._estimate_component_tokens(failure_patterns)
        breakdown.tool_result_tokens = self._estimate_component_tokens(tool_results)
        breakdown.total_tokens = (
            breakdown.system_prompt_tokens
            + breakdown.input_tokens
            + breakdown.history_tokens
            + breakdown.memory_tokens
            + breakdown.failure_pattern_tokens
            + breakdown.tool_result_tokens
        )

        trimmed = False
        trimmed_components: list[str] = []

        # Check if single input exceeds limit (edge case)
        minimum_tokens = breakdown.system_prompt_tokens + breakdown.input_tokens
        if minimum_tokens > self._effective_limit:
            logger.error(
                "Input alone exceeds context limit: %d > %d",
                minimum_tokens, self._effective_limit,
            )
            self._last_breakdown = breakdown
            self._last_trimmed = True
            self._last_trimmed_components = ["ERROR: input exceeds context limit"]
            return {
                "messages": [],
                "token_breakdown": breakdown.as_dict(),
                "trimmed": True,
                "trimmed_components": ["ERROR: input exceeds context limit"],
                "error": (
                    f"Input ({minimum_tokens} tokens) exceeds effective context "
                    f"limit ({self._effective_limit} tokens). Cannot process."
                ),
            }

        # Trim if over limit
        if breakdown.total_tokens > self._effective_limit:
            trim_result = self.trim_context(
                {
                    "system_prompt": system_prompt,
                    "conversation_history": list(conversation_history),
                    "grimoire_memories": list(grimoire_memories),
                    "failure_patterns": list(failure_patterns),
                    "tool_results": list(tool_results),
                    "current_input": current_input,
                },
                self._effective_limit,
            )
            conversation_history = trim_result["conversation_history"]
            grimoire_memories = trim_result["grimoire_memories"]
            failure_patterns = trim_result["failure_patterns"]
            tool_results = trim_result["tool_results"]
            trimmed = True
            trimmed_components = trim_result["trimmed_log"]

            # Recalculate after trimming
            breakdown.history_tokens = self.estimate_messages_tokens(conversation_history)
            breakdown.memory_tokens = self._estimate_component_tokens(grimoire_memories)
            breakdown.failure_pattern_tokens = self._estimate_component_tokens(failure_patterns)
            breakdown.tool_result_tokens = self._estimate_component_tokens(tool_results)
            breakdown.total_tokens = (
                breakdown.system_prompt_tokens
                + breakdown.input_tokens
                + breakdown.history_tokens
                + breakdown.memory_tokens
                + breakdown.failure_pattern_tokens
                + breakdown.tool_result_tokens
            )

        # Assemble messages
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)

        # Add memories as system context if present
        if grimoire_memories:
            memory_text = self._format_memories(grimoire_memories)
            if memory_text:
                messages.append({"role": "system", "content": f"Relevant memories:\n{memory_text}"})

        # Add failure patterns as system context if present
        if failure_patterns:
            pattern_text = self._format_failure_patterns(failure_patterns)
            if pattern_text:
                messages.append({"role": "system", "content": pattern_text})

        # Add tool results as context in the user message
        tool_context = self._format_tool_results(tool_results)
        user_message = current_input
        if tool_context:
            user_message = (
                f"{current_input}\n\n"
                f"--- Tool Results ---\n{tool_context}\n"
                f"Use the tool results above to inform your response."
            )
        messages.append({"role": "user", "content": user_message})

        # Store for reporting
        self._last_breakdown = breakdown
        self._last_trimmed = trimmed
        self._last_trimmed_components = trimmed_components

        if trimmed:
            logger.info(
                "Context trimmed: %d → %d tokens. Removed: %s",
                breakdown.total_tokens, self._effective_limit,
                ", ".join(trimmed_components),
            )

        return {
            "messages": messages,
            "token_breakdown": breakdown.as_dict(),
            "trimmed": trimmed,
            "trimmed_components": trimmed_components,
        }

    def trim_context(
        self,
        components: dict[str, Any],
        target_tokens: int,
    ) -> dict[str, Any]:
        """Trim context components to fit within target_tokens.

        Priority order (trim LAST priority first, preserve FIRST priority):
        1. PRESERVE: system_prompt (never trimmed)
        2. PRESERVE: current_input (never trimmed)
        3. PRESERVE: failure_patterns (trim only if very long)
        4. TRIM FIRST: tool_results (keep most recent, summarize older)
        5. TRIM SECOND: grimoire_memories (reduce count by relevance)
        6. TRIM THIRD: conversation_history (drop oldest, keep last 3 min)
        """
        trimmed_log: list[str] = []

        # Fixed costs — never trimmed
        fixed_tokens = (
            self.estimate_tokens(components["system_prompt"]) + 4
            + self.estimate_tokens(components["current_input"]) + 4
        )
        available = target_tokens - fixed_tokens

        # Mutable copies
        tool_results = list(components["tool_results"])
        memories = list(components["grimoire_memories"])
        history = list(components["conversation_history"])
        failure_patterns = list(components["failure_patterns"])

        # Calculate current variable usage
        def _variable_tokens() -> int:
            return (
                self.estimate_messages_tokens(history)
                + self._estimate_component_tokens(memories)
                + self._estimate_component_tokens(failure_patterns)
                + self._estimate_component_tokens(tool_results)
            )

        # --- TRIM FIRST: tool_results ---
        if _variable_tokens() > available and tool_results:
            original_count = len(tool_results)
            # Summarize older tool results (keep the most recent 2)
            if len(tool_results) > 2:
                for i in range(len(tool_results) - 2):
                    tool_results[i] = self._summarize_tool_result(tool_results[i])
                trimmed_log.append(f"tool_results: summarized {original_count - 2} older results")

            # If still over, drop all but most recent
            if _variable_tokens() > available and len(tool_results) > 1:
                dropped = len(tool_results) - 1
                tool_results = tool_results[-1:]
                trimmed_log.append(f"tool_results: dropped {dropped} results, kept 1")

            # If STILL over, summarize the last one too
            if _variable_tokens() > available and tool_results:
                tool_results = [self._summarize_tool_result(tool_results[0])]
                trimmed_log.append("tool_results: summarized last result")

            # Nuclear option: drop all tool results
            if _variable_tokens() > available:
                tool_results = []
                trimmed_log.append("tool_results: dropped all")

        # --- TRIM SECOND: grimoire_memories ---
        if _variable_tokens() > available and memories:
            original_count = len(memories)
            # Sort by relevance_score if available, keep highest
            memories = self._sort_memories_by_relevance(memories)

            # Reduce to 5
            if len(memories) > 5:
                memories = memories[:5]
                trimmed_log.append(f"memories: reduced {original_count} → 5")

            # Reduce to 3
            if _variable_tokens() > available and len(memories) > 3:
                memories = memories[:3]
                trimmed_log.append("memories: reduced to 3")

            # Reduce to 1
            if _variable_tokens() > available and len(memories) > 1:
                memories = memories[:1]
                trimmed_log.append("memories: reduced to 1")

            # Drop all
            if _variable_tokens() > available:
                memories = []
                trimmed_log.append("memories: dropped all")

        # --- TRIM THIRD: conversation_history ---
        if _variable_tokens() > available and history:
            original_count = len(history)
            min_keep = 6  # 3 exchanges (user+assistant pairs)

            # Drop oldest turns first, keep last 3 exchanges minimum
            while _variable_tokens() > available and len(history) > min_keep:
                removed = history.pop(0)
                topic = removed.get("content", "")[:50]
                trimmed_log.append(
                    f"history: dropped oldest turn ({removed.get('role', '?')}: {topic}...)"
                )

            # If still over and we have more than 0, summarize oldest remaining
            if _variable_tokens() > available and len(history) > 2:
                turns_to_summarize = len(history) - 2
                topic_summary = self._summarize_history_turns(history[:turns_to_summarize])
                history = [
                    {"role": "system", "content": topic_summary},
                    *history[-2:],
                ]
                trimmed_log.append(
                    f"history: summarized {turns_to_summarize} turns into summary"
                )

        # --- LAST RESORT: trim failure_patterns ---
        if _variable_tokens() > available and failure_patterns:
            original_count = len(failure_patterns)
            if len(failure_patterns) > 3:
                failure_patterns = failure_patterns[:3]
                trimmed_log.append(f"failure_patterns: reduced {original_count} → 3")

            if _variable_tokens() > available and len(failure_patterns) > 1:
                failure_patterns = failure_patterns[:1]
                trimmed_log.append("failure_patterns: reduced to 1")

            if _variable_tokens() > available:
                failure_patterns = []
                trimmed_log.append("failure_patterns: dropped all")

        return {
            "conversation_history": history,
            "grimoire_memories": memories,
            "failure_patterns": failure_patterns,
            "tool_results": tool_results,
            "trimmed_log": trimmed_log,
        }

    def get_usage_report(self) -> dict[str, Any]:
        """Return current context usage as percentage and breakdown.

        Returns a human-readable summary and raw numbers.
        """
        if self._last_breakdown is None:
            return {
                "summary": f"Context: 0/{self._max_tokens} tokens (0%). No data yet.",
                "breakdown": TokenBreakdown().as_dict(),
                "percentage": 0.0,
                "trimmed": False,
                "trimmed_components": [],
            }

        b = self._last_breakdown
        pct = (b.total_tokens / self._max_tokens) * 100 if self._max_tokens > 0 else 0

        summary = (
            f"Context: {b.total_tokens:,}/{self._max_tokens:,} tokens ({pct:.0f}%). "
            f"History: {b.history_tokens:,}, Memories: {b.memory_tokens:,}, "
            f"System: {b.system_prompt_tokens:,}, Input: {b.input_tokens:,}, "
            f"Tools: {b.tool_result_tokens:,}, Failures: {b.failure_pattern_tokens:,}, "
            f"Reserve: {self._reserve_tokens:,} free for response"
        )

        return {
            "summary": summary,
            "breakdown": b.as_dict(),
            "percentage": round(pct, 1),
            "trimmed": self._last_trimmed,
            "trimmed_components": self._last_trimmed_components,
        }

    def get_model_context_limit(self, model_name: str) -> int:
        """Look up context window size for a model.

        Checks config overrides first, then built-in defaults,
        then returns 128000 for unknown models.
        """
        # Exact match first
        if model_name in self._model_limits:
            return self._model_limits[model_name]

        # Case-insensitive match
        lower = model_name.lower()
        for name, limit in self._model_limits.items():
            if name.lower() == lower:
                return limit

        return _DEFAULT_CONTEXT_LIMIT

    def check_history_overflow(
        self,
        current_history: list[dict[str, str]],
        new_turn: dict[str, str],
        system_prompt_tokens: int = 0,
    ) -> bool:
        """Check if adding a new turn would push context over limit.

        Returns True if the turn would cause overflow.
        """
        current_tokens = (
            system_prompt_tokens
            + self.estimate_messages_tokens(current_history)
            + self.estimate_tokens(new_turn.get("content", "")) + 4
        )
        return current_tokens > self._effective_limit

    def update_model(self, model_name: str) -> None:
        """Update the context manager for a different model.

        Looks up the model's context limit and recalculates the
        effective limit.
        """
        self._max_tokens = self.get_model_context_limit(model_name)
        self._effective_limit = self._max_tokens - self._reserve_tokens
        logger.info(
            "Context manager updated for model '%s': max=%d, reserve=%d, effective=%d",
            model_name, self._max_tokens, self._reserve_tokens, self._effective_limit,
        )

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    def _estimate_component_tokens(self, items: list[dict[str, Any]]) -> int:
        """Estimate tokens for a list of context items."""
        if not items:
            return 0
        text = json.dumps(items, default=str)
        return self.estimate_tokens(text)

    def _summarize_tool_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Summarize a tool result to save tokens."""
        tool_name = result.get("tool_name", result.get("name", "unknown"))
        content = str(result.get("content", result.get("result", "")))
        preview = content[:100].replace("\n", " ")
        return {
            "tool_name": tool_name,
            "content": f"[Result from {tool_name}: {preview}... (truncated)]",
            "summarized": True,
        }

    def _sort_memories_by_relevance(self, memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort memories by relevance_score (highest first)."""
        def _score(m: dict[str, Any]) -> float:
            # Check common score field names
            for key in ("relevance_score", "score", "distance", "similarity"):
                if key in m:
                    val = m[key]
                    if isinstance(val, (int, float)):
                        # distance is inverse — lower = more relevant
                        if key == "distance":
                            return -val
                        return val
            return 0.0

        return sorted(memories, key=_score, reverse=True)

    def _summarize_history_turns(self, turns: list[dict[str, str]]) -> str:
        """Create a summary placeholder for removed history turns."""
        turn_count = len(turns)
        # Extract topic hints from the turns
        topics = set()
        for turn in turns:
            content = turn.get("content", "")
            # Take first few words as topic hint
            words = content.split()[:6]
            if words:
                topics.add(" ".join(words))

        topic_str = "; ".join(list(topics)[:3])
        return f"[Earlier conversation about: {topic_str} — {turn_count} turns removed]"

    def _format_memories(self, memories: list[dict[str, Any]]) -> str:
        """Format memories for inclusion in context."""
        lines = []
        for m in memories:
            if isinstance(m, str):
                lines.append(f"- {m}")
            elif isinstance(m, dict):
                content = m.get("content", m.get("document", m.get("text", str(m))))
                lines.append(f"- {content}")
        return "\n".join(lines)

    def _format_failure_patterns(self, patterns: list[dict[str, Any]]) -> str:
        """Format failure patterns for inclusion in context.

        Uses a clear label so the model knows to avoid these mistakes.
        Patterns from FailurePatternDB carry task_type, mistake, and
        correct_approach fields for structured formatting.
        """
        lines = ["PREVIOUS FAILURE PATTERNS (learn from these — do not repeat these mistakes):"]
        for p in patterns:
            if isinstance(p, str):
                lines.append(f"- {p}")
            elif isinstance(p, dict):
                # Prefer structured fields from FailurePatternDB
                task_type = p.get("task_type")
                mistake = p.get("mistake")
                correct_approach = p.get("correct_approach")
                if task_type and mistake and correct_approach:
                    lines.append(
                        f"- Task type: {task_type}. "
                        f"Mistake: {mistake}. "
                        f"Correct approach: {correct_approach}."
                    )
                else:
                    desc = p.get("description", p.get("pattern", str(p)))
                    lines.append(f"- {desc}")
        return "\n".join(lines)

    def _format_tool_results(self, results: list[dict[str, Any]]) -> str:
        """Format tool results for inclusion in context."""
        if not results:
            return ""
        lines = []
        for r in results:
            tool_name = r.get("tool_name", r.get("name", "unknown"))
            content = r.get("content", r.get("result", ""))
            if r.get("summarized"):
                lines.append(f"[Tool: {tool_name}] {content}")
            elif r.get("success", True):
                lines.append(f"[Tool: {tool_name}] Result: {content}")
            else:
                error = r.get("error", "unknown error")
                lines.append(f"[Tool: {tool_name}] Error: {error}")
        return "\n".join(lines)
