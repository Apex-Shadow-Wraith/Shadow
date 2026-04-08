"""Tests for LoRA Performance Tracker."""

import time
import pytest
from modules.shadow.lora_tracker import LoRAPerformanceTracker, AdapterProfile


@pytest.fixture
def tracker(tmp_path):
    """Create a tracker with a temporary database."""
    db = tmp_path / "test_lora.db"
    return LoRAPerformanceTracker(db_path=str(db))


@pytest.fixture
def populated_tracker(tracker):
    """Tracker pre-loaded with sample data across multiple adapters."""
    # Ethics adapter — consistently good
    for i in range(10):
        tracker.record("ethics_lora", "classification", "cerberus",
                       confidence_with=0.85 + i * 0.005,
                       confidence_without=0.70,
                       task_succeeded=True)

    # CUDA adapter — mixed results
    for i in range(10):
        imp = 0.1 if i < 3 else -0.1
        tracker.record("cuda_lora", "optimization", "cipher",
                       confidence_with=0.70 + imp,
                       confidence_without=0.70,
                       task_succeeded=i < 7)

    # Anti-sycophancy — helps on most tasks
    for i in range(10):
        tracker.record("anti_sycophancy", "generation", "nova",
                       confidence_with=0.90,
                       confidence_without=0.75,
                       task_succeeded=True)

    return tracker


# --- Recording ---

class TestRecording:
    def test_record_stores_all_fields(self, tracker):
        rid = tracker.record("test_adapter", "classification", "cerberus",
                             confidence_with=0.85, confidence_without=0.70,
                             task_succeeded=True)
        assert rid is not None
        assert len(rid) == 12

        row = tracker._conn.execute(
            "SELECT * FROM lora_records WHERE record_id = ?", (rid,)
        ).fetchone()
        assert row["adapter_name"] == "test_adapter"
        assert row["task_type"] == "classification"
        assert row["module"] == "cerberus"
        assert row["confidence_with"] == 0.85
        assert row["confidence_without"] == 0.70
        assert abs(row["improvement"] - 0.15) < 1e-9
        assert row["task_succeeded"] == 1

    def test_record_none_confidence_without(self, tracker):
        rid = tracker.record("test_adapter", "generation", "nova",
                             confidence_with=0.80)
        row = tracker._conn.execute(
            "SELECT * FROM lora_records WHERE record_id = ?", (rid,)
        ).fetchone()
        assert row["confidence_without"] is None
        assert row["improvement"] is None

    def test_multiple_records_accumulate(self, tracker):
        tracker.record("a", "t1", "m1", confidence_with=0.8, confidence_without=0.7)
        tracker.record("a", "t2", "m1", confidence_with=0.9, confidence_without=0.7)
        tracker.record("b", "t1", "m2", confidence_with=0.6, confidence_without=0.7)

        count = tracker._conn.execute("SELECT COUNT(*) FROM lora_records").fetchone()[0]
        assert count == 3


# --- Profiles ---

class TestProfiles:
    def test_avg_improvement_correct(self, populated_tracker):
        profile = populated_tracker.get_adapter_profile("ethics_lora")
        # All records: confidence_with ranges 0.85..0.895, confidence_without=0.70
        # Improvements: 0.15, 0.155, 0.16, ... 0.195 → avg ≈ 0.1725
        assert profile.avg_improvement > 0.15
        assert profile.total_tasks == 10

    def test_helped_hurt_neutral_categories(self, tracker):
        # 3 helped (improvement > 0.05)
        for _ in range(3):
            tracker.record("x", "t", "m", confidence_with=0.9, confidence_without=0.7)
        # 2 hurt (improvement < -0.05)
        for _ in range(2):
            tracker.record("x", "t", "m", confidence_with=0.6, confidence_without=0.7)
        # 1 neutral (|improvement| <= 0.05)
        tracker.record("x", "t", "m", confidence_with=0.72, confidence_without=0.7)

        profile = tracker.get_adapter_profile("x")
        assert profile.tasks_helped == 3
        assert profile.tasks_hurt == 2
        assert profile.tasks_neutral == 1

    def test_needs_retrain_high_hurt_rate(self, tracker):
        # 5 records all hurting
        for _ in range(5):
            tracker.record("bad_adapter", "t", "m",
                           confidence_with=0.5, confidence_without=0.7)
        profile = tracker.get_adapter_profile("bad_adapter")
        assert profile.needs_retrain is True
        assert profile.hurt_rate > 0.2

    def test_needs_retrain_declining_performance(self, tracker):
        """Adapter that was good but is getting worse needs retrain."""
        now = time.time()
        # Manually insert records with controlled timestamps
        for i in range(8):
            # First 4: good improvement, last 4: declining
            imp = 0.2 if i < 4 else 0.05
            ts = now - (7 * 86400) + (i * 86400 * 0.8)
            tracker._conn.execute(
                """INSERT INTO lora_records
                   (record_id, adapter_name, task_type, module,
                    confidence_with, confidence_without, improvement,
                    task_succeeded, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"r{i}", "declining", "t", "m", 0.7 + imp, 0.7, imp, 1, ts),
            )
        tracker._conn.commit()

        profile = tracker.get_adapter_profile("declining")
        assert profile.needs_retrain is True

    def test_get_all_profiles_sorted(self, populated_tracker):
        profiles = populated_tracker.get_all_profiles()
        assert len(profiles) == 3
        # Should be sorted by avg_improvement descending
        for i in range(len(profiles) - 1):
            assert profiles[i].avg_improvement >= profiles[i + 1].avg_improvement


# --- Recommendations ---

class TestRecommendations:
    def test_recommend_best_adapter(self, tracker):
        for _ in range(10):
            tracker.record("good", "analysis", "cipher",
                           confidence_with=0.9, confidence_without=0.7)
            tracker.record("mediocre", "analysis", "cipher",
                           confidence_with=0.75, confidence_without=0.7)

        rec = tracker.recommend_adapter("analysis")
        assert rec["recommended_adapter"] == "good"
        assert rec["expected_improvement"] > 0.1

    def test_recommend_no_positive_adapter(self, tracker):
        for _ in range(5):
            tracker.record("bad1", "task_x", "m",
                           confidence_with=0.6, confidence_without=0.7)
            tracker.record("bad2", "task_x", "m",
                           confidence_with=0.65, confidence_without=0.7)

        rec = tracker.recommend_adapter("task_x")
        assert rec["recommended_adapter"] is None
        assert rec["expected_improvement"] == 0.0

    def test_recommend_confidence_scales_with_samples(self, tracker):
        # Few samples → low confidence
        for _ in range(3):
            tracker.record("small_sample", "t", "m",
                           confidence_with=0.9, confidence_without=0.7)
        rec_small = tracker.recommend_adapter("t")
        assert rec_small["confidence"] < 0.5

        # Many samples → high confidence
        for _ in range(20):
            tracker.record("large_sample", "t2", "m",
                           confidence_with=0.9, confidence_without=0.7)
        rec_large = tracker.recommend_adapter("t2")
        assert rec_large["confidence"] >= 1.0

    def test_recommend_no_data(self, tracker):
        rec = tracker.recommend_adapter("nonexistent_task")
        assert rec["recommended_adapter"] is None
        assert rec["alternatives"] == []


# --- Overlap ---

class TestOverlap:
    def test_high_overlap_same_task_types(self, tracker):
        for tt in ["classification", "generation", "analysis"]:
            tracker.record("adapter_a", tt, "m",
                           confidence_with=0.9, confidence_without=0.7)
            tracker.record("adapter_b", tt, "m",
                           confidence_with=0.85, confidence_without=0.7)

        result = tracker.detect_overlap("adapter_a", "adapter_b")
        assert result["overlap_rate"] == 1.0
        assert "merging" in result["recommendation"].lower()

    def test_low_overlap_different_task_types(self, tracker):
        for tt in ["classification", "generation", "analysis"]:
            tracker.record("adapter_a", tt, "m",
                           confidence_with=0.9, confidence_without=0.7)
        for tt in ["optimization", "scheduling", "diagnosis"]:
            tracker.record("adapter_b", tt, "m",
                           confidence_with=0.85, confidence_without=0.7)

        result = tracker.detect_overlap("adapter_a", "adapter_b")
        assert result["overlap_rate"] == 0.0
        assert "specialized" in result["recommendation"].lower()

    def test_overlap_merge_recommendation(self, tracker):
        # 5 shared out of 6 total → overlap > 0.8
        shared = ["t1", "t2", "t3", "t4", "t5"]
        for tt in shared:
            tracker.record("a", tt, "m", confidence_with=0.9, confidence_without=0.7)
            tracker.record("b", tt, "m", confidence_with=0.85, confidence_without=0.7)
        tracker.record("a", "t6", "m", confidence_with=0.9, confidence_without=0.7)

        result = tracker.detect_overlap("a", "b")
        assert result["overlap_rate"] > 0.8
        assert "merging" in result["recommendation"].lower()


# --- Maintenance ---

class TestMaintenance:
    def test_retrain_candidates(self, tracker):
        # Create an adapter with high hurt rate
        for _ in range(10):
            tracker.record("needs_retrain", "t", "m",
                           confidence_with=0.5, confidence_without=0.7)
        # Create a healthy adapter
        for _ in range(10):
            tracker.record("healthy", "t", "m",
                           confidence_with=0.9, confidence_without=0.7)

        candidates = tracker.get_retrain_candidates()
        assert "needs_retrain" in candidates
        assert "healthy" not in candidates

    def test_performance_trend_daily(self, tracker):
        now = time.time()
        # Insert records across 3 days
        for day_offset in range(3):
            ts = now - (day_offset * 86400)
            tracker._conn.execute(
                """INSERT INTO lora_records
                   (record_id, adapter_name, task_type, module,
                    confidence_with, confidence_without, improvement,
                    task_succeeded, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"trend_{day_offset}", "trend_adapter", "t", "m",
                 0.85, 0.70, 0.15, 1, ts),
            )
        tracker._conn.commit()

        trend = tracker.get_performance_trend("trend_adapter")
        assert len(trend) >= 1
        for entry in trend:
            assert "date" in entry
            assert "avg_improvement" in entry
            assert "task_count" in entry


# --- Reporting ---

class TestReporting:
    def test_summary_readable(self, populated_tracker):
        summary = populated_tracker.get_tracker_summary()
        assert isinstance(summary, str)
        assert "tracked" in summary.lower()

    def test_summary_mentions_best_and_worst(self, tracker):
        # Best adapter
        for _ in range(10):
            tracker.record("best_one", "t", "m",
                           confidence_with=0.95, confidence_without=0.70)
        # Worst adapter
        for _ in range(10):
            tracker.record("worst_one", "t", "m",
                           confidence_with=0.55, confidence_without=0.70)

        summary = tracker.get_tracker_summary()
        assert "best_one" in summary
        assert "worst_one" in summary

    def test_summary_empty(self, tracker):
        summary = tracker.get_tracker_summary()
        assert "no lora" in summary.lower() or "no adapter" in summary.lower()


# --- Edge Cases ---

class TestEdgeCases:
    def test_no_records_empty_profile(self, tracker):
        profile = tracker.get_adapter_profile("nonexistent")
        assert profile.total_tasks == 0
        assert profile.avg_improvement == 0.0
        assert profile.best_task_types == []
        assert profile.needs_retrain is False

    def test_single_adapter_valid_profile(self, tracker):
        tracker.record("only_one", "t", "m",
                       confidence_with=0.85, confidence_without=0.70)
        profile = tracker.get_adapter_profile("only_one")
        assert profile.total_tasks == 1
        assert abs(profile.avg_improvement - 0.15) < 1e-9

    def test_db_created_on_init(self, tmp_path):
        db = tmp_path / "subdir" / "new.db"
        tracker = LoRAPerformanceTracker(db_path=str(db))
        assert db.exists()

    def test_unknown_adapter_empty_profile(self, tracker):
        # Add some data for one adapter, query another
        tracker.record("known", "t", "m", confidence_with=0.9, confidence_without=0.7)
        profile = tracker.get_adapter_profile("unknown")
        assert profile.total_tasks == 0
        assert profile.adapter_name == "unknown"
