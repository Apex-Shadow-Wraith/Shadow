"""
Integration Tests
==================
Verifies all 13 modules instantiate, expose valid tools,
have no duplicate tool names, and work with the registry.
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from modules.base import BaseModule, ModuleRegistry, ModuleStatus


# ===================================================================
# Module instantiation helpers
# ===================================================================

def _make_config(tmp_path: Path, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a safe config pointing all DBs/files to tmp_path."""
    cfg = {
        "db_path": str(tmp_path / "test.db"),
        "queue_file": str(tmp_path / "queue.json"),
        "limits_file": str(tmp_path / "limits.yaml"),
        "baseline_file": str(tmp_path / "baseline.json"),
        "quarantine_dir": str(tmp_path / "quarantine"),
        "project_root": str(tmp_path),
    }
    if overrides:
        cfg.update(overrides)
    return cfg


def _create_all_modules(tmp_path: Path) -> list[BaseModule]:
    """Instantiate all 13 modules with safe configs."""
    from modules.apex.apex import Apex
    from modules.cerberus.cerberus import Cerberus
    from modules.cipher.cipher import Cipher
    from modules.grimoire.grimoire_module import GrimoireModule
    from modules.harbinger.harbinger import Harbinger
    from modules.morpheus.morpheus import Morpheus
    from modules.nova.nova import Nova
    from modules.omen.omen import Omen
    from modules.reaper.reaper_module import ReaperModule
    from modules.sentinel.sentinel import Sentinel
    from modules.shadow.shadow_module import ShadowModule
    from modules.void.void import Void
    from modules.wraith.wraith import Wraith

    registry = ModuleRegistry()
    cfg = _make_config(tmp_path)

    modules = [
        Apex(config=cfg),
        Cerberus(config=cfg),
        Cipher(),
        GrimoireModule(config={
            "db_path": str(tmp_path / "grimoire.db"),
            "vector_path": str(tmp_path / "vectors"),
        }),
        Harbinger(config=cfg),
        Morpheus(config=cfg),
        Nova(),
        Omen(config=cfg),
        ReaperModule(config=cfg),
        Sentinel(config=cfg),
        ShadowModule(config=cfg, registry=registry),
        Void(config=cfg),
        Wraith(config=cfg),
    ]
    return modules


# ===================================================================
# Tests
# ===================================================================

class TestInstantiateAllModules:
    """Every module can be instantiated with safe test configs."""

    def test_instantiate_all_modules(self, tmp_path):
        """All 13 BaseModule subclasses instantiate without error."""
        modules = _create_all_modules(tmp_path)
        assert len(modules) == 13

        for mod in modules:
            assert isinstance(mod, BaseModule), f"{mod} is not a BaseModule"
            assert mod.name, f"Module has no name: {mod}"
            assert mod.description, f"Module has no description: {mod}"

    def test_all_modules_have_names(self, tmp_path):
        """Every module has a unique name."""
        modules = _create_all_modules(tmp_path)
        names = [m.name for m in modules]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"


class TestGetToolsStructure:
    """Every tool dict has the required fields."""

    def test_tool_dicts_have_required_fields(self, tmp_path):
        """Each tool returned by get_tools() has name, description, parameters, permission_level."""
        modules = _create_all_modules(tmp_path)
        required_keys = {"name", "description", "parameters", "permission_level"}

        for mod in modules:
            tools = mod.get_tools()
            for tool in tools:
                missing = required_keys - set(tool.keys())
                assert not missing, (
                    f"{mod.name}.{tool.get('name', '?')} missing keys: {missing}"
                )

    def test_tool_names_are_strings(self, tmp_path):
        """All tool names are non-empty strings."""
        modules = _create_all_modules(tmp_path)
        for mod in modules:
            for tool in mod.get_tools():
                assert isinstance(tool["name"], str)
                assert len(tool["name"]) > 0


class TestNoDuplicateToolNames:
    """No two modules should register the same tool name."""

    def test_no_duplicate_tool_names(self, tmp_path):
        """Collect all tool names across all modules and verify uniqueness."""
        modules = _create_all_modules(tmp_path)
        seen: dict[str, str] = {}  # tool_name -> module_name

        for mod in modules:
            for tool in mod.get_tools():
                name = tool["name"]
                assert name not in seen, (
                    f"Duplicate tool '{name}': registered by both "
                    f"'{seen[name]}' and '{mod.name}'"
                )
                seen[name] = mod.name


class TestToolCount:
    """Total tool count across all modules."""

    def test_tool_count(self, tmp_path):
        """Assert total tools = 108 across 13 modules."""
        modules = _create_all_modules(tmp_path)
        total = sum(len(m.get_tools()) for m in modules)
        assert total == 146, (
            f"Expected 146 tools, got {total}. "
            f"By module: {', '.join(f'{m.name}={len(m.get_tools())}' for m in modules)}"
        )


class TestRegistryRoundTrip:
    """Register all modules and verify tool routing."""

    def test_registry_round_trip(self, tmp_path):
        """Register all modules, then look up each tool's owner."""
        modules = _create_all_modules(tmp_path)
        registry = ModuleRegistry()

        # ShadowModule already got a registry in _create_all_modules,
        # but we need to register all into THIS registry
        for mod in modules:
            # ShadowModule may reference a different registry internally;
            # that's fine — we're testing the ModuleRegistry routing
            registry.register(mod)

        assert len(registry) == 13

        # Verify every tool routes back to the correct module
        for mod in modules:
            for tool in mod.get_tools():
                found = registry.get_module_for_tool(tool["name"])
                assert found.name == mod.name, (
                    f"Tool '{tool['name']}' expected module '{mod.name}', "
                    f"got '{found.name}'"
                )

    def test_registry_tool_stats(self, tmp_path):
        """Registry tool_stats() matches expected counts."""
        modules = _create_all_modules(tmp_path)
        registry = ModuleRegistry()
        for mod in modules:
            registry.register(mod)

        stats = registry.tool_stats()
        assert stats["total_tools"] == 146
        assert stats["total_modules"] == 13
