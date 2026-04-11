"""
Prompt Evolution Engine for Morpheus
======================================
Evolves Morpheus prompt templates based on experiment outcomes.

Tracks which templates produce which tier results. After N experiments,
generates mutated variants of top performers. Stores full lineage.

This is the core SI bridge — the system improving its own creative process.

Phase 1: Rule-based mutations only. No LLM calls.
Phase 2 (future): LLM-guided mutation using top-tier experiment context.
"""

from __future__ import annotations

import json
import logging
import random
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from modules.morpheus.prompt_templates import PromptTemplateRegistry

logger = logging.getLogger("shadow.morpheus.evolution")

# --- Mutation building blocks (rule-based, no LLM) ---

CONSTRAINT_POOL = [
    " ...but you cannot use any commonly cited solution.",
    " ...in under 50 words.",
    " ...using only concepts from biology.",
    " ...without referencing any existing framework.",
    " ...from the perspective of someone who disagrees.",
    " ...assuming the opposite of the conventional wisdom is true.",
    " ...using only analogies, no direct statements.",
    " ...as if explaining to a hostile audience.",
]

EXTENSION_POOL = [
    " Then: what's the second-order effect? What breaks if this works?",
    " Now: what would a critic say, and how would you respond?",
    " Next: identify the single most counterintuitive implication.",
    " Finally: what's the cheapest experiment to test this?",
    " Then: who loses if this succeeds? What's their counter-move?",
    " Now: compress everything above into one sentence. That's your thesis.",
    " Next: what adjacent problem does this accidentally solve?",
    " Finally: what would you bet money on based on this analysis?",
]

INVERSION_PAIRS = [
    ("strip away", "pile on"),
    ("remove", "add"),
    ("simplify", "complicate"),
    ("break down", "build up"),
    ("reduce", "expand"),
    ("fail", "succeed"),
    ("succeed", "fail"),
    ("strengths", "weaknesses"),
    ("weaknesses", "strengths"),
    ("prove", "disprove"),
    ("disprove", "prove"),
    ("solve", "create"),
    ("create", "destroy"),
    ("first", "last"),
    ("best", "worst"),
    ("worst", "best"),
]

SPECIALIZATION_DOMAINS = [
    "specifically for distributed systems",
    "applied to Python memory management",
    "in the context of landscaping business operations",
    "for CUDA kernel optimization",
    "within network security threat modeling",
    "applied to database query optimization",
    "in the context of team management",
    "for real-time embedded systems",
    "applied to content marketing strategy",
    "within biblical hermeneutics",
]

ABSTRACTION_REPLACEMENTS = [
    ("code", "system"),
    ("algorithm", "process"),
    ("function", "component"),
    ("database", "storage"),
    ("server", "node"),
    ("API", "interface"),
    ("test", "validation"),
    ("deploy", "release"),
    ("bug", "defect"),
    ("optimize", "improve"),
]


class PromptEvolutionEngine:
    """Evolves Morpheus prompt templates based on experiment outcomes.

    Tracks which templates produce which tier results. After N experiments,
    generates mutated variants of top performers. Stores full lineage.

    This is the core SI bridge — the system improving its own creative process.
    """

    def __init__(
        self,
        db_path: str | Path,
        registry: PromptTemplateRegistry,
    ) -> None:
        """Initialize the evolution engine.

        Args:
            db_path: Path to the SQLite database (shared with Morpheus).
            registry: The prompt template registry to read/write templates.
        """
        self._db_path = Path(db_path)
        self._registry = registry
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        self._last_evolution_experiment_count = self._total_outcomes()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    # --- Schema ---

    def _create_tables(self) -> None:
        """Create evolution tables if they don't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS template_performance (
                id TEXT PRIMARY KEY,
                template_id TEXT NOT NULL,
                experiment_id TEXT NOT NULL,
                tier INTEGER,
                score REAL,
                timestamp REAL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tp_template
            ON template_performance(template_id)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tp_experiment
            ON template_performance(experiment_id)
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS evolved_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                template TEXT NOT NULL,
                thinking_pattern TEXT NOT NULL,
                parent_id TEXT,
                generation INTEGER NOT NULL,
                mutation_type TEXT,
                mutation_history TEXT,
                created_at REAL,
                active INTEGER DEFAULT 1
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_et_pattern
            ON evolved_templates(thinking_pattern)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_et_active
            ON evolved_templates(active)
        """)
        self._conn.commit()

    # --- Core methods ---

    def record_outcome(
        self,
        template_id: str,
        experiment_id: str,
        tier: int,
        score: float,
    ) -> None:
        """Log a template's performance for a specific experiment.

        Args:
            template_id: The template that was used.
            experiment_id: The experiment that was evaluated.
            tier: Evaluation tier (1-4).
            score: Evaluation score (0.0-1.0).
        """
        record_id = str(uuid.uuid4())
        try:
            self._conn.execute(
                """INSERT INTO template_performance
                   (id, template_id, experiment_id, tier, score, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (record_id, template_id, experiment_id, tier, score, time.time()),
            )
            self._conn.commit()
        except sqlite3.IntegrityError:
            logger.debug("Duplicate outcome record for %s/%s", template_id, experiment_id)

    def get_template_stats(self) -> list[dict[str, Any]]:
        """Get performance statistics for each template.

        Returns:
            List of dicts, each with: template_id, total_uses, tier_distribution,
            avg_score, avg_tier, trend. Sorted by avg_tier ascending (best first).
        """
        rows = self._conn.execute("""
            SELECT template_id,
                   COUNT(*) as total_uses,
                   AVG(score) as avg_score,
                   AVG(tier) as avg_tier,
                   SUM(CASE WHEN tier = 1 THEN 1 ELSE 0 END) as tier_1,
                   SUM(CASE WHEN tier = 2 THEN 1 ELSE 0 END) as tier_2,
                   SUM(CASE WHEN tier = 3 THEN 1 ELSE 0 END) as tier_3,
                   SUM(CASE WHEN tier = 4 THEN 1 ELSE 0 END) as tier_4
            FROM template_performance
            GROUP BY template_id
            ORDER BY avg_tier ASC, avg_score DESC
        """).fetchall()

        stats = []
        for row in rows:
            template_id = row["template_id"]
            trend = self._calculate_trend(template_id)
            stats.append({
                "template_id": template_id,
                "total_uses": row["total_uses"],
                "avg_score": round(row["avg_score"], 4),
                "avg_tier": round(row["avg_tier"], 4),
                "tier_distribution": {
                    1: row["tier_1"],
                    2: row["tier_2"],
                    3: row["tier_3"],
                    4: row["tier_4"],
                },
                "trend": trend,
            })
        return stats

    def _calculate_trend(self, template_id: str) -> str:
        """Calculate whether a template's performance is improving, declining, or stable.

        Compares the average tier of the first half of uses to the second half.
        """
        rows = self._conn.execute(
            "SELECT tier FROM template_performance WHERE template_id=? ORDER BY timestamp ASC",
            (template_id,),
        ).fetchall()

        if len(rows) < 4:
            return "stable"

        tiers = [r["tier"] for r in rows]
        mid = len(tiers) // 2
        first_half_avg = sum(tiers[:mid]) / mid
        second_half_avg = sum(tiers[mid:]) / (len(tiers) - mid)

        diff = second_half_avg - first_half_avg
        if diff < -0.3:
            return "improving"
        elif diff > 0.3:
            return "declining"
        return "stable"

    def get_top_performers(
        self, n: int = 3, min_uses: int = 5
    ) -> list[dict[str, Any]]:
        """Get the best-performing templates.

        Args:
            n: Number of top performers to return.
            min_uses: Minimum number of uses to qualify (avoids flukes).

        Returns:
            Templates with best average tier, sorted ascending.
        """
        rows = self._conn.execute("""
            SELECT template_id,
                   COUNT(*) as total_uses,
                   AVG(score) as avg_score,
                   AVG(tier) as avg_tier
            FROM template_performance
            GROUP BY template_id
            HAVING COUNT(*) >= ?
            ORDER BY avg_tier ASC, avg_score DESC
            LIMIT ?
        """, (min_uses, n)).fetchall()

        return [
            {
                "template_id": row["template_id"],
                "total_uses": row["total_uses"],
                "avg_score": round(row["avg_score"], 4),
                "avg_tier": round(row["avg_tier"], 4),
            }
            for row in rows
        ]

    def get_underperformers(
        self, max_avg_tier: float = 3.5, min_uses: int = 5
    ) -> list[dict[str, Any]]:
        """Get consistently underperforming templates.

        Args:
            max_avg_tier: Templates with avg tier >= this are underperformers.
            min_uses: Minimum uses to qualify.

        Returns:
            Templates that consistently produce noise-tier results.
        """
        rows = self._conn.execute("""
            SELECT template_id,
                   COUNT(*) as total_uses,
                   AVG(score) as avg_score,
                   AVG(tier) as avg_tier
            FROM template_performance
            GROUP BY template_id
            HAVING COUNT(*) >= ? AND AVG(tier) >= ?
            ORDER BY avg_tier DESC
        """, (min_uses, max_avg_tier)).fetchall()

        return [
            {
                "template_id": row["template_id"],
                "total_uses": row["total_uses"],
                "avg_score": round(row["avg_score"], 4),
                "avg_tier": round(row["avg_tier"], 4),
            }
            for row in rows
        ]

    def generate_mutations(
        self, template_id: str, n_mutations: int = 3
    ) -> list[dict[str, Any]]:
        """Generate mutated variants of a template. Rule-based, no LLM.

        Args:
            template_id: Source template to mutate.
            n_mutations: Number of mutations to generate.

        Returns:
            List of new template dicts ready for registration.

        Raises:
            ValueError: If template_id not found in registry.
        """
        source = self._registry.get_by_id(template_id)
        if source is None:
            raise ValueError(f"Template {template_id} not found in registry")

        mutation_types = ["constrain", "extend", "combine", "invert", "specialize", "abstract"]
        mutations: list[dict[str, Any]] = []

        for _ in range(n_mutations):
            mtype = random.choice(mutation_types)
            mutated = self._apply_mutation(source, mtype)
            mutations.append(mutated)

        return mutations

    def _apply_mutation(
        self, source: dict[str, Any], mutation_type: str
    ) -> dict[str, Any]:
        """Apply a single mutation to a template.

        Args:
            source: The parent template dict.
            mutation_type: One of: constrain, extend, combine, invert, specialize, abstract.

        Returns:
            A new template dict with the mutation applied.
        """
        new_id = f"evolved_{uuid.uuid4().hex[:8]}"
        base_template = source["template"]
        parent_history = list(source.get("mutation_history", []))

        if mutation_type == "constrain":
            constraint = random.choice(CONSTRAINT_POOL)
            new_template = base_template + constraint
        elif mutation_type == "extend":
            extension = random.choice(EXTENSION_POOL)
            new_template = base_template + extension
        elif mutation_type == "combine":
            new_template = self._combine_mutation(source)
        elif mutation_type == "invert":
            new_template = self._invert_mutation(base_template)
        elif mutation_type == "specialize":
            domain = random.choice(SPECIALIZATION_DOMAINS)
            new_template = base_template + f" ({domain})"
        elif mutation_type == "abstract":
            new_template = self._abstract_mutation(base_template)
        else:
            new_template = base_template

        mutation_record = {
            "type": mutation_type,
            "generation": source["generation"] + 1,
            "parent_id": source["id"],
        }
        new_history = parent_history + [mutation_record]

        return {
            "id": new_id,
            "name": f"{source['name']} + {mutation_type} (gen {source['generation'] + 1})",
            "template": new_template,
            "thinking_pattern": source["thinking_pattern"],
            "parent_id": source["id"],
            "generation": source["generation"] + 1,
            "mutation_type": mutation_type,
            "mutation_history": new_history,
        }

    def _combine_mutation(self, source: dict[str, Any]) -> str:
        """Combine two templates: setup from source, twist from another."""
        all_templates = self._registry.get_all()
        others = [t for t in all_templates if t["id"] != source["id"]]
        if not others:
            return source["template"]
        other = random.choice(others)

        # Take first sentence/clause from source, second from other
        source_parts = source["template"].split(".")
        other_parts = other["template"].split(".")

        if len(source_parts) >= 1 and len(other_parts) >= 2:
            return source_parts[0] + ". " + ". ".join(other_parts[1:]).strip()
        elif len(other_parts) >= 1:
            return source_parts[0] + ". " + other_parts[-1].strip()
        return source["template"] + " " + other["template"]

    def _invert_mutation(self, template: str) -> str:
        """Flip the direction of a template using inversion word pairs."""
        result = template
        # Apply a random subset of inversions to avoid total garbling
        pairs_to_apply = random.sample(
            INVERSION_PAIRS, min(3, len(INVERSION_PAIRS))
        )
        for original, replacement in pairs_to_apply:
            if original in result.lower():
                # Case-preserving replacement
                idx = result.lower().find(original)
                result = result[:idx] + replacement + result[idx + len(original):]
        return result

    def _abstract_mutation(self, template: str) -> str:
        """Remove domain specifics, generalize the template."""
        result = template
        replacements_to_apply = random.sample(
            ABSTRACTION_REPLACEMENTS, min(3, len(ABSTRACTION_REPLACEMENTS))
        )
        for specific, general in replacements_to_apply:
            result = result.replace(specific, general)
        return result

    def evolve_cycle(self, min_experiments: int = 10) -> dict[str, Any]:
        """Run one evolution cycle.

        1. Check if enough experiments have run since last evolution.
        2. Get top 3 performers.
        3. Generate 2 mutations from each (6 new templates).
        4. Retire templates with avg_tier > 3.5 and 10+ uses.
        5. Register new templates.
        6. Return summary.

        Args:
            min_experiments: Minimum new experiments since last evolution to proceed.

        Returns:
            Dict with: new_templates, retired, top_performers, skipped (bool).
        """
        current_count = self._total_outcomes()
        if current_count - self._last_evolution_experiment_count < min_experiments:
            return {
                "new_templates": [],
                "retired": [],
                "top_performers": [],
                "skipped": True,
                "reason": f"Only {current_count - self._last_evolution_experiment_count} experiments since last evolution (need {min_experiments})",
            }

        # Get top performers (relax min_uses for early stages)
        top = self.get_top_performers(n=3, min_uses=2)
        if not top:
            # Cold start: pick random seeds
            all_seeds = self._registry.get_all()
            top = [
                {"template_id": t["id"], "total_uses": 0, "avg_score": 0, "avg_tier": 2.5}
                for t in random.sample(all_seeds, min(3, len(all_seeds)))
            ]

        # Generate mutations
        new_templates: list[dict[str, Any]] = []
        for performer in top:
            try:
                mutations = self.generate_mutations(performer["template_id"], n_mutations=2)
                for m in mutations:
                    self._persist_evolved_template(m)
                    self._registry.add_template(m)
                    new_templates.append(m)
            except ValueError:
                logger.warning("Could not mutate template %s", performer["template_id"])

        # Retire underperformers
        underperformers = self.get_underperformers(max_avg_tier=3.5, min_uses=10)
        retired: list[str] = []
        for up in underperformers:
            tid = up["template_id"]
            # Never retire seed templates
            if tid.startswith("seed_"):
                continue
            self._conn.execute(
                "UPDATE evolved_templates SET active=0 WHERE id=?",
                (tid,),
            )
            retired.append(tid)
        if retired:
            self._conn.commit()

        self._last_evolution_experiment_count = current_count

        return {
            "new_templates": [{"id": t["id"], "name": t["name"], "mutation_type": t.get("mutation_type")} for t in new_templates],
            "retired": retired,
            "top_performers": top,
            "skipped": False,
        }

    def select_template(self, category: str | None = None) -> dict[str, Any]:
        """Select a template for the next experiment using weighted random.

        Weight = inverse of average tier. New templates get a novelty bonus.

        Args:
            category: Optional category filter (not used for filtering templates,
                but could boost templates that perform well in this category).

        Returns:
            A template dict from the registry.
        """
        all_templates = self._registry.get_all()
        if not all_templates:
            raise ValueError("No templates available in registry")

        # Build stats lookup
        stats_list = self.get_template_stats()
        stats_by_id: dict[str, dict[str, Any]] = {
            s["template_id"]: s for s in stats_list
        }

        weights: list[float] = []
        for t in all_templates:
            tid = t["id"]
            stats = stats_by_id.get(tid)
            if stats is None or stats["total_uses"] == 0:
                weight = 3.0  # Encourage exploration
            elif stats["total_uses"] < 5:
                base_weight = 5.0 - stats["avg_tier"]
                novelty_bonus = (5 - stats["total_uses"]) * 0.5
                weight = base_weight + novelty_bonus
            else:
                weight = max(5.0 - stats["avg_tier"], 0.5)
            weights.append(weight)

        selected = random.choices(all_templates, weights=weights, k=1)[0]
        return selected

    def load_evolved_templates(self) -> list[dict[str, Any]]:
        """Load all active evolved templates from the database.

        Returns:
            List of template dicts suitable for registry.add_template().
        """
        rows = self._conn.execute(
            "SELECT * FROM evolved_templates WHERE active=1"
        ).fetchall()

        templates = []
        for row in rows:
            mutation_history = []
            if row["mutation_history"]:
                try:
                    mutation_history = json.loads(row["mutation_history"])
                except (json.JSONDecodeError, TypeError):
                    pass

            templates.append({
                "id": row["id"],
                "name": row["name"],
                "template": row["template"],
                "thinking_pattern": row["thinking_pattern"],
                "parent_id": row["parent_id"],
                "generation": row["generation"],
                "mutation_type": row["mutation_type"],
                "mutation_history": mutation_history,
            })
        return templates

    # --- Persistence helpers ---

    def _persist_evolved_template(self, template: dict[str, Any]) -> None:
        """Save an evolved template to the database."""
        self._conn.execute(
            """INSERT OR REPLACE INTO evolved_templates
               (id, name, template, thinking_pattern, parent_id,
                generation, mutation_type, mutation_history, created_at, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                template["id"],
                template["name"],
                template["template"],
                template["thinking_pattern"],
                template["parent_id"],
                template["generation"],
                template.get("mutation_type"),
                json.dumps(template.get("mutation_history", [])),
                time.time(),
            ),
        )
        self._conn.commit()

    def _total_outcomes(self) -> int:
        """Count total outcome records."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM template_performance"
        ).fetchone()
        return row[0] if row else 0
