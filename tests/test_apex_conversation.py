"""
Tests for Apex Conversation History
=====================================
Covers multi-turn conversation accumulation, history sent in API requests,
max_turns trimming, clear_history, and Grimoire transaction storage.
"""

import pytest
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock, call

from pydantic import SecretStr

from modules.apex.apex import Apex
from modules.apex.config import ApexSettings
from modules.base import ModuleStatus, ToolResult


@pytest.fixture
def apex(tmp_path: Path) -> Apex:
    """Create an Apex instance (dry_run=True — no keys needed)."""
    settings = ApexSettings(
        log_file=str(tmp_path / "apex_log.json"),
        escalation_db=str(tmp_path / "escalation.db"),
        max_turns=3,
        dry_run=True,
    )
    return Apex(settings)


@pytest.fixture
async def live_apex(tmp_path: Path) -> Apex:
    """Initialized Apex with a fake Anthropic key for live-mode dispatch."""
    settings = ApexSettings(
        log_file=str(tmp_path / "apex_log.json"),
        escalation_db=str(tmp_path / "escalation.db"),
        max_turns=3,
        dry_run=False,
        anthropic_api_key=SecretStr("sk-fake-key"),
    )
    apex = Apex(settings)
    await apex.initialize()
    return apex


def _stub_call_claude(response_text: str):
    """Return a value matching _call_claude's return signature."""
    return (response_text, 10, 20, "claude-sonnet-4-20250514")


# --- Conversation history accumulation ---

class TestConversationHistory:
    @pytest.mark.asyncio
    async def test_history_accumulates_across_calls(self, live_apex: Apex):
        """Conversation history grows with each successful API call."""
        with patch.object(live_apex, "_call_claude", side_effect=[
            _stub_call_claude("answer 1"),
            _stub_call_claude("answer 2"),
        ]):
            await live_apex.execute("apex_query", {"task": "question 1"})
            assert len(live_apex._conversation_history) == 2
            assert live_apex._conversation_history[0] == {"role": "user", "content": "question 1"}
            assert live_apex._conversation_history[1] == {"role": "assistant", "content": "answer 1"}

            await live_apex.execute("apex_query", {"task": "question 2"})
            assert len(live_apex._conversation_history) == 4
            assert live_apex._conversation_history[2] == {"role": "user", "content": "question 2"}
            assert live_apex._conversation_history[3] == {"role": "assistant", "content": "answer 2"}

    @pytest.mark.asyncio
    async def test_history_sent_in_api_request(self, live_apex: Apex):
        """The full conversation history is passed to _call_api on each call.

        We verify by checking that _conversation_history contains prior turns
        at the moment _call_claude is invoked for the second call.
        """
        history_snapshots = []

        def capturing_call_claude(task):
            """Capture a snapshot of conversation_history at call time."""
            history_snapshots.append(list(live_apex._conversation_history))
            return _stub_call_claude(f"reply to: {task}")

        with patch.object(live_apex, "_call_claude", side_effect=capturing_call_claude):
            await live_apex.execute("apex_query", {"task": "hello"})
            await live_apex.execute("apex_query", {"task": "follow up"})

        # First call: history should have just the new user message
        assert len(history_snapshots[0]) == 1
        assert history_snapshots[0][0] == {"role": "user", "content": "hello"}

        # Second call: history should have prior turn + new user message
        assert len(history_snapshots[1]) == 3
        assert history_snapshots[1][0] == {"role": "user", "content": "hello"}
        assert history_snapshots[1][1] == {"role": "assistant", "content": "reply to: hello"}
        assert history_snapshots[1][2] == {"role": "user", "content": "follow up"}

    @pytest.mark.asyncio
    async def test_history_not_added_on_api_failure(self, live_apex: Apex):
        """If the API call fails, the user message is rolled back from history."""
        with patch.object(live_apex, "_call_claude", side_effect=RuntimeError("API down")):
            result = await live_apex.execute("apex_query", {"task": "this will fail"})
            assert not result.success
            assert len(live_apex._conversation_history) == 0

    @pytest.mark.asyncio
    async def test_history_not_added_in_dry_run(self, tmp_path: Path):
        """Dry-run mode does not append to conversation history."""
        settings = ApexSettings(
            log_file=str(tmp_path / "apex_log.json"),
            escalation_db=str(tmp_path / "escalation.db"),
            dry_run=True,
            anthropic_api_key=SecretStr("sk-fake"),
        )
        apex = Apex(settings)
        await apex.initialize()

        result = await apex.execute("apex_query", {"task": "dry run task"})
        assert len(apex._conversation_history) == 0


# --- Max turns trimming ---

class TestMaxTurnsTrimming:
    @pytest.mark.asyncio
    async def test_max_turns_trims_oldest(self, live_apex: Apex):
        """When max_turns (3) is exceeded, oldest turns are dropped."""
        responses = [_stub_call_claude(f"reply {i}") for i in range(4)]

        with patch.object(live_apex, "_call_claude", side_effect=responses):
            for i in range(4):
                await live_apex.execute("apex_query", {"task": f"msg {i}"})

        # max_turns=3 means max 6 messages. 4 turns = 8 messages, so oldest trimmed.
        assert len(live_apex._conversation_history) == 6  # 3 turns * 2
        # Oldest turn (msg 0 / reply 0) should be gone
        assert live_apex._conversation_history[0]["content"] == "msg 1"
        assert live_apex._conversation_history[1]["content"] == "reply 1"
        # Newest should be present
        assert live_apex._conversation_history[-2]["content"] == "msg 3"
        assert live_apex._conversation_history[-1]["content"] == "reply 3"

    def test_trim_preserves_pairs(self, apex: Apex):
        """_trim_history always removes in user+assistant pairs."""
        # Manually fill 5 turns (10 messages) with max_turns=3
        for i in range(5):
            apex._conversation_history.append({"role": "user", "content": f"u{i}"})
            apex._conversation_history.append({"role": "assistant", "content": f"a{i}"})

        apex._trim_history()
        assert len(apex._conversation_history) == 6
        assert apex._conversation_history[0]["content"] == "u2"
        assert apex._conversation_history[1]["content"] == "a2"


# --- Clear history ---

class TestClearHistory:
    def test_clear_history_empties_list(self, apex: Apex):
        """clear_history() empties the conversation history."""
        apex._conversation_history = [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": "reply"},
        ]
        apex.clear_history()
        assert apex._conversation_history == []

    @pytest.mark.asyncio
    async def test_clear_history_tool(self, live_apex: Apex):
        """apex_clear_history tool clears history and reports count."""
        live_apex._conversation_history = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
            {"role": "assistant", "content": "d"},
        ]
        result = await live_apex.execute("apex_clear_history", {})
        assert result.success
        assert result.content["cleared"] is True
        assert result.content["turns_removed"] == 4
        assert live_apex._conversation_history == []

    @pytest.mark.asyncio
    async def test_shutdown_clears_history(self, live_apex: Apex):
        """Shutdown clears conversation history."""
        live_apex._conversation_history = [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": "reply"},
        ]
        await live_apex.shutdown()
        assert live_apex._conversation_history == []


# --- Grimoire transaction storage ---

class TestGrimoireTransactionStorage:
    @pytest.mark.asyncio
    async def test_transaction_stored_in_grimoire(self, live_apex: Apex):
        """Each successful API call stores a transaction in Grimoire."""
        mock_grimoire = MagicMock()
        mock_grimoire.remember = MagicMock(return_value="mem-123")
        live_apex.set_grimoire(mock_grimoire)

        with patch.object(live_apex, "_call_claude", return_value=("the answer", 50, 100, "claude-sonnet-4-20250514")):
            await live_apex.execute("apex_query", {"task": "store this"})

        # Verify grimoire.remember was called for the transaction
        remember_calls = mock_grimoire.remember.call_args_list
        transaction_call = None
        for c in remember_calls:
            kwargs = c.kwargs if c.kwargs else {}
            if kwargs.get("source") == "apex_transaction" and kwargs.get("category") == "apex_log":
                transaction_call = kwargs
                break

        assert transaction_call is not None, "No Grimoire transaction with source=apex_transaction found"
        assert "apex_transaction" in transaction_call["tags"]
        assert transaction_call["metadata"]["input_tokens"] == 50
        assert transaction_call["metadata"]["output_tokens"] == 100
        assert transaction_call["metadata"]["cost_usd"] > 0

    @pytest.mark.asyncio
    async def test_no_grimoire_no_crash(self, live_apex: Apex):
        """Without Grimoire linked, transactions still succeed (no crash)."""
        assert live_apex._grimoire is None

        with patch.object(live_apex, "_call_claude", return_value=_stub_call_claude("works fine")):
            result = await live_apex.execute("apex_query", {"task": "no grimoire"})

        assert result.success

    @pytest.mark.asyncio
    async def test_grimoire_failure_does_not_break_query(self, live_apex: Apex):
        """If Grimoire.remember() raises, the query still succeeds."""
        mock_grimoire = MagicMock()
        mock_grimoire.remember = MagicMock(side_effect=RuntimeError("db locked"))
        live_apex.set_grimoire(mock_grimoire)

        with patch.object(live_apex, "_call_claude", return_value=_stub_call_claude("still works")):
            result = await live_apex.execute("apex_query", {"task": "grimoire broken"})

        assert result.success


# --- Config ---

class TestConversationConfig:
    def test_default_max_turns(self, tmp_path: Path):
        """Default max_turns is 10 when not specified."""
        settings = ApexSettings(log_file=str(tmp_path / "log.json"), dry_run=True)
        apex = Apex(settings)
        assert apex._max_turns == 10

    def test_custom_max_turns(self, tmp_path: Path):
        """max_turns can be set via settings."""
        settings = ApexSettings(
            log_file=str(tmp_path / "log.json"), max_turns=5, dry_run=True,
        )
        apex = Apex(settings)
        assert apex._max_turns == 5

    def test_history_starts_empty(self, apex: Apex):
        """Conversation history starts as an empty list."""
        assert apex._conversation_history == []
