"""
CrossModuleDreamer — Cross-Module Capability Discovery
========================================================
Morpheus experimentally combines capabilities across modules that were
never designed to work together. Generates speculative hypotheses about
novel capabilities that could emerge from module combinations.

Dreams are SPECULATIVE — they enter experiment_store, not production.
MessageBus handles inter-module communication for active tasks;
this is deliberate experimentation.

Part of Morpheus (Creative Discovery Pipeline).
"""

from __future__ import annotations

import itertools
import json
import logging
import random
import time
import uuid
from typing import Any, Callable

logger = logging.getLogger("shadow.morpheus.cross_module_dreaming")

# All 13 Shadow modules with descriptions
MODULE_DESCRIPTIONS = {
    "shadow": "Master orchestrator/router, 7-step decision loop, task routing and delegation",
    "wraith": "Fast brain, daily tasks, reminders, task classification, temporal patterns",
    "cerberus": "Ethics, safety, approvals, injection detection, reversibility, watchdog",
    "apex": "Claude/GPT API fallback with cost tracking and teaching cycle",
    "grimoire": "Data storage, knowledge base, memory, vector DB, block search",
    "sentinel": "Security, firewall, network scanning, file integrity, quarantine",
    "harbinger": "Briefings, alerts, notifications, decision queue, safety reports, personalization",
    "reaper": "Research, web scraping, Reddit .json, YouTube transcription",
    "cipher": "Math, logic, unit conversion, financial, statistics",
    "omen": "Code execution, linting, review, git ops, pattern DB, failure learning, scaffolding",
    "nova": "Content creation, document generation, templates, business estimates",
    "morpheus": "Creative discovery pipeline, controlled hallucination, experiment tracking",
}

DREAM_PROMPT_TEMPLATE = """Module A ({module_a}) handles: {module_a_description}
Module B ({module_b}) handles: {module_b_description}

What novel capability could emerge from combining these two modules in ways they weren't designed for?
Examples:
- Sentinel (security) + Omen (code) → security-hardened code generation patterns
- Cipher (math) + Reaper (research) → statistical source reliability scoring

Generate 1-2 creative hypotheses. For each, provide:
1. A short title
2. A description of the combined capability
3. Whether it's testable (yes/no)
4. Potential value (high/medium/low)

Respond in JSON format: [{{"title": "...", "description": "...", "testable": true/false, "potential_value": "high/medium/low"}}]"""


class CrossModuleDreamer:
    """Generates speculative hypotheses about combining module capabilities.

    Picks random module pairs, asks an LLM to imagine novel combinations,
    evaluates whether the ideas are worth pursuing, and stores them as
    experiments for later investigation.

    Args:
        generate_fn: Callable that takes a prompt string and returns model output.
        grimoire: Optional Grimoire module for knowledge retrieval.
        module_registry: Optional dict of module_name -> description overrides.
        experiment_store: Optional ExperimentStore for persisting dreams.
    """

    def __init__(
        self,
        generate_fn: Callable | None = None,
        grimoire=None,
        module_registry: dict[str, str] | None = None,
        experiment_store=None,
    ) -> None:
        self._generate_fn = generate_fn
        self._grimoire = grimoire
        self._module_registry = module_registry
        self._experiment_store = experiment_store
        self._explored_pairs: set[tuple[str, str]] = set()
        self._dream_history: list[dict] = []

    def dream(self, max_combinations: int = 3) -> list[dict]:
        """Generate hypotheses for random module pair combinations.

        Picks up to max_combinations random module pairs that haven't been
        explored yet, generates hypotheses for each, and returns them.

        Args:
            max_combinations: Maximum number of module pairs to combine.

        Returns:
            List of dream dicts with keys: module_a, module_b, hypothesis,
            potential_value, testable.
        """
        descriptions = self.get_module_descriptions()
        if len(descriptions) < 2:
            return []

        unexplored = self.get_unexplored_combinations()
        if not unexplored:
            return []

        pairs_to_explore = random.sample(
            unexplored, min(max_combinations, len(unexplored))
        )

        all_dreams = []
        for module_a, module_b in pairs_to_explore:
            pair_key = tuple(sorted((module_a, module_b)))
            self._explored_pairs.add(pair_key)

            hypotheses = self._generate_hypotheses(
                module_a, descriptions.get(module_a, ""),
                module_b, descriptions.get(module_b, ""),
            )

            for h in hypotheses:
                dream = {
                    "module_a": module_a,
                    "module_b": module_b,
                    "hypothesis": h.get("title", h.get("description", "")),
                    "description": h.get("description", ""),
                    "potential_value": h.get("potential_value", "medium"),
                    "testable": h.get("testable", False),
                    "timestamp": time.time(),
                }
                all_dreams.append(dream)
                self._dream_history.append(dream)

        return all_dreams

    def get_module_descriptions(self) -> dict[str, str]:
        """Return descriptions for all 13 modules.

        Uses module_registry if provided, otherwise falls back to
        hardcoded MODULE_DESCRIPTIONS.

        Returns:
            Dict mapping module name to description string.
        """
        if self._module_registry is not None:
            return dict(self._module_registry)
        return dict(MODULE_DESCRIPTIONS)

    def evaluate_dream(self, dream: dict) -> dict:
        """Quick assessment of whether a dream is worth investigating.

        Checks that the dream isn't trivially obvious, both modules
        contribute meaningfully, and the result would be useful.

        Args:
            dream: A dream dict from dream().

        Returns:
            Dict with worth_investigating (bool), reason (str), priority (int 1-5).
        """
        hypothesis = dream.get("hypothesis", "")
        description = dream.get("description", "")
        module_a = dream.get("module_a", "")
        module_b = dream.get("module_b", "")
        potential_value = dream.get("potential_value", "medium")

        # Check for trivially empty dreams
        if not hypothesis and not description:
            return {
                "worth_investigating": False,
                "reason": "Empty hypothesis — no content to evaluate",
                "priority": 5,
            }

        text = (hypothesis + " " + description).lower()

        # Check if both modules are meaningfully involved
        descriptions = self.get_module_descriptions()
        desc_a = descriptions.get(module_a, "").lower()
        desc_b = descriptions.get(module_b, "").lower()

        # Trivial check: if the hypothesis just restates what one module already does
        hypothesis_lower = hypothesis.lower().strip()
        description_lower = description.lower().strip()
        if desc_a and (hypothesis_lower == desc_a.strip() or description_lower == desc_a.strip()):
            return {
                "worth_investigating": False,
                "reason": f"Hypothesis just restates {module_a}'s existing capability",
                "priority": 5,
            }
        if desc_b and (hypothesis_lower == desc_b.strip() or description_lower == desc_b.strip()):
            return {
                "worth_investigating": False,
                "reason": f"Hypothesis just restates {module_b}'s existing capability",
                "priority": 5,
            }

        # Check for trivial "just pass data between them" combinations
        trivial_phrases = [
            "send data from",
            "pass output to",
            "pipe results",
            "forward to",
            "just combine",
        ]
        if any(phrase in text for phrase in trivial_phrases):
            return {
                "worth_investigating": False,
                "reason": "Trivial data piping — no emergent capability",
                "priority": 5,
            }

        # Score based on potential value
        priority_map = {"high": 1, "medium": 3, "low": 4}
        priority = priority_map.get(potential_value, 3)

        # Testable dreams get a priority boost
        if dream.get("testable", False):
            priority = max(1, priority - 1)

        return {
            "worth_investigating": True,
            "reason": "Novel combination with potential emergent capability",
            "priority": priority,
        }

    def store_dream(self, dream: dict) -> str:
        """Store a dream in experiment_store as a new experiment.

        Args:
            dream: A dream dict from dream().

        Returns:
            Experiment ID string, or empty string if no store configured.
        """
        if self._experiment_store is None:
            return ""

        exp_id = self._experiment_store.store_failure(
            hypothesis=dream.get("hypothesis", ""),
            approach=f"cross_module_dream: {dream.get('module_a', '')} + {dream.get('module_b', '')}",
            domain_tags=["cross_module_dream", dream.get("module_a", ""), dream.get("module_b", "")],
            failure_reason="pending_investigation",
            conditions={
                "category": "cross_module_dream",
                "module_a": dream.get("module_a", ""),
                "module_b": dream.get("module_b", ""),
                "potential_value": dream.get("potential_value", "medium"),
                "testable": dream.get("testable", False),
                "description": dream.get("description", ""),
            },
            retry_triggers=[],
        )

        return exp_id

    def get_dream_history(self, limit: int = 20) -> list[dict]:
        """Return past dreams from this session.

        Args:
            limit: Maximum number of dreams to return.

        Returns:
            List of dream dicts, most recent first.
        """
        return list(reversed(self._dream_history[-limit:]))

    def get_unexplored_combinations(self) -> list[tuple[str, str]]:
        """Return module pairs that haven't been explored yet.

        13 modules = 78 possible pairs. Tracks which have been tried.

        Returns:
            List of (module_a, module_b) tuples not yet explored.
        """
        descriptions = self.get_module_descriptions()
        modules = sorted(descriptions.keys())
        all_pairs = list(itertools.combinations(modules, 2))

        unexplored = [
            pair for pair in all_pairs
            if tuple(sorted(pair)) not in self._explored_pairs
        ]

        return unexplored

    def get_dreaming_stats(self) -> dict:
        """Return dreaming statistics for Growth Engine.

        Returns:
            Dict with combinations_explored, total_dreams, validated_dreams,
            unexplored_pairs.
        """
        descriptions = self.get_module_descriptions()
        modules = sorted(descriptions.keys())
        total_possible = len(list(itertools.combinations(modules, 2)))

        validated = sum(
            1 for d in self._dream_history
            if self.evaluate_dream(d).get("worth_investigating", False)
        )

        return {
            "combinations_explored": len(self._explored_pairs),
            "total_dreams": len(self._dream_history),
            "validated_dreams": validated,
            "unexplored_pairs": total_possible - len(self._explored_pairs),
        }

    # --- Internal helpers ---

    def _generate_hypotheses(
        self,
        module_a: str, desc_a: str,
        module_b: str, desc_b: str,
    ) -> list[dict]:
        """Use generate_fn to produce hypotheses for a module pair.

        Falls back to an empty list if generate_fn is unavailable or fails.

        Args:
            module_a: Name of first module.
            desc_a: Description of first module.
            module_b: Name of second module.
            desc_b: Description of second module.

        Returns:
            List of hypothesis dicts with title, description, testable, potential_value.
        """
        if self._generate_fn is None:
            return []

        prompt = DREAM_PROMPT_TEMPLATE.format(
            module_a=module_a,
            module_a_description=desc_a,
            module_b=module_b,
            module_b_description=desc_b,
        )

        try:
            response = self._generate_fn(prompt)
        except Exception as e:
            logger.warning("generate_fn failed for %s + %s: %s", module_a, module_b, e)
            return []

        return self._parse_hypotheses(response)

    def _parse_hypotheses(self, response: str) -> list[dict]:
        """Parse LLM response into structured hypothesis dicts.

        Attempts JSON parsing first, then falls back to treating the
        whole response as a single hypothesis.

        Args:
            response: Raw LLM output string.

        Returns:
            List of hypothesis dicts.
        """
        if not response:
            return []

        # Try JSON parsing
        try:
            parsed = json.loads(response)
            if isinstance(parsed, list):
                return [self._normalize_hypothesis(h) for h in parsed if isinstance(h, dict)]
            if isinstance(parsed, dict):
                return [self._normalize_hypothesis(parsed)]
        except (json.JSONDecodeError, TypeError):
            pass

        # Try extracting JSON from response (might have surrounding text)
        try:
            start = response.index("[")
            end = response.rindex("]") + 1
            parsed = json.loads(response[start:end])
            if isinstance(parsed, list):
                return [self._normalize_hypothesis(h) for h in parsed if isinstance(h, dict)]
        except (ValueError, json.JSONDecodeError):
            pass

        # Fallback: treat entire response as a single hypothesis
        return [{
            "title": response[:100].strip(),
            "description": response.strip(),
            "testable": False,
            "potential_value": "medium",
        }]

    def _normalize_hypothesis(self, h: dict) -> dict:
        """Ensure hypothesis dict has all required keys with correct types."""
        return {
            "title": str(h.get("title", "")),
            "description": str(h.get("description", "")),
            "testable": bool(h.get("testable", False)),
            "potential_value": str(h.get("potential_value", "medium")),
        }
