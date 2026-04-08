"""
Teaching Extractor — 3-Tier Reasoning Storage
===============================================
Parses frontier model responses into three tiers of abstraction:

1. Specific Solution — exact answer to this exact problem
2. General Principle — underlying pattern/approach for similar problems
3. Meta-Principle — reasoning strategy applicable across domains

Each tier is stored separately in Grimoire with tiered retrieval
priority: specific > general > meta.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger("shadow.apex.teaching")

# XML tag patterns for structured extraction
_SPECIFIC_RE = re.compile(
    r"<specific_solution>(.*?)</specific_solution>", re.DOTALL
)
_GENERAL_RE = re.compile(
    r"<general_principle>(.*?)</general_principle>", re.DOTALL
)
_META_RE = re.compile(
    r"<meta_principle>(.*?)</meta_principle>", re.DOTALL
)

# Heuristic keyword sets for fallback extraction
_GENERAL_KEYWORDS = re.compile(
    r"\b(pattern|approach|when you|generally|technique|rule of thumb|"
    r"in general|common solution|typical)\b",
    re.IGNORECASE,
)
_META_KEYWORDS = re.compile(
    r"\b(think about|strategy|class of problem|always|reasoning|"
    r"first identify|step back|before you|high.level|mental model)\b",
    re.IGNORECASE,
)


def _task_hash(task: dict) -> str:
    """Generate a deterministic hash for a task dict."""
    raw = str(sorted(task.items())) if isinstance(task, dict) else str(task)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class TeachingExtractor:
    """Extract teaching signals from API escalation responses.

    Phase 1: Simple structured extraction without LLM analysis.
    Phase 1.5: Three-tier extraction with XML parsing + heuristic fallback.
    """

    # ── Legacy interface (backward compatible) ──────────────────────

    def extract_teaching_signal(
        self,
        task_input: str,
        api_response: str,
        task_type: str,
    ) -> dict[str, Any]:
        """Extract a teaching signal from an escalation (Phase 1 interface).

        Preserved for backward compatibility. New code should use
        extract_three_tiers() instead.

        Args:
            task_input: The original task sent to the API.
            api_response: The API's response.
            task_type: Category of the task.

        Returns:
            Dict with task_type, input_summary, approach, key_patterns.
        """
        return {
            "task_type": task_type,
            "input_summary": task_input[:200],
            "approach": api_response[:500],
            "key_patterns": [],
        }

    # ── Three-tier extraction ───────────────────────────────────────

    def extract_three_tiers(
        self,
        response: str,
        task: dict,
        domain_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Parse a frontier model response into three reasoning tiers.

        Tries XML tags first, falls back to heuristic sentence extraction.
        Never fails — worst case the full response becomes the specific
        solution.

        Args:
            response: The frontier model's full response text.
            task: Task dict (used for hashing / context).
            domain_tags: Optional domain tags for metadata.

        Returns:
            Dict with 'specific', 'general', 'meta' entries, plus
            'all_extracted' bool and 'missing_tiers' list.
        """
        tags = domain_tags or []
        task_h = _task_hash(task)

        specific = self._extract_xml(_SPECIFIC_RE, response)
        general = self._extract_xml(_GENERAL_RE, response)
        meta = self._extract_xml(_META_RE, response)

        # Heuristic fallback for missing tiers
        if not specific or not general or not meta:
            h_specific, h_general, h_meta = self._heuristic_extract(response)
            if not specific:
                specific = h_specific
            if not general:
                general = h_general
            if not meta:
                meta = h_meta

        # Ultimate fallback: full response = specific solution
        if not specific:
            specific = response.strip()

        missing: list[str] = []
        if not specific:
            missing.append("specific")
        if not general:
            missing.append("general")
        if not meta:
            missing.append("meta")

        if missing:
            logger.info(
                "3-tier extraction missing tiers %s for task %s",
                missing, task_h,
            )

        return {
            "specific": {
                "content": specific or "",
                "metadata": {
                    "tier": "specific",
                    "task_hash": task_h,
                    "domain_tags": tags,
                },
            },
            "general": {
                "content": general or "",
                "metadata": {
                    "tier": "general",
                    "domain_tags": tags,
                },
            },
            "meta": {
                "content": meta or "",
                "metadata": {
                    "tier": "meta",
                    "domain_tags": [t.split("/")[0] for t in tags] if tags else [],
                },
            },
            "all_extracted": len(missing) == 0,
            "missing_tiers": missing,
        }

    # ── Storage ─────────────────────────────────────────────────────

    def store_three_tiers(
        self,
        tiers: dict[str, Any],
        grimoire: Any,
        collection: str = "apex_teachings",
    ) -> list[str]:
        """Store each tier as a separate Grimoire entry.

        Args:
            tiers: Output of extract_three_tiers().
            grimoire: A Grimoire instance with remember().
            collection: Grimoire category/collection name.

        Returns:
            List of stored document IDs (one per non-empty tier).
        """
        stored_ids: list[str] = []
        task_hash = tiers["specific"]["metadata"].get("task_hash", "unknown")
        now = datetime.now().isoformat()

        for tier_name in ("specific", "general", "meta"):
            tier = tiers[tier_name]
            content = tier["content"]
            if not content:
                continue

            try:
                mem_id = grimoire.remember(
                    content=content,
                    source="system",
                    source_module="apex",
                    category=collection,
                    trust_level=0.5,
                    confidence=0.7,
                    tags=["apex_teaching", tier_name] + tier["metadata"].get("domain_tags", []),
                    metadata={
                        "tier": tier_name,
                        "source_task_hash": task_hash,
                        "domain_tags": tier["metadata"].get("domain_tags", []),
                        "timestamp": now,
                        "confidence_at_creation": 0.7,
                    },
                )
                stored_ids.append(str(mem_id))
            except Exception as e:
                logger.warning(
                    "Failed to store %s tier in Grimoire: %s", tier_name, e
                )

        return stored_ids

    # ── Tier-aware retrieval ────────────────────────────────────────

    def search_with_tier_priority(
        self,
        grimoire: Any,
        query: str,
        collection: str = "apex_teachings",
        n_results: int = 5,
    ) -> list[dict[str, Any]]:
        """Search Grimoire for teachings, re-ranked by tier priority.

        Priority: specific > general > meta.

        Args:
            grimoire: A Grimoire instance with recall().
            query: Search query string.
            collection: Grimoire category/collection name.
            n_results: Max results to return.

        Returns:
            Re-ranked list of result dicts.
        """
        try:
            # Fetch more than needed so we can re-rank
            results = grimoire.recall(
                query=query,
                n_results=n_results * 3,
                category=collection,
            )
        except Exception as e:
            logger.warning("Tier-priority search failed: %s", e)
            return []

        if not results:
            return []

        # Tier priority weights (lower = higher priority)
        tier_order = {"specific": 0, "general": 1, "meta": 2}

        def _sort_key(r: dict) -> tuple:
            metadata = r.get("metadata", {})
            # Handle metadata stored as string
            if isinstance(metadata, str):
                metadata = {}
            tier = metadata.get("tier", "meta")
            priority = tier_order.get(tier, 3)
            # Use negative distance (higher similarity = lower value) as
            # tiebreaker within the same tier
            distance = r.get("distance", 1.0)
            return (priority, distance)

        ranked = sorted(results, key=_sort_key)
        return ranked[:n_results]

    # ── Internal helpers ────────────────────────────────────────────

    @staticmethod
    def _extract_xml(pattern: re.Pattern, text: str) -> str | None:
        """Extract content from an XML tag pattern."""
        match = pattern.search(text)
        if match:
            content = match.group(1).strip()
            return content if content else None
        return None

    @staticmethod
    def _heuristic_extract(
        response: str,
    ) -> tuple[str | None, str | None, str | None]:
        """Heuristic fallback: split response into tiers by keywords.

        Returns (specific, general, meta) — any may be None.
        """
        # Split into sentences (rough)
        sentences = re.split(r"(?<=[.!?])\s+", response.strip())
        if not sentences:
            return None, None, None

        specific_parts: list[str] = []
        general_parts: list[str] = []
        meta_parts: list[str] = []

        # First code block → specific
        code_match = re.search(r"```[\s\S]*?```", response)
        if code_match:
            specific_parts.append(code_match.group(0).strip())

        for sentence in sentences:
            if _META_KEYWORDS.search(sentence):
                meta_parts.append(sentence)
            elif _GENERAL_KEYWORDS.search(sentence):
                general_parts.append(sentence)

        # If no code block found, first non-classified sentence → specific
        if not specific_parts:
            for sentence in sentences:
                if sentence not in general_parts and sentence not in meta_parts:
                    specific_parts.append(sentence)
                    break

        specific = " ".join(specific_parts).strip() or None
        general = " ".join(general_parts).strip() or None
        meta = " ".join(meta_parts).strip() or None

        return specific, general, meta


# Escalation template to inject into frontier model prompts
THREE_TIER_TEACHING_TEMPLATE = """
When teaching Shadow how to solve this problem, structure your response in three sections:

<specific_solution>
The exact solution to this specific problem with code/implementation.
</specific_solution>

<general_principle>
The underlying pattern or approach that applies to similar problems in this domain.
</general_principle>

<meta_principle>
The high-level reasoning strategy — how to think about this CLASS of problem, applicable across domains.
</meta_principle>
""".strip()
