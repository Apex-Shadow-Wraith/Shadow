"""
Prompt Template Registry for Morpheus
======================================
Registry of prompt templates with performance tracking.
Each template has a lineage — which parent it was derived from,
what mutations were applied, and its performance history.

Seed templates match the Innovation Reference Library from the
Unified Architecture (first principles, systematic experimentation,
cross-domain observation, etc).
"""

from __future__ import annotations

import copy
from typing import Any


SEED_TEMPLATES: dict[str, dict[str, Any]] = {
    "first_principles": {
        "id": "seed_first_principles",
        "name": "First Principles (Musk)",
        "template": "Strip away all assumptions about {topic}. What does physics/logic actually require? Rebuild from ground truth.",
        "thinking_pattern": "first_principles",
        "parent_id": None,
        "generation": 0,
        "mutation_history": [],
    },
    "systematic_experimentation": {
        "id": "seed_systematic_experimentation",
        "name": "Systematic Experimentation (Edison)",
        "template": "Generate 5 variations of {topic}. For each: what specific test would prove/disprove it? What does failure teach?",
        "thinking_pattern": "systematic_experimentation",
        "parent_id": None,
        "generation": 0,
        "mutation_history": [],
    },
    "cross_domain": {
        "id": "seed_cross_domain",
        "name": "Cross-Domain Observation (da Vinci)",
        "template": "What does {domain_a} teach us about {topic}? Find the structural parallel, not the surface similarity.",
        "thinking_pattern": "cross_domain",
        "parent_id": None,
        "generation": 0,
        "mutation_history": [],
    },
    "inversion": {
        "id": "seed_inversion",
        "name": "Inversion (Munger)",
        "template": "Instead of solving {topic}, how would you deliberately cause the problem? Now reverse each cause into a solution.",
        "thinking_pattern": "inversion",
        "parent_id": None,
        "generation": 0,
        "mutation_history": [],
    },
    "simplification": {
        "id": "seed_simplification",
        "name": "Simplification (Feynman)",
        "template": "Explain {topic} so a 12-year-old understands it. What falls away? What remains is the core insight.",
        "thinking_pattern": "simplification",
        "parent_id": None,
        "generation": 0,
        "mutation_history": [],
    },
    "iterative_failure": {
        "id": "seed_iterative_failure",
        "name": "Iterative Failure (Dyson)",
        "template": "What are 10 ways {topic} could fail? For each failure mode, what would you try next? Chain the failures into a solution.",
        "thinking_pattern": "iterative_failure",
        "parent_id": None,
        "generation": 0,
        "mutation_history": [],
    },
    "assumption_challenge": {
        "id": "seed_assumption_challenge",
        "name": "Challenge Assumptions (Hopper)",
        "template": "What is everyone assuming about {topic} that has never been tested? What if that assumption is wrong?",
        "thinking_pattern": "assumption_challenge",
        "parent_id": None,
        "generation": 0,
        "mutation_history": [],
    },
    "speculative_extension": {
        "id": "seed_speculative_extension",
        "name": "Speculative Extension",
        "template": "Given what you know about {known_a} and {known_b}, what would happen if {speculative_condition} were true?",
        "thinking_pattern": "speculative_extension",
        "parent_id": None,
        "generation": 0,
        "mutation_history": [],
    },
}


class PromptTemplateRegistry:
    """Registry of prompt templates with performance tracking.

    Each template has a lineage — which parent it was derived from,
    what mutations were applied, and its performance history.
    """

    def __init__(self) -> None:
        """Initialize with seed templates."""
        self._templates: dict[str, dict[str, Any]] = {}
        for seed in SEED_TEMPLATES.values():
            self._templates[seed["id"]] = copy.deepcopy(seed)

    def get_all(self) -> list[dict[str, Any]]:
        """Return all templates (seed + evolved)."""
        return [copy.deepcopy(t) for t in self._templates.values()]

    def get_by_id(self, template_id: str) -> dict[str, Any] | None:
        """Return a template by its ID, or None if not found."""
        t = self._templates.get(template_id)
        if t is not None:
            return copy.deepcopy(t)
        return None

    def get_by_pattern(self, thinking_pattern: str) -> list[dict[str, Any]]:
        """Return all templates matching the given thinking pattern."""
        return [
            copy.deepcopy(t)
            for t in self._templates.values()
            if t["thinking_pattern"] == thinking_pattern
        ]

    def add_template(self, template: dict[str, Any]) -> None:
        """Register a new evolved template.

        Args:
            template: Must contain at minimum: id, name, template,
                thinking_pattern, parent_id, generation, mutation_history.

        Raises:
            ValueError: If required keys are missing.
        """
        required_keys = {"id", "name", "template", "thinking_pattern",
                         "parent_id", "generation", "mutation_history"}
        missing = required_keys - set(template.keys())
        if missing:
            raise ValueError(f"Template missing required keys: {missing}")
        self._templates[template["id"]] = copy.deepcopy(template)

    def get_lineage(self, template_id: str) -> list[dict[str, Any]]:
        """Return the full parent chain back to the seed template.

        Returns a list ordered from the oldest ancestor to the given template.
        Returns an empty list if the template_id is not found.
        """
        chain: list[dict[str, Any]] = []
        current_id: str | None = template_id
        seen: set[str] = set()

        while current_id and current_id not in seen:
            seen.add(current_id)
            t = self._templates.get(current_id)
            if t is None:
                break
            chain.append(copy.deepcopy(t))
            current_id = t.get("parent_id")

        chain.reverse()
        return chain
