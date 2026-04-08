"""
Tests for Morpheus R&D Lab — idea-to-implementation pipeline.
"""

from __future__ import annotations

import json
import time
import pytest
from unittest.mock import MagicMock, patch

from modules.morpheus.rd_lab import RDLab, ExplorationReport, SPECULATION_COLLECTION
from unittest.mock import call


# --- Fixtures ---


@pytest.fixture
def mock_generate_fn():
    """Generate function that returns valid hypothesis JSON."""
    def gen(prompt):
        return json.dumps([
            {
                "hypothesis": "Combining caching from web domain with ML inference",
                "domains": ["web", "ml"],
                "testable": True,
                "test_approach": "Benchmark inference with and without caching layer",
            },
            {
                "hypothesis": "Apply landscaping scheduling heuristics to task queuing",
                "domains": ["landscaping", "scheduling"],
                "testable": False,
                "test_approach": "Theoretical comparison of scheduling approaches",
            },
        ])
    return gen


@pytest.fixture
def mock_grimoire():
    """Mock Grimoire with domain-filtered random entries and store."""
    grimoire = MagicMock()

    def _get_random_entries(count=5, domain=None):
        """Return entries tagged with the requested domain."""
        if domain:
            return [
                {"domain": domain, "content": f"Knowledge from {domain} domain"}
                for _ in range(count)
            ]
        return [
            {"domain": "code", "content": "HTTP caching reduces latency by 40%"},
            {"domain": "security", "content": "Batch inference improves throughput"},
            {"domain": "optimization", "content": "Route optimization saves fuel"},
        ]

    grimoire.get_random_entries.side_effect = _get_random_entries
    grimoire.store.return_value = "doc-123"
    return grimoire


@pytest.fixture
def mock_experiment_store():
    """Mock ExperimentStore."""
    store = MagicMock()
    store.store_failure.return_value = "exp-abc"
    return store


@pytest.fixture
def mock_sandbox():
    """Mock sandbox that returns successful execution."""
    sandbox = MagicMock()
    sandbox.execute.return_value = {
        "success": True,
        "output": "Caching improved inference by 35%",
        "metrics": {"improvement": 0.35, "novel": True},
    }
    return sandbox


@pytest.fixture
def lab(mock_generate_fn, mock_grimoire, mock_experiment_store, mock_sandbox):
    """Fully configured RDLab."""
    return RDLab(
        generate_fn=mock_generate_fn,
        grimoire=mock_grimoire,
        experiment_store=mock_experiment_store,
        sandbox=mock_sandbox,
    )


@pytest.fixture
def lab_no_sandbox(mock_generate_fn, mock_grimoire, mock_experiment_store):
    """RDLab without sandbox."""
    return RDLab(
        generate_fn=mock_generate_fn,
        grimoire=mock_grimoire,
        experiment_store=mock_experiment_store,
        sandbox=None,
    )


@pytest.fixture
def lab_no_grimoire(mock_generate_fn, mock_experiment_store):
    """RDLab without Grimoire."""
    return RDLab(
        generate_fn=mock_generate_fn,
        grimoire=None,
        experiment_store=mock_experiment_store,
    )


# --- Exploration Session Tests ---


class TestRunExplorationSession:
    """Tests for the full exploration session pipeline."""

    def test_generates_hypotheses_from_random_knowledge(self, lab, mock_grimoire):
        """Session pulls domain-filtered knowledge and generates hypotheses."""
        report = lab.run_exploration_session(duration_minutes=5)
        # Called once per selected domain (3 domains)
        assert mock_grimoire.get_random_entries.call_count == 3
        assert report.ideas_generated == 2

    def test_runs_testable_experiments_in_sandbox(self, lab, mock_sandbox):
        """Session runs testable hypotheses through sandbox."""
        report = lab.run_exploration_session(duration_minutes=5)
        assert mock_sandbox.execute.called
        assert report.experiments_run >= 1

    def test_stores_failures_in_experiment_store(self, mock_grimoire, mock_experiment_store):
        """Failed experiments are stored in experiment_store."""
        def gen_fn(prompt):
            return json.dumps([{
                "hypothesis": "Bad idea",
                "domains": ["test"],
                "testable": True,
                "test_approach": "Run test",
            }])

        sandbox = MagicMock()
        sandbox.execute.return_value = {
            "success": False,
            "output": "Test failed",
            "metrics": {},
        }

        lab = RDLab(
            generate_fn=gen_fn,
            grimoire=mock_grimoire,
            experiment_store=mock_experiment_store,
            sandbox=sandbox,
        )
        report = lab.run_exploration_session(duration_minutes=5)
        assert report.failures_stored >= 1

    def test_exploration_report_has_all_fields(self, lab):
        """ExplorationReport has all required fields."""
        report = lab.run_exploration_session(duration_minutes=5)
        assert isinstance(report, ExplorationReport)
        assert isinstance(report.session_id, str)
        assert isinstance(report.duration_minutes, float)
        assert isinstance(report.ideas_generated, int)
        assert isinstance(report.experiments_run, int)
        assert isinstance(report.discoveries_validated, int)
        assert isinstance(report.discoveries_speculative, int)
        assert isinstance(report.failures_stored, int)
        assert isinstance(report.serendipitous_findings, int)
        assert isinstance(report.timestamp, float)

    def test_session_with_validated_discovery(self, lab, mock_grimoire):
        """Validated discoveries are graduated to production Grimoire."""
        report = lab.run_exploration_session(duration_minutes=5)
        assert report.discoveries_validated >= 1
        # Grimoire.store should have been called for graduation
        assert mock_grimoire.store.called


# --- Hypothesis Generation Tests ---


class TestGenerateHypotheses:
    """Tests for hypothesis generation."""

    def test_produces_2_3_hypotheses(self, lab):
        """generate_hypotheses returns 2-3 hypotheses."""
        entries = [
            {"domain": "web", "content": "caching"},
            {"domain": "ml", "content": "inference"},
        ]
        hypotheses = lab.generate_hypotheses(entries)
        assert 2 <= len(hypotheses) <= 3

    def test_hypotheses_reference_multiple_domains(self, lab):
        """Each hypothesis references at least one domain."""
        entries = [
            {"domain": "web", "content": "caching"},
            {"domain": "ml", "content": "inference"},
        ]
        hypotheses = lab.generate_hypotheses(entries)
        for h in hypotheses:
            assert "domains" in h
            assert len(h["domains"]) >= 1

    def test_each_hypothesis_has_testable_flag(self, lab):
        """Each hypothesis has a testable boolean."""
        entries = [{"domain": "a", "content": "x"}]
        hypotheses = lab.generate_hypotheses(entries)
        for h in hypotheses:
            assert "testable" in h
            assert isinstance(h["testable"], bool)

    def test_no_generate_fn_raises(self):
        """generate_hypotheses raises RuntimeError without generate_fn."""
        lab = RDLab(generate_fn=None)
        with pytest.raises(RuntimeError, match="No generate_fn"):
            lab.generate_hypotheses([{"domain": "a", "content": "x"}])

    def test_unparseable_output_returns_empty(self):
        """If model returns garbage, generate_hypotheses returns empty list."""
        lab = RDLab(generate_fn=lambda p: "this is not json at all")
        entries = [{"domain": "a", "content": "x"}]
        hypotheses = lab.generate_hypotheses(entries)
        assert hypotheses == []

    def test_json_embedded_in_text(self):
        """Can extract JSON array embedded in surrounding text."""
        def gen_fn(prompt):
            return 'Here are my hypotheses:\n[{"hypothesis": "test", "domains": ["a"], "testable": true, "test_approach": "try it"}]\nDone!'

        lab = RDLab(generate_fn=gen_fn)
        hypotheses = lab.generate_hypotheses([{"domain": "a", "content": "x"}])
        assert len(hypotheses) == 1
        assert hypotheses[0]["hypothesis"] == "test"


# --- Experiment Tests ---


class TestRunExperiment:
    """Tests for running individual experiments."""

    def test_testable_hypothesis_runs_sandbox(self, lab, mock_sandbox):
        """Testable hypothesis with sandbox runs the experiment."""
        hypothesis = {
            "hypothesis": "Caching helps",
            "domains": ["web"],
            "testable": True,
            "test_approach": "Benchmark",
        }
        result = lab.run_experiment(hypothesis)
        assert result["tested"] is True
        assert result["success"] is True
        mock_sandbox.execute.assert_called_once()

    def test_non_testable_stores_speculative(self, lab):
        """Non-testable hypothesis stored as speculative."""
        hypothesis = {
            "hypothesis": "Theoretical idea",
            "domains": ["theory"],
            "testable": False,
            "test_approach": "Think about it",
        }
        result = lab.run_experiment(hypothesis)
        assert result["tested"] is False
        assert "Speculative" in result["result"]

    def test_no_sandbox_stores_speculative(self, lab_no_sandbox):
        """Testable hypothesis without sandbox stored as speculative."""
        hypothesis = {
            "hypothesis": "Needs testing",
            "domains": ["code"],
            "testable": True,
            "test_approach": "Run code",
        }
        result = lab_no_sandbox.run_experiment(hypothesis)
        assert result["tested"] is False

    def test_experiment_result_has_all_fields(self, lab):
        """Experiment result contains all required keys."""
        hypothesis = {
            "hypothesis": "Test",
            "domains": ["a"],
            "testable": True,
            "test_approach": "Run",
        }
        result = lab.run_experiment(hypothesis)
        assert "hypothesis" in result
        assert "tested" in result
        assert "result" in result
        assert "success" in result
        assert "metrics" in result

    def test_sandbox_exception_returns_failure(self):
        """Sandbox that throws returns a failure result."""
        sandbox = MagicMock()
        sandbox.execute.side_effect = RuntimeError("sandbox crash")

        lab = RDLab(
            generate_fn=lambda p: "print('hi')",
            sandbox=sandbox,
        )
        hypothesis = {
            "hypothesis": "Crash test",
            "domains": ["test"],
            "testable": True,
            "test_approach": "Will crash",
        }
        result = lab.run_experiment(hypothesis)
        assert result["tested"] is True
        assert result["success"] is False
        assert "Sandbox error" in result["result"]


# --- Validation Tests ---


class TestValidateDiscovery:
    """Tests for discovery validation."""

    def test_genuine_improvement_validates(self, lab):
        """Genuine improvement with metrics passes validation."""
        result = {
            "success": True,
            "tested": True,
            "metrics": {"improvement": 0.3, "novel": True},
        }
        assert lab.validate_discovery(result) is True

    def test_trivial_result_rejected(self, lab):
        """Trivial result is rejected."""
        result = {
            "success": True,
            "tested": True,
            "metrics": {"trivial": True, "improvement": 0},
        }
        assert lab.validate_discovery(result) is False

    def test_failed_experiment_rejected(self, lab):
        """Failed experiment can't be validated."""
        result = {
            "success": False,
            "tested": True,
            "metrics": {"improvement": 0.5},
        }
        assert lab.validate_discovery(result) is False

    def test_untested_rejected(self, lab):
        """Untested hypothesis can't be validated."""
        result = {
            "success": True,
            "tested": False,
            "metrics": {"improvement": 0.5},
        }
        assert lab.validate_discovery(result) is False

    def test_no_metrics_rejected(self, lab):
        """Result with empty metrics rejected."""
        result = {
            "success": True,
            "tested": True,
            "metrics": {},
        }
        assert lab.validate_discovery(result) is False

    def test_graduate_to_production_stores_in_grimoire(self, lab, mock_grimoire):
        """graduate_to_production stores in production Grimoire with tags."""
        discovery = {
            "hypothesis": "Caching helps ML",
            "result": "35% improvement",
            "domains": ["web", "ml"],
            "metrics": {"improvement": 0.35},
        }
        doc_id = lab.graduate_to_production(discovery)
        assert doc_id == "doc-123"
        mock_grimoire.store.assert_called()
        call_kwargs = mock_grimoire.store.call_args
        assert "morpheus_discovery" in str(call_kwargs)

    def test_speculative_uses_separate_collection(self, lab, mock_grimoire):
        """Speculative storage uses the speculative collection, not production."""
        result = {
            "hypothesis": "Speculative idea",
            "result": "Untested",
            "domains": ["theory"],
        }
        lab._store_speculative(result)
        mock_grimoire.store.assert_called()
        call_kwargs = mock_grimoire.store.call_args
        # Should use the speculative collection
        assert SPECULATION_COLLECTION in str(call_kwargs)


# --- Decision Tests ---


class TestShouldExplore:
    """Tests for should_explore decision logic."""

    def test_no_pending_tasks_returns_true(self, lab):
        """No pending tasks, no curriculum, low fatigue → explore."""
        lab.pending_tasks = 0
        lab.active_curriculum = False
        lab.fatigue = 0.0
        assert lab.should_explore() is True

    def test_pending_tasks_returns_false(self, lab):
        """Pending tasks prevent exploration."""
        lab.pending_tasks = 3
        assert lab.should_explore() is False

    def test_high_fatigue_returns_false(self, lab):
        """High fatigue prevents exploration."""
        lab.pending_tasks = 0
        lab.fatigue = 0.8
        assert lab.should_explore() is False

    def test_active_curriculum_returns_false(self, lab):
        """Active learning curriculum prevents exploration."""
        lab.pending_tasks = 0
        lab.active_curriculum = True
        assert lab.should_explore() is False

    def test_cooldown_returns_false(self, lab):
        """Cooldown period prevents exploration."""
        lab.pending_tasks = 0
        lab.cooldown_until = time.time() + 3600
        assert lab.should_explore() is False


# --- Stats Tests ---


class TestGetExplorationStats:
    """Tests for exploration statistics."""

    def test_stats_after_session(self, lab):
        """Stats are updated after running a session."""
        lab.run_exploration_session(duration_minutes=5)
        stats = lab.get_exploration_stats()
        assert stats["total_sessions"] == 1
        assert stats["total_hypotheses"] >= 1
        assert isinstance(stats["validation_rate"], float)
        assert isinstance(stats["discoveries_graduated"], int)
        assert isinstance(stats["domains_explored"], list)

    def test_initial_stats_zero(self):
        """Fresh lab has zeroed stats."""
        lab = RDLab()
        stats = lab.get_exploration_stats()
        assert stats["total_sessions"] == 0
        assert stats["total_hypotheses"] == 0
        assert stats["validation_rate"] == 0.0
        assert stats["discoveries_graduated"] == 0


# --- Domain Filtering Tests ---


class TestDomainFiltering:
    """Tests for technical domain filtering in knowledge pulls."""

    def test_only_technical_domains_queried(self, lab, mock_grimoire):
        """Only allowed technical domains are queried from Grimoire."""
        lab.run_exploration_session(duration_minutes=5)
        for c in mock_grimoire.get_random_entries.call_args_list:
            domain = c.kwargs.get("domain") or (c.args[1] if len(c.args) > 1 else None)
            assert domain in RDLab.EXPLORATION_DOMAINS, (
                f"Queried non-technical domain: {domain}"
            )

    def test_entries_come_from_different_domains(self, lab, mock_grimoire):
        """Knowledge entries are pulled from multiple distinct domains."""
        lab.run_exploration_session(duration_minutes=5)
        queried_domains = set()
        for c in mock_grimoire.get_random_entries.call_args_list:
            domain = c.kwargs.get("domain")
            if domain:
                queried_domains.add(domain)
        assert len(queried_domains) == 3, (
            f"Expected 3 different domains, got {len(queried_domains)}: {queried_domains}"
        )

    def test_personal_domains_never_pulled(self, lab, mock_grimoire):
        """Personal and non-technical domains are never queried."""
        excluded = {
            "personal", "reminders", "contacts", "schedule",
            "esv", "scratchpad_archive",
        }
        # Run multiple sessions to increase coverage
        for _ in range(10):
            lab.run_exploration_session(duration_minutes=5)
        for c in mock_grimoire.get_random_entries.call_args_list:
            domain = c.kwargs.get("domain")
            assert domain not in excluded, (
                f"Pulled from excluded domain: {domain}"
            )

    def test_exploration_domains_constant_exists(self):
        """EXPLORATION_DOMAINS is a class-level constant with expected entries."""
        assert hasattr(RDLab, "EXPLORATION_DOMAINS")
        assert "code" in RDLab.EXPLORATION_DOMAINS
        assert "security" in RDLab.EXPLORATION_DOMAINS
        assert "personal" not in RDLab.EXPLORATION_DOMAINS
        assert "reminders" not in RDLab.EXPLORATION_DOMAINS


# --- Edge Case Tests ---


class TestEdgeCases:
    """Edge case tests for RDLab."""

    def test_no_grimoire_returns_empty_session(self, lab_no_grimoire):
        """Without Grimoire, exploration returns empty report."""
        report = lab_no_grimoire.run_exploration_session(duration_minutes=5)
        assert report.ideas_generated == 0
        assert report.experiments_run == 0

    def test_no_sandbox_stores_speculative_only(self, lab_no_sandbox, mock_grimoire):
        """Without sandbox, all hypotheses stored as speculative."""
        report = lab_no_sandbox.run_exploration_session(duration_minutes=5)
        assert report.discoveries_validated == 0
        assert report.discoveries_speculative >= 1

    def test_generate_fn_failure_partial_report(self, mock_grimoire, mock_experiment_store):
        """If generate_fn throws, session ends with partial report."""
        def failing_gen(prompt):
            raise RuntimeError("Model crashed")

        lab = RDLab(
            generate_fn=failing_gen,
            grimoire=mock_grimoire,
            experiment_store=mock_experiment_store,
        )
        report = lab.run_exploration_session(duration_minutes=5)
        assert report.ideas_generated == 0
        assert report.experiments_run == 0

    def test_empty_knowledge_pull_clean_exit(self, mock_experiment_store):
        """Empty knowledge pull results in clean exit with no hypotheses."""
        grimoire = MagicMock()
        grimoire.get_random_entries.side_effect = lambda count=5, domain=None: []

        lab = RDLab(
            generate_fn=lambda p: "[]",
            grimoire=grimoire,
            experiment_store=mock_experiment_store,
        )
        report = lab.run_exploration_session(duration_minutes=5)
        assert report.ideas_generated == 0
        assert report.experiments_run == 0

    def test_graduate_without_grimoire_returns_empty(self):
        """Graduate without Grimoire returns empty string."""
        lab = RDLab()
        result = lab.graduate_to_production({"hypothesis": "test"})
        assert result == ""
