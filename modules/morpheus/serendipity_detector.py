"""
SerendipityDetector — Unexpected Discovery Detection for Failed Experiments
============================================================================
When a Morpheus experiment fails its intended goal, check whether it
accidentally improved something else. Happy accidents are preserved and
can graduate to production knowledge.

Part of Morpheus (Creative Discovery Pipeline).
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable

logger = logging.getLogger("shadow.morpheus.serendipity_detector")

DEFAULT_DOMAINS = ["code", "research", "math", "business", "security"]


@dataclass
class SerendipityFinding:
    """A serendipitous discovery from a failed experiment."""

    finding_id: str
    original_experiment_id: str
    original_goal: str
    unexpected_improvement: str
    improvement_domain: str
    improvement_magnitude: float
    baseline_metric: float
    new_metric: float
    timestamp: float
    status: str  # "detected", "investigating", "confirmed", "false_positive"


class SerendipityDetector:
    """Detects unexpected improvements from failed Morpheus experiments.

    After a failed experiment, runs broad metrics checks across all domains.
    Any unexpected improvement is flagged as a serendipitous finding.

    Args:
        grimoire: Optional Grimoire module for storing confirmed findings.
        benchmark_fn: Optional callable(domain: str) -> {score: float, metrics: dict}.
    """

    def __init__(
        self,
        grimoire=None,
        benchmark_fn: Callable | None = None,
    ) -> None:
        self._grimoire = grimoire
        self._benchmark_fn = benchmark_fn
        self._findings: list[SerendipityFinding] = []

    def check_for_serendipity(
        self,
        experiment: dict,
        pre_metrics: dict,
        post_metrics: dict,
    ) -> list[SerendipityFinding]:
        """Compare pre/post metrics across all domains after a failed experiment.

        Improvements in non-target domains are flagged as serendipitous.

        Args:
            experiment: Dict with at least 'id' (or 'experiment_id'), 'hypothesis',
                        and 'domain_tags' or 'target_domain'.
            pre_metrics: Baseline metrics snapshot {domain: {score: float, ...}}.
            post_metrics: Post-experiment metrics {domain: {score: float, ...}}.

        Returns:
            List of SerendipityFinding objects (usually 0, occasionally 1-2).
        """
        try:
            if not pre_metrics or not post_metrics:
                return []

            # Determine target domain(s) to exclude
            target_domains = set()
            if "domain_tags" in experiment:
                tags = experiment["domain_tags"]
                if isinstance(tags, list):
                    target_domains = set(tags)
                elif isinstance(tags, str):
                    target_domains = {tags}
            if "target_domain" in experiment:
                target_domains.add(experiment["target_domain"])

            exp_id = experiment.get("experiment_id", experiment.get("id", "unknown"))
            exp_goal = experiment.get("hypothesis", experiment.get("title", "unknown"))

            improvements = self.compare_metrics(pre_metrics, post_metrics)

            findings = []
            for imp in improvements:
                domain = imp["domain"]
                if domain in target_domains:
                    continue  # Expected improvement, not serendipitous

                finding = SerendipityFinding(
                    finding_id=str(uuid.uuid4()),
                    original_experiment_id=exp_id,
                    original_goal=exp_goal,
                    unexpected_improvement=f"{domain} improved by {imp['improvement_pct']:.1%}",
                    improvement_domain=domain,
                    improvement_magnitude=min(imp["improvement_pct"], 1.0),
                    baseline_metric=imp["baseline_score"],
                    new_metric=imp["current_score"],
                    timestamp=time.time(),
                    status="detected",
                )
                findings.append(finding)
                self._findings.append(finding)

            return findings

        except Exception as e:
            logger.error("Error checking for serendipity: %s", e)
            return []

    def capture_baseline_metrics(
        self, domains: list[str] | None = None
    ) -> dict:
        """Capture current performance metrics before an experiment runs.

        Args:
            domains: List of domains to benchmark. Defaults to DEFAULT_DOMAINS.

        Returns:
            Dict of {domain: {score: float, timestamp: float}}.
        """
        try:
            domains = domains or DEFAULT_DOMAINS
            metrics = {}
            now = time.time()

            for domain in domains:
                if self._benchmark_fn is not None:
                    try:
                        result = self._benchmark_fn(domain)
                        score = result.get("score", 0.0) if isinstance(result, dict) else 0.0
                        metrics[domain] = {"score": score, "timestamp": now}
                    except Exception as e:
                        logger.warning("Benchmark failed for domain '%s': %s", domain, e)
                        metrics[domain] = {"score": 0.0, "timestamp": now}
                else:
                    # Heuristic fallback: try Grimoire retrieval quality
                    score = self._heuristic_score(domain)
                    metrics[domain] = {"score": score, "timestamp": now}

            return metrics

        except Exception as e:
            logger.error("Error capturing baseline metrics: %s", e)
            return {}

    def compare_metrics(
        self,
        baseline: dict,
        current: dict,
        threshold: float = 0.05,
    ) -> list[dict]:
        """Compare two metric snapshots and return significant improvements.

        Args:
            baseline: Previous metrics {domain: {score: float, ...}}.
            current: Current metrics {domain: {score: float, ...}}.
            threshold: Minimum improvement fraction to report (default 5%).

        Returns:
            List of dicts with domain, baseline_score, current_score, improvement_pct.
        """
        try:
            if not baseline or not current:
                return []

            improvements = []
            for domain, current_data in current.items():
                if domain not in baseline:
                    continue

                baseline_data = baseline[domain]
                baseline_score = baseline_data.get("score", 0.0) if isinstance(baseline_data, dict) else float(baseline_data)
                current_score = current_data.get("score", 0.0) if isinstance(current_data, dict) else float(current_data)

                if baseline_score <= 0:
                    continue  # Can't calculate meaningful improvement from zero

                improvement_pct = (current_score - baseline_score) / baseline_score
                if improvement_pct > threshold:
                    improvements.append({
                        "domain": domain,
                        "baseline_score": baseline_score,
                        "current_score": current_score,
                        "improvement_pct": improvement_pct,
                    })

            return improvements

        except Exception as e:
            logger.error("Error comparing metrics: %s", e)
            return []

    def queue_for_investigation(
        self,
        finding: SerendipityFinding,
        experiment_store=None,
    ) -> str:
        """Add a finding to the investigation queue.

        If experiment_store is available, creates a new experiment to investigate
        the serendipitous discovery.

        Args:
            finding: The SerendipityFinding to investigate.
            experiment_store: Optional ExperimentStore for creating follow-up experiments.

        Returns:
            The finding_id.
        """
        try:
            finding.status = "investigating"
            # Update in internal store
            for i, f in enumerate(self._findings):
                if f.finding_id == finding.finding_id:
                    self._findings[i] = finding
                    break

            if experiment_store is not None:
                try:
                    experiment_store.store_failure(
                        hypothesis=(
                            f"Morpheus discovered that experiment {finding.original_experiment_id} "
                            f"accidentally improved {finding.improvement_domain}. Investigate why."
                        ),
                        approach=f"Investigate serendipitous improvement: {finding.unexpected_improvement}",
                        domain_tags=[finding.improvement_domain],
                        failure_reason="pending_investigation",
                        conditions={"source_finding": finding.finding_id},
                        retry_triggers=[],
                    )
                except Exception as e:
                    logger.warning("Failed to create investigation experiment: %s", e)

            return finding.finding_id

        except Exception as e:
            logger.error("Error queueing finding for investigation: %s", e)
            return finding.finding_id

    def get_findings(
        self,
        status: str | None = None,
        limit: int = 20,
    ) -> list[SerendipityFinding]:
        """Return serendipity findings, optionally filtered by status.

        Args:
            status: Optional status filter.
            limit: Maximum number of findings to return.

        Returns:
            List of findings sorted by improvement_magnitude descending.
        """
        try:
            findings = self._findings
            if status is not None:
                findings = [f for f in findings if f.status == status]

            findings = sorted(findings, key=lambda f: f.improvement_magnitude, reverse=True)
            return findings[:limit]

        except Exception as e:
            logger.error("Error getting findings: %s", e)
            return []

    def confirm_finding(self, finding_id: str) -> bool:
        """Mark a finding as confirmed after investigation validates it.

        Stores confirmed finding in Grimoire with category 'serendipitous_discovery'.

        Args:
            finding_id: The finding to confirm.

        Returns:
            True if found and confirmed, False otherwise.
        """
        try:
            for finding in self._findings:
                if finding.finding_id == finding_id:
                    finding.status = "confirmed"

                    if self._grimoire is not None:
                        try:
                            self._grimoire.store(
                                content=str(asdict(finding)),
                                category="serendipitous_discovery",
                                source=f"morpheus_serendipity:{finding_id}",
                            )
                        except Exception as e:
                            logger.warning("Failed to store finding in Grimoire: %s", e)

                    return True

            return False

        except Exception as e:
            logger.error("Error confirming finding: %s", e)
            return False

    def dismiss_finding(self, finding_id: str, reason: str = "") -> bool:
        """Mark a finding as false_positive with an optional reason.

        The finding is preserved for record-keeping.

        Args:
            finding_id: The finding to dismiss.
            reason: Why it was dismissed.

        Returns:
            True if found and dismissed, False otherwise.
        """
        try:
            for finding in self._findings:
                if finding.finding_id == finding_id:
                    finding.status = "false_positive"
                    return True

            return False

        except Exception as e:
            logger.error("Error dismissing finding: %s", e)
            return False

    def get_serendipity_stats(self) -> dict:
        """Return aggregate statistics about serendipity findings.

        Returns:
            Dict with total_detected, confirmed, false_positives, investigating,
            and most_productive_domains.
        """
        try:
            total = len(self._findings)
            confirmed = sum(1 for f in self._findings if f.status == "confirmed")
            false_positives = sum(1 for f in self._findings if f.status == "false_positive")
            investigating = sum(1 for f in self._findings if f.status == "investigating")
            detected = sum(1 for f in self._findings if f.status == "detected")

            # Most productive domain combinations
            domain_counts: dict[str, int] = {}
            for f in self._findings:
                if f.status != "false_positive":
                    domain_counts[f.improvement_domain] = domain_counts.get(f.improvement_domain, 0) + 1

            most_productive = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)

            return {
                "total_detected": total,
                "confirmed": confirmed,
                "false_positives": false_positives,
                "investigating": investigating,
                "detected": detected,
                "most_productive_domains": most_productive,
            }

        except Exception as e:
            logger.error("Error getting serendipity stats: %s", e)
            return {
                "total_detected": 0,
                "confirmed": 0,
                "false_positives": 0,
                "investigating": 0,
                "detected": 0,
                "most_productive_domains": [],
            }

    # --- Internal helpers ---

    def _heuristic_score(self, domain: str) -> float:
        """Generate a heuristic score for a domain without a benchmark function.

        Uses Grimoire retrieval quality if available, otherwise returns a
        neutral baseline.

        Args:
            domain: The domain to score.

        Returns:
            A float score (0.0-1.0).
        """
        if self._grimoire is not None:
            try:
                result = self._grimoire.query(domain, limit=5)
                if isinstance(result, dict) and "results" in result:
                    results = result["results"]
                    if results:
                        scores = [r.get("score", 0.5) for r in results if isinstance(r, dict)]
                        return sum(scores) / len(scores) if scores else 0.5
                return 0.5
            except Exception:
                return 0.5
        return 0.5
