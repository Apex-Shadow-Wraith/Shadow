"""Regression tests for the router opt-out mechanism.

Verifies that `ModuleRegistry.is_routable()` correctly integrates with
`config.<name>.enabled` and that orchestrator routing surfaces skip
modules whose `enabled` flag is False.

Primary consumer in practice is Morpheus (default
`config.morpheus.enabled=False` after Phase A). These tests assume
Morpheus-style semantics for a module class `Dummy` whose config has
an `enabled: bool` field.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from modules.base import BaseModule, ModuleRegistry, ModuleStatus, ToolResult


class _DummyOnline(BaseModule):
    """Minimal BaseModule that's ONLINE out of the box."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name, description="dummy for tests")
        self.status = ModuleStatus.ONLINE

    async def initialize(self) -> None: ...
    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, content=None, tool_name=tool_name, module=self.name)
    async def shutdown(self) -> None: ...
    def get_tools(self) -> list[dict[str, Any]]:
        return [{
            "name": f"{self.name}_tool",
            "description": f"dummy tool for {self.name}",
            "parameters": {},
            "permission_level": "autonomous",
        }]


def test_is_routable_returns_false_when_not_registered():
    r = ModuleRegistry()
    assert r.is_routable("morpheus") is False


def test_is_routable_returns_false_when_offline():
    r = ModuleRegistry()
    m = _DummyOnline("morpheus")
    m.status = ModuleStatus.OFFLINE
    r._modules["morpheus"] = m
    assert r.is_routable("morpheus") is False


def test_is_routable_respects_enabled_flag():
    r = ModuleRegistry()
    r._modules["morpheus"] = _DummyOnline("morpheus")

    # Patch the singleton's morpheus settings so is_routable sees False.
    fake_cfg = MagicMock()
    fake_cfg.morpheus = MagicMock()
    fake_cfg.morpheus.enabled = False
    with patch("shadow.config.config", fake_cfg):
        assert r.is_routable("morpheus") is False

    fake_cfg.morpheus.enabled = True
    with patch("shadow.config.config", fake_cfg):
        assert r.is_routable("morpheus") is True


def test_is_routable_backward_compat_modules_without_enabled():
    """A module whose settings class has no `enabled` attribute is routable."""
    r = ModuleRegistry()
    r._modules["some_legacy_module"] = _DummyOnline("some_legacy_module")

    # shadow.config.config has no attribute for this module → getattr returns None
    assert r.is_routable("some_legacy_module") is True


def test_fast_path_skips_morpheus_when_dormant(tmp_path):
    """When Morpheus is dormant, 'brainstorm ideas' must NOT fast-path to morpheus."""
    from modules.shadow.orchestrator import Orchestrator

    cfg = {
        "system": {"state_file": str(tmp_path / "state.json")},
        "models": {
            "ollama_base_url": "http://localhost:11434",
            "router": {"name": "phi4-mini"},
            "fast_brain": {"name": "phi4-mini"},
            "smart_brain": {"name": "phi4-mini"},
        },
        "decision_loop": {"context_memories": 3},
    }
    orch = Orchestrator(cfg)
    # No modules registered → is_routable("morpheus") is False → Priority-7 block skipped.
    result = orch._fast_path_classify("brainstorm some ideas for the project")
    if result is not None:
        assert result.target_module != "morpheus", (
            "Fast-path returned morpheus target despite dormant state"
        )
