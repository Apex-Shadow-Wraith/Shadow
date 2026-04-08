"""Tests for the Confidence Calibration Curve module."""

from __future__ import annotations

import os
import tempfile
import time

import pytest

from modules.shadow.confidence_calibration import (
    CalibrationRecord,
    ConfidenceCalibrator,
)


@pytest.fixture
def calibrator(tmp_path):
    """Create a calibrator with a temp database."""
    db = str(tmp_path / "test_calibration.db")
    cal = ConfidenceCalibrator(db_path=db, bucket_count=10)
    yield cal
    cal.close()


@pytest.fixture
def overconfident_calibrator(tmp_path):
    """Calibrator populated with overconfident data (predicts 0.8, succeeds ~60%)."""
    db = str(tmp_path / "overconfident.db")
    cal = ConfidenceCalibrator(db_path=db, bucket_count=10)
    # 20 records at 0.85 confidence: 12 successes = 60%
    for i in range(20):
        cal.record(0.85, i < 12, task_type="general", module="wraith")
    yield cal
    cal.close()


@pytest.fixture
def underconfident_calibrator(tmp_path):
    """Calibrator populated with underconfident data (predicts 0.3, succeeds ~70%)."""
    db = str(tmp_path / "underconfident.db")
    cal = ConfidenceCalibrator(db_path=db, bucket_count=10)
    # 20 records at 0.35 confidence: 14 successes = 70%
    for i in range(20):
        cal.record(0.35, i < 14, task_type="general", module="cipher")
    yield cal
    cal.close()


@pytest.fixture
def well_calibrated_calibrator(tmp_path):
    """Calibrator populated with well-calibrated data."""
    db = str(tmp_path / "wellcal.db")
    cal = ConfidenceCalibrator(db_path=db, bucket_count=10)
    # 0.85 confidence, ~85% success rate
    for i in range(20):
        cal.record(0.85, i < 17, task_type="general", module="wraith")
    # 0.45 confidence, ~45% success rate
    for i in range(20):
        cal.record(0.45, i < 9, task_type="general", module="wraith")
    yield cal
    cal.close()


# --- Recording Tests ---

class TestRecording:
    def test_record_stores_pair(self, calibrator):
        """Record stores a prediction-outcome pair in SQLite."""
        record_id = calibrator.record(0.8, True, "general", "wraith")
        assert record_id != ""
        cursor = calibrator._conn.execute(
            "SELECT * FROM calibration_records WHERE record_id = ?",
            (record_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[2] == 0.8  # predicted_confidence
        assert row[3] == 1    # actual_success

    def test_multiple_records_accumulate(self, calibrator):
        """Multiple records accumulate correctly."""
        calibrator.record(0.8, True)
        calibrator.record(0.6, False)
        calibrator.record(0.9, True)
        cursor = calibrator._conn.execute(
            "SELECT COUNT(*) FROM calibration_records"
        )
        assert cursor.fetchone()[0] == 3


# --- Calibration Curve Tests ---

class TestCalibrationCurve:
    def test_buckets_records_correctly(self, overconfident_calibrator):
        """get_calibration_curve buckets records correctly."""
        curve = overconfident_calibrator.get_calibration_curve()
        assert len(curve["buckets"]) == 10
        # 0.85 should land in 0.8-0.9 bucket
        bucket_08 = curve["buckets"][8]
        assert bucket_08["sample_count"] == 20

    def test_overconfident_detected(self, overconfident_calibrator):
        """Overconfident pattern detected."""
        curve = overconfident_calibrator.get_calibration_curve()
        assert curve["direction"] == "overconfident"
        assert curve["overall_calibration_error"] > 0.05

    def test_underconfident_detected(self, underconfident_calibrator):
        """Underconfident pattern detected."""
        curve = underconfident_calibrator.get_calibration_curve()
        assert curve["direction"] == "underconfident"

    def test_well_calibrated_detected(self, well_calibrated_calibrator):
        """Well-calibrated pattern detected."""
        curve = well_calibrated_calibrator.get_calibration_curve()
        assert curve["direction"] == "well_calibrated"

    def test_overall_error_calculated(self, overconfident_calibrator):
        """overall_calibration_error calculated correctly."""
        curve = overconfident_calibrator.get_calibration_curve()
        # Predicted ~0.85, actual ~0.60, error ~0.25
        assert 0.15 < curve["overall_calibration_error"] < 0.35

    def test_empty_db_valid_curve(self, calibrator):
        """Empty DB returns a valid empty curve."""
        curve = calibrator.get_calibration_curve()
        assert "buckets" in curve
        assert len(curve["buckets"]) == 10
        assert curve["overall_calibration_error"] == 0.0
        assert curve["direction"] == "well_calibrated"


# --- Adjustment Tests ---

class TestAdjustment:
    def test_overconfident_adjustment_lowers(self, overconfident_calibrator):
        """Overconfident bucket: adjustment factor < predicted."""
        adjusted = overconfident_calibrator.get_adjustment_factor(0.85)
        assert adjusted < 0.85

    def test_underconfident_adjustment_raises(self, underconfident_calibrator):
        """Underconfident bucket: adjustment factor > predicted."""
        adjusted = underconfident_calibrator.get_adjustment_factor(0.35)
        assert adjusted > 0.35

    def test_insufficient_data_unchanged(self, calibrator):
        """Insufficient data returns predicted_confidence unchanged."""
        # Only 5 records (< 10 minimum)
        for i in range(5):
            calibrator.record(0.8, True)
        adjusted = calibrator.get_adjustment_factor(0.8)
        assert adjusted == 0.8

    def test_calibrate_clamps(self, calibrator):
        """calibrate applies adjustment and clamps to 0.0-1.0."""
        result = calibrator.calibrate(1.5)
        assert 0.0 <= result <= 1.0
        result = calibrator.calibrate(-0.5)
        assert 0.0 <= result <= 1.0

    def test_calibrate_well_calibrated_minimal_change(self, well_calibrated_calibrator):
        """Well-calibrated: calibrate returns value close to input."""
        result = well_calibrated_calibrator.calibrate(0.85)
        assert abs(result - 0.85) < 0.10


# --- Filtering Tests ---

class TestFiltering:
    def test_filter_by_task_type(self, calibrator):
        """get_calibration_by_type filters by task_type."""
        for i in range(15):
            calibrator.record(0.8, True, task_type="code")
        for i in range(15):
            calibrator.record(0.8, False, task_type="research")

        code_curve = calibrator.get_calibration_by_type(task_type="code")
        research_curve = calibrator.get_calibration_by_type(task_type="research")

        code_bucket = [b for b in code_curve["buckets"] if b["sample_count"] > 0][0]
        research_bucket = [b for b in research_curve["buckets"] if b["sample_count"] > 0][0]

        assert code_bucket["actual_success_rate"] == 1.0
        assert research_bucket["actual_success_rate"] == 0.0

    def test_filter_by_module(self, calibrator):
        """get_calibration_by_type filters by module."""
        for i in range(15):
            calibrator.record(0.7, True, module="wraith")
        for i in range(15):
            calibrator.record(0.7, False, module="cipher")

        wraith_curve = calibrator.get_calibration_by_type(module="wraith")
        cipher_curve = calibrator.get_calibration_by_type(module="cipher")

        wraith_bucket = [b for b in wraith_curve["buckets"] if b["sample_count"] > 0][0]
        cipher_bucket = [b for b in cipher_curve["buckets"] if b["sample_count"] > 0][0]

        assert wraith_bucket["actual_success_rate"] == 1.0
        assert cipher_bucket["actual_success_rate"] == 0.0

    def test_different_modules_different_calibration(self, calibrator):
        """Different modules can have different calibration."""
        for i in range(15):
            calibrator.record(0.8, i < 12, module="wraith")  # 80% actual
        for i in range(15):
            calibrator.record(0.8, i < 5, module="cipher")   # 33% actual

        wraith = calibrator.get_calibration_by_type(module="wraith")
        cipher = calibrator.get_calibration_by_type(module="cipher")

        assert wraith["overall_calibration_error"] != cipher["overall_calibration_error"]


# --- Reporting Tests ---

class TestReporting:
    def test_report_returns_string(self, overconfident_calibrator):
        """get_calibration_report returns a readable string."""
        report = overconfident_calibrator.get_calibration_report()
        assert isinstance(report, str)
        assert len(report) > 20
        assert "overconfident" in report.lower() or "calibration" in report.lower()

    def test_monthly_trend_returns_data(self, overconfident_calibrator):
        """get_monthly_trend returns monthly data."""
        trend = overconfident_calibrator.get_monthly_trend(months=3)
        assert isinstance(trend, list)
        assert len(trend) == 3
        for entry in trend:
            assert "calibration_error" in entry
            assert "direction" in entry
            assert "record_count" in entry

    def test_should_recalibrate_high_error(self, overconfident_calibrator):
        """should_recalibrate True when error > 0.15."""
        assert overconfident_calibrator.should_recalibrate() is True

    def test_should_recalibrate_many_records(self, calibrator):
        """should_recalibrate True when many new records since last check."""
        # Mark a recalibration at 0
        calibrator.mark_recalibrated()
        # Add 101 well-calibrated records
        for i in range(101):
            calibrator.record(0.85, i < 86)
        assert calibrator.should_recalibrate() is True


# --- Edge Cases ---

class TestEdgeCases:
    def test_single_record(self, calibrator):
        """Single record: valid but insufficient data for adjustment."""
        calibrator.record(0.9, True)
        curve = calibrator.get_calibration_curve()
        assert curve is not None
        adjusted = calibrator.get_adjustment_factor(0.9)
        assert adjusted == 0.9  # insufficient data

    def test_all_successes(self, calibrator):
        """All successes: calibration reflects that."""
        for _ in range(15):
            calibrator.record(0.8, True)
        curve = calibrator.get_calibration_curve()
        bucket = [b for b in curve["buckets"] if b["sample_count"] > 0][0]
        assert bucket["actual_success_rate"] == 1.0

    def test_all_failures(self, calibrator):
        """All failures: calibration reflects that."""
        for _ in range(15):
            calibrator.record(0.8, False)
        curve = calibrator.get_calibration_curve()
        bucket = [b for b in curve["buckets"] if b["sample_count"] > 0][0]
        assert bucket["actual_success_rate"] == 0.0

    def test_db_created_on_init(self, tmp_path):
        """SQLite DB created on init."""
        db = str(tmp_path / "newdir" / "new_calibration.db")
        cal = ConfidenceCalibrator(db_path=db)
        assert os.path.exists(db)
        cal.close()

    def test_empty_report(self, calibrator):
        """Empty database returns meaningful report."""
        report = calibrator.get_calibration_report()
        assert "no calibration data" in report.lower() or "unavailable" in report.lower()
