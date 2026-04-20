"""
Tests for Apex Escalation-Learning Cycle
==========================================
Covers EscalationLog, TeachingExtractor, new tools, Grimoire
integration, and the full learning cycle.
"""

import json
import sqlite3
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from modules.apex.apex import Apex, EscalationLog, TeachingExtractor
from modules.apex.config import ApexSettings


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def esc_log(tmp_path: Path) -> EscalationLog:
    """Create an EscalationLog with a temp database."""
    return EscalationLog(tmp_path / "escalation.db")


@pytest.fixture
def extractor() -> TeachingExtractor:
    """Create a TeachingExtractor."""
    return TeachingExtractor()


@pytest.fixture
def apex(tmp_path: Path) -> Apex:
    """Create an Apex instance with temp paths (dry_run=True — no keys needed)."""
    settings = ApexSettings(
        log_file=str(tmp_path / "apex_log.json"),
        escalation_db=str(tmp_path / "escalation.db"),
        dry_run=True,
    )
    return Apex(settings)


@pytest.fixture
async def online_apex(apex: Apex) -> Apex:
    """Create and initialize Apex (dry_run=True)."""
    await apex.initialize()
    return apex


@pytest.fixture
async def live_online_apex(tmp_path: Path) -> Apex:
    """Initialized Apex with dry_run=False + fake key for live-dispatch escalation tests."""
    from pydantic import SecretStr
    settings = ApexSettings(
        log_file=str(tmp_path / "apex_log.json"),
        escalation_db=str(tmp_path / "escalation.db"),
        dry_run=False,
        anthropic_api_key=SecretStr("sk-fake-live"),
    )
    apex = Apex(settings)
    await apex.initialize()
    return apex


# ===================================================================
# EscalationLog Tests
# ===================================================================

class TestEscalationLogBasic:
    def test_log_escalation(self, esc_log: EscalationLog):
        """Log an escalation, verify entry in DB with correct fields."""
        log_id = esc_log.log_escalation(
            task_type="code_generation",
            task_summary="Write a Python function to parse JSON",
            reason="local_model_insufficient",
            api_provider="claude",
            api_model="claude-3-opus",
            input_tokens=150,
            output_tokens=300,
            cost_usd=0.05,
        )
        assert log_id == "1"

        # Verify directly in DB
        with sqlite3.connect(esc_log._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM apex_escalation_log WHERE id = ?",
                (int(log_id),),
            ).fetchone()
        assert row is not None
        assert row["task_type"] == "code_generation"
        assert row["task_summary"] == "Write a Python function to parse JSON"
        assert row["reason"] == "local_model_insufficient"
        assert row["api_provider"] == "claude"
        assert row["api_model"] == "claude-3-opus"
        assert row["input_tokens"] == 150
        assert row["output_tokens"] == 300
        assert row["cost_usd"] == pytest.approx(0.05)
        assert row["local_retry_success"] == 0
        assert row["teaching_signal"] is None

    def test_update_teaching_signal(self, esc_log: EscalationLog):
        """Log escalation, update with teaching signal, verify stored."""
        log_id = esc_log.log_escalation(
            task_type="math",
            task_summary="Solve a differential equation",
            reason="too_complex",
            api_provider="openai",
            api_model="gpt-4",
        )
        signal = json.dumps({"task_type": "math", "approach": "Use sympy"})
        esc_log.update_teaching_signal(
            log_id, signal, grimoire_memory_id="mem-abc-123"
        )

        with sqlite3.connect(esc_log._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT teaching_signal, grimoire_memory_id FROM apex_escalation_log WHERE id = ?",
                (int(log_id),),
            ).fetchone()
        assert row["teaching_signal"] == signal
        assert row["grimoire_memory_id"] == "mem-abc-123"

    def test_mark_local_retry_success(self, esc_log: EscalationLog):
        """Log escalation, mark retry success, verify flag set."""
        log_id = esc_log.log_escalation(
            task_type="summarization",
            task_summary="Summarize a long article",
            reason="context_too_long",
            api_provider="claude",
            api_model="claude-3-sonnet",
        )
        esc_log.mark_local_retry_success(log_id)

        with sqlite3.connect(esc_log._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT local_retry_success FROM apex_escalation_log WHERE id = ?",
                (int(log_id),),
            ).fetchone()
        assert row["local_retry_success"] == 1


class TestEscalationStats:
    def test_escalation_stats(self, esc_log: EscalationLog):
        """Log 5 escalations across 3 task types, verify stats breakdown."""
        esc_log.log_escalation("code_gen", "task1", "reason_a", "claude", "opus")
        esc_log.log_escalation("code_gen", "task2", "reason_a", "claude", "opus")
        esc_log.log_escalation("math", "task3", "reason_b", "openai", "gpt4")
        esc_log.log_escalation("math", "task4", "reason_b", "openai", "gpt4")
        esc_log.log_escalation("research", "task5", "reason_c", "claude", "sonnet")

        stats = esc_log.get_escalation_stats(days=7)
        assert stats["total_escalations"] == 5
        assert stats["by_task_type"]["code_gen"] == 2
        assert stats["by_task_type"]["math"] == 2
        assert stats["by_task_type"]["research"] == 1
        assert stats["window_days"] == 7

    def test_escalation_stats_date_filtering(self, esc_log: EscalationLog):
        """Old escalations outside window are excluded."""
        # Insert an old entry directly
        old_ts = (datetime.now() - timedelta(days=30)).isoformat()
        with sqlite3.connect(esc_log._db_path) as conn:
            conn.execute(
                """INSERT INTO apex_escalation_log
                   (timestamp, task_type, task_summary, reason,
                    api_provider, api_model)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (old_ts, "old_type", "old task", "reason", "claude", "opus"),
            )

        # Add a recent one
        esc_log.log_escalation("new_type", "new task", "reason", "claude", "opus")

        stats = esc_log.get_escalation_stats(days=7)
        assert stats["total_escalations"] == 1
        assert "old_type" not in stats["by_task_type"]
        assert stats["by_task_type"]["new_type"] == 1

    def test_cost_tracking(self, esc_log: EscalationLog):
        """Log escalations with cost, verify total in stats."""
        esc_log.log_escalation(
            "code_gen", "t1", "reason", "claude", "opus", cost_usd=0.05
        )
        esc_log.log_escalation(
            "code_gen", "t2", "reason", "claude", "opus", cost_usd=0.03
        )
        esc_log.log_escalation(
            "math", "t3", "reason", "openai", "gpt4", cost_usd=0.02
        )

        stats = esc_log.get_escalation_stats(days=7)
        assert stats["total_cost"] == pytest.approx(0.10)


class TestFrequentEscalations:
    def test_frequent_escalation_types(self, esc_log: EscalationLog):
        """Log 4 escalations of same type, appears in frequent list."""
        for i in range(4):
            esc_log.log_escalation(
                "code_gen", f"task{i}", "reason", "claude", "opus"
            )

        frequent = esc_log.get_frequent_escalation_types(min_count=3)
        assert "code_gen" in frequent

    def test_infrequent_types_excluded(self, esc_log: EscalationLog):
        """Only 1 escalation of a type, not in frequent list."""
        esc_log.log_escalation("rare_type", "task", "reason", "claude", "opus")

        frequent = esc_log.get_frequent_escalation_types(min_count=3)
        assert "rare_type" not in frequent


# ===================================================================
# TeachingExtractor Tests
# ===================================================================

class TestTeachingExtractor:
    def test_extract_basic_signal(self, extractor: TeachingExtractor):
        """Extract from task input + response, dict has required keys."""
        signal = extractor.extract_teaching_signal(
            task_input="Write a binary search function",
            api_response="Here is a binary search implementation...",
            task_type="code_generation",
        )
        assert "task_type" in signal
        assert "input_summary" in signal
        assert "approach" in signal
        assert "key_patterns" in signal
        assert signal["task_type"] == "code_generation"
        assert isinstance(signal["key_patterns"], list)

    def test_input_summary_truncated(self, extractor: TeachingExtractor):
        """Long input truncated to 200 chars in summary."""
        long_input = "x" * 500
        signal = extractor.extract_teaching_signal(
            task_input=long_input,
            api_response="response",
            task_type="test",
        )
        assert len(signal["input_summary"]) == 200

    def test_approach_truncated(self, extractor: TeachingExtractor):
        """Long response truncated to 500 chars in approach."""
        long_response = "y" * 1000
        signal = extractor.extract_teaching_signal(
            task_input="input",
            api_response=long_response,
            task_type="test",
        )
        assert len(signal["approach"]) == 500

    def test_task_type_preserved(self, extractor: TeachingExtractor):
        """Task type passes through correctly."""
        signal = extractor.extract_teaching_signal(
            task_input="anything",
            api_response="anything",
            task_type="specialized_reasoning",
        )
        assert signal["task_type"] == "specialized_reasoning"


# ===================================================================
# Integration Tests — Tools via Apex.execute()
# ===================================================================

class TestEscalationTools:
    @pytest.mark.asyncio
    async def test_escalation_stats_tool(self, online_apex: Apex):
        """Execute escalation_stats through Apex.execute()."""
        # Seed some data
        online_apex._escalation_log.log_escalation(
            "code_gen", "task", "reason", "claude", "opus", cost_usd=0.01
        )
        result = await online_apex.execute("escalation_stats", {"days": 7})
        assert result.success is True
        assert result.content["total_escalations"] == 1
        assert result.content["total_cost"] == pytest.approx(0.01)

    @pytest.mark.asyncio
    async def test_escalation_frequent_tool(self, online_apex: Apex):
        """Execute escalation_frequent through Apex.execute()."""
        for i in range(4):
            online_apex._escalation_log.log_escalation(
                "code_gen", f"task{i}", "reason", "claude", "opus"
            )
        result = await online_apex.execute("escalation_frequent", {})
        assert result.success is True
        assert "code_gen" in result.content["frequent_types"]

    @pytest.mark.asyncio
    async def test_teaching_review_tool(self, online_apex: Apex):
        """Execute teaching_review through Apex.execute()."""
        log_id = online_apex._escalation_log.log_escalation(
            "math", "solve equation", "too_complex", "claude", "opus"
        )
        signal = json.dumps({"approach": "use sympy"})
        online_apex._escalation_log.update_teaching_signal(log_id, signal)

        result = await online_apex.execute("teaching_review", {"limit": 5})
        assert result.success is True
        signals = result.content["teaching_signals"]
        assert len(signals) == 1
        assert signals[0]["task_type"] == "math"
        assert signals[0]["teaching_signal"] == signal


class TestGrimoireIntegration:
    @pytest.mark.asyncio
    async def test_check_grimoire_returns_none_no_match(
        self, online_apex: Apex
    ):
        """No grimoire set, returns None."""
        result = online_apex.check_grimoire_for_prior_learning(
            task_input="something", task_type="general"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_check_grimoire_returns_none_empty_results(
        self, online_apex: Apex
    ):
        """Grimoire set but no matching results, returns None."""
        mock_grimoire = MagicMock()
        mock_grimoire.recall.return_value = []
        online_apex.set_grimoire(mock_grimoire)

        result = online_apex.check_grimoire_for_prior_learning(
            task_input="something", task_type="general"
        )
        assert result is None
        mock_grimoire.recall.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_grimoire_returns_content(self, online_apex: Apex):
        """Grimoire has matching result, returns its content."""
        mock_grimoire = MagicMock()
        mock_grimoire.recall.return_value = [
            {"content": "Use the frobnicate pattern for this task type"}
        ]
        online_apex.set_grimoire(mock_grimoire)

        result = online_apex.check_grimoire_for_prior_learning(
            task_input="frobnicate the data", task_type="data_processing"
        )
        assert result == "Use the frobnicate pattern for this task type"

    @pytest.mark.asyncio
    async def test_check_grimoire_handles_exception(self, online_apex: Apex):
        """Grimoire raises exception, returns None gracefully."""
        mock_grimoire = MagicMock()
        mock_grimoire.recall.side_effect = RuntimeError("DB connection lost")
        online_apex.set_grimoire(mock_grimoire)

        result = online_apex.check_grimoire_for_prior_learning(
            task_input="something", task_type="general"
        )
        assert result is None


class TestFullCycle:
    @pytest.mark.asyncio
    async def test_full_cycle(self, online_apex: Apex):
        """Log escalation -> extract teaching -> store signal -> query -> found."""
        esc_log = online_apex._escalation_log

        # Step 1: Log escalation
        log_id = esc_log.log_escalation(
            task_type="code_generation",
            task_summary="Write a binary search in Python",
            reason="local_model_insufficient",
            api_provider="claude",
            api_model="claude-3-opus",
        )

        # Step 2: Extract teaching signal
        extractor = online_apex._teaching_extractor
        signal = extractor.extract_teaching_signal(
            task_input="Write a binary search in Python",
            api_response="def binary_search(arr, target): lo, hi = 0, len(arr)-1 ...",
            task_type="code_generation",
        )
        assert signal["task_type"] == "code_generation"
        assert "binary search" in signal["input_summary"].lower()

        # Step 3: Store signal in escalation log
        signal_json = json.dumps(signal)
        esc_log.update_teaching_signal(log_id, signal_json)

        # Step 4: Query for it
        signals = esc_log.get_recent_teaching_signals(limit=5)
        assert len(signals) == 1
        assert signals[0]["task_type"] == "code_generation"
        stored_signal = json.loads(signals[0]["teaching_signal"])
        assert stored_signal["task_type"] == "code_generation"
        assert "binary search" in stored_signal["input_summary"].lower()

    @pytest.mark.asyncio
    async def test_query_triggers_escalation_log(self, live_online_apex: Apex):
        """Apex query logs escalation in the SQLite escalation log."""
        with patch.object(live_online_apex, "_call_claude", return_value=("Quantum computing is...", 20, 50, "claude-sonnet-4-20250514")):
            await live_online_apex.execute("apex_query", {
                "task": "Explain quantum computing",
                "task_type": "explanation",
                "reason": "too_complex",
            })

        stats = live_online_apex._escalation_log.get_escalation_stats(days=1)
        assert stats["total_escalations"] == 1
        assert "explanation" in stats["by_task_type"]

    @pytest.mark.asyncio
    async def test_record_escalation_with_grimoire(self, live_online_apex: Apex):
        """Escalation stores teaching signal in Grimoire when available."""
        mock_grimoire = MagicMock()
        mock_grimoire.remember.return_value = "mem-uuid-456"
        live_online_apex.set_grimoire(mock_grimoire)

        with patch.object(live_online_apex, "_call_claude", return_value=("Complex answer", 30, 60, "claude-sonnet-4-20250514")):
            await live_online_apex.execute("apex_query", {
                "task": "Complex task needing API",
                "task_type": "reasoning",
            })

        # Apex now stores two memories per query: the transaction log and the
        # teaching signal. Verify the teaching-signal call specifically (the
        # one this test actually cares about) was made.
        teaching_calls = [
            call
            for call in mock_grimoire.remember.call_args_list
            if call.kwargs.get("category") == "apex_teaching"
        ]
        assert len(teaching_calls) == 1, (
            f"Expected exactly one apex_teaching call, got {len(teaching_calls)} "
            f"(all calls: {mock_grimoire.remember.call_args_list})"
        )
        call_kwargs = teaching_calls[0]
        assert call_kwargs.kwargs["source_module"] == "apex"

        # Escalation log should reference the grimoire memory ID
        signals = live_online_apex._escalation_log.get_recent_teaching_signals(1)
        assert len(signals) == 1
        assert signals[0]["grimoire_memory_id"] == "mem-uuid-456"


# ===================================================================
# Tool count verification
# ===================================================================

class TestToolCount:
    def test_tools_include_learning_tools(self, apex: Apex):
        """Apex has 10 tools (5 core + 3 learning + 2 training)."""
        tools = apex.get_tools()
        assert len(tools) == 10
        names = [t["name"] for t in tools]
        assert "escalation_stats" in names
        assert "escalation_frequent" in names
        assert "teaching_review" in names
