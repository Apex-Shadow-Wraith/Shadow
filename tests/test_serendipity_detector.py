"""
Tests for SerendipityDetector — Unexpected Discovery Detection
================================================================
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from modules.morpheus.serendipity_detector import (
    SerendipityDetector,
    SerendipityFinding,
    DEFAULT_DOMAINS,
)


# --- Fixtures ---

@pytest.fixture
def detector():
    """Basic detector with no dependencies."""
    return SerendipityDetector()


@pytest.fixture
def mock_grimoire():
    """Mock Grimoire module."""
    grimoire = MagicMock()
    grimoire.store = MagicMock()
    grimoire.query = MagicMock(return_value={"results": [{"score": 0.7}]})
    return grimoire


@pytest.fixture
def mock_benchmark():
    """Mock benchmark function."""
    def benchmark_fn(domain: str) -> dict:
        scores = {
            "code": 0.75,
            "research": 0.60,
            "math": 0.80,
            "business": 0.65,
            "security": 0.70,
        }
        return {"score": scores.get(domain, 0.5), "metrics": {}}
    return benchmark_fn


@pytest.fixture
def sample_experiment():
    """Sample failed experiment dict."""
    return {
        "experiment_id": "exp-001",
        "hypothesis": "Optimize code generation speed",
        "domain_tags": ["code"],
        "target_domain": "code",
        "status": "failed",
    }


@pytest.fixture
def pre_metrics():
    """Pre-experiment baseline metrics."""
    return {
        "code": {"score": 0.70, "timestamp": time.time() - 100},
        "research": {"score": 0.60, "timestamp": time.time() - 100},
        "math": {"score": 0.80, "timestamp": time.time() - 100},
        "business": {"score": 0.65, "timestamp": time.time() - 100},
        "security": {"score": 0.70, "timestamp": time.time() - 100},
    }


@pytest.fixture
def post_metrics_with_serendipity():
    """Post-experiment metrics with unexpected research improvement."""
    return {
        "code": {"score": 0.68, "timestamp": time.time()},       # Worse (failed)
        "research": {"score": 0.72, "timestamp": time.time()},    # +20% improvement!
        "math": {"score": 0.80, "timestamp": time.time()},        # Same
        "business": {"score": 0.65, "timestamp": time.time()},    # Same
        "security": {"score": 0.70, "timestamp": time.time()},    # Same
    }


# --- Detection Tests ---

class TestCheckForSerendipity:
    """Tests for check_for_serendipity method."""

    def test_improvement_in_non_target_domain_detected(
        self, detector, sample_experiment, pre_metrics, post_metrics_with_serendipity
    ):
        """Improvement in non-target domain → finding detected."""
        findings = detector.check_for_serendipity(
            sample_experiment, pre_metrics, post_metrics_with_serendipity
        )
        assert len(findings) == 1
        assert findings[0].improvement_domain == "research"
        assert findings[0].status == "detected"
        assert findings[0].original_experiment_id == "exp-001"

    def test_improvement_in_target_domain_not_serendipitous(
        self, detector, pre_metrics
    ):
        """Improvement in target domain → NOT serendipitous."""
        experiment = {
            "experiment_id": "exp-002",
            "hypothesis": "Improve research quality",
            "domain_tags": ["research"],
        }
        post = {
            "code": {"score": 0.70, "timestamp": time.time()},
            "research": {"score": 0.72, "timestamp": time.time()},  # Target improved
            "math": {"score": 0.80, "timestamp": time.time()},
            "business": {"score": 0.65, "timestamp": time.time()},
            "security": {"score": 0.70, "timestamp": time.time()},
        }
        findings = detector.check_for_serendipity(experiment, pre_metrics, post)
        assert len(findings) == 0

    def test_no_improvements_empty_list(
        self, detector, sample_experiment, pre_metrics
    ):
        """No improvements → empty list."""
        # Post metrics same as pre
        findings = detector.check_for_serendipity(
            sample_experiment, pre_metrics, pre_metrics
        )
        assert findings == []

    def test_multiple_domains_improved(self, detector, pre_metrics):
        """Multiple non-target domains improved → multiple findings."""
        experiment = {
            "experiment_id": "exp-003",
            "hypothesis": "Test security hardening",
            "domain_tags": ["security"],
        }
        post = {
            "code": {"score": 0.84, "timestamp": time.time()},       # +20%
            "research": {"score": 0.72, "timestamp": time.time()},    # +20%
            "math": {"score": 0.80, "timestamp": time.time()},        # Same
            "business": {"score": 0.65, "timestamp": time.time()},    # Same
            "security": {"score": 0.75, "timestamp": time.time()},    # Target improved
        }
        findings = detector.check_for_serendipity(experiment, pre_metrics, post)
        assert len(findings) == 2
        domains = {f.improvement_domain for f in findings}
        assert domains == {"code", "research"}

    def test_threshold_below_not_detected(self, detector, pre_metrics):
        """4% improvement (below 5% threshold) → not detected."""
        experiment = {
            "experiment_id": "exp-004",
            "hypothesis": "Test math optimization",
            "domain_tags": ["math"],
        }
        post = {
            "code": {"score": 0.70, "timestamp": time.time()},
            "research": {"score": 0.624, "timestamp": time.time()},   # +4% (below threshold)
            "math": {"score": 0.80, "timestamp": time.time()},
            "business": {"score": 0.65, "timestamp": time.time()},
            "security": {"score": 0.70, "timestamp": time.time()},
        }
        findings = detector.check_for_serendipity(experiment, pre_metrics, post)
        assert len(findings) == 0

    def test_threshold_above_detected(self, detector, pre_metrics):
        """6% improvement (above 5% threshold) → detected."""
        experiment = {
            "experiment_id": "exp-005",
            "hypothesis": "Test math optimization",
            "domain_tags": ["math"],
        }
        post = {
            "code": {"score": 0.70, "timestamp": time.time()},
            "research": {"score": 0.636, "timestamp": time.time()},   # +6%
            "math": {"score": 0.80, "timestamp": time.time()},
            "business": {"score": 0.65, "timestamp": time.time()},
            "security": {"score": 0.70, "timestamp": time.time()},
        }
        findings = detector.check_for_serendipity(experiment, pre_metrics, post)
        assert len(findings) == 1
        assert findings[0].improvement_domain == "research"


# --- Metrics Tests ---

class TestMetrics:
    """Tests for capture_baseline_metrics and compare_metrics."""

    def test_capture_baseline_returns_valid_snapshot(self, mock_benchmark):
        """capture_baseline_metrics returns valid snapshot with scores."""
        detector = SerendipityDetector(benchmark_fn=mock_benchmark)
        metrics = detector.capture_baseline_metrics()
        assert isinstance(metrics, dict)
        assert len(metrics) == len(DEFAULT_DOMAINS)
        for domain in DEFAULT_DOMAINS:
            assert "score" in metrics[domain]
            assert "timestamp" in metrics[domain]
            assert isinstance(metrics[domain]["score"], float)

    def test_compare_metrics_identifies_improvements(self, detector):
        """compare_metrics correctly identifies improvements above threshold."""
        baseline = {"code": {"score": 0.70}, "research": {"score": 0.60}}
        current = {"code": {"score": 0.70}, "research": {"score": 0.72}}
        result = detector.compare_metrics(baseline, current)
        assert len(result) == 1
        assert result[0]["domain"] == "research"
        assert result[0]["improvement_pct"] == pytest.approx(0.2, rel=1e-2)

    def test_compare_metrics_regression_not_reported(self, detector):
        """Regression (worse score) not reported as improvement."""
        baseline = {"code": {"score": 0.70}, "research": {"score": 0.60}}
        current = {"code": {"score": 0.50}, "research": {"score": 0.55}}
        result = detector.compare_metrics(baseline, current)
        assert len(result) == 0

    def test_capture_baseline_no_benchmark_uses_heuristic(self):
        """Without benchmark_fn, uses heuristic scoring."""
        detector = SerendipityDetector()
        metrics = detector.capture_baseline_metrics(["code", "research"])
        assert len(metrics) == 2
        for domain in ["code", "research"]:
            assert "score" in metrics[domain]
            assert metrics[domain]["score"] == 0.5  # Default heuristic


# --- Investigation Tests ---

class TestInvestigation:
    """Tests for queue_for_investigation, confirm, dismiss."""

    def _make_finding(self, finding_id="find-001") -> SerendipityFinding:
        return SerendipityFinding(
            finding_id=finding_id,
            original_experiment_id="exp-001",
            original_goal="Optimize code generation",
            unexpected_improvement="research improved by 20%",
            improvement_domain="research",
            improvement_magnitude=0.2,
            baseline_metric=0.60,
            new_metric=0.72,
            timestamp=time.time(),
            status="detected",
        )

    def test_queue_for_investigation_creates_experiment(self):
        """queue_for_investigation creates experiment in store."""
        detector = SerendipityDetector()
        finding = self._make_finding()
        detector._findings.append(finding)

        mock_store = MagicMock()
        result = detector.queue_for_investigation(finding, experiment_store=mock_store)

        assert result == "find-001"
        assert finding.status == "investigating"
        mock_store.store_failure.assert_called_once()

    def test_confirm_finding_stores_in_grimoire(self, mock_grimoire):
        """confirm_finding stores in Grimoire."""
        detector = SerendipityDetector(grimoire=mock_grimoire)
        finding = self._make_finding()
        detector._findings.append(finding)

        result = detector.confirm_finding("find-001")
        assert result is True
        assert finding.status == "confirmed"
        mock_grimoire.store.assert_called_once()
        call_kwargs = mock_grimoire.store.call_args
        assert "serendipitous_discovery" in str(call_kwargs)

    def test_dismiss_finding_marks_false_positive(self):
        """dismiss_finding marks as false_positive."""
        detector = SerendipityDetector()
        finding = self._make_finding()
        detector._findings.append(finding)

        result = detector.dismiss_finding("find-001", reason="Noise in metrics")
        assert result is True
        assert finding.status == "false_positive"

    def test_get_findings_filters_by_status(self):
        """get_findings filters by status correctly."""
        detector = SerendipityDetector()
        f1 = self._make_finding("f1")
        f1.status = "confirmed"
        f2 = self._make_finding("f2")
        f2.status = "detected"
        f3 = self._make_finding("f3")
        f3.status = "confirmed"
        detector._findings = [f1, f2, f3]

        confirmed = detector.get_findings(status="confirmed")
        assert len(confirmed) == 2
        detected = detector.get_findings(status="detected")
        assert len(detected) == 1


# --- Stats Tests ---

class TestStats:
    """Tests for get_serendipity_stats."""

    def test_stats_returns_accurate_counts(self):
        """get_serendipity_stats returns accurate counts."""
        detector = SerendipityDetector()
        now = time.time()

        for status in ["detected", "confirmed", "confirmed", "false_positive", "investigating"]:
            f = SerendipityFinding(
                finding_id=str(id(status)),
                original_experiment_id="exp-x",
                original_goal="test",
                unexpected_improvement="test",
                improvement_domain="code",
                improvement_magnitude=0.1,
                baseline_metric=0.5,
                new_metric=0.55,
                timestamp=now,
                status=status,
            )
            detector._findings.append(f)

        stats = detector.get_serendipity_stats()
        assert stats["total_detected"] == 5
        assert stats["confirmed"] == 2
        assert stats["false_positives"] == 1
        assert stats["investigating"] == 1
        assert stats["detected"] == 1


# --- Edge Cases ---

class TestEdgeCases:
    """Edge case handling."""

    def test_no_benchmark_fn_uses_heuristic(self):
        """No benchmark_fn → uses heuristic comparison."""
        detector = SerendipityDetector()
        metrics = detector.capture_baseline_metrics(["code"])
        assert metrics["code"]["score"] == 0.5

    def test_empty_metrics_no_findings(self, detector, sample_experiment):
        """Empty metrics → no findings."""
        assert detector.check_for_serendipity(sample_experiment, {}, {}) == []

    def test_same_metrics_no_findings(self, detector, sample_experiment, pre_metrics):
        """Same metrics pre/post → no findings."""
        findings = detector.check_for_serendipity(
            sample_experiment, pre_metrics, pre_metrics
        )
        assert findings == []

    def test_graceful_when_experiment_store_unavailable(self):
        """queue_for_investigation works without experiment_store."""
        detector = SerendipityDetector()
        finding = SerendipityFinding(
            finding_id="f-solo",
            original_experiment_id="exp-x",
            original_goal="test",
            unexpected_improvement="test",
            improvement_domain="code",
            improvement_magnitude=0.1,
            baseline_metric=0.5,
            new_metric=0.55,
            timestamp=time.time(),
            status="detected",
        )
        detector._findings.append(finding)
        result = detector.queue_for_investigation(finding, experiment_store=None)
        assert result == "f-solo"
        assert finding.status == "investigating"

    def test_graceful_when_grimoire_unavailable(self):
        """confirm_finding works without Grimoire."""
        detector = SerendipityDetector(grimoire=None)
        finding = SerendipityFinding(
            finding_id="f-nogrim",
            original_experiment_id="exp-x",
            original_goal="test",
            unexpected_improvement="test",
            improvement_domain="code",
            improvement_magnitude=0.1,
            baseline_metric=0.5,
            new_metric=0.55,
            timestamp=time.time(),
            status="detected",
        )
        detector._findings.append(finding)
        result = detector.confirm_finding("f-nogrim")
        assert result is True
        assert finding.status == "confirmed"

    def test_confirm_nonexistent_finding(self, detector):
        """Confirming a finding that doesn't exist returns False."""
        assert detector.confirm_finding("nonexistent") is False

    def test_dismiss_nonexistent_finding(self, detector):
        """Dismissing a finding that doesn't exist returns False."""
        assert detector.dismiss_finding("nonexistent") is False
