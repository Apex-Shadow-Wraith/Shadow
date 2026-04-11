"""
Shadow Teaching Shadow — Zero-Cost Knowledge Accumulation
===========================================================
When Shadow solves a hard problem WITHOUT escalating to Apex,
generate a teaching document anyway. This creates a second
knowledge accumulation pathway that costs ZERO API tokens.

Self-generated teachings are stored with trust_level 0.5
(lower than Apex's 0.7) since they haven't been validated
by an external, more capable model.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any, Callable

logger = logging.getLogger("shadow.self_teaching")

# Task types where teaching is valuable
_TEACHABLE_TYPES = frozenset({
    "code", "math", "research", "security", "business",
    "analysis", "creation", "question",
})

# Keywords that increase difficulty estimates
_CODE_KEYWORDS = re.compile(
    r"\b(function|class|implement|debug|refactor|algorithm|api|code|script|program)\b",
    re.IGNORECASE,
)
_MATH_KEYWORDS = re.compile(
    r"\b(calculate|compute|prove|equation|formula|integral|derivative|sum|average|statistics)\b",
    re.IGNORECASE,
)
_MULTISTEP_INDICATORS = re.compile(
    r"\b(then|after that|finally|next|subsequently|followed by|step \d)\b",
    re.IGNORECASE,
)
_ANALYSIS_KEYWORDS = re.compile(
    r"\b(compare|contrast|analyze|evaluate|assess|review|critique)\b",
    re.IGNORECASE,
)

_TEACHING_PROMPT = """You completed a {task_type} task. The user asked: "{task_description}"
You responded with: "{solution}"

What did you learn? Write three short paragraphs:

1. SOLUTION: What specifically solved this problem.
2. PRINCIPLE: What general pattern or approach works for this type of problem.
3. STRATEGY: How to think about this class of problem in the future."""

_RETRY_PROMPT = """You completed a {task_type} task: "{task_description}"

What is the key lesson from this? Write 1-2 sentences about what you learned that would help handle similar tasks better."""


class SelfTeacher:
    """Generate teaching documents from successful local completions.

    When Shadow solves a hard problem without Apex escalation,
    this class generates a structured teaching document and stores
    it in Grimoire for future retrieval.
    """

    def __init__(
        self,
        generate_fn: Callable | None = None,
        grimoire: Any | None = None,
        teaching_extractor: Any | None = None,
        config: dict | None = None,
    ) -> None:
        self._generate_fn = generate_fn
        # Unwrap GrimoireModule adapter if needed — we need the inner
        # Grimoire instance that has the .remember() method.
        if grimoire is not None and not hasattr(grimoire, "remember"):
            grimoire = getattr(grimoire, "_grimoire", grimoire)
        self._grimoire = grimoire
        self._teaching_extractor = teaching_extractor
        cfg = config or {}
        self._difficulty_threshold = cfg.get("difficulty_threshold", 5)
        self._confidence_threshold = cfg.get("confidence_threshold", 0.7)

    def should_teach(
        self,
        task: dict,
        confidence_score: float,
        was_escalated: bool,
    ) -> bool:
        """Determine whether a self-teaching event should fire.

        All four conditions must be true:
        1. Task difficulty > difficulty_threshold
        2. Confidence score > confidence_threshold
        3. No Apex escalation was used
        4. Task type is teachable (not routing/greetings)
        """
        if was_escalated:
            return False

        if confidence_score <= self._confidence_threshold:
            return False

        task_type = task.get("type", "").lower()
        if task_type and task_type not in _TEACHABLE_TYPES:
            return False

        difficulty = task.get("difficulty") or self.estimate_difficulty(task)
        if difficulty <= self._difficulty_threshold:
            return False

        return True

    def estimate_difficulty(self, task: dict) -> int:
        """Estimate task difficulty on a 1-10 scale using heuristics.

        Factors: description length, code/math keywords,
        multi-step indicators, analysis keywords.
        """
        description = task.get("description", "")
        words = description.split()
        word_count = len(words)

        # Base score from length
        if word_count <= 3:
            score = 1
        elif word_count <= 10:
            score = 3
        elif word_count <= 30:
            score = 5
        elif word_count <= 80:
            score = 7
        else:
            score = 8

        # Keyword bonuses
        if _CODE_KEYWORDS.search(description):
            score += 2
        if _MATH_KEYWORDS.search(description):
            score += 2
        if _ANALYSIS_KEYWORDS.search(description):
            score += 2

        # Multi-step indicators: +1 per match
        multistep_matches = _MULTISTEP_INDICATORS.findall(description)
        score += len(multistep_matches)

        return min(score, 10)

    def generate_teaching(
        self,
        task: dict,
        solution: str,
        reasoning_steps: list | None = None,
    ) -> dict:
        """Generate a teaching document from a successful task completion.

        Uses the local model (via generate_fn) to produce structured
        teaching content in three tiers.

        Returns:
            Dict with raw_teaching, tiers, task_hash, domain_tags,
            generated_at, and source fields.
        """
        description = task.get("description", "")
        task_type = task.get("type", "general")
        # Truncate long inputs to keep prompt under 2000 chars
        desc_short = description[:300]
        solution_short = solution[:400]

        prompt = _TEACHING_PROMPT.format(
            task_type=task_type,
            task_description=desc_short,
            solution=solution_short,
        )

        raw_teaching = ""
        if self._generate_fn is not None:
            raw_teaching = self._call_generate_with_retry(
                prompt, task_type, desc_short,
            )
        else:
            logger.error("generate_teaching() called but generate_fn is None — "
                         "no model available to generate teachings")

        tiers = self._extract_tiers(raw_teaching)

        task_hash = hashlib.sha256(description.encode()).hexdigest()[:16]
        task_type = task.get("type", "general").lower()
        domain_tags = self._infer_domain_tags(task_type, description)

        return {
            "raw_teaching": raw_teaching,
            "tiers": tiers,
            "task_hash": task_hash,
            "domain_tags": domain_tags,
            "generated_at": time.time(),
            "source": "self_teaching",
        }

    def store_teaching(self, teaching: dict) -> list[str]:
        """Store the teaching document in Grimoire.

        Uses TeachingExtractor.store_three_tiers() if available,
        otherwise stores directly in Grimoire with appropriate metadata.

        Returns:
            List of stored document IDs.
        """
        stored_ids: list[str] = []
        logger.info("store_teaching() called: tiers=%s, task_hash=%s",
                     list(teaching.get("tiers", {}).keys()),
                     teaching.get("task_hash", "?"))

        # Try TeachingExtractor first
        if self._teaching_extractor is not None:
            try:
                if hasattr(self._teaching_extractor, "store_three_tiers"):
                    ids = self._teaching_extractor.store_three_tiers(
                        teaching["tiers"],
                        metadata={
                            "source": "self_teaching",
                            "task_hash": teaching.get("task_hash", ""),
                            "domain_tags": teaching.get("domain_tags", []),
                        },
                    )
                    if ids:
                        return list(ids)
            except Exception as e:
                logger.warning("TeachingExtractor store failed, falling back to Grimoire: %s: %s",
                           type(e).__name__, e)

        # Direct Grimoire storage
        if self._grimoire is None:
            logger.error("No Grimoire available — self-teaching NOT stored "
                         "(grimoire was never wired into SelfTeacher)")
            return stored_ids

        tiers = teaching.get("tiers", {})
        for tier_name, tier_content in tiers.items():
            if not tier_content:
                continue
            try:
                logger.info("Grimoire store attempt: source=self_teaching, "
                            "tier=%s, content_preview=%.80s", tier_name, tier_content)
                doc_id = self._grimoire.remember(
                    content=tier_content,
                    source="self_teaching",
                    source_module="shadow",
                    category="self_teaching",
                    trust_level=0.5,
                    tags=teaching.get("domain_tags", []),
                    metadata={
                        "tier": tier_name,
                        "task_hash": teaching.get("task_hash", ""),
                        "generated_at": teaching.get("generated_at", 0),
                    },
                )
                if doc_id:
                    logger.info("Grimoire store SUCCESS: tier=%s, memory_id=%s",
                                tier_name, doc_id)
                    stored_ids.append(doc_id)
                else:
                    logger.error("Grimoire store FAILED: tier=%s, remember() returned None",
                                 tier_name)
            except Exception as e:
                logger.exception("Grimoire store FAILED for tier '%s': %s: %s",
                                 tier_name, type(e).__name__, e)

        return stored_ids

    def teach_from_success(
        self,
        task: dict,
        solution: str,
        confidence_score: float,
        was_escalated: bool,
        reasoning_steps: list | None = None,
    ) -> dict | None:
        """Combined convenience method: check → generate → store.

        This is the method the orchestrator calls after every
        successful task completion.

        Returns:
            Teaching dict if generated and stored, None if conditions not met.
        """
        if not self.should_teach(task, confidence_score, was_escalated):
            return None

        try:
            teaching = self.generate_teaching(task, solution, reasoning_steps)
        except Exception as e:
            logger.warning("Self-teaching generation failed: %s: %s", type(e).__name__, e)
            return None

        try:
            teaching["stored_ids"] = self.store_teaching(teaching)
        except Exception as e:
            logger.warning("Self-teaching storage failed: %s: %s", type(e).__name__, e)
            teaching["stored_ids"] = []

        return teaching

    # --- Private helpers ---

    def _call_generate_with_retry(
        self, prompt: str, task_type: str, desc_short: str,
    ) -> str:
        """Call generate_fn with one retry using a simpler fallback prompt."""
        logger.debug("Teaching prompt:\n%s", prompt)
        logger.info(
            "generate_teaching() calling generate_fn, "
            "task_type=%s, prompt_len=%d",
            task_type, len(prompt),
        )
        try:
            raw = self._generate_fn(prompt)
        except Exception as e:
            logger.warning("Self-teaching generation failed: %s", e)
            raw = ""

        if raw and raw.strip():
            logger.info(
                "generate_teaching() raw output length=%d, preview=%.100s",
                len(raw), raw[:100],
            )
            return raw.strip()

        # First attempt returned empty — retry with shorter fallback prompt
        logger.warning(
            "generate_teaching() got empty response on first attempt, "
            "retrying with simplified prompt"
        )
        retry_prompt = _RETRY_PROMPT.format(
            task_type=task_type,
            task_description=desc_short,
        )
        logger.debug("Retry prompt:\n%s", retry_prompt)
        try:
            raw = self._generate_fn(retry_prompt)
        except Exception as e:
            logger.warning("Self-teaching retry also failed: %s", e)
            return ""

        if raw and raw.strip():
            logger.info(
                "generate_teaching() retry succeeded, length=%d, preview=%.100s",
                len(raw), raw[:100],
            )
            return raw.strip()

        logger.error(
            "generate_teaching() retry also returned empty — "
            "model may be refusing or misconfigured"
        )
        return ""

    def _extract_tiers(self, raw: str) -> dict:
        """Extract three-tier content from model output.

        Supports two formats:
        1. XML-tagged: <specific_solution>...</specific_solution> etc.
        2. Numbered paragraphs: 1. SOLUTION: ... 2. PRINCIPLE: ... 3. STRATEGY: ...
        Falls back to storing the entire response as specific_solution.
        """
        if not raw:
            return {"specific_solution": "", "general_principle": "", "meta_principle": ""}

        # Try XML tags first (backward compatibility)
        tiers: dict[str, str] = {}
        xml_found = False
        for tier in ("specific_solution", "general_principle", "meta_principle"):
            match = re.search(
                rf"<{tier}>(.*?)</{tier}>", raw, re.DOTALL,
            )
            if match:
                tiers[tier] = match.group(1).strip()
                xml_found = True
            else:
                tiers[tier] = ""

        if xml_found and any(tiers.values()):
            return tiers

        # Try numbered paragraph extraction
        paragraphs = self._split_numbered_paragraphs(raw)
        if len(paragraphs) >= 3:
            return {
                "specific_solution": paragraphs[0],
                "general_principle": paragraphs[1],
                "meta_principle": paragraphs[2],
            }
        if len(paragraphs) == 2:
            return {
                "specific_solution": paragraphs[0],
                "general_principle": paragraphs[1],
                "meta_principle": "",
            }

        # Fallback: store entire response as specific_solution
        return {
            "specific_solution": raw.strip(),
            "general_principle": "",
            "meta_principle": "",
        }

    @staticmethod
    def _split_numbered_paragraphs(text: str) -> list[str]:
        """Split text by numbered headings (1. / 2. / 3.) or keyword labels."""
        # Match patterns like "1.", "1. SOLUTION:", "SOLUTION:", "**SOLUTION:**"
        parts = re.split(
            r"(?:^|\n)\s*(?:\d+[\.\)]\s*)?(?:\*{0,2})"
            r"(?:SOLUTION|PRINCIPLE|STRATEGY|LESSON)"
            r"(?:\*{0,2})\s*:?\s*",
            text,
            flags=re.IGNORECASE,
        )
        # Filter empty chunks
        return [p.strip() for p in parts if p and p.strip()]

    def _infer_domain_tags(self, task_type: str, description: str) -> list[str]:
        """Infer domain tags from task type and description."""
        tags = []
        if task_type:
            tags.append(task_type)
        if _CODE_KEYWORDS.search(description):
            tags.append("code")
        if _MATH_KEYWORDS.search(description):
            tags.append("math")
        if _ANALYSIS_KEYWORDS.search(description):
            tags.append("analysis")
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for t in tags:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique
