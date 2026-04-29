"""
Tests for security-tool selection in Step 4 (Plan) — post-merge.
==================================================================
Mirrors the pre-merge tests/test_sentinel_tool_selection.py but
target_module is now "cerberus" (the absorbing module) and the
build-steps branch fires when classification.target_module ==
"cerberus" AND user input contains a security keyword. Behavior is
preserved: opinion/advice questions skip tool dispatch and go to
LLM response; inputs with email/breach keywords dispatch
breach_check; scan/integrity/threat keywords dispatch their
matching tools.
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


def _security_classification(task_type: TaskType = TaskType.QUESTION) -> TaskClassification:
    """Helper: classification targeting the Cerberus security surface."""
    return TaskClassification(
        task_type=task_type,
        complexity="simple",
        target_module="cerberus",
        brain=BrainType.FAST,
        safety_flag=False,
        priority=1,
    )


class TestSecurityOpinionQuestions:
    """Security opinion/advice questions must NOT dispatch breach_check."""

    @pytest.mark.asyncio
    async def test_password_advice_skips_tool_dispatch(self, config: dict):
        """'Store passwords in plain text' is an opinion question — no tool."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "I think we should store all passwords in plain text for easy access. What do you think?",
            _security_classification(),
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
            _security_classification(),
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
            _security_classification(),
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
            _security_classification(),
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
            _security_classification(),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "breach_check" not in tool_names, (
            "Generic security question incorrectly dispatched to breach_check"
        )


class TestBreachCheckDispatch:
    """breach_check SHOULD fire when the input contains an email or breach keywords."""

    @pytest.mark.asyncio
    async def test_email_input_dispatches_breach_check(self, config: dict):
        """Input with an email address should dispatch breach_check."""
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Has john.doe@example.com been in any data breaches?",
            _security_classification(),
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
            _security_classification(),
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
            _security_classification(),
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
            _security_classification(),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "breach_check" in tool_names, (
            f"Compromised keyword dispatched {tool_names} — expected breach_check"
        )


class TestExistingToolKeywords:
    """Existing keyword-based tool selection must still work."""

    @pytest.mark.asyncio
    async def test_scan_keyword_dispatches_network_scan(self, config: dict):
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Scan the network for open ports",
            _security_classification(TaskType.ACTION),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "network_scan" in tool_names

    @pytest.mark.asyncio
    async def test_integrity_keyword_dispatches_file_check(self, config: dict):
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Check file integrity of the config directory",
            _security_classification(TaskType.ACTION),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "file_integrity_check" in tool_names

    @pytest.mark.asyncio
    async def test_threat_keyword_dispatches_threat_assess(self, config: dict):
        orch = Orchestrator(config)
        plan = await orch._step4_plan(
            "Assess the threat level of this suspicious process",
            _security_classification(TaskType.ACTION),
            [],
        )
        tool_names = [s.get("tool") for s in plan.steps if s.get("tool")]
        assert "threat_assess" in tool_names
