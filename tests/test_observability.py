"""
Tests for Shadow Observability (Langfuse tracing) — v4 SDK
============================================================
Verifies the trace_interaction decorator doesn't break existing
orchestrator functionality and degrades gracefully when observability
is disabled or misconfigured.
"""

import pytest
from unittest.mock import MagicMock, patch

from modules.shadow.observability import trace_interaction


# --- Helpers ---

class FakeOrchestrator:
    """Minimal stand-in for Orchestrator to exercise the decorator."""

    class _State:
        interaction_count = 5

    def __init__(self):
        self._state = self._State()

    @trace_interaction
    async def process_input(self, user_input: str, source: str = "user") -> str:
        return f"echo: {user_input}"


# --- Tests ---

@pytest.mark.asyncio
@patch("modules.shadow.observability.get_client")
async def test_decorator_passes_through_without_langfuse(mock_get_client):
    """Decorator must be invisible when Langfuse client is not available."""
    mock_get_client.return_value = None
    orch = FakeOrchestrator()
    result = await orch.process_input("hello")
    assert result == "echo: hello"


@pytest.mark.asyncio
@patch("modules.shadow.observability.get_client")
async def test_decorator_preserves_exception(mock_get_client):
    """If the wrapped function raises, the decorator must re-raise."""
    mock_get_client.return_value = None  # no client - direct passthrough

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
@patch("modules.shadow.observability.get_client")
async def test_decorator_calls_langfuse_when_configured(mock_get_client):
    """With a configured client, decorator emits a v4 observation and flushes."""
    mock_client = MagicMock()
    mock_span = MagicMock()
    mock_observation_cm = MagicMock()
    mock_observation_cm.__enter__ = MagicMock(return_value=mock_span)
    mock_observation_cm.__exit__ = MagicMock(return_value=False)
    mock_client.start_as_current_observation.return_value = mock_observation_cm
    mock_get_client.return_value = mock_client

    orch = FakeOrchestrator()
    result = await orch.process_input("hello", source="telegram_message")

    assert result == "echo: hello"
    mock_client.start_as_current_observation.assert_called_once()
    call_kwargs = mock_client.start_as_current_observation.call_args.kwargs
    assert call_kwargs["input"]["user_input"] == "hello"
    assert call_kwargs["input"]["source"] == "telegram_message"
    assert call_kwargs["metadata"]["interaction_count"] == 6  # state was 5
    mock_span.update.assert_called_once()
    mock_client.flush.assert_called_once()


@pytest.mark.asyncio
@patch("modules.shadow.observability.get_client")
async def test_decorator_records_exception_on_span(mock_get_client):
    """When wrapped function raises, span is updated with error metadata before re-raising."""
    mock_client = MagicMock()
    mock_span = MagicMock()
    mock_observation_cm = MagicMock()
    mock_observation_cm.__enter__ = MagicMock(return_value=mock_span)
    mock_observation_cm.__exit__ = MagicMock(return_value=False)
    mock_client.start_as_current_observation.return_value = mock_observation_cm
    mock_get_client.return_value = mock_client

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

    # Span should have been updated with the error before the re-raise.
    mock_span.update.assert_called_once()
    err_kwargs = mock_span.update.call_args.kwargs
    assert err_kwargs["output"] == {"error": "decision_loop_exception"}
    mock_client.flush.assert_called_once()


@pytest.mark.asyncio
@patch("modules.shadow.observability.get_client")
async def test_decorator_survives_span_start_failure(mock_get_client):
    """If start_as_current_observation itself raises, the request still succeeds."""
    mock_client = MagicMock()
    mock_client.start_as_current_observation.side_effect = RuntimeError("network down")
    mock_get_client.return_value = mock_client

    orch = FakeOrchestrator()
    result = await orch.process_input("hello")
    assert result == "echo: hello"  # decorator fell through cleanly
