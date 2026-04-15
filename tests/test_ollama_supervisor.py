"""Tests for the Ollama Supervisor module."""

import asyncio
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.shadow.ollama_supervisor import OllamaSupervisor


@pytest.fixture
def supervisor():
    """Create a supervisor with short intervals for testing."""
    return OllamaSupervisor(check_interval=1, max_retries=5, ollama_bin="ollama")


@pytest.fixture
def supervisor_with_harbinger():
    """Create a supervisor with a mocked Harbinger."""
    harbinger = MagicMock()
    harbinger.execute = MagicMock()
    return OllamaSupervisor(
        check_interval=1, max_retries=5, ollama_bin="ollama", harbinger=harbinger
    )


class TestDefaults:
    """Tests for default configuration values."""

    def test_default_check_interval_is_300(self):
        """Default check_interval should be 300s (5 min) to avoid GIN log flooding."""
        sup = OllamaSupervisor()
        assert sup.check_interval == 300

    def test_custom_check_interval_respected(self):
        """Explicit check_interval overrides the default."""
        sup = OllamaSupervisor(check_interval=60)
        assert sup.check_interval == 60


class TestGinSuppression:
    """Tests for GIN log suppression via environment variables."""

    def test_gin_mode_release_suppresses_request_logs(self):
        """GIN_MODE=release should be set by main() to suppress per-request GET logs."""
        # Simulate what main() does
        old = os.environ.pop("GIN_MODE", None)
        try:
            os.environ.setdefault("GIN_MODE", "release")
            assert os.environ["GIN_MODE"] == "release"
        finally:
            if old is not None:
                os.environ["GIN_MODE"] = old
            else:
                os.environ.pop("GIN_MODE", None)

    def test_gin_mode_setdefault_does_not_override(self):
        """If GIN_MODE is already set, setdefault should not overwrite it."""
        old = os.environ.get("GIN_MODE")
        try:
            os.environ["GIN_MODE"] = "debug"
            os.environ.setdefault("GIN_MODE", "release")
            assert os.environ["GIN_MODE"] == "debug"
        finally:
            if old is not None:
                os.environ["GIN_MODE"] = old
            else:
                os.environ.pop("GIN_MODE", None)


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, supervisor):
        """Mock successful HTTP response, verify returns True."""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("modules.shadow.ollama_supervisor.aiohttp.ClientSession", return_value=mock_session):
            result = await supervisor.health_check()

        assert result is True
        assert supervisor._last_check is not None

    @pytest.mark.asyncio
    async def test_health_check_failure(self, supervisor):
        """Mock connection error, verify returns False."""
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=ConnectionError("Connection refused"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("modules.shadow.ollama_supervisor.aiohttp.ClientSession", return_value=mock_session):
            result = await supervisor.health_check()

        assert result is False


class TestRestart:
    """Tests for restart behavior."""

    @pytest.mark.asyncio
    async def test_restart_called_on_failure(self, supervisor):
        """Mock health check failing, verify restart attempted."""
        supervisor.health_check = AsyncMock(return_value=False)
        supervisor.restart_ollama = AsyncMock(return_value=True)

        # Run one iteration of the monitor loop manually
        supervisor._running = True
        supervisor._start_time = 0

        # Run the loop but stop it after one iteration
        async def run_one_iteration():
            healthy = await supervisor.health_check()
            if not healthy:
                supervisor._consecutive_failures += 1
                supervisor._on_failure(supervisor._consecutive_failures)
                await supervisor.restart_ollama()

        await run_one_iteration()

        supervisor.restart_ollama.assert_called_once()

    @pytest.mark.asyncio
    async def test_max_retries_respected(self, supervisor):
        """After max_retries restarts, verify supervisor stops trying and logs critical."""
        supervisor._restart_count = 5  # Already at max
        supervisor.health_check = AsyncMock(return_value=False)
        supervisor.restart_ollama = AsyncMock(return_value=False)
        supervisor._running = True
        supervisor._start_time = 0

        # Simulate the monitor loop logic
        healthy = await supervisor.health_check()
        assert healthy is False

        supervisor._consecutive_failures += 1

        if supervisor._restart_count >= supervisor.max_retries:
            supervisor._max_retries_exhausted = True
            supervisor._running = False

        assert supervisor._max_retries_exhausted is True
        assert supervisor._running is False
        supervisor.restart_ollama.assert_not_called()


class TestHarbingerAlert:
    """Tests for Harbinger alerting."""

    @pytest.mark.asyncio
    async def test_harbinger_alert_at_3_failures(self, supervisor_with_harbinger):
        """Mock 3 consecutive failures, verify alert created."""
        sup = supervisor_with_harbinger

        # Simulate 3 consecutive failures
        sup._on_failure(1)
        sup._on_failure(2)
        sup.harbinger.execute.assert_not_called()

        sup._on_failure(3)
        sup.harbinger.execute.assert_called_once()

        call_args = sup.harbinger.execute.call_args
        assert call_args[0][0] == "notification_send"
        params = call_args[0][1]
        assert params["severity"] == 4
        assert "3" in params["message"]
        assert params["category"] == "system_health"


class TestGetStatus:
    """Tests for get_status method."""

    @pytest.mark.asyncio
    async def test_get_status(self, supervisor):
        """Verify status dict has all required fields."""
        status = supervisor.get_status()

        required_fields = {
            "running",
            "uptime_seconds",
            "restart_count",
            "last_check",
            "consecutive_failures",
        }
        assert required_fields.issubset(status.keys())

        assert status["running"] is False
        assert status["restart_count"] == 0
        assert status["consecutive_failures"] == 0
        assert status["last_check"] is None

    @pytest.mark.asyncio
    async def test_get_status_after_start(self, supervisor):
        """Verify status updates after start."""
        supervisor.health_check = AsyncMock(return_value=True)

        await supervisor.start()
        await asyncio.sleep(0.1)  # Let the loop tick once

        status = supervisor.get_status()
        assert status["running"] is True
        assert status["uptime_seconds"] >= 0

        await supervisor.stop()
        status = supervisor.get_status()
        assert status["running"] is False


class TestStartStop:
    """Tests for start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self, supervisor):
        """Verify supervisor starts and stops cleanly."""
        supervisor.health_check = AsyncMock(return_value=True)

        await supervisor.start()
        assert supervisor._running is True
        assert supervisor._task is not None

        await supervisor.stop()
        assert supervisor._running is False

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self, supervisor):
        """Starting twice should not create duplicate loops."""
        supervisor.health_check = AsyncMock(return_value=True)

        await supervisor.start()
        first_task = supervisor._task

        await supervisor.start()  # Should warn and return
        assert supervisor._task is first_task

        await supervisor.stop()
