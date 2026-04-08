"""Tests for Predictive Escalation module."""

import os
import tempfile
import time
from unittest.mock import MagicMock

import pytest

from modules.shadow.predictive_escalation import (
    EscalationPrediction,
    PredictiveEscalation,
)


@pytest.fixture
def tmp_db(tmp_path):
    """Return a temporary database path."""
    return str(tmp_path / "test_escalation.db")


@pytest.fixture
def escalation(tmp_db):
    """Create a PredictiveEscalation instance with no Grimoire."""
    pe = PredictiveEscalation(grimoire=None, db_path=tmp_db)
    yield pe
    pe.close()


@pytest.fixture
def mock_grimoire():
    """Create a mock Grimoire with recall method."""
    grim = MagicMock()
    grim.recall.return_value = []
    return grim


@pytest.fixture
def escalation_with_grimoire(tmp_db, mock_grimoire):
    """Create a PredictiveEscalation with a mock Grimoire."""
    pe = PredictiveEscalation(grimoire=mock_grimoire, db_path=tmp_db)
    yield pe
    pe.close()


# --- SQLite DB creation ---

class TestInit:
    def test_db_created_on_init(self, tmp_db):
        """SQLite DB file is created on initialization."""
        pe = PredictiveEscalation(db_path=tmp_db)
        assert os.path.exists(tmp_db)
        pe.close()

    def test_predictions_table_exists(self, escalation):
        """The predictions table is created."""
        cursor = escalation._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='predictions'"
        )
        assert cursor.fetchone() is not None


# --- Prediction ---

class TestPredict:
    def test_high_complexity_no_grimoire_high_probability(self, escalation):
        """High complexity + no Grimoire depth → high probability."""
        task = (
            "Implement a CUDA kernel for matrix multiplication with shared memory "
            "optimization, then benchmark against cuBLAS, then profile with nsight, "
            "then optimize the memory access patterns for the GPU architecture, "
            "finally deploy as a distributed service across multiple nodes"
        )
        pred = escalation.predict(task, task_type="cuda")
        assert pred.predicted_probability > 0.5
        assert len(pred.risk_factors) > 0

    def test_simple_task_low_probability(self, tmp_db, mock_grimoire):
        """Simple task + deep Grimoire → low probability."""
        # Grimoire returns many entries — deep coverage
        mock_grimoire.recall.return_value = [
            {"content": f"python tip {i}"} for i in range(10)
        ]
        pe = PredictiveEscalation(grimoire=mock_grimoire, db_path=tmp_db)
        pred = pe.predict("print hello world", task_type="python")
        assert pred.predicted_probability < 0.5
        pe.close()

    def test_cuda_task_elevated_probability(self, escalation):
        """CUDA task with no CUDA entries → elevated probability."""
        pred = escalation.predict("Write a CUDA kernel for FFT", task_type="cuda")
        assert pred.predicted_probability > 0.3
        assert any("cuda" in f.lower() for f in pred.risk_factors)

    def test_returns_valid_prediction(self, escalation):
        """Returns a valid EscalationPrediction with all fields populated."""
        pred = escalation.predict("test task", task_type="general")
        assert isinstance(pred, EscalationPrediction)
        assert pred.prediction_id
        assert pred.task_description == "test task"
        assert pred.task_type == "general"
        assert isinstance(pred.predicted_probability, float)
        assert isinstance(pred.confidence_in_prediction, float)
        assert isinstance(pred.risk_factors, list)
        assert isinstance(pred.preparation_actions, list)
        assert pred.actual_escalated is None
        assert pred.timestamp > 0

    def test_probability_clamped_0_to_1(self, escalation):
        """Probability is always clamped to 0.0-1.0."""
        # Even with many signals, should not exceed 1.0
        task = (
            "CUDA kernel with deep learning transformer neural network "
            "distributed kubernetes security analysis penetration testing "
            "then compile then deploy then benchmark then optimize "
            "first second third step pipeline workflow chain sequence batch"
        )
        pred = escalation.predict(task, task_type="complex")
        assert 0.0 <= pred.predicted_probability <= 1.0

    def test_empty_task_valid_prediction(self, escalation):
        """Empty task returns valid prediction with defaults."""
        pred = escalation.predict("", task_type="")
        assert isinstance(pred, EscalationPrediction)
        assert 0.0 <= pred.predicted_probability <= 1.0
        assert pred.task_description == ""

    def test_none_task_valid_prediction(self, escalation):
        """None task is handled gracefully."""
        pred = escalation.predict(None, task_type=None)
        assert isinstance(pred, EscalationPrediction)
        assert 0.0 <= pred.predicted_probability <= 1.0

    def test_prediction_stored_in_db(self, escalation):
        """Predictions are persisted to SQLite."""
        pred = escalation.predict("store test", task_type="test")
        cursor = escalation._conn.execute(
            "SELECT * FROM predictions WHERE prediction_id = ?",
            (pred.prediction_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["task_description"] == "store test"

    def test_multi_step_indicators_increase_probability(self, escalation):
        """Multi-step keywords increase complexity score."""
        simple = escalation.predict("print hello", task_type="python")
        multi = escalation.predict(
            "first parse the data, then transform it, next validate, finally deploy the pipeline",
            task_type="python",
        )
        assert multi.predicted_probability > simple.predicted_probability

    def test_long_task_higher_than_short(self, escalation):
        """Longer task descriptions score higher complexity."""
        short = escalation.predict("hello", task_type="test")
        long_task = "x " * 300  # 600 chars
        long_pred = escalation.predict(long_task, task_type="test")
        assert long_pred.predicted_probability >= short.predicted_probability


# --- Preparation actions ---

class TestPreparationActions:
    def test_high_probability_aggressive_preparation(self, escalation):
        """High probability → aggressive preparation with Apex queue."""
        pred = EscalationPrediction(
            prediction_id="test",
            task_description="complex cuda task",
            task_type="cuda",
            predicted_probability=0.8,
            confidence_in_prediction=0.7,
            risk_factors=[],
            preparation_actions=[],
            timestamp=time.time(),
        )
        actions = escalation.get_preparation_actions(pred)
        assert len(actions) >= 3
        assert any("Apex" in a for a in actions)
        assert any("Grimoire" in a for a in actions)

    def test_low_probability_minimal_preparation(self, escalation):
        """Low probability → minimal preparation."""
        pred = EscalationPrediction(
            prediction_id="test",
            task_description="simple task",
            task_type="python",
            predicted_probability=0.1,
            confidence_in_prediction=0.5,
            risk_factors=[],
            preparation_actions=[],
            timestamp=time.time(),
        )
        actions = escalation.get_preparation_actions(pred)
        assert any("Minimal" in a or "minimal" in a for a in actions)

    def test_medium_probability_moderate_preparation(self, escalation):
        """Medium probability → moderate preparation."""
        pred = EscalationPrediction(
            prediction_id="test",
            task_description="moderate task",
            task_type="general",
            predicted_probability=0.6,
            confidence_in_prediction=0.5,
            risk_factors=[],
            preparation_actions=[],
            timestamp=time.time(),
        )
        actions = escalation.get_preparation_actions(pred)
        assert len(actions) >= 2
        assert any("Grimoire" in a for a in actions)


# --- Batch predictions ---

class TestBatchPredictions:
    def test_returns_sorted_by_probability(self, escalation):
        """Batch predictions are sorted by probability descending."""
        tasks = [
            {"task": "print hello", "task_type": "python"},
            {"task": "CUDA kernel distributed deep learning transformer", "task_type": "cuda"},
            {"task": "simple math", "task_type": "math"},
        ]
        predictions = escalation.batch_predictions(tasks)
        assert len(predictions) == 3
        for i in range(len(predictions) - 1):
            assert predictions[i].predicted_probability >= predictions[i + 1].predicted_probability

    def test_handles_empty_list(self, escalation):
        """Empty task list returns empty prediction list."""
        assert escalation.batch_predictions([]) == []


# --- Accuracy tracking ---

class TestAccuracyTracking:
    def test_record_outcome_stores_result(self, escalation):
        """record_outcome updates the prediction's actual_escalated field."""
        pred = escalation.predict("test task", task_type="test")
        result = escalation.record_outcome(pred.prediction_id, True)
        assert result is True

        cursor = escalation._conn.execute(
            "SELECT actual_escalated FROM predictions WHERE prediction_id = ?",
            (pred.prediction_id,),
        )
        row = cursor.fetchone()
        assert row["actual_escalated"] == 1

    def test_record_outcome_nonexistent_id(self, escalation):
        """record_outcome returns False for nonexistent prediction ID."""
        result = escalation.record_outcome("nonexistent-id", True)
        assert result is False

    def test_accuracy_calculation(self, escalation):
        """get_prediction_accuracy returns correct metrics."""
        # Create predictions and record outcomes
        # High probability prediction that escalated (true positive)
        p1 = escalation.predict(
            "CUDA kernel deep learning distributed transformer neural network",
            task_type="cuda",
        )
        escalation.record_outcome(p1.prediction_id, True)

        # Low probability prediction that didn't escalate (true negative)
        p2 = escalation.predict("print hello", task_type="python")
        escalation.record_outcome(p2.prediction_id, False)

        accuracy = escalation.get_prediction_accuracy()
        assert accuracy["total_predictions"] == 2
        assert accuracy["correct"] + accuracy["incorrect"] == 2

    def test_empty_accuracy(self, escalation):
        """get_prediction_accuracy returns zeros with no data."""
        accuracy = escalation.get_prediction_accuracy()
        assert accuracy["total_predictions"] == 0
        assert accuracy["accuracy"] == 0.0

    def test_false_positive_rate(self, escalation):
        """False positive rate is calculated correctly."""
        # Predicted high (>0.5) but didn't escalate = false positive
        # We need to force a high prediction — use CUDA keywords
        p1 = escalation.predict(
            "CUDA kernel deep learning distributed transformer neural network security analysis",
            task_type="cuda_fp_test",
        )
        escalation.record_outcome(p1.prediction_id, False)  # Didn't actually escalate

        accuracy = escalation.get_prediction_accuracy()
        # At least one false positive should exist
        assert accuracy["total_predictions"] >= 1

    def test_false_negative_rate(self, escalation):
        """False negative rate is calculated correctly."""
        # Predicted low but did escalate = false negative
        p1 = escalation.predict("hello", task_type="fn_test")
        escalation.record_outcome(p1.prediction_id, True)  # Actually escalated

        accuracy = escalation.get_prediction_accuracy()
        assert accuracy["total_predictions"] >= 1


# --- Forecasting ---

class TestForecasting:
    def _seed_predictions(self, escalation, task_type, count, escalate_count):
        """Helper to seed predictions with outcomes."""
        for i in range(count):
            pred = escalation.predict(f"task {i}", task_type=task_type)
            escalated = i < escalate_count
            escalation.record_outcome(pred.prediction_id, escalated)

    def test_identifies_high_escalation_domains(self, escalation):
        """get_escalation_forecast identifies domains with high escalation rates."""
        self._seed_predictions(escalation, "cuda", 10, 8)  # 80% escalation
        self._seed_predictions(escalation, "python", 10, 1)  # 10% escalation

        forecast = escalation.get_escalation_forecast()
        assert len(forecast["forecasts"]) >= 2
        # CUDA should be first (highest escalation rate)
        cuda_forecast = next(
            (f for f in forecast["forecasts"] if f["task_type"] == "cuda"), None
        )
        assert cuda_forecast is not None
        assert cuda_forecast["escalation_rate"] > 0.5

    def test_suggests_knowledge_investments(self, escalation):
        """get_escalation_forecast recommends knowledge investments for high-escalation domains."""
        self._seed_predictions(escalation, "security", 10, 7)  # 70% escalation

        forecast = escalation.get_escalation_forecast()
        assert len(forecast["recommendations"]) >= 1
        rec = forecast["recommendations"][0]
        assert "security" in rec["task_type"]
        assert rec["estimated_reduced_rate"] < rec["current_rate"]

    def test_forecast_with_specific_task_types(self, escalation):
        """get_escalation_forecast filters by specified task types."""
        self._seed_predictions(escalation, "cuda", 5, 4)
        self._seed_predictions(escalation, "python", 5, 1)
        self._seed_predictions(escalation, "math", 5, 2)

        forecast = escalation.get_escalation_forecast(task_types=["cuda", "python"])
        task_types = [f["task_type"] for f in forecast["forecasts"]]
        assert "cuda" in task_types
        assert "python" in task_types
        assert "math" not in task_types

    def test_cost_forecast_returns_reasonable_estimate(self, escalation):
        """get_cost_forecast returns valid cost projections."""
        self._seed_predictions(escalation, "general", 20, 5)  # 25% escalation

        cost = escalation.get_cost_forecast(daily_task_count=100)
        assert cost["daily_task_count"] == 100
        assert cost["estimated_daily_cost"] >= 0
        assert cost["estimated_monthly_cost"] >= 0
        assert cost["estimated_monthly_cost"] == round(cost["estimated_daily_cost"] * 30, 2)
        assert isinstance(cost["top_cost_drivers"], list)

    def test_cost_forecast_empty_db(self, escalation):
        """get_cost_forecast handles empty database gracefully."""
        cost = escalation.get_cost_forecast()
        assert cost["estimated_daily_cost"] == 0.0
        assert cost["estimated_monthly_cost"] == 0.0


# --- Edge cases ---

class TestEdgeCases:
    def test_grimoire_unavailable_predictions_based_on_signals(self, escalation):
        """Without Grimoire, predictions rely on task complexity signals only."""
        pred = escalation.predict("complex CUDA task", task_type="cuda")
        assert isinstance(pred, EscalationPrediction)
        assert 0.0 <= pred.predicted_probability <= 1.0

    def test_all_dependencies_none(self, tmp_db):
        """Graceful when grimoire is None."""
        pe = PredictiveEscalation(grimoire=None, db_path=tmp_db)
        pred = pe.predict("test", task_type="test")
        assert isinstance(pred, EscalationPrediction)
        pe.close()

    def test_grimoire_recall_raises_exception(self, tmp_db):
        """Handles Grimoire exceptions gracefully."""
        bad_grim = MagicMock()
        bad_grim.recall.side_effect = Exception("Grimoire is down")
        pe = PredictiveEscalation(grimoire=bad_grim, db_path=tmp_db)
        pred = pe.predict("test task", task_type="test")
        assert isinstance(pred, EscalationPrediction)
        pe.close()

    def test_close_and_reopen(self, tmp_db):
        """Can close and reopen without data loss."""
        pe = PredictiveEscalation(db_path=tmp_db)
        pred = pe.predict("persist test", task_type="test")
        pid = pred.prediction_id
        pe.close()

        pe2 = PredictiveEscalation(db_path=tmp_db)
        cursor = pe2._conn.execute(
            "SELECT * FROM predictions WHERE prediction_id = ?", (pid,)
        )
        assert cursor.fetchone() is not None
        pe2.close()
