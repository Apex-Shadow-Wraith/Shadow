"""
Tests for ExperimentStore — Failed Experiment Knowledge Base with Retry Triggers.
"""

import json
import os
import tempfile
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest

from modules.morpheus.experiment_store import Experiment, ExperimentStore


@pytest.fixture
def tmp_db(tmp_path):
    """Return a path to a temporary database file."""
    return str(tmp_path / "test_experiments.db")


@pytest.fixture
def store(tmp_db):
    """Create an ExperimentStore with a temporary database."""
    s = ExperimentStore(db_path=tmp_db)
    yield s
    s.close()


@pytest.fixture
def mock_grimoire():
    """Create a mock Grimoire module."""
    g = MagicMock()
    g.store = MagicMock(return_value="stored_id")
    return g


@pytest.fixture
def store_with_grimoire(tmp_db, mock_grimoire):
    """Create an ExperimentStore with a mock Grimoire."""
    s = ExperimentStore(grimoire=mock_grimoire, db_path=tmp_db)
    yield s
    s.close()


def _make_experiment(
    success=False,
    status="failed",
    failure_reason="out of memory",
    retry_triggers=None,
    conditions=None,
    domain_tags=None,
    attempt_count=1,
    attempt_history=None,
    deprioritized=False,
) -> Experiment:
    """Helper to create an Experiment with sensible defaults."""
    now = time.time()
    exp_id = str(uuid.uuid4())
    if conditions is None:
        conditions = {"model": "phi4-mini"}
    if retry_triggers is None:
        retry_triggers = ["model_changed"]
    if domain_tags is None:
        domain_tags = ["cuda", "optimization"]
    if attempt_history is None:
        attempt_history = [{
            "attempt": 1,
            "date": now,
            "conditions": conditions,
            "result": failure_reason if not success else "success",
        }]
    return Experiment(
        id=exp_id,
        hypothesis="CUDA kernels can speed up embedding generation",
        approach="Replace numpy ops with CUDA kernels",
        domain_tags=domain_tags,
        result="" if not success else "Worked great",
        success=success,
        failure_reason=failure_reason if not success else "",
        conditions=conditions,
        retry_triggers=retry_triggers,
        attempt_count=attempt_count,
        attempt_history=attempt_history,
        created_at=now,
        last_attempted=now,
        status=status,
        deprioritized=deprioritized,
    )


class TestStoreExperiment:
    """Tests for store_experiment."""

    def test_persists_to_sqlite(self, store):
        """store_experiment persists to SQLite and returns the ID."""
        exp = _make_experiment()
        result_id = store.store_experiment(exp)
        assert result_id == exp.id

        # Verify it's in the DB
        row = store._conn.execute(
            "SELECT * FROM failed_experiments WHERE id=?", (exp.id,)
        ).fetchone()
        assert row is not None
        assert row["hypothesis"] == exp.hypothesis
        assert row["approach"] == exp.approach
        assert json.loads(row["domain_tags"]) == exp.domain_tags
        assert row["status"] == "failed"

    def test_success_stores_in_grimoire(self, store_with_grimoire, mock_grimoire):
        """store_experiment with success=True stores findings in Grimoire."""
        exp = _make_experiment(success=True, status="succeeded")
        store_with_grimoire.store_experiment(exp)

        mock_grimoire.store.assert_called_once()
        call_kwargs = mock_grimoire.store.call_args
        assert call_kwargs[1]["category"] == "experiment_result"
        assert exp.id in call_kwargs[1]["source"]

    def test_failure_does_not_store_in_grimoire(self, store_with_grimoire, mock_grimoire):
        """store_experiment with success=False does not call Grimoire."""
        exp = _make_experiment(success=False)
        store_with_grimoire.store_experiment(exp)
        mock_grimoire.store.assert_not_called()


class TestStoreFailure:
    """Tests for store_failure."""

    def test_creates_correct_experiment(self, store):
        """store_failure creates an Experiment with success=False, attempt_count=1."""
        exp_id = store.store_failure(
            hypothesis="Test hypothesis",
            approach="Test approach",
            domain_tags=["testing"],
            failure_reason="It broke",
            conditions={"model": "phi4-mini"},
            retry_triggers=["model_changed"],
        )
        assert exp_id is not None

        row = store._conn.execute(
            "SELECT * FROM failed_experiments WHERE id=?", (exp_id,)
        ).fetchone()
        assert row is not None
        assert row["success"] == 0
        assert row["attempt_count"] == 1
        assert row["status"] == "failed"
        assert row["failure_reason"] == "It broke"
        assert row["hypothesis"] == "Test hypothesis"


class TestCheckRetryTriggers:
    """Tests for check_retry_triggers."""

    def test_new_grimoire_knowledge_trigger(self, store):
        """Trigger 'new_grimoire_knowledge:cuda' matches when conditions include cuda."""
        exp = _make_experiment(retry_triggers=["new_grimoire_knowledge:cuda"])
        store.store_experiment(exp)

        result = store.check_retry_triggers({"new_knowledge_domains": ["cuda"]})
        assert len(result) == 1
        assert result[0].id == exp.id

    def test_trigger_not_met(self, store):
        """Experiment not returned when triggers are not met."""
        exp = _make_experiment(retry_triggers=["new_grimoire_knowledge:cuda"])
        store.store_experiment(exp)

        result = store.check_retry_triggers({"new_knowledge_domains": ["nlp"]})
        assert len(result) == 0

    def test_deprioritized_not_returned(self, store):
        """Deprioritized experiments are not returned by check_retry_triggers."""
        exp = _make_experiment(
            retry_triggers=["new_grimoire_knowledge:cuda"],
            deprioritized=True,
            status="deprioritized",
        )
        store.store_experiment(exp)

        result = store.check_retry_triggers({"new_knowledge_domains": ["cuda"]})
        assert len(result) == 0

    def test_model_changed_trigger(self, store):
        """Trigger 'model_changed' fires when model differs from experiment conditions."""
        exp = _make_experiment(
            retry_triggers=["model_changed"],
            conditions={"model": "phi4-mini"},
        )
        store.store_experiment(exp)

        result = store.check_retry_triggers({"model": "gemma4-26b"})
        assert len(result) == 1

    def test_model_changed_same_model(self, store):
        """Trigger 'model_changed' does NOT fire when model is the same."""
        exp = _make_experiment(
            retry_triggers=["model_changed"],
            conditions={"model": "phi4-mini"},
        )
        store.store_experiment(exp)

        result = store.check_retry_triggers({"model": "phi4-mini"})
        assert len(result) == 0

    def test_tool_added_trigger(self, store):
        """Trigger 'tool_added:cuda_kernel' matches when tool is available."""
        exp = _make_experiment(retry_triggers=["tool_added:cuda_kernel"])
        store.store_experiment(exp)

        result = store.check_retry_triggers({"available_tools": ["cuda_kernel", "other"]})
        assert len(result) == 1

    def test_knowledge_depth_trigger(self, store):
        """Trigger 'knowledge_depth:cuda:5' matches when domain has 5+ entries."""
        exp = _make_experiment(retry_triggers=["knowledge_depth:cuda:5"])
        store.store_experiment(exp)

        # Not enough
        result = store.check_retry_triggers({"knowledge_counts": {"cuda": 3}})
        assert len(result) == 0

        # Enough
        result = store.check_retry_triggers({"knowledge_counts": {"cuda": 5}})
        assert len(result) == 1

    def test_zero_retry_triggers_never_matches(self, store):
        """Experiment with 0 retry_triggers never triggers retry."""
        exp = _make_experiment(retry_triggers=[])
        store.store_experiment(exp)

        result = store.check_retry_triggers({
            "new_knowledge_domains": ["cuda"],
            "model": "new_model",
            "available_tools": ["everything"],
        })
        assert len(result) == 0

    def test_embedding_model_changed_trigger(self, store):
        """Trigger 'embedding_model_changed' fires when embedding model differs."""
        exp = _make_experiment(
            retry_triggers=["embedding_model_changed"],
            conditions={"embedding_model": "nomic-embed-text"},
        )
        store.store_experiment(exp)

        result = store.check_retry_triggers({"embedding_model": "bge-large"})
        assert len(result) == 1


class TestQueueForRetry:
    """Tests for queue_for_retry."""

    def test_increments_attempt_count(self, store):
        """queue_for_retry increments attempt_count."""
        exp = _make_experiment()
        store.store_experiment(exp)
        store.queue_for_retry(exp.id)

        row = store._conn.execute(
            "SELECT * FROM failed_experiments WHERE id=?", (exp.id,)
        ).fetchone()
        assert row["attempt_count"] == 2
        assert row["status"] == "queued_for_retry"

    def test_deprioritizes_after_3_different_conditions(self, store):
        """queue_for_retry sets deprioritized after 3 failed attempts under different conditions."""
        now = time.time()
        exp = _make_experiment(
            attempt_count=2,
            attempt_history=[
                {"attempt": 1, "date": now - 200, "conditions": {"model": "a"}, "result": "fail"},
                {"attempt": 2, "date": now - 100, "conditions": {"model": "b"}, "result": "fail"},
            ],
        )
        store.store_experiment(exp)
        store.queue_for_retry(exp.id)

        row = store._conn.execute(
            "SELECT * FROM failed_experiments WHERE id=?", (exp.id,)
        ).fetchone()
        assert row["attempt_count"] == 3
        # The new entry added by queue_for_retry has empty conditions,
        # so _all_different_conditions checks only non-empty ones.
        # Two different non-empty conditions: {"model": "a"} and {"model": "b"}
        # That's only 2 unique non-empty, which is >= 2 but the empty one is skipped.
        # With 2 unique non-empty conditions from 2 entries, all are different → True
        assert row["deprioritized"] == 1
        assert row["status"] == "deprioritized"

    def test_does_not_deprioritize_same_conditions(self, store):
        """queue_for_retry does NOT deprioritize if same conditions (not genuinely different)."""
        now = time.time()
        conds = {"model": "same_model"}
        exp = _make_experiment(
            attempt_count=2,
            attempt_history=[
                {"attempt": 1, "date": now - 200, "conditions": conds, "result": "fail"},
                {"attempt": 2, "date": now - 100, "conditions": conds, "result": "fail"},
            ],
        )
        store.store_experiment(exp)
        store.queue_for_retry(exp.id)

        row = store._conn.execute(
            "SELECT * FROM failed_experiments WHERE id=?", (exp.id,)
        ).fetchone()
        assert row["attempt_count"] == 3
        assert row["deprioritized"] == 0
        assert row["status"] == "queued_for_retry"

    def test_returns_false_for_missing_id(self, store):
        """queue_for_retry returns False for non-existent experiment."""
        assert store.queue_for_retry("nonexistent-id") is False


class TestRecordRetryResult:
    """Tests for record_retry_result."""

    def test_success_updates_status_and_grimoire(self, store_with_grimoire, mock_grimoire):
        """Successful retry updates status and stores in Grimoire."""
        exp = _make_experiment()
        store_with_grimoire.store_experiment(exp)
        store_with_grimoire.queue_for_retry(exp.id)

        result = store_with_grimoire.record_retry_result(
            exp.id, success=True, result="It worked!", conditions={"model": "gemma4-26b"}
        )
        assert result is True

        row = store_with_grimoire._conn.execute(
            "SELECT * FROM failed_experiments WHERE id=?", (exp.id,)
        ).fetchone()
        assert row["status"] == "succeeded"
        assert row["success"] == 1
        mock_grimoire.store.assert_called_once()

    def test_failure_updates_attempt_history(self, store):
        """Failed retry updates attempt_history."""
        exp = _make_experiment()
        store.store_experiment(exp)
        store.queue_for_retry(exp.id)

        result = store.record_retry_result(
            exp.id, success=False, result="Still broken", conditions={"model": "gemma4-26b"}
        )
        assert result is True

        row = store._conn.execute(
            "SELECT * FROM failed_experiments WHERE id=?", (exp.id,)
        ).fetchone()
        assert row["status"] == "failed"
        history = json.loads(row["attempt_history"])
        assert history[-1]["result"] == "Still broken"
        assert history[-1]["conditions"] == {"model": "gemma4-26b"}

    def test_returns_false_for_missing_id(self, store):
        """record_retry_result returns False for non-existent experiment."""
        assert store.record_retry_result("nope", True, "ok", {}) is False


class TestGetPendingRetries:
    """Tests for get_pending_retries."""

    def test_returns_queued_ordered_correctly(self, store):
        """get_pending_retries returns queued experiments ordered by attempt_count."""
        exp1 = _make_experiment(attempt_count=3)
        exp1.status = "queued_for_retry"
        store.store_experiment(exp1)

        exp2 = _make_experiment(attempt_count=1)
        exp2.status = "queued_for_retry"
        store.store_experiment(exp2)

        retries = store.get_pending_retries()
        assert len(retries) == 2
        assert retries[0].attempt_count <= retries[1].attempt_count

    def test_excludes_non_queued(self, store):
        """get_pending_retries excludes experiments not queued for retry."""
        exp = _make_experiment(status="failed")
        store.store_experiment(exp)

        retries = store.get_pending_retries()
        assert len(retries) == 0


class TestGetExperimentStats:
    """Tests for get_experiment_stats."""

    def test_returns_accurate_counts(self, store):
        """get_experiment_stats returns accurate counts for all statuses."""
        store.store_experiment(_make_experiment(status="failed"))
        store.store_experiment(_make_experiment(status="failed"))
        exp_s = _make_experiment(success=True, status="succeeded")
        store.store_experiment(exp_s)
        store.store_experiment(_make_experiment(status="deprioritized", deprioritized=True))

        stats = store.get_experiment_stats()
        assert stats["total_experiments"] == 4
        assert stats["failed"] == 2
        assert stats["succeeded"] == 1
        assert stats["deprioritized"] == 1
        assert stats["queued_for_retry"] == 0


class TestGetExperimentsByDomain:
    """Tests for get_experiments_by_domain."""

    def test_filters_correctly(self, store):
        """get_experiments_by_domain filters by domain tag."""
        store.store_experiment(_make_experiment(domain_tags=["cuda", "optimization"]))
        store.store_experiment(_make_experiment(domain_tags=["nlp"]))

        results = store.get_experiments_by_domain("cuda")
        assert len(results) == 1
        assert "cuda" in results[0].domain_tags

    def test_deprioritized_excluded_by_default(self, store):
        """Deprioritized experiments excluded by default."""
        store.store_experiment(_make_experiment(
            domain_tags=["cuda"], deprioritized=True, status="deprioritized",
        ))

        results = store.get_experiments_by_domain("cuda")
        assert len(results) == 0

    def test_deprioritized_included_when_requested(self, store):
        """Deprioritized experiments included with include_deprioritized=True."""
        store.store_experiment(_make_experiment(
            domain_tags=["cuda"], deprioritized=True, status="deprioritized",
        ))

        results = store.get_experiments_by_domain("cuda", include_deprioritized=True)
        assert len(results) == 1


class TestEdgeCases:
    """Edge case and robustness tests."""

    def test_db_created_if_not_exists(self, tmp_path):
        """SQLite DB is created if it doesn't exist."""
        db_path = str(tmp_path / "new_dir" / "experiments.db")
        s = ExperimentStore(db_path=db_path)
        assert os.path.exists(db_path)
        s.close()

    def test_grimoire_unavailable_graceful(self, tmp_db):
        """Graceful handling when Grimoire raises an exception."""
        bad_grimoire = MagicMock()
        bad_grimoire.store.side_effect = Exception("Grimoire is down")

        s = ExperimentStore(grimoire=bad_grimoire, db_path=tmp_db)
        exp = _make_experiment(success=True, status="succeeded")
        # Should not raise
        exp_id = s.store_experiment(exp)
        assert exp_id == exp.id
        s.close()

    def test_grimoire_none_no_error(self, store):
        """No error when grimoire is None and experiment succeeds."""
        exp = _make_experiment(success=True, status="succeeded")
        exp_id = store.store_experiment(exp)
        assert exp_id == exp.id
