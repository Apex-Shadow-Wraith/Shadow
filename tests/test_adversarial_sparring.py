"""
Tests for Adversarial Model Sparring — Dual-Instance Debate
=============================================================
~25 tests covering debate flow, critic parsing, quality metrics,
Grimoire storage, decision logic, and edge cases.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from modules.shadow.adversarial_sparring import (
    CRITIC_SYSTEM_PROMPT,
    SOLVER_SYSTEM_PROMPT,
    AdversarialSparring,
    DebateRound,
    SparringResult,
)


# ── Helpers ─────────────────────────────────────────────────────────

def _make_generate_fn(responses: list[str]):
    """Create a mock generate_fn that returns responses in order."""
    call_log = []
    idx = {"i": 0}

    def fn(system_prompt: str, prompt: str) -> str:
        call_log.append({"system_prompt": system_prompt, "prompt": prompt})
        resp = responses[idx["i"] % len(responses)]
        idx["i"] += 1
        return resp

    fn.call_log = call_log
    return fn


# ── Debate Flow Tests ───────────────────────────────────────────────

class TestDebateFlow:
    """Tests for the core spar() method and debate mechanics."""

    def test_solver_and_critic_called_alternately(self):
        """Solver and critic should be called in alternating order."""
        gen = _make_generate_fn([
            "Solution v1",             # solver round 1
            "1. Missing edge case",    # critic round 1
            "Solution v2",             # solver round 2
            "No issues found",         # critic round 2
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        sparring.spar("Implement sort")

        prompts = [c["system_prompt"] for c in gen.call_log]
        assert prompts[0] == SOLVER_SYSTEM_PROMPT
        assert prompts[1] == CRITIC_SYSTEM_PROMPT
        assert prompts[2] == SOLVER_SYSTEM_PROMPT
        assert prompts[3] == CRITIC_SYSTEM_PROMPT

    def test_three_rounds_by_default(self):
        """Default max_rounds=3 should produce up to 3 rounds."""
        gen = _make_generate_fn([
            "Solution v1", "1. Issue A",
            "Solution v2", "1. Issue B",
            "Solution v3", "1. Issue C",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        result = sparring.spar("Complex task")

        assert len(result.rounds) == 3

    def test_early_exit_when_no_issues(self):
        """Debate should stop early when critic finds no issues."""
        gen = _make_generate_fn([
            "Perfect solution",
            "No issues found. The solution is correct.",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        result = sparring.spar("Simple task")

        assert len(result.rounds) == 1
        assert result.rounds[0].issues_found == []

    def test_solver_receives_critics_issues(self):
        """Solver's prompt in round 2+ should contain critic's issues."""
        gen = _make_generate_fn([
            "Solution v1",
            "1. Missing null check\n2. Off-by-one error",
            "Solution v2 with fixes",
            "No issues found",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        sparring.spar("Fix the bug")

        # Round 2 solver prompt should reference the issues
        round2_solver_prompt = gen.call_log[2]["prompt"]
        assert "Missing null check" in round2_solver_prompt
        assert "Off-by-one error" in round2_solver_prompt

    def test_final_solution_is_solvers_last_response(self):
        """final_solution should be the solver's most recent output."""
        gen = _make_generate_fn([
            "Solution v1",
            "1. Bug found",
            "Solution v2 FINAL",
            "No issues found",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        result = sparring.spar("Task")

        assert result.final_solution == "Solution v2 FINAL"


# ── Critic Parsing Tests ───────────────────────────────────────────

class TestCriticParsing:
    """Tests for parse_critic_issues()."""

    def test_numbered_list(self):
        """Numbered lists should be parsed into individual issues."""
        sparring = AdversarialSparring()
        issues = sparring.parse_critic_issues(
            "1. Missing edge case for empty input\n"
            "2. Off-by-one error in loop\n"
            "3. No error handling for network failure"
        )
        assert len(issues) == 3
        assert "Missing edge case for empty input" in issues

    def test_bullet_points(self):
        """Bullet points should be parsed into individual issues."""
        sparring = AdversarialSparring()
        issues = sparring.parse_critic_issues(
            "- Division by zero possible\n"
            "- Memory leak in handler\n"
            "* Thread safety concern"
        )
        assert len(issues) == 3

    def test_no_issues_found(self):
        """'No issues found' should return empty list."""
        sparring = AdversarialSparring()
        assert sparring.parse_critic_issues("No issues found") == []

    def test_looks_good(self):
        """'looks good' / 'correct' signals should return empty list."""
        sparring = AdversarialSparring()
        assert sparring.parse_critic_issues("The solution looks good.") == []
        assert sparring.parse_critic_issues("This is correct.") == []

    def test_mixed_format(self):
        """Mixed numbered/bullet/labeled formats should all be extracted."""
        sparring = AdversarialSparring()
        issues = sparring.parse_critic_issues(
            "Issue: SQL injection vulnerability\n"
            "1. Missing input validation\n"
            "- No rate limiting\n"
            "Problem: Hardcoded credentials"
        )
        assert len(issues) == 4

    def test_empty_response(self):
        """Empty response should return empty list."""
        sparring = AdversarialSparring()
        assert sparring.parse_critic_issues("") == []
        assert sparring.parse_critic_issues("   ") == []

    def test_labeled_issues(self):
        """Labeled issues (Issue:, Bug:, Error:) should be extracted."""
        sparring = AdversarialSparring()
        issues = sparring.parse_critic_issues(
            "Bug: Null pointer dereference\n"
            "Error: Uncaught exception in handler"
        )
        assert len(issues) == 2


# ── Quality Metric Tests ───────────────────────────────────────────

class TestQualityMetrics:
    """Tests for confidence scoring and improvement detection."""

    def test_confidence_improves_when_issues_resolved(self):
        """confidence_after >= confidence_before when issues were found and fixed."""
        gen = _make_generate_fn([
            "Short solution",
            "1. Missing edge case\n2. No error handling",
            "Much longer and more thorough solution that addresses all the edge cases "
            "and includes proper error handling with detailed explanations of the approach",
            "No issues found",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        result = sparring.spar("Implement error handling")

        assert result.confidence_after >= result.confidence_before

    def test_improved_true_when_confidence_raised(self):
        """improved=True when sparring raised confidence."""
        gen = _make_generate_fn([
            "Brief",
            "1. Too brief, missing details",
            "A comprehensive solution with all the details that were missing before "
            "including thorough explanations and edge case coverage for the task",
            "No issues found",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        result = sparring.spar("Explain algorithm")

        assert result.improved is True

    def test_improved_false_when_no_improvement(self):
        """improved=False when sparring didn't help."""
        gen = _make_generate_fn([
            "Already a good solution with sufficient detail and explanation",
            "No issues found",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        result = sparring.spar("Simple question")

        # No issues found, no resolution boost — improved should be False
        assert result.total_issues_found == 0


# ── Grimoire Storage Tests ─────────────────────────────────────────

class TestGrimoireStorage:
    """Tests for store_critique_patterns()."""

    def test_stores_in_grimoire(self):
        """Critique patterns should be stored via grimoire.store()."""
        mock_grimoire = MagicMock()
        mock_grimoire.store.return_value = "doc_123"

        sparring = AdversarialSparring()
        result = SparringResult(
            task="Implement sort",
            rounds=[
                DebateRound(
                    round_number=1,
                    solver_response="v1",
                    critic_response="1. Bug found",
                    issues_found=["Bug found"],
                    solver_addressed=True,
                    timestamp=time.time(),
                ),
                DebateRound(
                    round_number=2,
                    solver_response="v2",
                    critic_response="No issues found",
                    issues_found=[],
                    solver_addressed=False,
                    timestamp=time.time(),
                ),
            ],
            final_solution="v2",
            total_issues_found=1,
            issues_resolved=1,
            confidence_before=0.5,
            confidence_after=0.7,
            improved=True,
            duration_seconds=1.0,
        )

        doc_ids = sparring.store_critique_patterns(result, mock_grimoire)
        assert len(doc_ids) == 1
        mock_grimoire.store.assert_called_once()

    def test_only_stores_resolved_issues(self):
        """Only issues from rounds where solver_addressed=True should be stored."""
        mock_grimoire = MagicMock()
        mock_grimoire.store.return_value = "doc_456"

        sparring = AdversarialSparring()
        result = SparringResult(
            task="Task",
            rounds=[
                DebateRound(
                    round_number=1,
                    solver_response="v1",
                    critic_response="1. Issue A\n2. Issue B",
                    issues_found=["Issue A", "Issue B"],
                    solver_addressed=True,
                    timestamp=time.time(),
                ),
                DebateRound(
                    round_number=2,
                    solver_response="v2",
                    critic_response="1. Issue C",
                    issues_found=["Issue C"],
                    solver_addressed=False,  # last round, not addressed
                    timestamp=time.time(),
                ),
            ],
            final_solution="v2",
            total_issues_found=3,
            issues_resolved=2,
            confidence_before=0.4,
            confidence_after=0.6,
            improved=True,
            duration_seconds=1.0,
        )

        doc_ids = sparring.store_critique_patterns(result, mock_grimoire)
        # Only 2 issues from round 1 (addressed), not Issue C from round 2
        assert len(doc_ids) == 2
        assert mock_grimoire.store.call_count == 2

    def test_critique_pattern_metadata(self):
        """Stored patterns should have correct metadata fields."""
        mock_grimoire = MagicMock()
        mock_grimoire.store.return_value = "doc_789"

        sparring = AdversarialSparring()
        result = SparringResult(
            task="Implement database migration",
            rounds=[
                DebateRound(
                    round_number=1,
                    solver_response="v1",
                    critic_response="1. SQL injection vulnerability",
                    issues_found=["SQL injection vulnerability"],
                    solver_addressed=True,
                    timestamp=time.time(),
                ),
            ],
            final_solution="v2",
            total_issues_found=1,
            issues_resolved=1,
            confidence_before=0.5,
            confidence_after=0.7,
            improved=True,
            duration_seconds=1.0,
        )

        sparring.store_critique_patterns(result, mock_grimoire)
        call_kwargs = mock_grimoire.store.call_args
        metadata = call_kwargs.kwargs.get("metadata") or call_kwargs[1].get("metadata")
        category = call_kwargs.kwargs.get("category") or call_kwargs[1].get("category")

        assert category == "critique_pattern"
        assert metadata["resolution"] == "resolved"
        assert metadata["source"] == "adversarial_sparring"
        assert metadata["round_number"] == 1


# ── Decision Logic Tests ───────────────────────────────────────────

class TestShouldSpar:
    """Tests for should_spar() decision method."""

    def test_low_confidence_code_task(self):
        """Low confidence + code task → should spar."""
        sparring = AdversarialSparring()
        assert sparring.should_spar("Implement a binary search algorithm", 0.4) is True

    def test_high_confidence(self):
        """High confidence → should NOT spar."""
        sparring = AdversarialSparring()
        assert sparring.should_spar("Implement sort", 0.8) is False

    def test_simple_greeting(self):
        """Simple greeting → should NOT spar."""
        sparring = AdversarialSparring()
        assert sparring.should_spar("Hello, how are you?", 0.3) is False

    def test_security_task_low_confidence(self):
        """Security task with low confidence → should spar."""
        sparring = AdversarialSparring()
        assert sparring.should_spar("Review authentication vulnerability", 0.5) is True

    def test_math_task_low_confidence(self):
        """Math task with low confidence → should spar."""
        sparring = AdversarialSparring()
        assert sparring.should_spar("Calculate the integral of this function", 0.4) is True


# ── Edge Case Tests ─────────────────────────────────────────────────

class TestEdgeCases:
    """Tests for error handling and boundary conditions."""

    def test_generate_fn_failure_returns_best_solution(self):
        """If generate_fn fails, return the best available solution."""
        call_count = {"n": 0}

        def failing_gen(system_prompt, prompt):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return "Initial solution from solver"
            if call_count["n"] == 2:
                return "1. Issue found"
            raise RuntimeError("Model crashed")

        sparring = AdversarialSparring(generate_fn=failing_gen, max_rounds=3)
        result = sparring.spar("Complex task")

        assert result.final_solution is not None
        assert len(result.final_solution) > 0

    def test_single_round(self):
        """max_rounds=1 should work correctly."""
        gen = _make_generate_fn([
            "One-shot solution",
            "1. Minor issue",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=1)
        result = sparring.spar("Quick task")

        assert len(result.rounds) == 1

    def test_empty_initial_solution(self):
        """No initial_solution → solver generates from scratch."""
        gen = _make_generate_fn([
            "Generated from scratch",
            "No issues found",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        result = sparring.spar("New task", initial_solution=None)

        assert result.final_solution == "Generated from scratch"

    def test_with_initial_solution(self):
        """Providing initial_solution should pass it to solver."""
        gen = _make_generate_fn([
            "Improved solution",
            "No issues found",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        result = sparring.spar("Task", initial_solution="Starting point")

        # Solver should have received the starting point
        assert "Starting point" in gen.call_log[0]["prompt"]

    def test_get_sparring_stats_empty(self):
        """Stats with no history should return zeros."""
        sparring = AdversarialSparring()
        stats = sparring.get_sparring_stats()

        assert stats["total_spars"] == 0
        assert stats["avg_rounds"] == 0.0
        assert stats["avg_issues_found"] == 0.0

    def test_get_sparring_stats_with_data(self):
        """Stats should reflect actual sparring history."""
        gen = _make_generate_fn([
            "Solution",
            "1. Issue",
            "Fixed solution",
            "No issues found",
        ])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=3)
        sparring.spar("Task 1")
        sparring.spar("Task 2")

        stats = sparring.get_sparring_stats()
        assert stats["total_spars"] == 2
        assert stats["avg_rounds"] > 0

    def test_duration_tracked(self):
        """duration_seconds should be positive."""
        gen = _make_generate_fn(["Solution", "No issues found"])
        sparring = AdversarialSparring(generate_fn=gen, max_rounds=1)
        result = sparring.spar("Task")

        assert result.duration_seconds >= 0

    def test_no_generate_fn(self):
        """None generate_fn should handle gracefully."""
        sparring = AdversarialSparring(generate_fn=None, max_rounds=3)
        result = sparring.spar("Task")

        assert result.final_solution == ""
        assert len(result.rounds) == 0
