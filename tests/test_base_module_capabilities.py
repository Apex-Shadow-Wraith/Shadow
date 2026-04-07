"""
Tests for BaseModule Convenience Methods
==========================================
Tests the Grimoire access and module state awareness methods
added to BaseModule, including graceful degradation when
reader/manager are not wired.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from modules.base import BaseModule, ModuleStatus, ToolResult


class ConcreteModule(BaseModule):
    """Concrete implementation of BaseModule for testing."""

    def __init__(self, name: str = "test_module"):
        super().__init__(name, "Test module for unit tests")

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, content="ok", tool_name=tool_name, module=self.name)

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [{"name": "test_tool", "description": "A test tool", "parameters": {}, "permission_level": "autonomous"}]


@pytest.fixture
def module():
    """Create a concrete module instance."""
    return ConcreteModule()


@pytest.fixture
def module_with_reader(module):
    """Module with a mocked GrimoireReader."""
    mock_reader = MagicMock()
    module._grimoire_reader = mock_reader
    return module, mock_reader


@pytest.fixture
def module_with_state(module):
    """Module with a mocked ModuleStateManager."""
    mock_manager = MagicMock()
    module._state_manager = mock_manager
    return module, mock_manager


class TestGrimoireAccessGracefulDegradation:
    """Tests that Grimoire methods gracefully degrade when reader not wired."""

    def test_search_knowledge_without_reader(self, module):
        """Should return empty list when reader not wired."""
        result = module.search_knowledge("test query")
        assert result == []

    def test_has_knowledge_without_reader(self, module):
        """Should return False when reader not wired."""
        assert module.has_knowledge("test query") is False

    def test_get_my_knowledge_without_reader(self, module):
        """Should return empty list when reader not wired."""
        result = module.get_my_knowledge()
        assert result == []

    def test_browse_category_without_reader(self, module):
        """Should return empty list when reader not wired."""
        result = module.browse_category("test_category")
        assert result == []


class TestGrimoireAccessDelegation:
    """Tests that Grimoire methods properly delegate to GrimoireReader."""

    def test_search_knowledge_delegates(self, module_with_reader):
        """Should delegate to reader.search with correct args."""
        module, reader = module_with_reader
        reader.search.return_value = [{"content": "result"}]

        result = module.search_knowledge("firewall rules", limit=3)

        reader.search.assert_called_once_with("firewall rules", limit=3)
        assert result == [{"content": "result"}]

    def test_has_knowledge_delegates(self, module_with_reader):
        """Should delegate to reader.check_knowledge_exists."""
        module, reader = module_with_reader
        reader.check_knowledge_exists.return_value = True

        result = module.has_knowledge("test topic")

        reader.check_knowledge_exists.assert_called_once_with("test topic")
        assert result is True

    def test_get_my_knowledge_uses_module_name(self, module_with_reader):
        """Should pass own module name to reader.get_module_knowledge."""
        module, reader = module_with_reader
        reader.get_module_knowledge.return_value = [{"content": "my stuff"}]

        result = module.get_my_knowledge(limit=10)

        reader.get_module_knowledge.assert_called_once_with("test_module", limit=10)
        assert result == [{"content": "my stuff"}]

    def test_browse_category_delegates(self, module_with_reader):
        """Should delegate to reader.search_by_category."""
        module, reader = module_with_reader
        reader.search_by_category.return_value = [{"content": "categorized"}]

        result = module.browse_category("code_pattern", limit=5)

        reader.search_by_category.assert_called_once_with("code_pattern", limit=5)
        assert result == [{"content": "categorized"}]


class TestStateAwarenessGracefulDegradation:
    """Tests that state methods gracefully degrade when manager not wired."""

    def test_is_module_available_without_manager(self, module):
        """Should return False when manager not wired."""
        assert module.is_module_available("wraith") is False

    def test_get_module_status_without_manager(self, module):
        """Should return 'unknown' when manager not wired."""
        assert module.get_module_status("wraith") == "unknown"

    def test_who_can_do_without_manager(self, module):
        """Should return None when manager not wired."""
        assert module.who_can_do("network_scan") is None


class TestStateAwarenessDelegation:
    """Tests that state methods properly delegate to ModuleStateManager."""

    def test_is_module_available_idle(self, module_with_state):
        """Should return True when target module is idle."""
        module, manager = module_with_state
        mock_state = MagicMock()
        mock_state.status = "idle"
        manager.get_state.return_value = mock_state

        assert module.is_module_available("wraith") is True
        manager.get_state.assert_called_once_with("wraith")

    def test_is_module_available_busy(self, module_with_state):
        """Should return False when target module is busy."""
        module, manager = module_with_state
        mock_state = MagicMock()
        mock_state.status = "busy"
        manager.get_state.return_value = mock_state

        assert module.is_module_available("wraith") is False

    def test_is_module_available_unknown(self, module_with_state):
        """Should return False when target module not registered."""
        module, manager = module_with_state
        manager.get_state.side_effect = KeyError("not found")

        assert module.is_module_available("nonexistent") is False

    def test_get_module_status_delegates(self, module_with_state):
        """Should return the module's status string."""
        module, manager = module_with_state
        mock_state = MagicMock()
        mock_state.status = "busy"
        manager.get_state.return_value = mock_state

        assert module.get_module_status("omen") == "busy"

    def test_get_module_status_unknown_module(self, module_with_state):
        """Should return 'unknown' for unregistered module."""
        module, manager = module_with_state
        manager.get_state.side_effect = KeyError("not found")

        assert module.get_module_status("nonexistent") == "unknown"

    def test_who_can_do_delegates(self, module_with_state):
        """Should delegate to manager.find_capable_module."""
        module, manager = module_with_state
        manager.find_capable_module.return_value = "sentinel"

        result = module.who_can_do("network_scan")

        manager.find_capable_module.assert_called_once_with("network_scan")
        assert result == "sentinel"


class TestAttributesExist:
    """Verify the new attributes are present on BaseModule."""

    def test_grimoire_reader_attribute(self, module):
        """BaseModule should have _grimoire_reader attribute."""
        assert hasattr(module, "_grimoire_reader")
        assert module._grimoire_reader is None

    def test_state_manager_attribute(self, module):
        """BaseModule should have _state_manager attribute."""
        assert hasattr(module, "_state_manager")
        assert module._state_manager is None
