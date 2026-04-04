"""
Tests for BaseModule and ModuleRegistry
=========================================
Verifies the foundation everything else stands on.
"""

import pytest
from typing import Any

from modules.base import BaseModule, ModuleRegistry, ModuleStatus, ToolResult


# --- Test fixtures: Concrete module implementations for testing ---

class MockModule(BaseModule):
    """Minimal concrete module for testing."""

    def __init__(self, name: str = "mock", tools: list[dict] | None = None):
        super().__init__(name=name, description=f"Mock module: {name}")
        self._tools = tools or [
            {
                "name": f"{name}_tool",
                "description": f"Tool from {name}",
                "parameters": {},
                "permission_level": "autonomous",
            }
        ]

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        return ToolResult(
            success=True,
            content=f"Executed {tool_name}",
            tool_name=tool_name,
            module=self.name,
        )

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return self._tools


class FailingModule(BaseModule):
    """Module that fails on initialize."""

    def __init__(self):
        super().__init__(name="failing", description="Always fails")

    async def initialize(self) -> None:
        self.status = ModuleStatus.ERROR
        raise RuntimeError("Intentional failure")

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=False, content=None, tool_name=tool_name,
                          module=self.name, error="Module in error state")

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return []


# --- ToolResult tests ---

class TestToolResult:
    def test_successful_result(self):
        result = ToolResult(
            success=True, content="hello", tool_name="test", module="mock"
        )
        assert result.success is True
        assert "OK" in str(result)

    def test_failed_result(self):
        result = ToolResult(
            success=False, content=None, tool_name="test",
            module="mock", error="something broke"
        )
        assert result.success is False
        assert "FAILED" in str(result)

    def test_metadata_defaults_to_empty(self):
        result = ToolResult(success=True, content="x", tool_name="t", module="m")
        assert result.metadata == {}
        assert result.execution_time_ms == 0.0


# --- BaseModule tests ---

class TestBaseModule:
    @pytest.mark.asyncio
    async def test_lifecycle(self):
        mod = MockModule()
        assert mod.status == ModuleStatus.OFFLINE

        await mod.initialize()
        assert mod.status == ModuleStatus.ONLINE

        await mod.shutdown()
        assert mod.status == ModuleStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_execute_returns_tool_result(self):
        mod = MockModule()
        await mod.initialize()
        result = await mod.execute("mock_tool", {})
        assert isinstance(result, ToolResult)
        assert result.success is True

    def test_success_rate_starts_at_100(self):
        mod = MockModule()
        assert mod.success_rate == 1.0

    def test_success_rate_tracks_failures(self):
        mod = MockModule()
        mod._record_call(True)
        mod._record_call(True)
        mod._record_call(False)
        assert mod.success_rate == pytest.approx(2 / 3)

    def test_info_dict(self):
        mod = MockModule(name="test_mod")
        info = mod.info
        assert info["name"] == "test_mod"
        assert info["status"] == "offline"
        assert info["call_count"] == 0

    def test_get_tools_returns_list(self):
        mod = MockModule()
        tools = mod.get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 1
        assert tools[0]["name"] == "mock_tool"


# --- ModuleRegistry tests ---

class TestModuleRegistry:
    def test_register_and_get(self):
        reg = ModuleRegistry()
        mod = MockModule(name="alpha")
        reg.register(mod)
        assert reg.get_module("alpha") is mod

    def test_register_duplicate_raises(self):
        reg = ModuleRegistry()
        mod = MockModule(name="alpha")
        reg.register(mod)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(MockModule(name="alpha"))

    def test_register_duplicate_tool_raises(self):
        """Two modules cannot provide the same tool name."""
        reg = ModuleRegistry()
        mod1 = MockModule(name="mod1", tools=[
            {"name": "shared_tool", "description": "t", "parameters": {}, "permission_level": "autonomous"}
        ])
        mod2 = MockModule(name="mod2", tools=[
            {"name": "shared_tool", "description": "t", "parameters": {}, "permission_level": "autonomous"}
        ])
        reg.register(mod1)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(mod2)

    def test_unregister(self):
        reg = ModuleRegistry()
        mod = MockModule(name="temp")
        reg.register(mod)
        assert "temp" in reg
        reg.unregister("temp")
        assert "temp" not in reg

    def test_unregister_nonexistent_raises(self):
        reg = ModuleRegistry()
        with pytest.raises(KeyError):
            reg.unregister("ghost")

    def test_get_nonexistent_raises(self):
        reg = ModuleRegistry()
        with pytest.raises(KeyError):
            reg.get_module("ghost")

    def test_get_module_for_tool(self):
        reg = ModuleRegistry()
        mod = MockModule(name="finder")
        reg.register(mod)
        found = reg.get_module_for_tool("finder_tool")
        assert found.name == "finder"

    def test_get_module_for_unknown_tool_raises(self):
        reg = ModuleRegistry()
        with pytest.raises(KeyError):
            reg.get_module_for_tool("nonexistent_tool")

    @pytest.mark.asyncio
    async def test_list_tools_only_online(self):
        """list_tools() should only include tools from ONLINE modules."""
        reg = ModuleRegistry()
        online_mod = MockModule(name="up")
        offline_mod = MockModule(name="down")

        await online_mod.initialize()  # Sets to ONLINE
        # offline_mod stays OFFLINE

        reg.register(online_mod)
        reg.register(offline_mod)

        tools = reg.list_tools()
        tool_names = [t["name"] for t in tools]
        assert "up_tool" in tool_names
        assert "down_tool" not in tool_names

    def test_online_modules(self):
        reg = ModuleRegistry()
        mod = MockModule(name="test")
        mod.status = ModuleStatus.ONLINE
        reg.register(mod)
        assert "test" in reg.online_modules

    def test_len(self):
        reg = ModuleRegistry()
        assert len(reg) == 0
        reg.register(MockModule(name="a"))
        reg.register(MockModule(name="b"))
        assert len(reg) == 2
