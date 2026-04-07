"""
Shadow Module Base Class & Registry
=====================================
Every Shadow module inherits from BaseModule. The ModuleRegistry tracks
all loaded modules so the orchestrator can route tasks and manage lifecycle.

Design principle: Build small, match the interfaces. When we move to Ubuntu
with dual 5090s, these interfaces stay the same — only the implementations
grow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ModuleStatus(Enum):
    """Current state of a module."""
    OFFLINE = "offline"
    STARTING = "starting"
    ONLINE = "online"
    DEGRADED = "degraded"
    ERROR = "error"
    STOPPING = "stopping"


@dataclass
class ToolResult:
    """Structured result from any tool call.

    From Session 12 architecture update: every tool returns a structured
    result with success/failure, content, and metadata. This replaces
    raw strings and makes Cerberus post-hooks possible.
    """
    success: bool
    content: Any
    tool_name: str
    module: str
    error: str | None = None
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.success:
            return f"[{self.tool_name}] OK: {self.content}"
        return f"[{self.tool_name}] FAILED: {self.error}"


class BaseModule(ABC):
    """Abstract base class for all Shadow modules.

    Every module — Grimoire, Reaper, Cerberus, Wraith, all 13 —
    inherits from this. The orchestrator talks to modules through
    this interface only. Module internals are private.

    Lifecycle: __init__ → initialize() → execute() (many times) → shutdown()
    """

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description
        self.status = ModuleStatus.OFFLINE
        self._initialized_at: datetime | None = None
        self._call_count: int = 0
        self._error_count: int = 0
        # Inter-module communication — set by orchestrator after init
        self._message_bus: Any | None = None
        self._event_system: Any | None = None

    @abstractmethod
    async def initialize(self) -> None:
        """Start the module. Load configs, connect to databases, etc.

        Sets status to ONLINE on success, ERROR on failure.
        Called once by the orchestrator at startup.
        """

    @abstractmethod
    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a tool call on this module.

        This is the single entry point the orchestrator uses to interact
        with any module. The module decides internally how to handle
        the tool call based on tool_name.

        Args:
            tool_name: Which tool to invoke (e.g., 'memory_store', 'web_search')
            params: Tool-specific parameters

        Returns:
            ToolResult with success/failure and structured content
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean shutdown. Save state, close connections, release resources.

        Called by orchestrator on exit or when unloading a module.
        """

    @abstractmethod
    def get_tools(self) -> list[dict[str, Any]]:
        """Return list of tools this module provides.

        Each tool is a dict with: name, description, parameters, permission_level.
        The orchestrator uses this to build the MCP tool registry.
        This is how the model knows 'what tools do I have?'
        """

    def _record_call(self, success: bool) -> None:
        """Track call stats for performance monitoring."""
        self._call_count += 1
        if not success:
            self._error_count += 1

    @property
    def success_rate(self) -> float:
        """Rolling success rate. Used by registry for tool health."""
        if self._call_count == 0:
            return 1.0
        return (self._call_count - self._error_count) / self._call_count

    # ── Inter-Module Communication Convenience Methods ─────────────

    def send_message(
        self,
        target: str,
        payload: dict[str, Any],
        priority: int = 3,
        message_type: str = "request",
        requires_cerberus: bool = True,
    ) -> str | None:
        """Send a message to another module via the MessageBus.

        Safe no-op if MessageBus is not wired yet. Returns message_id
        or None if bus unavailable. Must be awaited externally since
        BaseModule methods are sync — use the async version in subclasses
        if needed.

        Args:
            target: Target module name or "broadcast".
            payload: Message content.
            priority: 1=critical, 2=high, 3=normal, 4=background.
            message_type: "request", "notification", etc.
            requires_cerberus: Whether to safety-check before delivery.

        Returns:
            message_id string, or None if bus not available.
        """
        if self._message_bus is None:
            return None
        import uuid as _uuid
        from modules.shadow.message_bus import ModuleMessage
        msg = ModuleMessage(
            message_id=str(_uuid.uuid4()),
            source_module=self.name,
            target_module=target,
            message_type=message_type,
            priority=priority,
            payload=payload,
            requires_cerberus=requires_cerberus,
            timestamp=datetime.now(),
        )
        # Return the coroutine for the caller to await
        return self._message_bus.send(msg)

    def request_module(
        self,
        target: str,
        task: str,
        input_data: dict[str, Any],
        output_format: dict[str, Any] | None = None,
    ) -> Any | None:
        """Create a handoff request to another module.

        Returns the coroutine for creating the handoff. Caller must await it.
        Safe no-op if handoff protocol is not wired.

        Args:
            target: Target module name.
            task: Human-readable task description.
            input_data: Data the target module needs.
            output_format: Expected result format.

        Returns:
            Coroutine that creates the handoff, or None.
        """
        if self._message_bus is None or not hasattr(self._message_bus, '_handoff_protocol'):
            return None
        protocol = getattr(self._message_bus, '_handoff_protocol', None)
        if protocol is None:
            return None
        return protocol.create_handoff(
            from_module=self.name,
            to_module=target,
            task=task,
            input_data=input_data,
            output_format=output_format,
        )

    def check_inbox(
        self,
        filter_type: str | None = None,
    ) -> list[Any]:
        """Check this module's inbox for pending messages.

        Safe no-op if MessageBus is not wired yet.

        Args:
            filter_type: Only return messages of this type.

        Returns:
            List of ModuleMessage objects, or empty list.
        """
        if self._message_bus is None:
            return []
        return self._message_bus.receive(self.name, filter_type=filter_type)

    def emit_event(
        self,
        event_name: str,
        payload: dict[str, Any],
        priority: int = 3,
    ) -> Any | None:
        """Emit an event to all subscribers.

        Returns the coroutine for the caller to await.
        Safe no-op if EventSystem is not wired.

        Args:
            event_name: Event constant from modules.shadow.events.
            payload: Event data.
            priority: Message priority.

        Returns:
            Coroutine that emits the event, or None.
        """
        if self._event_system is None:
            return None
        return self._event_system.emit(self.name, event_name, payload, priority)

    def subscribe_event(
        self,
        event_name: str,
        callback: Any | None = None,
    ) -> None:
        """Subscribe to an event.

        Safe no-op if EventSystem is not wired.

        Args:
            event_name: Event constant from modules.shadow.events.
            callback: Optional callable invoked when event fires.
        """
        if self._event_system is None:
            return
        self._event_system.subscribe(self.name, event_name, callback)

    @property
    def info(self) -> dict[str, Any]:
        """Module status snapshot for monitoring and logging."""
        return {
            "name": self.name,
            "status": self.status.value,
            "description": self.description,
            "initialized_at": (
                self._initialized_at.isoformat() if self._initialized_at else None
            ),
            "call_count": self._call_count,
            "error_count": self._error_count,
            "success_rate": self.success_rate,
        }


class ModuleRegistry:
    """Tracks all loaded modules. The orchestrator's phonebook.

    The registry is how the orchestrator knows what modules exist,
    what tools are available, and where to route tasks. It also
    tracks module health for the daily briefing.

    From architecture doc: 'Always running: Grimoire, Cerberus, Void.
    On demand: Reaper, Cipher, Omen, Nova. Scheduled: Harbinger, Morpheus.'
    """

    def __init__(self) -> None:
        self._modules: dict[str, BaseModule] = {}
        self._tool_index: dict[str, str] = {}  # tool_name → module_name

    def register(self, module: BaseModule) -> None:
        """Register a module. Builds tool index from module's tool list.

        This operation is atomic — if any validation fails, the registry
        is unchanged. No partial registrations.
        """
        if module.name in self._modules:
            raise ValueError(f"Module '{module.name}' already registered")

        # Validate ALL tools before mutating any state
        tools = module.get_tools()
        for tool in tools:
            tool_name = tool["name"]
            if tool_name in self._tool_index:
                existing = self._tool_index[tool_name]
                raise ValueError(
                    f"Tool '{tool_name}' already registered by '{existing}'"
                )

        # All checks passed — now mutate state
        self._modules[module.name] = module
        for tool in tools:
            self._tool_index[tool["name"]] = module.name

    def unregister(self, module_name: str) -> None:
        """Remove a module and its tools from the registry."""
        if module_name not in self._modules:
            raise KeyError(f"Module '{module_name}' not registered")
        module = self._modules[module_name]

        # Remove tool index entries
        for tool in module.get_tools():
            self._tool_index.pop(tool["name"], None)

        del self._modules[module_name]

    def get_module(self, name: str) -> BaseModule:
        """Get a module by name. Raises KeyError if not found."""
        if name not in self._modules:
            raise KeyError(f"Module '{name}' not registered")
        return self._modules[name]

    def get_module_for_tool(self, tool_name: str) -> BaseModule:
        """Find which module owns a given tool."""
        if tool_name not in self._tool_index:
            raise KeyError(f"Tool '{tool_name}' not registered")
        module_name = self._tool_index[tool_name]
        return self._modules[module_name]

    def list_tools(self) -> list[dict[str, Any]]:
        """All available tools across all modules. Fed to the LLM prompt."""
        tools = []
        for module in self._modules.values():
            if module.status == ModuleStatus.ONLINE:
                for tool in module.get_tools():
                    tool["module"] = module.name
                    tool["status"] = module.status.value
                    tools.append(tool)
        return tools

    def list_modules(self) -> list[dict[str, Any]]:
        """Status of all registered modules. For monitoring/briefing."""
        return [m.info for m in self._modules.values()]

    @property
    def online_modules(self) -> list[str]:
        """Names of all modules currently online."""
        return [
            name for name, m in self._modules.items()
            if m.status == ModuleStatus.ONLINE
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._modules

    def find_tools(
        self,
        name: str | None = None,
        module: str | None = None,
        permission_level: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query tools by name, module, or permission level.

        All filters are AND-combined. None means no filter on that field.
        Returns tools from ALL modules (not just ONLINE), with module/status.
        """
        results = []
        for mod in self._modules.values():
            if module and mod.name != module:
                continue
            for tool in mod.get_tools():
                if name and tool["name"] != name:
                    continue
                if permission_level and tool.get("permission_level") != permission_level:
                    continue
                tool_copy = dict(tool)
                tool_copy["module"] = mod.name
                tool_copy["status"] = mod.status.value
                results.append(tool_copy)
        return results

    def tool_stats(self) -> dict[str, Any]:
        """Tool count statistics across all modules."""
        total = 0
        by_module: dict[str, int] = {}
        by_permission: dict[str, int] = {}
        for mod in self._modules.values():
            tools = mod.get_tools()
            count = len(tools)
            total += count
            by_module[mod.name] = count
            for tool in tools:
                perm = tool.get("permission_level", "unknown")
                by_permission[perm] = by_permission.get(perm, 0) + 1
        return {
            "total_tools": total,
            "by_module": by_module,
            "by_permission": by_permission,
            "online_modules": len(self.online_modules),
            "total_modules": len(self._modules),
        }

    def __len__(self) -> int:
        return len(self._modules)
