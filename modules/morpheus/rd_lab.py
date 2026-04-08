"""
RDLab — Morpheus R&D Laboratory
================================
Research and development laboratory with a complete idea-to-implementation
pipeline. Dreams -> Tests -> Stores.

Speculative knowledge is firewalled from production Grimoire. Only validated
discoveries graduate to production collections.

Part of Morpheus (Creative Discovery Pipeline).
"""

from __future__ import annotations

import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable

logger = logging.getLogger("shadow.morpheus.rd_lab")

SPECULATION_COLLECTION = "speculative_knowledge"


@dataclass
class ExplorationReport:
    """Summary of an R&D exploration session."""

    session_id: str
    duration_minutes: float
    ideas_generated: int
    experiments_run: int
    discoveries_validated: int
    discoveries_speculative: int
    failures_stored: int
    serendipitous_findings: int
    timestamp: float


class RDLab:
    """Morpheus R&D Laboratory — idea-to-implementation pipeline.

    Pulls domain-filtered knowledge from Grimoire technical collections,
    generates cross-domain hypotheses, tests them empirically when possible,
    and graduates validated discoveries to production.

    Args:
        generate_fn: Callable that takes a prompt string and returns model output.
        grimoire: Grimoire module for knowledge retrieval and storage.
        experiment_store: ExperimentStore for tracking failed experiments.
        sandbox: Omen's CodeSandbox for empirical testing.
        config: Optional configuration dict.
    """

    EXPLORATION_DOMAINS = [
        "code",
        "optimization",
        "security",
        "architecture",
        "escalation_teachings",
        "escalation_answers",
        "failure_patterns",
        "workflows",
        "fingerprinted_solution",
        "apex_teachings",
        "self_teaching",
    ]

    def __init__(
        self,
        generate_fn: Callable | None = None,
        grimoire=None,
        experiment_store=None,
        sandbox=None,
        config: dict | None = None,
    ) -> None:
        self._generate_fn = generate_fn
        self._grimoire = grimoire
        self._experiment_store = experiment_store
        self._sandbox = sandbox
        self._config = config or {}
        self._idle_threshold_minutes = self._config.get("idle_threshold_minutes", 30)
        self._max_experiments_per_session = self._config.get("max_experiments_per_session", 5)
        self._speculation_collection = self._config.get(
            "speculation_collection", SPECULATION_COLLECTION
        )

        # Stats tracking
        self._total_sessions = 0
        self._total_hypotheses = 0
        self._total_validated = 0
        self._total_graduated = 0
        self._total_speculative = 0
        self._total_failures = 0
        self._domains_explored: set[str] = set()

        # Operational state (can be set externally)
        self.pending_tasks: int = 0
        self.active_curriculum: bool = False
        self.fatigue: float = 0.0
        self.cooldown_until: float = 0.0

    def run_exploration_session(self, duration_minutes: int = 30) -> ExplorationReport:
        """Run a full R&D exploration session.

        Flow:
        1. Pull 3-5 random knowledge entries from Grimoire
        2. Generate cross-domain hypotheses
        3. For each hypothesis: test or store as speculative
        4. Graduate validated discoveries to production

        Args:
            duration_minutes: Target session duration (used for reporting).

        Returns:
            ExplorationReport summarizing the session.
        """
        session_id = str(uuid.uuid4())
        start_time = time.time()

        ideas_generated = 0
        experiments_run = 0
        discoveries_validated = 0
        discoveries_speculative = 0
        failures_stored = 0
        serendipitous_findings = 0

        try:
            # Step 1: Pull random knowledge
            knowledge_entries = self._pull_random_knowledge()
            if not knowledge_entries:
                logger.info("No knowledge entries available for exploration.")
                return ExplorationReport(
                    session_id=session_id,
                    duration_minutes=0.0,
                    ideas_generated=0,
                    experiments_run=0,
                    discoveries_validated=0,
                    discoveries_speculative=0,
                    failures_stored=0,
                    serendipitous_findings=0,
                    timestamp=start_time,
                )

            # Step 2: Generate hypotheses
            try:
                hypotheses = self.generate_hypotheses(knowledge_entries)
            except Exception as e:
                logger.error("Hypothesis generation failed: %s", e)
                elapsed = (time.time() - start_time) / 60.0
                return ExplorationReport(
                    session_id=session_id,
                    duration_minutes=elapsed,
                    ideas_generated=0,
                    experiments_run=0,
                    discoveries_validated=0,
                    discoveries_speculative=0,
                    failures_stored=0,
                    serendipitous_findings=0,
                    timestamp=start_time,
                )

            ideas_generated = len(hypotheses)

            # Step 3: Run experiments (up to max per session)
            for hypothesis in hypotheses[: self._max_experiments_per_session]:
                try:
                    # Record in experiment store
                    if self._experiment_store:
                        try:
                            self._experiment_store.store_failure(
                                hypothesis=hypothesis.get("hypothesis", ""),
                                approach=hypothesis.get("test_approach", "speculative"),
                                domain_tags=hypothesis.get("domains", []),
                                failure_reason="pending",
                                conditions={"session_id": session_id},
                                retry_triggers=[],
                            )
                        except Exception as e:
                            logger.warning("Failed to record experiment: %s", e)

                    result = self.run_experiment(hypothesis)
                    experiments_run += 1

                    if result.get("tested"):
                        if result.get("success"):
                            # Validate discovery
                            if self.validate_discovery(result):
                                self.graduate_to_production(result, self._grimoire)
                                discoveries_validated += 1
                                # Check for serendipitous findings
                                if result.get("metrics", {}).get("unexpected_improvement"):
                                    serendipitous_findings += 1
                            else:
                                discoveries_speculative += 1
                                self._store_speculative(result)
                        else:
                            failures_stored += 1
                            self._store_failure(result, session_id)
                    else:
                        discoveries_speculative += 1
                        self._store_speculative(result)

                    # Track domains
                    for domain in hypothesis.get("domains", []):
                        self._domains_explored.add(domain)

                except Exception as e:
                    logger.error("Experiment failed: %s", e)
                    failures_stored += 1

        except Exception as e:
            logger.error("Exploration session error: %s", e)

        elapsed = (time.time() - start_time) / 60.0

        # Update stats
        self._total_sessions += 1
        self._total_hypotheses += ideas_generated
        self._total_validated += discoveries_validated
        self._total_speculative += discoveries_speculative
        self._total_failures += failures_stored
        self._total_graduated += discoveries_validated

        report = ExplorationReport(
            session_id=session_id,
            duration_minutes=elapsed,
            ideas_generated=ideas_generated,
            experiments_run=experiments_run,
            discoveries_validated=discoveries_validated,
            discoveries_speculative=discoveries_speculative,
            failures_stored=failures_stored,
            serendipitous_findings=serendipitous_findings,
            timestamp=start_time,
        )

        logger.info(
            "Exploration session %s complete: %d ideas, %d experiments, %d validated",
            session_id[:8],
            ideas_generated,
            experiments_run,
            discoveries_validated,
        )

        return report

    def generate_hypotheses(self, knowledge_entries: list[dict]) -> list[dict]:
        """Generate cross-domain connection hypotheses from knowledge entries.

        Args:
            knowledge_entries: Random Grimoire entries from different domains.

        Returns:
            List of hypothesis dicts with keys:
            hypothesis, domains, testable, test_approach.
        """
        if not self._generate_fn:
            raise RuntimeError("No generate_fn available for hypothesis generation")

        entries_text = "\n".join(
            f"- [{e.get('domain', 'unknown')}] {e.get('content', str(e))}"
            for e in knowledge_entries
        )

        prompt = (
            "You have knowledge from different domains. Find unexpected connections, "
            "novel combinations, or approaches from one domain that might apply to another.\n\n"
            f"Knowledge:\n{entries_text}\n\n"
            "Generate 2-3 hypotheses about connections or applications.\n"
            "Return JSON array: [{\"hypothesis\": str, \"domains\": [str], "
            "\"testable\": bool, \"test_approach\": str}]"
        )

        raw_output = self._generate_fn(prompt)

        try:
            hypotheses = json.loads(raw_output)
            if isinstance(hypotheses, list):
                return hypotheses
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to extract JSON from mixed output
        try:
            start = raw_output.index("[")
            end = raw_output.rindex("]") + 1
            hypotheses = json.loads(raw_output[start:end])
            if isinstance(hypotheses, list):
                return hypotheses
        except (ValueError, json.JSONDecodeError):
            pass

        logger.warning("Could not parse hypotheses from model output")
        return []

    def run_experiment(self, hypothesis: dict) -> dict:
        """Run an experiment for a hypothesis.

        If testable and sandbox is available, generates test code and runs it.
        Otherwise stores as speculative with reasoning.

        Args:
            hypothesis: Dict with hypothesis, domains, testable, test_approach.

        Returns:
            Dict with hypothesis, tested, result, success, metrics.
        """
        is_testable = hypothesis.get("testable", False)

        if is_testable and self._sandbox is not None:
            try:
                test_code = self._generate_test_code(hypothesis)
                sandbox_result = self._sandbox.execute(test_code)

                success = sandbox_result.get("success", False)
                return {
                    "hypothesis": hypothesis.get("hypothesis", ""),
                    "domains": hypothesis.get("domains", []),
                    "tested": True,
                    "result": sandbox_result.get("output", ""),
                    "success": success,
                    "metrics": sandbox_result.get("metrics", {}),
                }
            except Exception as e:
                logger.warning("Sandbox execution failed: %s", e)
                return {
                    "hypothesis": hypothesis.get("hypothesis", ""),
                    "domains": hypothesis.get("domains", []),
                    "tested": True,
                    "result": f"Sandbox error: {e}",
                    "success": False,
                    "metrics": {},
                }

        # Not testable or no sandbox — store as speculative
        return {
            "hypothesis": hypothesis.get("hypothesis", ""),
            "domains": hypothesis.get("domains", []),
            "tested": False,
            "result": f"Speculative: {hypothesis.get('test_approach', 'no approach')}",
            "success": False,
            "metrics": {},
        }

    def validate_discovery(self, experiment_result: dict) -> bool:
        """Validate whether a discovery should graduate to production.

        Checks:
        - Not trivially obvious
        - Produces measurable improvement
        - Reproducible (tested successfully)

        Args:
            experiment_result: Result dict from run_experiment.

        Returns:
            True if discovery should graduate to production.
        """
        if not experiment_result.get("success"):
            return False

        if not experiment_result.get("tested"):
            return False

        metrics = experiment_result.get("metrics", {})

        # Must have some measurable outcome
        if not metrics:
            return False

        # Check for trivial results
        if metrics.get("trivial", False):
            return False

        # Must show improvement or novel finding
        improvement = metrics.get("improvement", 0)
        novel = metrics.get("novel", False)

        if improvement > 0 or novel:
            return True

        return False

    def graduate_to_production(self, discovery: dict, grimoire=None) -> str:
        """Move a validated discovery from speculative to production Grimoire.

        Tags with source: "morpheus_discovery", validated: True, and domain tags.

        Args:
            discovery: Validated experiment result dict.
            grimoire: Grimoire module (uses self._grimoire if None).

        Returns:
            Document ID from Grimoire, or empty string on failure.
        """
        target_grimoire = grimoire or self._grimoire
        if target_grimoire is None:
            logger.warning("No Grimoire available for graduation")
            return ""

        try:
            content = json.dumps({
                "hypothesis": discovery.get("hypothesis", ""),
                "result": discovery.get("result", ""),
                "domains": discovery.get("domains", []),
                "metrics": discovery.get("metrics", {}),
                "source": "morpheus_discovery",
                "validated": True,
            })

            doc_id = target_grimoire.store(
                content=content,
                category="morpheus_discovery",
                source="morpheus_rd_lab",
                metadata={
                    "source": "morpheus_discovery",
                    "validated": True,
                    "domains": discovery.get("domains", []),
                },
            )
            logger.info("Discovery graduated to production: %s", doc_id)
            return doc_id or ""
        except Exception as e:
            logger.error("Failed to graduate discovery: %s", e)
            return ""

    def should_explore(self) -> bool:
        """Determine if now is a good time for R&D exploration.

        Returns True if:
        - No pending tasks
        - No active learning curriculum
        - Not in cooldown period
        - Fatigue is below threshold (< 0.7)

        Returns:
            True if exploration is appropriate.
        """
        if self.pending_tasks > 0:
            return False

        if self.active_curriculum:
            return False

        if time.time() < self.cooldown_until:
            return False

        if self.fatigue >= 0.7:
            return False

        return True

    def get_exploration_stats(self) -> dict:
        """Return aggregate exploration statistics.

        Returns:
            Dict with total_sessions, total_hypotheses, validation_rate,
            discoveries_graduated, domains_explored.
        """
        validation_rate = 0.0
        if self._total_hypotheses > 0:
            validation_rate = self._total_validated / self._total_hypotheses

        return {
            "total_sessions": self._total_sessions,
            "total_hypotheses": self._total_hypotheses,
            "validation_rate": validation_rate,
            "discoveries_graduated": self._total_graduated,
            "discoveries_speculative": self._total_speculative,
            "total_failures": self._total_failures,
            "domains_explored": sorted(self._domains_explored),
        }

    # --- Internal helpers ---

    def _pull_random_knowledge(self, count: int = 5) -> list[dict]:
        """Pull domain-filtered knowledge from different technical Grimoire collections.

        Selects 3 different technical domains at random and pulls 1-2 entries
        from each, ensuring cross-domain pollination while excluding personal
        and non-technical collections.

        Args:
            count: Target number of entries (used as upper bound).

        Returns:
            List of knowledge entry dicts from diverse technical domains.
        """
        if self._grimoire is None:
            return []

        # Pick 3 different technical domains for cross-pollination
        num_domains = min(3, len(self.EXPLORATION_DOMAINS))
        selected_domains = random.sample(self.EXPLORATION_DOMAINS, num_domains)

        entries: list[dict] = []
        for domain in selected_domains:
            try:
                per_domain = random.randint(1, 2)
                domain_entries = self._grimoire.get_random_entries(
                    count=per_domain, domain=domain
                )
                if isinstance(domain_entries, list):
                    for entry in domain_entries:
                        if isinstance(entry, dict) and "domain" not in entry:
                            entry["domain"] = domain
                        entries.append(entry)
            except Exception as e:
                logger.warning("Failed to pull from domain %s: %s", domain, e)

        return entries[:count]

    def _generate_test_code(self, hypothesis: dict) -> str:
        """Generate test code for a hypothesis using the model.

        Args:
            hypothesis: Hypothesis dict with test_approach.

        Returns:
            Generated test code string.
        """
        if not self._generate_fn:
            return ""

        prompt = (
            f"Generate a simple Python test to evaluate this hypothesis:\n"
            f"Hypothesis: {hypothesis.get('hypothesis', '')}\n"
            f"Test approach: {hypothesis.get('test_approach', '')}\n\n"
            f"Return only executable Python code that prints results."
        )

        return self._generate_fn(prompt)

    def _store_speculative(self, result: dict) -> None:
        """Store a result in the speculative knowledge collection.

        Args:
            result: Experiment result dict.
        """
        if self._grimoire is None:
            return

        try:
            content = json.dumps({
                "hypothesis": result.get("hypothesis", ""),
                "result": result.get("result", ""),
                "domains": result.get("domains", []),
                "source": "morpheus_speculation",
                "validated": False,
            })

            self._grimoire.store(
                content=content,
                category="speculative_knowledge",
                source="morpheus_rd_lab",
                collection=self._speculation_collection,
            )
        except Exception as e:
            logger.warning("Failed to store speculative result: %s", e)

    def _store_failure(self, result: dict, session_id: str) -> None:
        """Store a failed experiment in the ExperimentStore.

        Args:
            result: Failed experiment result dict.
            session_id: Current session ID.
        """
        if self._experiment_store is None:
            return

        try:
            self._experiment_store.store_failure(
                hypothesis=result.get("hypothesis", ""),
                approach=result.get("result", ""),
                domain_tags=result.get("domains", []),
                failure_reason=result.get("result", "unknown failure"),
                conditions={"session_id": session_id},
                retry_triggers=[
                    f"new_grimoire_knowledge:{d}"
                    for d in result.get("domains", [])
                ],
            )
        except Exception as e:
            logger.warning("Failed to store failure: %s", e)
