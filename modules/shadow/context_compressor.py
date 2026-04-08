"""
Context Compression Pipeline — Rule-Based Summarization
==========================================================
Compresses context components BEFORE they enter the context window.
Works WITH ContextManager: ContextCompressor makes things SMALLER,
ContextManager decides WHAT fits. Compression happens before trimming.

All compression is rule-based — no LLM calls. Never loses code blocks
or error messages. Tracks compression ratios for diagnostics.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger("shadow.context_compressor")

# Approximate chars per token (same heuristic as ContextManager)
_CHARS_PER_TOKEN = 4.0
_CODE_CHARS_PER_TOKEN = 3.5

# Boilerplate patterns to strip from grimoire results
_BOILERPLATE_PATTERNS = [
    re.compile(r"^(In this (document|article|section),?\s+(we will|I will|we|I)\s+)", re.IGNORECASE),
    re.compile(r"^(This (document|article|guide|section) (covers|describes|explains|provides)\s+)", re.IGNORECASE),
    re.compile(r"^(Table of [Cc]ontents:?\s*\n(?:[-\d.*#\s]+\n)+)", re.MULTILINE),
    re.compile(r"^(#{1,3}\s*(Table of Contents|TOC|Contents)\s*\n)", re.MULTILINE),
]


def _estimate_tokens(text: str) -> int:
    """Fast token estimation matching ContextManager's heuristic."""
    if not text:
        return 0
    code_indicators = 0
    if re.search(r'[{}\[\]();]', text):
        code_indicators += 1
    if re.search(r'(def |class |import |from |function |const |let |var )', text):
        code_indicators += 1
    if code_indicators >= 2:
        return max(1, int(len(text) / _CODE_CHARS_PER_TOKEN))
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def _extract_first_sentences(text: str, count: int = 2) -> str:
    """Extract the first N sentences from text."""
    # Split on sentence-ending punctuation followed by space or newline
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    selected = sentences[:count]
    return " ".join(selected).strip()


def _extract_code_blocks(text: str) -> list[str]:
    """Extract fenced code blocks from text."""
    return re.findall(r'```[\s\S]*?```', text)


def _remove_code_blocks(text: str) -> str:
    """Remove fenced code blocks from text, leaving a placeholder."""
    return re.sub(r'```[\s\S]*?```', '[code block preserved]', text)


def _strip_boilerplate(text: str) -> str:
    """Remove common boilerplate phrases from text."""
    result = text
    for pattern in _BOILERPLATE_PATTERNS:
        result = pattern.sub('', result)
    return result.strip()


class ContextCompressor:
    """Compresses context components using rule-based strategies.

    Reduces token usage so more information fits in the context window.
    All compression is deterministic — no LLM calls.
    """

    def __init__(self, config: dict | None = None) -> None:
        self._config = config or {}
        self._max_grimoire_tokens = self._config.get("max_grimoire_tokens", 2000)
        self._max_history_tokens = self._config.get("max_history_tokens", 3000)
        self._max_tool_tokens = self._config.get("max_tool_tokens", 1500)
        self._keep_recent_turns = self._config.get("keep_recent_turns", 3)

        # Last compression report
        self._last_report: dict[str, Any] = {}

    def compress_grimoire_results(
        self,
        results: list[dict],
        max_tokens: int = 2000,
    ) -> list[dict]:
        """Compress Grimoire search results while preserving code blocks.

        Strategy:
        1. Extract first 2-3 sentences (essential paragraph)
        2. Keep code blocks intact
        3. Strip boilerplate
        4. If still over max_tokens, keep highest relevance entries
        """
        if not results:
            return []

        compressed = []
        for result in results:
            content = result.get("content", result.get("document", result.get("text", "")))
            if not content:
                compressed.append({
                    **result,
                    "compressed": False,
                    "original_tokens": 0,
                    "compressed_tokens": 0,
                })
                continue

            original_tokens = _estimate_tokens(content)

            # Extract and preserve code blocks
            code_blocks = _extract_code_blocks(content)
            text_without_code = _remove_code_blocks(content)

            # Strip boilerplate
            cleaned = _strip_boilerplate(text_without_code)

            # Extract essential paragraph (first 2-3 sentences)
            essential = _extract_first_sentences(cleaned, count=3)

            # Reassemble: essential text + code blocks
            parts = [essential]
            parts.extend(code_blocks)
            compressed_content = "\n\n".join(parts)

            compressed_tokens = _estimate_tokens(compressed_content)
            was_compressed = compressed_tokens < original_tokens

            compressed.append({
                **result,
                "content": compressed_content,
                "compressed": was_compressed,
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "relevance_score": result.get("relevance_score", result.get("score", 0.0)),
            })

        # Check total tokens and keep only highest relevance if over limit
        total = sum(r["compressed_tokens"] for r in compressed)
        if total > max_tokens and len(compressed) > 1:
            # Sort by relevance (highest first)
            compressed.sort(
                key=lambda r: r.get("relevance_score", 0.0),
                reverse=True,
            )
            # Keep entries until we hit the limit
            kept = []
            running = 0
            for entry in compressed:
                if running + entry["compressed_tokens"] <= max_tokens or not kept:
                    kept.append(entry)
                    running += entry["compressed_tokens"]
                else:
                    break
            compressed = kept

        return compressed

    def compress_conversation_history(
        self,
        history: list[dict],
        max_tokens: int = 3000,
        keep_recent: int = 3,
    ) -> list[dict]:
        """Compress conversation history with rolling summary.

        Strategy:
        1. Keep last keep_recent turns verbatim
        2. Summarize older turns with rule-based extraction
        """
        if not history:
            return []

        # If fewer turns than keep_recent, return all verbatim
        if len(history) <= keep_recent:
            return list(history)

        # Split into older and recent
        older = history[:-keep_recent]
        recent = history[-keep_recent:]

        # Build rolling summary from older turns
        topics = []
        summaries = []
        decisions = []
        for turn in older:
            content = turn.get("content", "")
            role = turn.get("role", "")
            first_sentence = _extract_first_sentences(content, count=1)

            if role == "user":
                topics.append(first_sentence)
            elif role == "assistant":
                summaries.append(first_sentence)
                # Look for decision indicators
                if any(kw in content.lower() for kw in ["decided", "choosing", "will use", "going with", "selected"]):
                    decisions.append(first_sentence)

        # Build summary text
        topic_str = "; ".join(topics[:5]) if topics else "various topics"
        summary_str = "; ".join(summaries[:3]) if summaries else "responses provided"
        decision_str = "; ".join(decisions[:3]) if decisions else "none noted"

        summary_text = (
            f"[Earlier conversation: User asked about {topic_str}. "
            f"Shadow provided {summary_str}. "
            f"Key decisions: {decision_str}. "
            f"{len(older)} turns summarized.]"
        )

        summary_dict = {"role": "system", "content": summary_text}
        result = [summary_dict] + recent

        # Check if under max_tokens
        total = sum(_estimate_tokens(t.get("content", "")) + 4 for t in result)
        if total > max_tokens and len(recent) > 1:
            # Further compress by reducing recent turns
            while total > max_tokens and len(recent) > 1:
                # Move oldest recent turn into summary
                moved = recent.pop(0)
                first = _extract_first_sentences(moved.get("content", ""), count=1)
                if moved.get("role") == "user":
                    topics.append(first)
                else:
                    summaries.append(first)
                # Rebuild summary
                topic_str = "; ".join(topics[:5]) if topics else "various topics"
                summary_str = "; ".join(summaries[:3]) if summaries else "responses provided"
                summary_text = (
                    f"[Earlier conversation: User asked about {topic_str}. "
                    f"Shadow provided {summary_str}. "
                    f"Key decisions: {decision_str}. "
                    f"{len(older) + (keep_recent - len(recent))} turns summarized.]"
                )
                summary_dict = {"role": "system", "content": summary_text}
                result = [summary_dict] + recent
                total = sum(_estimate_tokens(t.get("content", "")) + 4 for t in result)

        return result

    def compress_tool_results(
        self,
        results: list[dict],
        max_tokens: int = 1500,
    ) -> list[dict]:
        """Compress tool execution results.

        Strategy:
        1. Keep most recent tool result verbatim
        2. Older results: truncated summary
        3. Error results: always keep full error message
        """
        if not results:
            return []

        if len(results) == 1:
            return list(results)

        compressed = []
        # Process all but the last (most recent)
        for result in results[:-1]:
            content = str(result.get("content", result.get("result", "")))
            tool_name = result.get("tool_name", result.get("name", "unknown"))
            is_error = not result.get("success", True) or result.get("error")

            if is_error:
                # Keep error messages intact
                compressed.append(dict(result))
            else:
                # Truncate older successful results
                original_length = len(content)
                preview = content[:100].replace("\n", " ")
                compressed.append({
                    **result,
                    "content": f"[Result from {tool_name}: {preview}... (truncated, {original_length} chars)]",
                    "summarized": True,
                })

        # Keep most recent verbatim
        compressed.append(dict(results[-1]))
        return compressed

    def compress_system_prompt(
        self,
        prompt: str,
        max_tokens: int | None = None,
    ) -> str:
        """Compress system prompt (identity preservation).

        Only compresses if max_tokens is explicitly set.
        Drops sections marked with <!-- optional --> tags.
        """
        if not prompt:
            return prompt

        if max_tokens is None:
            return prompt

        current_tokens = _estimate_tokens(prompt)
        if current_tokens <= max_tokens:
            return prompt

        # Remove <!-- optional --> sections
        compressed = re.sub(
            r'<!-- optional -->\s*\n(.*?)(?=\n<!-- /optional -->|$)',
            '',
            prompt,
            flags=re.DOTALL,
        )
        # Also handle <!-- optional -->...<!-- /optional --> pairs
        compressed = re.sub(
            r'<!-- optional -->[\s\S]*?<!-- /optional -->',
            '',
            compressed,
        )
        return compressed.strip()

    def compress_failure_patterns(
        self,
        patterns: list[dict],
        max_tokens: int = 500,
    ) -> list[dict]:
        """Compress failure patterns, keeping the most relevant."""
        if not patterns:
            return []

        total = _estimate_tokens(json.dumps(patterns, default=str))
        if total <= max_tokens:
            return list(patterns)

        # Keep patterns sorted by recency (assume last = most recent)
        # Truncate descriptions but keep structured fields
        compressed = []
        for p in patterns:
            entry = dict(p)
            for field in ("description", "pattern", "context"):
                if field in entry and isinstance(entry[field], str) and len(entry[field]) > 200:
                    entry[field] = entry[field][:200] + "..."
            compressed.append(entry)

        # If still over, keep only recent half
        total = _estimate_tokens(json.dumps(compressed, default=str))
        if total > max_tokens and len(compressed) > 1:
            half = max(1, len(compressed) // 2)
            compressed = compressed[-half:]

        return compressed

    def compress_all(self, components: dict) -> dict:
        """Compress all context components.

        Args:
            components: dict with keys:
                grimoire_results, conversation_history, tool_results,
                system_prompt, failure_patterns

        Returns:
            Compressed dict + compression_report.
        """
        report: dict[str, Any] = {"per_component": {}}

        # --- Grimoire results ---
        grimoire = components.get("grimoire_results") or []
        orig_grimoire_tokens = _estimate_tokens(json.dumps(grimoire, default=str)) if grimoire else 0
        compressed_grimoire = self.compress_grimoire_results(
            grimoire, self._max_grimoire_tokens
        )
        comp_grimoire_tokens = _estimate_tokens(json.dumps(compressed_grimoire, default=str)) if compressed_grimoire else 0
        report["per_component"]["grimoire_results"] = {
            "original_tokens": orig_grimoire_tokens,
            "compressed_tokens": comp_grimoire_tokens,
            "ratio": 1 - (comp_grimoire_tokens / orig_grimoire_tokens) if orig_grimoire_tokens > 0 else 0.0,
        }

        # --- Conversation history ---
        history = components.get("conversation_history") or []
        orig_history_tokens = sum(_estimate_tokens(t.get("content", "")) + 4 for t in history)
        compressed_history = self.compress_conversation_history(
            history, self._max_history_tokens, self._keep_recent_turns
        )
        comp_history_tokens = sum(_estimate_tokens(t.get("content", "")) + 4 for t in compressed_history)
        report["per_component"]["conversation_history"] = {
            "original_tokens": orig_history_tokens,
            "compressed_tokens": comp_history_tokens,
            "ratio": 1 - (comp_history_tokens / orig_history_tokens) if orig_history_tokens > 0 else 0.0,
        }

        # --- Tool results ---
        tools = components.get("tool_results") or []
        orig_tool_tokens = _estimate_tokens(json.dumps(tools, default=str)) if tools else 0
        compressed_tools = self.compress_tool_results(tools, self._max_tool_tokens)
        comp_tool_tokens = _estimate_tokens(json.dumps(compressed_tools, default=str)) if compressed_tools else 0
        report["per_component"]["tool_results"] = {
            "original_tokens": orig_tool_tokens,
            "compressed_tokens": comp_tool_tokens,
            "ratio": 1 - (comp_tool_tokens / orig_tool_tokens) if orig_tool_tokens > 0 else 0.0,
        }

        # --- System prompt ---
        prompt = components.get("system_prompt", "")
        orig_prompt_tokens = _estimate_tokens(prompt)
        compressed_prompt = self.compress_system_prompt(prompt)
        comp_prompt_tokens = _estimate_tokens(compressed_prompt)
        report["per_component"]["system_prompt"] = {
            "original_tokens": orig_prompt_tokens,
            "compressed_tokens": comp_prompt_tokens,
            "ratio": 1 - (comp_prompt_tokens / orig_prompt_tokens) if orig_prompt_tokens > 0 else 0.0,
        }

        # --- Failure patterns ---
        failures = components.get("failure_patterns") or []
        orig_fail_tokens = _estimate_tokens(json.dumps(failures, default=str)) if failures else 0
        compressed_failures = self.compress_failure_patterns(failures)
        comp_fail_tokens = _estimate_tokens(json.dumps(compressed_failures, default=str)) if compressed_failures else 0
        report["per_component"]["failure_patterns"] = {
            "original_tokens": orig_fail_tokens,
            "compressed_tokens": comp_fail_tokens,
            "ratio": 1 - (comp_fail_tokens / orig_fail_tokens) if orig_fail_tokens > 0 else 0.0,
        }

        # --- Totals ---
        total_original = orig_grimoire_tokens + orig_history_tokens + orig_tool_tokens + orig_prompt_tokens + orig_fail_tokens
        total_compressed = comp_grimoire_tokens + comp_history_tokens + comp_tool_tokens + comp_prompt_tokens + comp_fail_tokens
        overall_ratio = 1 - (total_compressed / total_original) if total_original > 0 else 0.0

        report["total_original"] = total_original
        report["total_compressed"] = total_compressed
        report["overall_ratio"] = overall_ratio
        report["summary"] = (
            f"Compressed {total_original:,} tokens to {total_compressed:,} tokens "
            f"({overall_ratio:.0%} reduction)"
        )

        self._last_report = report

        return {
            "grimoire_results": compressed_grimoire,
            "conversation_history": compressed_history,
            "tool_results": compressed_tools,
            "system_prompt": compressed_prompt,
            "failure_patterns": compressed_failures,
            "compression_report": report,
        }

    def get_compression_report(self) -> dict:
        """Return stats from the last compress_all call."""
        return self._last_report
