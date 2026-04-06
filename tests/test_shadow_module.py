"""
Tests for ShadowModule — Task Tracking & System Health
========================================================
Covers lifecycle, task CRUD, task listing with filters, and
module health queries via the registry.
"""

import pytest
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleRegistry, ModuleStatus, ToolResult
from modules.shadow.shadow_module import ShadowModule


# --- Mock module for health tests ---

class HealthMock(BaseModule):
    """Minimal module for testing module_health queries."""

    def __init__(self, name: str = "mock_target"):
        super().__init__(name=name, description=f"Mock: {name}")

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, content="ok", tool_name=tool_name, module=self.name)

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return []


# --- Fixtures ---

@pytest.fixture
def registry() -> ModuleRegistry:
    """Create a registry with a mock module for health tests."""
    reg = ModuleRegistry()
    return reg


@pytest.fixture
def shadow_module(tmp_path: Path, registry: ModuleRegistry) -> ShadowModule:
    """Create a ShadowModule with a temp database."""
    config = {"db_path": str(tmp_path / "shadow_tasks.db")}
    return ShadowModule(config, registry)


@pytest.fixture
async def online_shadow(shadow_module: ShadowModule) -> ShadowModule:
    """Create and initialize a ShadowModule."""
    await shadow_module.initialize()
    return shadow_module


# --- Lifecycle Tests ---

class TestShadowModuleLifecycle:
    @pytest.mark.asyncio
    async def test_initialize_sets_online(self, shadow_module: ShadowModule):
        assert shadow_module.status == ModuleStatus.OFFLINE
        await shadow_module.initialize()
        assert shadow_module.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown_sets_offline(self, online_shadow: ShadowModule):
        await online_shadow.shutdown()
        assert online_shadow.status == ModuleStatus.OFFLINE

    def test_get_tools_returns_all_tools(self, shadow_module: ShadowModule):
        tools = shadow_module.get_tools()
        assert isinstance(tools, list)
        assert len(tools) == 4
        tool_names = [t["name"] for t in tools]
        assert "task_create" in tool_names
        assert "task_status" in tool_names
        assert "task_list" in tool_names
        assert "module_health" in tool_names

    def test_all_tools_have_required_fields(self, shadow_module: ShadowModule):
        for tool in shadow_module.get_tools():
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "permission_level" in tool

    def test_module_info(self, shadow_module: ShadowModule):
        info = shadow_module.info
        assert info["name"] == "shadow"
        assert info["status"] == "offline"


# --- Task Create Tests ---

class TestTaskCreate:
    @pytest.mark.asyncio
    async def test_success(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_create", {
            "description": "Research competitor pricing",
            "assigned_module": "reaper",
            "priority": 2,
        })
        assert result.success is True
        assert result.content["description"] == "Research competitor pricing"
        assert result.content["assigned_module"] == "reaper"
        assert result.content["priority"] == 2
        assert result.content["status"] == "pending"
        assert "task_id" in result.content

    @pytest.mark.asyncio
    async def test_default_priority(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_create", {
            "description": "Check system health",
            "assigned_module": "void",
        })
        assert result.success is True
        assert result.content["priority"] == 3

    @pytest.mark.asyncio
    async def test_missing_description(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_create", {
            "assigned_module": "wraith",
        })
        assert result.success is False
        assert "description" in result.error

    @pytest.mark.asyncio
    async def test_missing_assigned_module(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_create", {
            "description": "Some task",
        })
        assert result.success is False
        assert "assigned_module" in result.error

    @pytest.mark.asyncio
    async def test_invalid_priority_too_high(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_create", {
            "description": "Bad priority",
            "assigned_module": "wraith",
            "priority": 10,
        })
        assert result.success is False
        assert "priority" in result.error

    @pytest.mark.asyncio
    async def test_invalid_priority_zero(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_create", {
            "description": "Bad priority",
            "assigned_module": "wraith",
            "priority": 0,
        })
        assert result.success is False

    @pytest.mark.asyncio
    async def test_invalid_priority_string(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_create", {
            "description": "Bad priority",
            "assigned_module": "wraith",
            "priority": "high",
        })
        assert result.success is False


# --- Task Status Tests ---

class TestTaskStatus:
    @pytest.mark.asyncio
    async def test_found(self, online_shadow: ShadowModule):
        create = await online_shadow.execute("task_create", {
            "description": "Test task",
            "assigned_module": "wraith",
        })
        task_id = create.content["task_id"]

        result = await online_shadow.execute("task_status", {"task_id": task_id})
        assert result.success is True
        assert result.content["id"] == task_id
        assert result.content["description"] == "Test task"
        assert result.content["status"] == "pending"

    @pytest.mark.asyncio
    async def test_not_found(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_status", {
            "task_id": "nonexistent-uuid",
        })
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_missing_task_id(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_status", {})
        assert result.success is False
        assert "task_id" in result.error


# --- Task List Tests ---

class TestTaskList:
    @pytest.mark.asyncio
    async def test_empty_list(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_list", {})
        assert result.success is True
        assert result.content == []

    @pytest.mark.asyncio
    async def test_lists_all_tasks(self, online_shadow: ShadowModule):
        await online_shadow.execute("task_create", {
            "description": "Task A", "assigned_module": "wraith", "priority": 3,
        })
        await online_shadow.execute("task_create", {
            "description": "Task B", "assigned_module": "reaper", "priority": 1,
        })

        result = await online_shadow.execute("task_list", {})
        assert result.success is True
        assert len(result.content) == 2
        # Should be sorted by priority ASC — priority 1 first
        assert result.content[0]["priority"] == 1

    @pytest.mark.asyncio
    async def test_filter_by_status(self, online_shadow: ShadowModule):
        await online_shadow.execute("task_create", {
            "description": "Pending task", "assigned_module": "wraith",
        })

        result = await online_shadow.execute("task_list", {
            "status_filter": "pending",
        })
        assert result.success is True
        assert len(result.content) == 1

        result = await online_shadow.execute("task_list", {
            "status_filter": "completed",
        })
        assert result.success is True
        assert len(result.content) == 0

    @pytest.mark.asyncio
    async def test_invalid_status_filter(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("task_list", {
            "status_filter": "bogus",
        })
        assert result.success is False
        assert "Invalid status" in result.error


# --- Module Health Tests ---

class TestModuleHealth:
    @pytest.mark.asyncio
    async def test_known_module(self, online_shadow: ShadowModule, registry: ModuleRegistry):
        mock = HealthMock(name="wraith_mock")
        await mock.initialize()
        mock._record_call(True)
        mock._record_call(True)
        mock._record_call(False)
        registry.register(mock)

        result = await online_shadow.execute("module_health", {
            "module_name": "wraith_mock",
        })
        assert result.success is True
        assert result.content["name"] == "wraith_mock"
        assert result.content["status"] == "online"
        assert result.content["call_count"] == 3
        assert result.content["error_count"] == 1

    @pytest.mark.asyncio
    async def test_unknown_module(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("module_health", {
            "module_name": "nonexistent",
        })
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_missing_module_name(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("module_health", {})
        assert result.success is False
        assert "module_name" in result.error


# --- Unknown Tool Test ---

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, online_shadow: ShadowModule):
        result = await online_shadow.execute("nonexistent_tool", {})
        assert result.success is False
        assert "Unknown" in result.error
