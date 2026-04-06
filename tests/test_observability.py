"""
Tests for Shadow Observability (Langfuse tracing)
====================================================
Verifies the trace_interaction decorator doesn't break
existing orchestrator functionality and degrades gracefully.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.shadow.observability import trace_interaction, _get_langfuse_client


# --- Helpers ---

class FakeOrchestrator:
    """Minimal stand-in for Orchestrator to test the decorator."""

    class _State:
        interaction_count = 5

    def __init__(self):
        self._state = self._State()

    @trace_interaction
    async def process_input(self, user_input: str, source: str = "user") -> str:
        return f"echo: {user_input}"


# --- Tests ---

@pytest.mark.asyncio
async def test_decorator_passes_through_without_langfuse():
    """Decorator should be invisible when Langfuse is not configured."""
    orch = FakeOrchestrator()
    result = await orch.process_input("hello")
    assert result == "echo: hello"


@pytest.mark.asyncio
async def test_decorator_preserves_exception():
    """If the wrapped function raises, the decorator must re-raise."""

    class FailOrch:
        class _State:
            interaction_count = 0

        def __init__(self):
            self._state = self._State()

        @trace_interaction
        async def process_input(self, user_input: str, source: str = "user") -> str:
            raise ValueError("boom")

    orch = FailOrch()
    with pytest.raises(ValueError, match="boom"):
        await orch.process_input("test")


@pytest.mark.asyncio
@patch("modules.shadow.observability._get_langfuse_client")
async def test_decorator_calls_langfuse_when_configured(mock_get_client):
    """When Langfuse is available, decorator creates a trace and flushes."""
    mock_client = MagicMock()
    mock_trace = MagicMock()
    mock_client.trace.return_value = mock_trace
    mock_get_client.return_value = mock_client

    orch = FakeOrchestrator()
    result = await orch.process_input("hello", source="telegram_message")

    assert result == "echo: hello"
    mock_client.trace.assert_called_once()
    call_kwargs = mock_client.trace.call_args[1]
    assert call_kwargs["input"]["user_input"] == "hello"
    assert call_kwargs["input"]["source"] == "telegram_message"
    mock_trace.update.assert_called_once()
    mock_client.flush.assert_called_once()


def test_get_langfuse_client_returns_none_without_keys():
    """Without env vars, _get_langfuse_client returns None."""
    with patch.dict("os.environ", {}, clear=True):
        assert _get_langfuse_client() is None
