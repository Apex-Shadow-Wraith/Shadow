"""
Tests for Sentinel tool selection in Step 4 (Plan).

Validates that security opinion/advice questions (no actionable input like
email/IP) skip tool dispatch and go to LLM response, while inputs with
emails or breach-related keywords correctly dispatch to breach_check.
"""

import pytest
from pathlib import Path
from modules.shadow.orchestrator import (
    Orchestrator,
    TaskClassification,
    TaskType,
    BrainType,
)


TEST_CONFIG = {
    "system": {"state_file": ""},
    "models": {
        "ollama_base_url": "http://localhost:11434",
        "router": {"name": "phi4-mini"},
        "fast_brain": {"name": "phi4-mini"},
        "smart_brain": {"name": "phi4-mini"},
    },
    "decision_loop": {
        "context_memories": 3,
    },
}


@pytest.fixture
def config(tmp_path: Path) -> dict:
    """Orchestrator config matching existing test conventions."""
    cfg = dict(TEST_CONFIG)
    cfg["system"] = {"state_file": str(tmp_path / "state.json")}
    return cfg


def _sentinel_classification(task_type: TaskType = TaskType.QUESTION) -> TaskClassification:
    """Helper: build a Sentinel-targeted classification."""
    return TaskClassification(
        task_type=task_type,
        complexity="simple",
        target_module="sentinel",
        brain=BrainType.FAST,
        safety_flag=False,
        priority=1,
    )


class TestSentinelOpinionQuestions:
    """Security opinion/advice questions must NOT dispatch breach_check."""

    @pytest.mark.asyncio
    async def test_password_advice_skips_tool_dispatch(self, config: dict):
        """'Store passwords in plain text' is an opinion question — no tool."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "I think we should store all passwords in plain text for easy access. What do you think?",
            _sentinel_classification(),
            [],
        )
        tools = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert tools == [], (
            f"Opinion question dispatched tools {tools} — expected no tools (LLM-only)"
        )

    @pytest.mark.asyncio
    async def test_security_best_practice_skips_tool_dispatch(self, config: dict):
        """General security best-practice question — no tool needed."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "What are the best practices for securing a REST API?",
            _sentinel_classification(),
            [],
        )
        tools = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert tools == [], (
            f"Best-practice question dispatched tools {tools} — expected no tools"
        )

    @pytest.mark.asyncio
    async def test_encryption_advice_skips_tool_dispatch(self, config: dict):
        """Encryption advice question — no actionable input, LLM-only."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Should I use AES-256 or ChaCha20 for encrypting files at rest?",
            _sentinel_classification(),
            [],
        )
        tools = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert tools == [], (
            f"Encryption advice dispatched tools {tools} — expected no tools"
        )

    @pytest.mark.asyncio
    async def test_firewall_opinion_skips_tool_dispatch(self, config: dict):
        """Opinion about firewall strategy — no IP or config to analyze."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Is it safe to leave port 22 open on a public server?",
            _sentinel_classification(),
            [],
        )
        tools = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert tools == [], (
            f"Firewall opinion dispatched tools {tools} — expected no tools"
        )

    @pytest.mark.asyncio
    async def test_generic_security_question_skips_breach_check(self, config: dict):
        """Vague security question must NOT fall through to breach_check."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "How do I protect my home network from hackers?",
            _sentinel_classification(),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "breach_check" not in tool_names, (
            "Generic security question incorrectly dispatched to breach_check"
        )


class TestSentinelBreachCheckDispatch:
    """breach_check SHOULD fire when the input contains an email or breach keywords."""

    @pytest.mark.asyncio
    async def test_email_input_dispatches_breach_check(self, config: dict):
        """Input with an email address should dispatch breach_check."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Has john.doe@example.com been in any data breaches?",
            _sentinel_classification(),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "breach_check" in tool_names, (
            f"Email input dispatched {tool_names} — expected breach_check"
        )

    @pytest.mark.asyncio
    async def test_breach_keyword_dispatches_breach_check(self, config: dict):
        """'breach' keyword without email should still try breach_check."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Check if my account was in a breach",
            _sentinel_classification(),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "breach_check" in tool_names, (
            f"Breach keyword dispatched {tool_names} — expected breach_check"
        )

    @pytest.mark.asyncio
    async def test_pwned_keyword_dispatches_breach_check(self, config: dict):
        """'pwned' keyword should dispatch breach_check."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Have I been pwned?",
            _sentinel_classification(),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "breach_check" in tool_names, (
            f"Pwned keyword dispatched {tool_names} — expected breach_check"
        )

    @pytest.mark.asyncio
    async def test_compromised_keyword_dispatches_breach_check(self, config: dict):
        """'compromised' keyword should dispatch breach_check."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Was my email compromised in the latest leak?",
            _sentinel_classification(),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "breach_check" in tool_names, (
            f"Compromised keyword dispatched {tool_names} — expected breach_check"
        )


class TestSentinelExistingToolKeywords:
    """Existing keyword-based tool selection must still work."""

    @pytest.mark.asyncio
    async def test_scan_keyword_dispatches_network_scan(self, config: dict):
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Scan the network for open ports",
            _sentinel_classification(TaskType.ACTION),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "network_scan" in tool_names

    @pytest.mark.asyncio
    async def test_integrity_keyword_dispatches_file_check(self, config: dict):
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Check file integrity of the config directory",
            _sentinel_classification(TaskType.ACTION),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "file_integrity_check" in tool_names

    @pytest.mark.asyncio
    async def test_threat_keyword_dispatches_threat_assess(self, config: dict):
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Assess the threat level of this suspicious process",
            _sentinel_classification(TaskType.ACTION),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "threat_assess" in tool_names
