"""Tests for DynamicToolLoader — load only active module's tools."""

from __future__ import annotations

import pytest

from modules.shadow.tool_loader import DEFAULT_CORE_TOOLS, DynamicToolLoader


# ---------------------------------------------------------------------------
# Helpers: mock registry with 3 modules
# ---------------------------------------------------------------------------

def _make_tool(name: str, desc: str = "desc", params: dict | None = None) -> dict:
    return {
        "name": name,
        "description": desc,
        "parameters": params or {"input": "str — input"},
        "permission_level": "autonomous",
    }


class _FakeRegistry:
    """Minimal stand-in for ModuleRegistry.list_tools()."""

    def __init__(self, tools_by_module: dict[str, list[dict]]) -> None:
        self._tools_by_module = tools_by_module

    def list_tools(self) -> list[dict]:
        result = []
        for mod_name, tools in self._tools_by_module.items():
            for tool in tools:
                t = dict(tool)
                t["module"] = mod_name
                t["status"] = "online"
                result.append(t)
        return result


def _default_registry() -> _FakeRegistry:
    """Registry with 3 modules: wraith (3 tools), omen (2 tools), grimoire (2 tools)."""
    return _FakeRegistry({
        "wraith": [
            _make_tool("set_reminder"),
            _make_tool("list_tasks"),
            _make_tool("get_time"),          # also a core tool
        ],
        "omen": [
            _make_tool("run_code"),
            _make_tool("lint_file"),
        ],
        "grimoire": [
            _make_tool("grimoire_search"),   # core tool
            _make_tool("grimoire_store"),     # core tool
        ],
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetToolsForModule:
    def test_returns_only_module_tools(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        tools = loader.get_tools_for_module("wraith")
        names = {t["name"] for t in tools}
        assert names == {"set_reminder", "list_tasks", "get_time"}

    def test_returns_empty_for_unknown_module(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        tools = loader.get_tools_for_module("nonexistent")
        assert tools == []

    def test_returns_empty_when_module_has_no_tools(self):
        registry = _FakeRegistry({"empty_mod": []})
        loader = DynamicToolLoader(module_registry=registry)
        tools = loader.get_tools_for_module("empty_mod")
        assert tools == []


class TestGetCoreTools:
    def test_returns_minimal_always_available_set(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        core = loader.get_core_tools()
        core_names = {t["name"] for t in core}
        # From the mock registry, only get_time, grimoire_search, grimoire_store exist
        assert "grimoire_search" in core_names
        assert "grimoire_store" in core_names
        assert "get_time" in core_names

    def test_core_tools_configurable(self):
        loader = DynamicToolLoader(
            module_registry=_default_registry(),
            core_tool_names={"lint_file"},
        )
        core = loader.get_core_tools()
        assert len(core) == 1
        assert core[0]["name"] == "lint_file"


class TestGetToolsForTask:
    def test_combines_module_and_core_tools(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        tools = loader.get_tools_for_task(module_name="omen")
        names = {t["name"] for t in tools}
        # omen tools + core tools from registry
        assert "run_code" in names
        assert "lint_file" in names
        assert "grimoire_search" in names
        assert "grimoire_store" in names
        assert "get_time" in names

    def test_deduplicates_core_in_module(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        # wraith has get_time which is also a core tool
        tools = loader.get_tools_for_task(module_name="wraith")
        names = [t["name"] for t in tools]
        assert names.count("get_time") == 1

    def test_none_module_returns_only_core(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        tools = loader.get_tools_for_task(module_name=None)
        names = {t["name"] for t in tools}
        # Should only be core tools that exist in the registry
        assert names <= {"get_time", "grimoire_search", "grimoire_store"}
        assert len(names) > 0

    def test_unknown_module_returns_only_core(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        tools = loader.get_tools_for_task(module_name="nonexistent")
        names = {t["name"] for t in tools}
        assert names <= {"get_time", "grimoire_search", "grimoire_store"}

    def test_cross_module_detection(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        task = {"input": "search the web for python tutorials"}
        tools = loader.get_tools_for_task(module_name="omen", task=task)
        # reaper isn't in mock registry, so no extra tools added but no crash
        names = {t["name"] for t in tools}
        assert "run_code" in names  # still has omen tools


class TestEstimateToolTokens:
    def test_returns_reasonable_count(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        tools = loader.get_tools_for_module("wraith")
        tokens = loader.estimate_tool_tokens(tools)
        assert tokens > 0

    def test_fewer_tools_fewer_tokens(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        one_mod = loader.get_tools_for_module("omen")
        all_tools = [t for tools in loader._index.values() for t in tools]
        assert loader.estimate_tool_tokens(one_mod) < loader.estimate_tool_tokens(all_tools)

    def test_empty_list_returns_zero(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        assert loader.estimate_tool_tokens([]) == 0


class TestGetLoadingReport:
    def test_has_correct_fields(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        loader.get_tools_for_task(module_name="omen")
        report = loader.get_loading_report()
        assert "tools_loaded" in report
        assert "tools_available" in report
        assert "tokens_saved" in report
        assert "module_loaded" in report

    def test_token_savings_correct(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        loader.get_tools_for_task(module_name="omen")
        report = loader.get_loading_report()
        # Loading 1 module (omen: 2 tools + 3 core) < all 7 tools
        assert report["tools_loaded"] <= report["tools_available"]
        assert report["tokens_saved"] >= 0

    def test_one_module_fewer_than_all(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        loader.get_tools_for_task(module_name="omen")
        report = loader.get_loading_report()
        assert report["tools_loaded"] < report["tools_available"]

    def test_default_report_without_task(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        report = loader.get_loading_report()
        assert report["tools_loaded"] == 0
        assert report["module_loaded"] is None


class TestGracefulHandling:
    def test_none_registry(self):
        loader = DynamicToolLoader(module_registry=None)
        assert loader.get_tools_for_module("anything") == []
        assert loader.get_core_tools() == []
        assert loader.get_tools_for_task(module_name="anything") == []

    def test_registry_none_get_loading_report(self):
        loader = DynamicToolLoader(module_registry=None)
        report = loader.get_loading_report()
        assert report["tools_loaded"] == 0


class TestToolSchemaFormat:
    def test_tools_have_name_and_description(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        for tools in loader._index.values():
            for tool in tools:
                assert "name" in tool, f"Tool missing 'name': {tool}"
                assert "description" in tool, f"Tool missing 'description': {tool}"

    def test_refresh_rebuilds_index(self):
        loader = DynamicToolLoader(module_registry=_default_registry())
        assert len(loader._index) == 3
        loader._registry = _FakeRegistry({"single": [_make_tool("only_tool")]})
        loader.refresh()
        assert len(loader._index) == 1
        assert loader.get_tools_for_module("single")[0]["name"] == "only_tool"
