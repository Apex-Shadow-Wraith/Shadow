"""
Tests for Morpheus Prompt Evolution Engine
============================================
Template registry, evolution engine, mutations, selection, integration.
"""

import pytest
import random
from collections import Counter
from pathlib import Path
from typing import Any

from modules.morpheus.prompt_templates import PromptTemplateRegistry, SEED_TEMPLATES
from modules.morpheus.prompt_evolution import PromptEvolutionEngine
from modules.morpheus.morpheus import Morpheus
from modules.base import ToolResult


# --- Fixtures ---


@pytest.fixture
def registry() -> PromptTemplateRegistry:
    return PromptTemplateRegistry()


@pytest.fixture
def engine(tmp_path: Path, registry: PromptTemplateRegistry) -> PromptEvolutionEngine:
    db_path = tmp_path / "evolution_test.db"
    eng = PromptEvolutionEngine(db_path=db_path, registry=registry)
    return eng


@pytest.fixture
def morpheus(tmp_path: Path) -> Morpheus:
    config = {"db_path": str(tmp_path / "morpheus_evo_test.db")}
    return Morpheus(config)


@pytest.fixture
async def online_morpheus(morpheus: Morpheus) -> Morpheus:
    await morpheus.initialize()
    return morpheus


async def _propose(m: Morpheus, **overrides) -> ToolResult:
    """Helper to propose an experiment with defaults."""
    params = {
        "title": "Test experiment",
        "hypothesis": "This will work",
        "category": "exploration",
        "priority": 3,
    }
    params.update(overrides)
    return await m.execute("experiment_propose", params)


async def _full_lifecycle(m: Morpheus, **propose_overrides) -> str:
    """Helper: propose -> start -> complete -> evaluate. Returns experiment_id."""
    r = await _propose(m, **propose_overrides)
    eid = r.content["experiment_id"]
    await m.execute("experiment_start", {"experiment_id": eid})
    await m.execute("experiment_complete", {
        "experiment_id": eid,
        "result_data": {"output": "test result"},
    })
    return eid


# ===================================================================
# TestPromptTemplateRegistry
# ===================================================================


class TestPromptTemplateRegistry:
    def test_seed_templates_count(self, registry: PromptTemplateRegistry):
        """All 8 seed templates loaded on init."""
        all_t = registry.get_all()
        assert len(all_t) == 8

    def test_seed_template_ids(self, registry: PromptTemplateRegistry):
        """Each seed has the expected ID prefix."""
        ids = {t["id"] for t in registry.get_all()}
        assert all(tid.startswith("seed_") for tid in ids)

    def test_get_all_returns_copies(self, registry: PromptTemplateRegistry):
        """get_all returns deep copies, not references."""
        all_t = registry.get_all()
        all_t[0]["name"] = "MODIFIED"
        original = registry.get_by_id(all_t[0]["id"])
        assert original["name"] != "MODIFIED"

    def test_get_by_id_existing(self, registry: PromptTemplateRegistry):
        """Get a known seed template by ID."""
        t = registry.get_by_id("seed_first_principles")
        assert t is not None
        assert t["name"] == "First Principles (Musk)"
        assert t["generation"] == 0
        assert t["parent_id"] is None

    def test_get_by_id_nonexistent(self, registry: PromptTemplateRegistry):
        """Returns None for unknown ID."""
        assert registry.get_by_id("nonexistent_id") is None

    def test_get_by_pattern(self, registry: PromptTemplateRegistry):
        """Filter by thinking_pattern returns correct templates."""
        results = registry.get_by_pattern("inversion")
        assert len(results) == 1
        assert results[0]["id"] == "seed_inversion"

    def test_get_by_pattern_no_match(self, registry: PromptTemplateRegistry):
        """Filter by unknown pattern returns empty list."""
        results = registry.get_by_pattern("nonexistent_pattern")
        assert results == []

    def test_add_template(self, registry: PromptTemplateRegistry):
        """Add an evolved template and retrieve it."""
        evolved = {
            "id": "evolved_test_001",
            "name": "Test Evolved",
            "template": "This is a test template for {topic}.",
            "thinking_pattern": "first_principles",
            "parent_id": "seed_first_principles",
            "generation": 1,
            "mutation_history": [{"type": "constrain"}],
        }
        registry.add_template(evolved)
        assert len(registry.get_all()) == 9
        t = registry.get_by_id("evolved_test_001")
        assert t is not None
        assert t["name"] == "Test Evolved"

    def test_add_template_missing_keys(self, registry: PromptTemplateRegistry):
        """Adding a template with missing keys raises ValueError."""
        with pytest.raises(ValueError, match="missing required keys"):
            registry.add_template({"id": "bad", "name": "incomplete"})

    def test_get_lineage_seed(self, registry: PromptTemplateRegistry):
        """Lineage of a seed template is just itself."""
        lineage = registry.get_lineage("seed_inversion")
        assert len(lineage) == 1
        assert lineage[0]["id"] == "seed_inversion"

    def test_get_lineage_chain(self, registry: PromptTemplateRegistry):
        """Lineage walks parent_id chain: seed -> child -> grandchild."""
        child = {
            "id": "evolved_child",
            "name": "Child",
            "template": "child template",
            "thinking_pattern": "inversion",
            "parent_id": "seed_inversion",
            "generation": 1,
            "mutation_history": [{"type": "extend"}],
        }
        grandchild = {
            "id": "evolved_grandchild",
            "name": "Grandchild",
            "template": "grandchild template",
            "thinking_pattern": "inversion",
            "parent_id": "evolved_child",
            "generation": 2,
            "mutation_history": [{"type": "extend"}, {"type": "constrain"}],
        }
        registry.add_template(child)
        registry.add_template(grandchild)

        lineage = registry.get_lineage("evolved_grandchild")
        assert len(lineage) == 3
        assert lineage[0]["id"] == "seed_inversion"
        assert lineage[1]["id"] == "evolved_child"
        assert lineage[2]["id"] == "evolved_grandchild"

    def test_get_lineage_nonexistent(self, registry: PromptTemplateRegistry):
        """Lineage of nonexistent template is empty list."""
        assert registry.get_lineage("nonexistent") == []

    def test_seed_templates_have_required_fields(self, registry: PromptTemplateRegistry):
        """Every seed template has all required fields."""
        required = {"id", "name", "template", "thinking_pattern", "parent_id", "generation", "mutation_history"}
        for t in registry.get_all():
            assert required.issubset(t.keys()), f"Template {t['id']} missing keys"
            assert t["generation"] == 0
            assert t["parent_id"] is None
            assert t["mutation_history"] == []


# ===================================================================
# TestPromptEvolutionEngine
# ===================================================================


class TestPromptEvolutionEngine:
    def test_tables_created(self, engine: PromptEvolutionEngine):
        """Both template_performance and evolved_templates tables exist."""
        tables = engine._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        assert "template_performance" in table_names
        assert "evolved_templates" in table_names

    def test_record_outcome(self, engine: PromptEvolutionEngine):
        """Recording an outcome inserts a row."""
        engine.record_outcome("seed_first_principles", "exp_001", tier=2, score=0.75)
        row = engine._conn.execute(
            "SELECT * FROM template_performance WHERE experiment_id='exp_001'"
        ).fetchone()
        assert row is not None
        assert row["template_id"] == "seed_first_principles"
        assert row["tier"] == 2
        assert row["score"] == 0.75

    def test_record_outcome_multiple(self, engine: PromptEvolutionEngine):
        """Multiple outcomes for the same template accumulate."""
        engine.record_outcome("seed_inversion", "exp_a", tier=1, score=0.9)
        engine.record_outcome("seed_inversion", "exp_b", tier=3, score=0.4)
        count = engine._conn.execute(
            "SELECT COUNT(*) FROM template_performance WHERE template_id='seed_inversion'"
        ).fetchone()[0]
        assert count == 2

    def test_get_template_stats_empty(self, engine: PromptEvolutionEngine):
        """Stats with no data returns empty list."""
        stats = engine.get_template_stats()
        assert stats == []

    def test_get_template_stats(self, engine: PromptEvolutionEngine):
        """Stats aggregates correctly across multiple outcomes."""
        engine.record_outcome("seed_first_principles", "e1", tier=1, score=0.9)
        engine.record_outcome("seed_first_principles", "e2", tier=2, score=0.7)
        engine.record_outcome("seed_first_principles", "e3", tier=1, score=0.85)
        engine.record_outcome("seed_inversion", "e4", tier=4, score=0.2)

        stats = engine.get_template_stats()
        assert len(stats) == 2

        fp_stats = next(s for s in stats if s["template_id"] == "seed_first_principles")
        assert fp_stats["total_uses"] == 3
        assert fp_stats["tier_distribution"][1] == 2
        assert fp_stats["tier_distribution"][2] == 1
        assert fp_stats["avg_tier"] < 2.0  # avg of 1,2,1 = 1.333

    def test_get_template_stats_trend(self, engine: PromptEvolutionEngine):
        """Trend detection: declining when recent tiers are worse."""
        import time as _time
        # First half: good (tier 1)
        for i in range(4):
            engine.record_outcome("seed_first_principles", f"e_good_{i}", tier=1, score=0.9)
        # Second half: bad (tier 4)
        for i in range(4):
            engine.record_outcome("seed_first_principles", f"e_bad_{i}", tier=4, score=0.2)

        stats = engine.get_template_stats()
        fp_stats = next(s for s in stats if s["template_id"] == "seed_first_principles")
        assert fp_stats["trend"] == "declining"

    def test_get_top_performers(self, engine: PromptEvolutionEngine):
        """Top performers sorted by best avg tier."""
        # Template A: consistently great
        for i in range(6):
            engine.record_outcome("seed_first_principles", f"a_{i}", tier=1, score=0.9)
        # Template B: mediocre
        for i in range(6):
            engine.record_outcome("seed_inversion", f"b_{i}", tier=3, score=0.4)

        top = engine.get_top_performers(n=2, min_uses=5)
        assert len(top) == 2
        assert top[0]["template_id"] == "seed_first_principles"
        assert top[0]["avg_tier"] < top[1]["avg_tier"]

    def test_get_top_performers_min_uses_filter(self, engine: PromptEvolutionEngine):
        """Templates with fewer than min_uses are excluded."""
        engine.record_outcome("seed_first_principles", "e1", tier=1, score=0.9)
        engine.record_outcome("seed_first_principles", "e2", tier=1, score=0.85)

        top = engine.get_top_performers(n=3, min_uses=5)
        assert len(top) == 0  # Only 2 uses, need 5

    def test_get_underperformers(self, engine: PromptEvolutionEngine):
        """Underperformers have avg tier >= 3.5."""
        for i in range(6):
            engine.record_outcome("seed_inversion", f"u_{i}", tier=4, score=0.1)
        for i in range(6):
            engine.record_outcome("seed_first_principles", f"g_{i}", tier=1, score=0.9)

        under = engine.get_underperformers(max_avg_tier=3.5, min_uses=5)
        assert len(under) == 1
        assert under[0]["template_id"] == "seed_inversion"

    def test_get_underperformers_none(self, engine: PromptEvolutionEngine):
        """No underperformers when all templates perform well."""
        for i in range(6):
            engine.record_outcome("seed_first_principles", f"e_{i}", tier=1, score=0.9)
        under = engine.get_underperformers(min_uses=5)
        assert under == []

    def test_generate_mutations_count(self, engine: PromptEvolutionEngine):
        """Generates the requested number of mutations."""
        mutations = engine.generate_mutations("seed_first_principles", n_mutations=4)
        assert len(mutations) == 4

    def test_generate_mutations_valid_type(self, engine: PromptEvolutionEngine):
        """Each mutation has a valid mutation_type."""
        valid_types = {"constrain", "extend", "combine", "invert", "specialize", "abstract"}
        mutations = engine.generate_mutations("seed_first_principles", n_mutations=10)
        for m in mutations:
            assert m["mutation_type"] in valid_types

    def test_generate_mutations_lineage(self, engine: PromptEvolutionEngine):
        """Mutations have correct parent_id pointing to source."""
        mutations = engine.generate_mutations("seed_first_principles", n_mutations=3)
        for m in mutations:
            assert m["parent_id"] == "seed_first_principles"
            assert m["generation"] == 1
            assert len(m["mutation_history"]) >= 1

    def test_generate_mutations_unique_ids(self, engine: PromptEvolutionEngine):
        """Each mutation gets a unique ID."""
        mutations = engine.generate_mutations("seed_first_principles", n_mutations=5)
        ids = [m["id"] for m in mutations]
        assert len(ids) == len(set(ids))

    def test_generate_mutations_nonexistent_template(self, engine: PromptEvolutionEngine):
        """Mutating a nonexistent template raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            engine.generate_mutations("nonexistent_template")

    def test_mutation_constrain(self, engine: PromptEvolutionEngine):
        """Constrain mutation appends to the template text."""
        random.seed(42)
        source = engine._registry.get_by_id("seed_first_principles")
        mutated = engine._apply_mutation(source, "constrain")
        assert len(mutated["template"]) > len(source["template"])
        assert mutated["mutation_type"] == "constrain"

    def test_mutation_extend(self, engine: PromptEvolutionEngine):
        """Extend mutation appends a follow-up step."""
        random.seed(42)
        source = engine._registry.get_by_id("seed_first_principles")
        mutated = engine._apply_mutation(source, "extend")
        assert len(mutated["template"]) > len(source["template"])
        assert mutated["mutation_type"] == "extend"

    def test_mutation_combine(self, engine: PromptEvolutionEngine):
        """Combine mutation merges two templates."""
        random.seed(42)
        source = engine._registry.get_by_id("seed_first_principles")
        mutated = engine._apply_mutation(source, "combine")
        assert mutated["template"] != source["template"]
        assert mutated["mutation_type"] == "combine"

    def test_mutation_invert(self, engine: PromptEvolutionEngine):
        """Invert mutation produces a different template."""
        random.seed(42)
        source = engine._registry.get_by_id("seed_first_principles")
        mutated = engine._apply_mutation(source, "invert")
        assert mutated["mutation_type"] == "invert"

    def test_mutation_specialize(self, engine: PromptEvolutionEngine):
        """Specialize mutation adds domain-specific framing."""
        random.seed(42)
        source = engine._registry.get_by_id("seed_first_principles")
        mutated = engine._apply_mutation(source, "specialize")
        assert len(mutated["template"]) > len(source["template"])
        assert mutated["mutation_type"] == "specialize"

    def test_mutation_abstract(self, engine: PromptEvolutionEngine):
        """Abstract mutation generalizes the template."""
        random.seed(42)
        source = engine._registry.get_by_id("seed_first_principles")
        mutated = engine._apply_mutation(source, "abstract")
        assert mutated["mutation_type"] == "abstract"

    def test_mutation_of_mutated_template(self, engine: PromptEvolutionEngine, registry: PromptTemplateRegistry):
        """Mutating an already-mutated template increments generation correctly."""
        gen1 = engine.generate_mutations("seed_first_principles", n_mutations=1)[0]
        registry.add_template(gen1)
        assert gen1["generation"] == 1

        gen2 = engine.generate_mutations(gen1["id"], n_mutations=1)[0]
        assert gen2["generation"] == 2
        assert gen2["parent_id"] == gen1["id"]
        assert len(gen2["mutation_history"]) == 2

    def test_evolve_cycle_insufficient_data(self, engine: PromptEvolutionEngine):
        """Evolve cycle returns early when not enough experiments."""
        result = engine.evolve_cycle(min_experiments=10)
        assert result["skipped"] is True
        assert result["new_templates"] == []

    def test_evolve_cycle_produces_templates(self, engine: PromptEvolutionEngine):
        """Evolve cycle with enough data produces new templates."""
        # Record 12 outcomes across templates
        for i in range(6):
            engine.record_outcome("seed_first_principles", f"e_fp_{i}", tier=1, score=0.9)
        for i in range(6):
            engine.record_outcome("seed_inversion", f"e_inv_{i}", tier=2, score=0.7)

        result = engine.evolve_cycle(min_experiments=10)
        assert result["skipped"] is False
        assert len(result["new_templates"]) > 0
        assert len(result["top_performers"]) > 0

    def test_evolve_cycle_retires_bad_templates(self, engine: PromptEvolutionEngine, registry: PromptTemplateRegistry):
        """Evolve cycle retires templates with avg_tier > 3.5 and 10+ uses."""
        # Create an evolved template that performs badly
        bad_template = {
            "id": "evolved_bad_001",
            "name": "Bad Template",
            "template": "This template is terrible for {topic}.",
            "thinking_pattern": "first_principles",
            "parent_id": "seed_first_principles",
            "generation": 1,
            "mutation_history": [{"type": "constrain"}],
        }
        registry.add_template(bad_template)
        engine._persist_evolved_template(bad_template)

        # Give it 12 bad outcomes (need 10+ for retirement)
        for i in range(12):
            engine.record_outcome("evolved_bad_001", f"bad_{i}", tier=4, score=0.1)

        # Also need enough good outcomes for top performers
        for i in range(6):
            engine.record_outcome("seed_first_principles", f"good_{i}", tier=1, score=0.9)

        # Reset counter so evolve_cycle doesn't skip
        engine._last_evolution_experiment_count = 0

        result = engine.evolve_cycle(min_experiments=10)
        assert "evolved_bad_001" in result["retired"]

    def test_evolve_cycle_never_retires_seeds(self, engine: PromptEvolutionEngine):
        """Seed templates are never retired, even with bad performance."""
        for i in range(12):
            engine.record_outcome("seed_inversion", f"seed_bad_{i}", tier=4, score=0.1)
        for i in range(6):
            engine.record_outcome("seed_first_principles", f"good_{i}", tier=1, score=0.9)

        engine._last_evolution_experiment_count = 0
        result = engine.evolve_cycle(min_experiments=10)
        assert "seed_inversion" not in result["retired"]


# ===================================================================
# TestSelectTemplate
# ===================================================================


class TestSelectTemplate:
    def test_select_returns_valid_template(self, engine: PromptEvolutionEngine, registry: PromptTemplateRegistry):
        """Selected template exists in registry."""
        selected = engine.select_template()
        assert registry.get_by_id(selected["id"]) is not None

    def test_select_all_seeds_eligible(self, engine: PromptEvolutionEngine):
        """Before any outcomes, all seeds are eligible (equal weight)."""
        random.seed(42)
        seen_ids = set()
        for _ in range(200):
            t = engine.select_template()
            seen_ids.add(t["id"])
        # With 200 draws from 8 equally-weighted items, we should see most
        assert len(seen_ids) >= 6

    def test_select_favors_high_performers(self, engine: PromptEvolutionEngine):
        """Top-tier templates are selected more often (statistical test)."""
        # Make first_principles a clear winner
        for i in range(10):
            engine.record_outcome("seed_first_principles", f"win_{i}", tier=1, score=0.95)
        # Make inversion a clear loser
        for i in range(10):
            engine.record_outcome("seed_inversion", f"lose_{i}", tier=4, score=0.1)

        random.seed(42)
        counts: Counter = Counter()
        for _ in range(500):
            t = engine.select_template()
            counts[t["id"]] += 1

        # first_principles (tier 1, weight=4.0) should be picked much more than
        # inversion (tier 4, weight=max(1.0, 0.5)=1.0)
        assert counts["seed_first_principles"] > counts["seed_inversion"]

    def test_select_novelty_bonus(self, engine: PromptEvolutionEngine, registry: PromptTemplateRegistry):
        """Templates with < 5 uses get a novelty bonus."""
        # Give most templates many uses with mediocre performance
        seeds = [t for t in registry.get_all() if t["id"] != "seed_speculative_extension"]
        for seed in seeds:
            for i in range(10):
                engine.record_outcome(seed["id"], f"{seed['id']}_{i}", tier=3, score=0.5)

        # speculative_extension has 0 uses — should get novelty bonus (weight=3.0)
        random.seed(42)
        counts: Counter = Counter()
        for _ in range(500):
            t = engine.select_template()
            counts[t["id"]] += 1

        # The unused template should be selected at a reasonable rate
        spec_count = counts.get("seed_speculative_extension", 0)
        avg_others = sum(c for tid, c in counts.items() if tid != "seed_speculative_extension") / max(len(counts) - 1, 1)
        # Novelty bonus (3.0) vs mediocre (5-3=2.0), so should be selected >= average
        assert spec_count > avg_others * 0.5  # At least half as often as average

    def test_select_never_fully_excludes(self, engine: PromptEvolutionEngine):
        """Even the worst performer has a non-zero selection chance."""
        for i in range(10):
            engine.record_outcome("seed_inversion", f"worst_{i}", tier=4, score=0.05)
        for i in range(10):
            engine.record_outcome("seed_first_principles", f"best_{i}", tier=1, score=0.95)

        random.seed(42)
        seen = set()
        for _ in range(1000):
            t = engine.select_template()
            seen.add(t["id"])

        # Inversion should still appear despite being worst
        assert "seed_inversion" in seen

    def test_select_with_no_performance_data(self, engine: PromptEvolutionEngine):
        """Selection works with no performance data (all equal weight)."""
        selected = engine.select_template()
        assert selected is not None
        assert "id" in selected

    def test_load_evolved_templates(self, engine: PromptEvolutionEngine, registry: PromptTemplateRegistry):
        """Persisted evolved templates reload correctly."""
        # Create and persist
        mutations = engine.generate_mutations("seed_first_principles", n_mutations=2)
        for m in mutations:
            engine._persist_evolved_template(m)

        # Load
        loaded = engine.load_evolved_templates()
        assert len(loaded) == 2
        for t in loaded:
            assert "id" in t
            assert "template" in t
            assert t["generation"] == 1

    def test_load_evolved_excludes_inactive(self, engine: PromptEvolutionEngine):
        """Inactive (retired) templates are not loaded."""
        mutations = engine.generate_mutations("seed_first_principles", n_mutations=2)
        for m in mutations:
            engine._persist_evolved_template(m)

        # Retire one
        engine._conn.execute(
            "UPDATE evolved_templates SET active=0 WHERE id=?",
            (mutations[0]["id"],),
        )
        engine._conn.commit()

        loaded = engine.load_evolved_templates()
        assert len(loaded) == 1
        assert loaded[0]["id"] == mutations[1]["id"]


# ===================================================================
# TestMorpheusIntegration
# ===================================================================


class TestMorpheusIntegration:
    @pytest.mark.asyncio
    async def test_tool_count(self, online_morpheus: Morpheus):
        """Morpheus now has 9 tools (7 original + 2 evolution)."""
        tools = online_morpheus.get_tools()
        assert len(tools) == 9

    @pytest.mark.asyncio
    async def test_new_tool_names(self, online_morpheus: Morpheus):
        """prompt_evolve and prompt_stats are in tool list."""
        names = {t["name"] for t in online_morpheus.get_tools()}
        assert "prompt_evolve" in names
        assert "prompt_stats" in names

    @pytest.mark.asyncio
    async def test_propose_gets_template_id(self, online_morpheus: Morpheus):
        """Proposed experiments get a template_id auto-assigned."""
        r = await _propose(online_morpheus)
        assert r.success
        assert r.content.get("template_id") is not None

    @pytest.mark.asyncio
    async def test_propose_with_explicit_template_id(self, online_morpheus: Morpheus):
        """Can pass a specific template_id."""
        r = await _propose(online_morpheus, template_id="seed_inversion")
        assert r.success
        assert r.content["template_id"] == "seed_inversion"

    @pytest.mark.asyncio
    async def test_propose_template_id_optional(self, online_morpheus: Morpheus):
        """template_id is optional — doesn't break existing callers."""
        r = await online_morpheus.execute("experiment_propose", {
            "title": "Backward compat test",
            "hypothesis": "Old callers still work",
            "category": "validation",
        })
        assert r.success

    @pytest.mark.asyncio
    async def test_evaluate_records_outcome(self, online_morpheus: Morpheus):
        """Evaluating an experiment records outcome in evolution engine."""
        eid = await _full_lifecycle(online_morpheus, template_id="seed_first_principles")
        r = await online_morpheus.execute("experiment_evaluate", {
            "experiment_id": eid,
            "score": 0.85,
            "tier": 1,
        })
        assert r.success

        # Check the outcome was recorded
        stats = online_morpheus._evolution.get_template_stats()
        fp_stats = next(
            (s for s in stats if s["template_id"] == "seed_first_principles"),
            None,
        )
        assert fp_stats is not None
        assert fp_stats["total_uses"] == 1

    @pytest.mark.asyncio
    async def test_prompt_stats_tool(self, online_morpheus: Morpheus):
        """prompt_stats tool returns stats data."""
        r = await online_morpheus.execute("prompt_stats", {})
        assert r.success
        assert "all_stats" in r.content
        assert "top_performers" in r.content
        assert "total_templates" in r.content

    @pytest.mark.asyncio
    async def test_prompt_stats_specific_template(self, online_morpheus: Morpheus):
        """prompt_stats with template_id returns single template data."""
        r = await online_morpheus.execute("prompt_stats", {
            "template_id": "seed_first_principles",
        })
        assert r.success
        # No data yet, so message about no performance data
        assert r.content.get("message") == "No performance data" or r.content.get("template_id") == "seed_first_principles"

    @pytest.mark.asyncio
    async def test_prompt_evolve_insufficient_data(self, online_morpheus: Morpheus):
        """prompt_evolve with insufficient experiments returns skipped."""
        r = await online_morpheus.execute("prompt_evolve", {"min_experiments": 100})
        assert r.success
        assert r.content["skipped"] is True

    @pytest.mark.asyncio
    async def test_prompt_evolve_tool(self, online_morpheus: Morpheus):
        """prompt_evolve produces new templates after enough experiments."""
        # Run 12 experiments through full lifecycle
        for i in range(12):
            eid = await _full_lifecycle(
                online_morpheus,
                title=f"Evo test {i}",
                template_id="seed_first_principles",
            )
            await online_morpheus.execute("experiment_evaluate", {
                "experiment_id": eid,
                "score": 0.8,
                "tier": 1 if i < 6 else 2,
            })

        r = await online_morpheus.execute("prompt_evolve", {"min_experiments": 10})
        assert r.success
        assert r.content["skipped"] is False
        assert len(r.content["new_templates"]) > 0

    @pytest.mark.asyncio
    async def test_full_evolution_lifecycle(self, online_morpheus: Morpheus):
        """Full cycle: propose with template -> evaluate -> evolve -> propose with evolved."""
        # Phase 1: build performance data
        for i in range(12):
            eid = await _full_lifecycle(
                online_morpheus,
                title=f"Phase1 exp {i}",
                template_id="seed_first_principles",
            )
            await online_morpheus.execute("experiment_evaluate", {
                "experiment_id": eid,
                "score": 0.9,
                "tier": 1,
            })

        # Phase 2: evolve
        evolve_r = await online_morpheus.execute("prompt_evolve", {"min_experiments": 10})
        assert evolve_r.success
        new_templates = evolve_r.content["new_templates"]
        assert len(new_templates) > 0

        # Phase 3: propose using an evolved template
        evolved_id = new_templates[0]["id"]
        r = await _propose(online_morpheus, template_id=evolved_id)
        assert r.success
        assert r.content["template_id"] == evolved_id

    @pytest.mark.asyncio
    async def test_template_id_column_exists(self, online_morpheus: Morpheus):
        """Schema migration added template_id column to morpheus_experiments."""
        row = online_morpheus._conn.execute(
            "PRAGMA table_info(morpheus_experiments)"
        ).fetchall()
        columns = {r["name"] for r in row}
        assert "template_id" in columns
