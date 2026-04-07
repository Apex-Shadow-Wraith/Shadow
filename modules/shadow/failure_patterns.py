"""
Failure Pattern Database — Shadow Learns From Mistakes
========================================================
Stores, retrieves, and analyzes failure patterns so Shadow never
repeats the same mistake twice. Integrates with Grimoire for
persistent storage and ChromaDB for semantic search.

A failure pattern captures:
- What kind of task failed
- What approach was wrong
- What actually worked
- Where the learning came from (retry engine vs Apex)

The orchestrator queries this database at Step 3 (Load Context)
before every non-trivial task. Matching patterns become HIGH
priority context that survives trimming.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger("shadow.failure_patterns")


class FailurePatternDB:
    """Manages failure pattern storage, retrieval, deduplication, and analytics.

    Works through Grimoire (memory_store / memory_search) to persist patterns
    in both SQLite and ChromaDB. Does NOT hold its own database — everything
    goes through the existing Grimoire infrastructure.

    Usage:
        db = FailurePatternDB()
        # Store a pattern after a failed attempt
        mid = await db.store_failure_pattern(
            grimoire=grimoire_module,
            task="calculate compound interest",
            task_type="math",
            mistake="Used simple interest formula",
            correct_approach="Use A = P(1 + r/n)^(nt) for compound interest",
            source="retry_engine",
            trust_level=0.5,
        )
        # Search for relevant patterns before a new task
        patterns = await db.search_failure_patterns(
            grimoire=grimoire_module,
            query="interest rate calculation",
            limit=3,
        )
    """

    # Category used to tag all failure patterns in Grimoire
    CATEGORY = "failure_pattern"

    # Similarity threshold for deduplication (0.0-1.0, higher = more similar)
    DEDUP_THRESHOLD = 0.9

    async def store_failure_pattern(
        self,
        grimoire: Any,
        task: str,
        task_type: str,
        mistake: str,
        correct_approach: str,
        source: str = "retry_engine",
        trust_level: float = 0.5,
    ) -> str:
        """Store a failure pattern in Grimoire.

        Args:
            grimoire: The GrimoireModule instance (must be online).
            task: The original task text that failed.
            task_type: Classification (code, math, research, ethics, etc.).
            mistake: What approach was wrong.
            correct_approach: What actually worked.
            source: Where the learning came from (retry_engine, apex_learning).
            trust_level: 0.7 for Apex discoveries, 0.5 for self-discovery.

        Returns:
            Memory ID of the stored pattern, or existing ID if deduplicated.
        """
        # Build the content string for embedding and storage
        content = (
            f"FAILURE PATTERN [{task_type}]: "
            f"Task: {task}. "
            f"Mistake: {mistake}. "
            f"Correct approach: {correct_approach}."
        )

        # Check for duplicates before storing
        existing = await self._find_duplicate(grimoire, content)
        if existing is not None:
            # Update the existing pattern instead of creating a duplicate
            return await self._update_existing(
                grimoire, existing, task, task_type, mistake,
                correct_approach, source, trust_level,
            )

        # Build metadata following the schema
        metadata = {
            "type": self.CATEGORY,
            "category": self.CATEGORY,
            "task_type": task_type,
            "task_keywords": self._extract_keywords(task),
            "mistake": mistake,
            "correct_approach": correct_approach,
            "source": source,
            "trust_level": trust_level,
            "source_module": source,
            "match_count": 0,
            "last_matched": None,
            "timestamp": datetime.now().isoformat(),
            "tags": ["failure_pattern", task_type, source],
        }

        result = await grimoire.execute(
            "memory_store",
            {"content": content, "metadata": metadata},
        )

        if result.success:
            # Extract memory ID from result content
            memory_id = result.content
            if isinstance(memory_id, str) and ":" in memory_id:
                memory_id = memory_id.split(":")[-1].strip()
            logger.info(
                "Stored failure pattern [%s]: %s → %s (id=%s)",
                task_type, mistake[:60], correct_approach[:60], memory_id,
            )
            return memory_id

        logger.error("Failed to store failure pattern: %s", result.error)
        return ""

    async def search_failure_patterns(
        self,
        grimoire: Any,
        query: str,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """Search for failure patterns relevant to a task.

        Args:
            grimoire: The GrimoireModule instance.
            query: The current task text to match against.
            limit: Maximum number of patterns to return.

        Returns:
            List of failure pattern dicts with task_type, mistake,
            correct_approach, source, trust_level, and relevance.
        """
        # Search Grimoire with extra results, then filter to failure_pattern category
        search_n = limit * 3  # Fetch more to filter
        result = await grimoire.execute(
            "memory_search",
            {"query": f"FAILURE PATTERN: {query}", "n_results": search_n},
        )

        if not result.success or not result.content:
            return []

        patterns = []
        raw_results = result.content

        # Handle different result formats from Grimoire
        if isinstance(raw_results, list):
            items = raw_results
        elif isinstance(raw_results, dict):
            items = raw_results.get("documents", raw_results.get("results", []))
        else:
            return []

        for item in items:
            if isinstance(item, str):
                # Raw content string — check if it's a failure pattern
                if "FAILURE PATTERN" not in item:
                    continue
                patterns.append(self._parse_pattern_from_content(item))
            elif isinstance(item, dict):
                # Structured result — check category in metadata
                metadata = item.get("metadata", {})
                category = metadata.get("category", metadata.get("type", ""))
                content = item.get("content", "")

                if category == self.CATEGORY or "FAILURE PATTERN" in str(content):
                    patterns.append({
                        "task_type": metadata.get("task_type", "unknown"),
                        "mistake": metadata.get("mistake", ""),
                        "correct_approach": metadata.get("correct_approach", ""),
                        "source": metadata.get("source", "unknown"),
                        "trust_level": metadata.get("trust_level", 0.5),
                        "relevance": item.get("relevance", 0.0),
                        "match_count": metadata.get("match_count", 0),
                        "memory_id": item.get("id", ""),
                    })

            if len(patterns) >= limit:
                break

        # Increment match_count for returned patterns (best-effort)
        for p in patterns:
            mid = p.get("memory_id", "")
            if mid:
                try:
                    await self._increment_match_count(grimoire, mid)
                except Exception:
                    pass

        logger.info(
            "Found %d failure patterns for query: %s",
            len(patterns), query[:80],
        )
        return patterns

    async def get_common_failures(
        self,
        grimoire: Any,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return most frequently matched failure patterns.

        Used by Growth Engine and Harbinger daily briefing to identify
        recurring mistakes Shadow keeps making.

        Args:
            grimoire: The GrimoireModule instance.
            limit: Maximum number of patterns to return.

        Returns:
            List of failure pattern dicts sorted by match_count descending.
        """
        # Search broadly for all failure patterns
        result = await grimoire.execute(
            "memory_search",
            {"query": "FAILURE PATTERN", "n_results": limit * 3},
        )

        if not result.success or not result.content:
            return []

        patterns = []
        raw_results = result.content
        items = raw_results if isinstance(raw_results, list) else raw_results.get("documents", [])

        for item in items:
            if isinstance(item, dict):
                metadata = item.get("metadata", {})
                category = metadata.get("category", metadata.get("type", ""))
                if category == self.CATEGORY or "FAILURE PATTERN" in str(item.get("content", "")):
                    patterns.append({
                        "task_type": metadata.get("task_type", "unknown"),
                        "mistake": metadata.get("mistake", ""),
                        "correct_approach": metadata.get("correct_approach", ""),
                        "source": metadata.get("source", "unknown"),
                        "match_count": metadata.get("match_count", 0),
                        "trust_level": metadata.get("trust_level", 0.5),
                        "timestamp": metadata.get("timestamp", ""),
                        "memory_id": item.get("id", ""),
                    })
            elif isinstance(item, str) and "FAILURE PATTERN" in item:
                patterns.append(self._parse_pattern_from_content(item))

        # Sort by match_count descending
        patterns.sort(key=lambda p: p.get("match_count", 0), reverse=True)
        return patterns[:limit]

    async def get_failure_trend(
        self,
        grimoire: Any,
        days: int = 7,
    ) -> dict[str, Any]:
        """Analyze failure pattern trends over time.

        Determines whether Shadow is learning (fewer matches over time)
        or stagnating (same patterns keep matching).

        Args:
            grimoire: The GrimoireModule instance.
            days: Number of days to analyze.

        Returns:
            Dict with total_matches, trend, and most_common_category.
        """
        patterns = await self.get_common_failures(grimoire, limit=50)

        if not patterns:
            return {
                "total_matches": 0,
                "trend": "improving",
                "most_common_category": None,
            }

        # Calculate totals
        total_matches = sum(p.get("match_count", 0) for p in patterns)

        # Find most common task type
        type_counts: dict[str, int] = {}
        for p in patterns:
            tt = p.get("task_type", "unknown")
            type_counts[tt] = type_counts.get(tt, 0) + p.get("match_count", 0)

        most_common = max(type_counts, key=type_counts.get) if type_counts else None

        # Determine trend based on timestamps and match counts
        # Split patterns into recent (last half of period) vs older (first half)
        cutoff = datetime.now() - timedelta(days=days)
        half_cutoff = datetime.now() - timedelta(days=days // 2)

        recent_matches = 0
        older_matches = 0

        for p in patterns:
            ts_str = p.get("timestamp", "")
            if not ts_str:
                older_matches += p.get("match_count", 0)
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts >= half_cutoff:
                    recent_matches += p.get("match_count", 0)
                elif ts >= cutoff:
                    older_matches += p.get("match_count", 0)
            except (ValueError, TypeError):
                older_matches += p.get("match_count", 0)

        # Determine trend
        if total_matches == 0:
            trend = "improving"
        elif older_matches == 0 and recent_matches > 0:
            trend = "degrading"
        elif recent_matches == 0 and older_matches > 0:
            trend = "improving"
        elif older_matches > 0 and recent_matches < older_matches * 0.7:
            trend = "improving"
        elif older_matches > 0 and recent_matches > older_matches * 1.3:
            trend = "degrading"
        else:
            trend = "stagnant"

        return {
            "total_matches": total_matches,
            "trend": trend,
            "most_common_category": most_common,
        }

    def format_patterns_for_context(
        self,
        patterns: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Format failure patterns for inclusion in the context manager.

        Returns dicts compatible with ContextManager's failure_patterns parameter.

        Args:
            patterns: Raw failure pattern dicts from search_failure_patterns.

        Returns:
            List of dicts with description key for context manager formatting.
        """
        formatted = []
        for p in patterns:
            description = (
                f"Task type: {p.get('task_type', 'unknown')}. "
                f"Mistake: {p.get('mistake', 'unknown')}. "
                f"Correct approach: {p.get('correct_approach', 'unknown')}."
            )
            formatted.append({
                "description": description,
                "task_type": p.get("task_type", "unknown"),
                "mistake": p.get("mistake", ""),
                "correct_approach": p.get("correct_approach", ""),
                "source": p.get("source", "unknown"),
                "trust_level": p.get("trust_level", 0.5),
            })
        return formatted

    # ----------------------------------------------------------------
    # Private helpers
    # ----------------------------------------------------------------

    async def _find_duplicate(
        self,
        grimoire: Any,
        content: str,
    ) -> dict[str, Any] | None:
        """Check if a very similar failure pattern already exists.

        Returns the existing pattern dict if similarity > DEDUP_THRESHOLD,
        otherwise None.
        """
        result = await grimoire.execute(
            "memory_search",
            {"query": content, "n_results": 3},
        )

        if not result.success or not result.content:
            return None

        raw = result.content
        items = raw if isinstance(raw, list) else raw.get("documents", [])

        for item in items:
            if isinstance(item, dict):
                metadata = item.get("metadata", {})
                category = metadata.get("category", metadata.get("type", ""))
                relevance = item.get("relevance", 0.0)

                if category == self.CATEGORY and relevance >= self.DEDUP_THRESHOLD:
                    return item
            elif isinstance(item, str) and "FAILURE PATTERN" in item:
                # String results don't carry relevance — can't dedup reliably
                pass

        return None

    async def _update_existing(
        self,
        grimoire: Any,
        existing: dict[str, Any],
        task: str,
        task_type: str,
        mistake: str,
        correct_approach: str,
        source: str,
        trust_level: float,
    ) -> str:
        """Update an existing failure pattern with new information.

        If the new pattern has higher trust, update the approach.
        Always increment the match count.
        """
        memory_id = existing.get("id", "")
        metadata = existing.get("metadata", {})
        old_trust = metadata.get("trust_level", 0.5)

        # Build updated content
        content = (
            f"FAILURE PATTERN [{task_type}]: "
            f"Task: {task}. "
            f"Mistake: {mistake}. "
            f"Correct approach: {correct_approach}."
        )

        # Update metadata — keep higher trust, increment match count
        updated_metadata = {
            "type": self.CATEGORY,
            "category": self.CATEGORY,
            "task_type": task_type,
            "task_keywords": self._extract_keywords(task),
            "mistake": mistake,
            "correct_approach": correct_approach,
            "source": source if trust_level >= old_trust else metadata.get("source", source),
            "trust_level": max(trust_level, old_trust),
            "source_module": source,
            "match_count": metadata.get("match_count", 0) + 1,
            "last_matched": datetime.now().isoformat(),
            "timestamp": metadata.get("timestamp", datetime.now().isoformat()),
            "tags": ["failure_pattern", task_type, source],
            "updated_at": datetime.now().isoformat(),
        }

        # Delete old and store new (Grimoire doesn't have an update-in-place)
        if memory_id:
            try:
                await grimoire.execute("memory_forget", {"memory_id": memory_id})
            except Exception as e:
                logger.warning("Could not delete old pattern %s: %s", memory_id, e)

        result = await grimoire.execute(
            "memory_store",
            {"content": content, "metadata": updated_metadata},
        )

        if result.success:
            new_id = result.content
            if isinstance(new_id, str) and ":" in new_id:
                new_id = new_id.split(":")[-1].strip()
            logger.info("Updated existing failure pattern: %s → %s", memory_id, new_id)
            return new_id

        logger.error("Failed to update failure pattern: %s", result.error)
        return memory_id or ""

    async def _increment_match_count(self, grimoire: Any, memory_id: str) -> None:
        """Increment the match_count for a retrieved pattern.

        Best-effort — failures here don't break the search flow.
        """
        # We can't easily update metadata in-place through the module interface,
        # so we just log it. The actual match_count update happens during
        # deduplication when the same pattern is stored again.
        logger.debug("Pattern %s matched (count tracked on next store)", memory_id)

    def _extract_keywords(self, task: str) -> str:
        """Extract key terms from task text for metadata storage."""
        # Simple keyword extraction — strip common words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "about", "that", "this", "it", "i", "me", "my",
            "and", "or", "but", "if", "not", "no", "so", "what", "how",
        }
        words = task.lower().split()
        keywords = [w.strip(".,!?;:'\"") for w in words if w.lower().strip(".,!?;:'\"") not in stop_words]
        return ", ".join(keywords[:10])

    def _parse_pattern_from_content(self, content: str) -> dict[str, Any]:
        """Parse a failure pattern from its content string.

        Handles the case where Grimoire returns raw strings instead of
        structured dicts.
        """
        pattern = {
            "task_type": "unknown",
            "mistake": "",
            "correct_approach": "",
            "source": "unknown",
            "trust_level": 0.5,
            "relevance": 0.0,
            "match_count": 0,
            "memory_id": "",
        }

        # Try to extract task_type from bracket notation
        if "[" in content and "]" in content:
            bracket_start = content.index("[") + 1
            bracket_end = content.index("]")
            pattern["task_type"] = content[bracket_start:bracket_end].strip()

        # Try to extract mistake and correct_approach
        if "Mistake:" in content:
            mistake_start = content.index("Mistake:") + len("Mistake:")
            mistake_end = content.index("Correct approach:") if "Correct approach:" in content else len(content)
            pattern["mistake"] = content[mistake_start:mistake_end].strip().rstrip(".")

        if "Correct approach:" in content:
            approach_start = content.index("Correct approach:") + len("Correct approach:")
            pattern["correct_approach"] = content[approach_start:].strip().rstrip(".")

        return pattern
