"""
Context Orchestrator — Unified Context Assembly Pipeline
==========================================================
The engine that dynamically assembles optimal context windows for every
LLM call by coordinating ContextManager, ContextCompressor, StagedRetrieval,
DynamicToolLoader, and FailurePatternDB.

Called by the orchestrator before every LLM call. Replaces manual context
assembly with a single pipeline that compresses, retrieves, loads tools,
and trims — all respecting the model's token budget.

Author: Patrick (with Claude Opus 4.6)
Project: Shadow
Module: Shadow / Context Orchestrator
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("shadow.context_orchestrator")


@dataclass
class ContextPackage:
    """Complete context package ready for an LLM call."""

    system_prompt: str = ""
    messages: list[dict] = field(default_factory=list)
    grimoire_context: str = ""
    failure_patterns: str = ""
    tool_schemas: list[dict] = field(default_factory=list)
    total_tokens: int = 0
    token_budget: int = 0
    token_breakdown: dict = field(default_factory=dict)
    trimmed: bool = False
    trimmed_details: list[str] = field(default_factory=list)
    compression_report: dict = field(default_factory=dict)
    retrieval_stats: dict = field(default_factory=dict)


# Default token budget when no ContextManager is available
_DEFAULT_TOKEN_BUDGET = 128000
_DEFAULT_RESERVE = 4096


class ContextOrchestrator:
    """Coordinates all context subsystems into a single assembly pipeline.

    Dependencies are all optional — graceful degradation if any are missing.
    Falls back to basic concatenation if nothing is available.
    """

    def __init__(
        self,
        context_manager=None,
        compressor=None,
        staged_retrieval=None,
        tool_loader=None,
        failure_pattern_db=None,
        grimoire=None,
    ) -> None:
        self._context_manager = context_manager
        self._compressor = compressor
        self._staged_retrieval = staged_retrieval
        self._tool_loader = tool_loader
        self._failure_pattern_db = failure_pattern_db
        self._grimoire = grimoire

        # Profiling — keep last N build stats
        self._build_history: deque[dict] = deque(maxlen=100)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def build_optimal_context(
        self,
        task: dict,
        system_prompt: str,
        conversation_history: list[dict],
        model: str = "gemma4-26b",
    ) -> ContextPackage:
        """Assemble the optimal context window for an LLM call.

        Pipeline:
        1. Get token budget from ContextManager
        2. Load failure patterns from FailurePatternDB
        3. Staged Grimoire retrieval (summaries -> full docs for top 3)
        4. Dynamic tool loading for the target module
        5. Compress conversation history
        6. Assemble all components
        7. Check token budget
        8. Trim if over budget (tool results first, then memories, then history)
        9. Return ContextPackage with full breakdown
        """
        start_time = time.time()
        pkg = ContextPackage(system_prompt=system_prompt)
        task_description = task.get("description", "")
        task_type = task.get("type", "unknown")
        target_module = task.get("module")

        # --- Step 1: Get token budget ---
        try:
            pkg.token_budget = self._get_token_budget(model)
        except Exception as e:
            logger.warning("Failed to get token budget: %s", e)
            pkg.token_budget = _DEFAULT_TOKEN_BUDGET - _DEFAULT_RESERVE

        # --- Step 2: Load failure patterns ---
        failure_pattern_text = ""
        try:
            failure_pattern_text = self._load_failure_patterns(task_description)
        except Exception as e:
            logger.warning("Failed to load failure patterns: %s", e)

        pkg.failure_patterns = failure_pattern_text

        # --- Step 3: Staged Grimoire retrieval ---
        grimoire_text = ""
        retrieval_stats = {}
        try:
            grimoire_text, retrieval_stats = self._staged_grimoire_retrieval(
                task_description
            )
        except Exception as e:
            logger.warning("Staged Grimoire retrieval failed: %s", e)

        pkg.grimoire_context = grimoire_text
        pkg.retrieval_stats = retrieval_stats

        # --- Step 4: Dynamic tool loading ---
        tool_schemas = []
        try:
            tool_schemas = self._load_tools(target_module, task)
        except Exception as e:
            logger.warning("Dynamic tool loading failed: %s", e)

        pkg.tool_schemas = tool_schemas

        # --- Step 5: Compress conversation history ---
        compressed_history = list(conversation_history) if conversation_history else []
        compression_report = {}
        try:
            compressed_history, compression_report = self._compress_history(
                conversation_history or []
            )
        except Exception as e:
            logger.warning("Conversation compression failed: %s", e)

        pkg.messages = compressed_history
        pkg.compression_report = compression_report

        # --- Step 6: Assemble and calculate token counts ---
        breakdown = self._calculate_token_breakdown(
            system_prompt=system_prompt,
            messages=compressed_history,
            grimoire_context=grimoire_text,
            failure_patterns=failure_pattern_text,
            tool_schemas=tool_schemas,
        )
        pkg.token_breakdown = breakdown
        pkg.total_tokens = breakdown.get("total", 0)

        # --- Step 7-8: Check budget and trim if needed ---
        if pkg.total_tokens > pkg.token_budget:
            try:
                pkg = self._trim_to_budget(pkg)
            except Exception as e:
                logger.warning("Trimming failed: %s", e)

        # --- Step 9: Record stats and return ---
        elapsed = time.time() - start_time
        self._record_build_stats(pkg, elapsed)

        logger.info(
            "ContextOrchestrator: %d/%d tokens (%.0f%%) in %.3fs. Trimmed: %s",
            pkg.total_tokens,
            pkg.token_budget,
            (pkg.total_tokens / pkg.token_budget * 100) if pkg.token_budget > 0 else 0,
            elapsed,
            pkg.trimmed,
        )

        return pkg

    # ------------------------------------------------------------------
    # Minimal context (fast/simple tasks)
    # ------------------------------------------------------------------

    def build_minimal_context(
        self,
        task: dict,
        system_prompt: str,
        model: str = "gemma4-26b",
    ) -> ContextPackage:
        """Lightweight context for simple/fast tasks.

        No Grimoire search, no failure patterns, core tools only.
        Just: system_prompt + task + core tools.
        """
        pkg = ContextPackage(system_prompt=system_prompt)

        try:
            pkg.token_budget = self._get_token_budget(model)
        except Exception:
            pkg.token_budget = _DEFAULT_TOKEN_BUDGET - _DEFAULT_RESERVE

        # Core tools only
        try:
            if self._tool_loader is not None:
                pkg.tool_schemas = self._tool_loader.get_core_tools()
        except Exception as e:
            logger.warning("Failed to load core tools: %s", e)

        # Calculate tokens
        breakdown = self._calculate_token_breakdown(
            system_prompt=system_prompt,
            messages=[],
            grimoire_context="",
            failure_patterns="",
            tool_schemas=pkg.tool_schemas,
        )
        pkg.token_breakdown = breakdown
        pkg.total_tokens = breakdown.get("total", 0)

        return pkg

    # ------------------------------------------------------------------
    # Profiling / stats
    # ------------------------------------------------------------------

    def get_context_profile(self) -> dict:
        """Stats from the last N builds for Growth Engine and Harbinger."""
        if not self._build_history:
            return {
                "avg_tokens_used": 0,
                "avg_tokens_budget": 0,
                "avg_usage_percent": 0.0,
                "avg_grimoire_tokens": 0,
                "avg_tool_tokens": 0,
                "avg_history_tokens": 0,
                "avg_compression_ratio": 0.0,
                "times_trimmed": 0,
                "times_over_budget": 0,
                "most_common_trim_target": None,
                "total_builds": 0,
            }

        builds = list(self._build_history)
        n = len(builds)

        avg_used = sum(b.get("total_tokens", 0) for b in builds) / n
        avg_budget = sum(b.get("token_budget", 0) for b in builds) / n
        avg_pct = sum(b.get("usage_percent", 0) for b in builds) / n
        avg_grimoire = sum(b.get("grimoire_tokens", 0) for b in builds) / n
        avg_tool = sum(b.get("tool_tokens", 0) for b in builds) / n
        avg_history = sum(b.get("history_tokens", 0) for b in builds) / n
        avg_compression = sum(b.get("compression_ratio", 0) for b in builds) / n
        times_trimmed = sum(1 for b in builds if b.get("trimmed", False))

        # Most common trim target
        trim_targets: dict[str, int] = {}
        for b in builds:
            for target in b.get("trimmed_details", []):
                trim_targets[target] = trim_targets.get(target, 0) + 1

        most_common = max(trim_targets, key=trim_targets.get) if trim_targets else None

        return {
            "avg_tokens_used": round(avg_used),
            "avg_tokens_budget": round(avg_budget),
            "avg_usage_percent": round(avg_pct, 1),
            "avg_grimoire_tokens": round(avg_grimoire),
            "avg_tool_tokens": round(avg_tool),
            "avg_history_tokens": round(avg_history),
            "avg_compression_ratio": round(avg_compression, 3),
            "times_trimmed": times_trimmed,
            "times_over_budget": times_trimmed,
            "most_common_trim_target": most_common,
            "total_builds": n,
        }

    def estimate_context_for_task(
        self, task: dict, model: str = "gemma4-26b"
    ) -> dict:
        """Quick estimate WITHOUT actually building the context.

        Returns estimated_total_tokens, estimated_usage_percent, will_need_trimming.
        """
        try:
            budget = self._get_token_budget(model)
        except Exception:
            budget = _DEFAULT_TOKEN_BUDGET - _DEFAULT_RESERVE

        # Rough estimates per component
        system_prompt_est = 500  # typical identity prompt
        history_est = 1500      # ~5 turns compressed
        grimoire_est = 2000     # staged retrieval typical
        failure_est = 300       # 2-3 patterns
        tool_est = 1000         # module tools + core

        total_est = system_prompt_est + history_est + grimoire_est + failure_est + tool_est
        usage_pct = (total_est / budget * 100) if budget > 0 else 0

        return {
            "estimated_total_tokens": total_est,
            "estimated_usage_percent": round(usage_pct, 1),
            "will_need_trimming": total_est > budget,
            "token_budget": budget,
        }

    # ------------------------------------------------------------------
    # Internal pipeline steps
    # ------------------------------------------------------------------

    def _get_token_budget(self, model: str) -> int:
        """Get the effective token budget for a model."""
        if self._context_manager is not None:
            self._context_manager.update_model(model)
            return self._context_manager.effective_limit
        return _DEFAULT_TOKEN_BUDGET - _DEFAULT_RESERVE

    def _load_failure_patterns(self, task_description: str) -> str:
        """Search FailurePatternDB and format patterns for context."""
        if self._failure_pattern_db is None or self._grimoire is None:
            return ""

        # FailurePatternDB.search_failure_patterns is async, but we need sync here.
        # The orchestrator integration will pass pre-fetched patterns.
        # For direct use, format_patterns_for_context works on already-fetched patterns.
        # We store the DB reference so the orchestrator can call it async and pass results.
        return ""

    def _load_failure_patterns_from_results(
        self, patterns: list[dict]
    ) -> str:
        """Format pre-fetched failure patterns for context inclusion."""
        if not patterns:
            return ""

        if self._failure_pattern_db is not None:
            formatted = self._failure_pattern_db.format_patterns_for_context(patterns)
        else:
            formatted = patterns

        lines = [
            "PREVIOUS FAILURE PATTERNS (learn from these — do not repeat these mistakes):"
        ]
        for p in formatted:
            if isinstance(p, dict):
                desc = p.get("description", str(p))
                lines.append(f"- {desc}")
            else:
                lines.append(f"- {p}")

        return "\n".join(lines)

    def set_failure_patterns(self, patterns: list[dict]) -> None:
        """Set pre-fetched failure patterns (called by orchestrator after async fetch)."""
        self._prefetched_failure_patterns = patterns

    def _staged_grimoire_retrieval(self, query: str) -> tuple[str, dict]:
        """Use StagedRetrieval for two-stage search."""
        if self._staged_retrieval is None:
            return "", {}

        if not query or not query.strip():
            return "", {}

        results = self._staged_retrieval.search(
            query=query,
            n_results=10,
            auto_select=3,
        )

        if not results:
            return "", {}

        # Separate stats from content results
        stats = {}
        content_results = []
        for r in results:
            if isinstance(r, dict) and "_stats" in r:
                stats = r["_stats"]
            else:
                content_results.append(r)

        # Format results into context text
        lines = []
        for r in content_results:
            content = r.get("content", "")
            result_type = r.get("type", "unknown")
            if content:
                prefix = "[Full]" if result_type == "full" else "[Summary]"
                lines.append(f"{prefix} {content}")

        grimoire_text = "\n\n".join(lines) if lines else ""
        retrieval_stats = self._staged_retrieval.get_retrieval_stats()
        retrieval_stats.update(stats)

        return grimoire_text, retrieval_stats

    def _load_tools(
        self, module_name: str | None, task: dict
    ) -> list[dict]:
        """Load tools via DynamicToolLoader."""
        if self._tool_loader is None:
            return []

        return self._tool_loader.get_tools_for_task(
            module_name=module_name,
            task=task,
        )

    def _compress_history(
        self, history: list[dict]
    ) -> tuple[list[dict], dict]:
        """Compress conversation history via ContextCompressor."""
        if not history:
            return [], {}

        if self._compressor is None:
            return list(history), {}

        compressed = self._compressor.compress_conversation_history(
            history,
            keep_recent=3,
        )

        report = self._compressor.get_compression_report()
        return compressed, report

    def _estimate_tokens(self, text: str) -> int:
        """Estimate tokens for text using ContextManager or fallback heuristic."""
        if not text:
            return 0
        if self._context_manager is not None:
            return self._context_manager.estimate_tokens(text)
        # Fallback: ~4 chars per token
        return max(1, len(text) // 4)

    def _calculate_token_breakdown(
        self,
        system_prompt: str,
        messages: list[dict],
        grimoire_context: str,
        failure_patterns: str,
        tool_schemas: list[dict],
    ) -> dict:
        """Calculate token counts per component."""
        system_tokens = self._estimate_tokens(system_prompt)

        history_tokens = 0
        for msg in messages:
            history_tokens += 4  # role/formatting overhead
            history_tokens += self._estimate_tokens(msg.get("content", ""))

        grimoire_tokens = self._estimate_tokens(grimoire_context)
        failure_tokens = self._estimate_tokens(failure_patterns)

        tool_tokens = 0
        if tool_schemas:
            tool_text = json.dumps(tool_schemas, default=str)
            tool_tokens = self._estimate_tokens(tool_text)

        total = system_tokens + history_tokens + grimoire_tokens + failure_tokens + tool_tokens

        return {
            "system_prompt": system_tokens,
            "history": history_tokens,
            "grimoire": grimoire_tokens,
            "failure_patterns": failure_tokens,
            "tools": tool_tokens,
            "total": total,
        }

    def _trim_to_budget(self, pkg: ContextPackage) -> ContextPackage:
        """Trim context components to fit within token budget.

        Priority order (trim first → last):
        1. Tool schemas (reduce count)
        2. Grimoire context (truncate)
        3. Conversation history (drop oldest)
        NEVER trim: system_prompt
        """
        budget = pkg.token_budget
        trimmed_details = []

        # Calculate what we need to cut
        system_tokens = self._estimate_tokens(pkg.system_prompt)
        available = budget - system_tokens

        # --- Trim tools first ---
        tool_tokens = pkg.token_breakdown.get("tools", 0)
        grimoire_tokens = pkg.token_breakdown.get("grimoire", 0)
        history_tokens = pkg.token_breakdown.get("history", 0)
        failure_tokens = pkg.token_breakdown.get("failure_patterns", 0)

        current_variable = tool_tokens + grimoire_tokens + history_tokens + failure_tokens

        if current_variable > available and pkg.tool_schemas:
            # Keep only half the tools
            original_count = len(pkg.tool_schemas)
            half = max(1, original_count // 2)
            pkg.tool_schemas = pkg.tool_schemas[:half]
            tool_text = json.dumps(pkg.tool_schemas, default=str)
            tool_tokens = self._estimate_tokens(tool_text)
            trimmed_details.append(f"tools: reduced {original_count} -> {half}")
            current_variable = tool_tokens + grimoire_tokens + history_tokens + failure_tokens

        # --- Trim grimoire context ---
        if current_variable > available and pkg.grimoire_context:
            # Truncate to fit
            max_grimoire_chars = (available - history_tokens - failure_tokens - tool_tokens) * 4
            if max_grimoire_chars > 0:
                original_len = len(pkg.grimoire_context)
                pkg.grimoire_context = pkg.grimoire_context[:int(max_grimoire_chars)]
                grimoire_tokens = self._estimate_tokens(pkg.grimoire_context)
                trimmed_details.append(
                    f"grimoire: truncated {original_len} -> {len(pkg.grimoire_context)} chars"
                )
            else:
                pkg.grimoire_context = ""
                grimoire_tokens = 0
                trimmed_details.append("grimoire: dropped all")
            current_variable = tool_tokens + grimoire_tokens + history_tokens + failure_tokens

        # --- Trim history ---
        if current_variable > available and pkg.messages:
            original_count = len(pkg.messages)
            # Keep last 3, drop oldest
            while current_variable > available and len(pkg.messages) > 3:
                pkg.messages.pop(0)
                history_tokens = sum(
                    4 + self._estimate_tokens(m.get("content", ""))
                    for m in pkg.messages
                )
                current_variable = tool_tokens + grimoire_tokens + history_tokens + failure_tokens

            if len(pkg.messages) < original_count:
                trimmed_details.append(
                    f"history: reduced {original_count} -> {len(pkg.messages)} messages"
                )

        # --- Last resort: trim failure patterns ---
        if current_variable > available and pkg.failure_patterns:
            pkg.failure_patterns = ""
            failure_tokens = 0
            trimmed_details.append("failure_patterns: dropped all")

        # Recalculate breakdown
        pkg.token_breakdown = self._calculate_token_breakdown(
            system_prompt=pkg.system_prompt,
            messages=pkg.messages,
            grimoire_context=pkg.grimoire_context,
            failure_patterns=pkg.failure_patterns,
            tool_schemas=pkg.tool_schemas,
        )
        pkg.total_tokens = pkg.token_breakdown.get("total", 0)
        pkg.trimmed = bool(trimmed_details)
        pkg.trimmed_details = trimmed_details

        return pkg

    def _record_build_stats(self, pkg: ContextPackage, elapsed: float) -> None:
        """Record build stats for profiling."""
        compression_ratio = 0.0
        if pkg.compression_report:
            compression_ratio = pkg.compression_report.get("overall_ratio", 0.0)

        self._build_history.append({
            "total_tokens": pkg.total_tokens,
            "token_budget": pkg.token_budget,
            "usage_percent": (
                (pkg.total_tokens / pkg.token_budget * 100)
                if pkg.token_budget > 0
                else 0
            ),
            "grimoire_tokens": pkg.token_breakdown.get("grimoire", 0),
            "tool_tokens": pkg.token_breakdown.get("tools", 0),
            "history_tokens": pkg.token_breakdown.get("history", 0),
            "compression_ratio": compression_ratio,
            "trimmed": pkg.trimmed,
            "trimmed_details": pkg.trimmed_details,
            "elapsed_seconds": elapsed,
        })
