"""Dynamic Tool Loading — load only the active module's tool schemas into context.

Saves 2-4K tokens per request by loading only the tools relevant to the
routed module instead of all 138+ tools across all 13 modules.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default core tools available regardless of which module is active.
DEFAULT_CORE_TOOLS = frozenset({
    "grimoire_search",
    "grimoire_store",
    "send_notification",
    "get_time",
    "get_date",
})


class DynamicToolLoader:
    """Load only the active module's tool schemas instead of the full set.

    Integrates with ModuleRegistry to build a module→tools index and
    return the minimal tool set needed for a given request.
    """

    def __init__(
        self,
        module_registry: Any | None = None,
        core_tool_names: set[str] | None = None,
    ) -> None:
        self._registry = module_registry
        self._core_tool_names: set[str] = set(
            core_tool_names if core_tool_names is not None else DEFAULT_CORE_TOOLS
        )
        # Cache: module_name → [tool_schema, ...]
        self._index: dict[str, list[dict[str, Any]]] = {}
        self._last_report: dict[str, Any] = {}

        if self._registry is not None:
            self._build_index()

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def _build_index(self) -> None:
        """Build the internal module→tools mapping from the registry."""
        try:
            all_tools = self._registry.list_tools()
            self._index.clear()
            for tool in all_tools:
                mod_name = tool.get("module", "unknown")
                self._index.setdefault(mod_name, []).append(tool)

            total_tools = sum(len(t) for t in self._index.values())
            logger.info(
                "Tool index built: %d modules, %d tools. Modules: %s",
                len(self._index),
                total_tools,
                ", ".join(
                    f"{m}({len(t)})" for m, t in sorted(self._index.items())
                ) if self._index else "(empty)",
            )

            # Keep _last_report in sync so get_loading_report() is accurate
            self._last_report = {
                "tools_loaded": 0,
                "tools_available": total_tools,
                "tokens_saved": 0,
                "tokens_loaded": 0,
                "module_loaded": None,
            }
        except Exception as e:
            logger.warning("Failed to build tool index: %s", e)
            self._index = {}

    def refresh(self) -> None:
        """Rebuild the index (call after modules go online/offline)."""
        if self._registry is not None:
            old_count = len(self._index)
            self._build_index()
            new_count = len(self._index)
            if new_count == 0 and old_count == 0:
                logger.warning(
                    "Tool index still empty after refresh — are modules ONLINE?"
                )
        else:
            logger.warning("refresh() called but no registry is set")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_tools_for_module(self, module_name: str) -> list[dict[str, Any]]:
        """Return only the tool schemas belonging to the specified module.

        Returns an empty list (with a warning) if the module is not found.
        Auto-refreshes the index if it's empty but the registry has modules.
        """
        try:
            # Auto-refresh: index empty but registry has registered modules
            if not self._index and self._registry is not None:
                try:
                    registered = self._registry.list_modules()
                    if registered:
                        logger.info(
                            "Tool index empty but registry has %d modules — auto-refreshing",
                            len(registered),
                        )
                        self._build_index()
                except Exception:
                    pass  # list_modules may not exist on mock registries

            if module_name not in self._index:
                available = sorted(self._index.keys()) if self._index else []
                logger.warning(
                    "Module '%s' not found in tool index (available: %s)",
                    module_name,
                    ", ".join(available) if available else "none — index is empty",
                )
                return []
            return list(self._index[module_name])
        except Exception as e:
            logger.warning("get_tools_for_module failed: %s", e)
            return []

    def get_core_tools(self) -> list[dict[str, Any]]:
        """Return the minimal set of always-available tools.

        Core tools (memory access, notifications, time utilities) are
        loaded when routing is uncertain or as a fallback.
        """
        try:
            core: list[dict[str, Any]] = []
            for tools in self._index.values():
                for tool in tools:
                    if tool.get("name") in self._core_tool_names:
                        core.append(tool)
            return core
        except Exception as e:
            logger.warning("get_core_tools failed: %s", e)
            return []

    def get_tools_for_task(
        self,
        module_name: str | None = None,
        task: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Primary method called by the orchestrator.

        Returns module-specific tools + core tools (deduplicated).
        If module_name is None or unknown, returns only core tools.
        """
        try:
            if module_name:
                module_tools = self.get_tools_for_module(module_name)
            else:
                module_tools = []

            core_tools = self.get_core_tools()

            # Deduplicate: module tools take priority over core duplicates
            seen_names: set[str] = set()
            combined: list[dict[str, Any]] = []

            for tool in module_tools:
                name = tool.get("name", "")
                if name not in seen_names:
                    seen_names.add(name)
                    combined.append(tool)

            for tool in core_tools:
                name = tool.get("name", "")
                if name not in seen_names:
                    seen_names.add(name)
                    combined.append(tool)

            # Cross-module hint: if task metadata mentions another module's
            # capability, include those tools too.
            if task and module_name:
                extra_module = self._detect_cross_module_need(task)
                if extra_module and extra_module != module_name:
                    for tool in self.get_tools_for_module(extra_module):
                        name = tool.get("name", "")
                        if name not in seen_names:
                            seen_names.add(name)
                            combined.append(tool)

            # Build report
            all_count = sum(len(t) for t in self._index.values())
            all_tokens = self.estimate_tool_tokens(
                [t for tools in self._index.values() for t in tools]
            )
            loaded_tokens = self.estimate_tool_tokens(combined)
            self._last_report = {
                "tools_loaded": len(combined),
                "tools_available": all_count,
                "tokens_saved": max(0, all_tokens - loaded_tokens),
                "tokens_loaded": loaded_tokens,
                "module_loaded": module_name,
            }

            return combined
        except Exception as e:
            logger.warning("get_tools_for_task failed: %s", e)
            return []

    def estimate_tool_tokens(self, tools: list[dict[str, Any]]) -> int:
        """Estimate token count for tool schemas using 4 chars/token heuristic."""
        try:
            total_chars = 0
            for tool in tools:
                total_chars += len(str(tool.get("name", "")))
                total_chars += len(str(tool.get("description", "")))
                total_chars += len(str(tool.get("parameters", {})))
            return total_chars // 4
        except Exception as e:
            logger.warning("estimate_tool_tokens failed: %s", e)
            return 0

    def get_loading_report(self) -> dict[str, Any]:
        """Return stats from the last get_tools_for_task call.

        Keys: tools_loaded, tools_available, tokens_saved,
              tokens_loaded, module_loaded.
        """
        return dict(self._last_report) if self._last_report else {
            "tools_loaded": 0,
            "tools_available": 0,
            "tokens_saved": 0,
            "tokens_loaded": 0,
            "module_loaded": None,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    _CROSS_MODULE_KEYWORDS: dict[str, list[str]] = {
        "reaper": ["search the web", "scrape", "reddit", "research online"],
        "grimoire": ["remember", "recall", "memory", "stored knowledge"],
        "sentinel": ["security", "scan network", "firewall"],
        "cipher": ["calculate", "math", "convert units"],
        "nova": ["generate content", "write document", "create image"],
        "omen": ["write code", "debug", "lint", "git"],
        "harbinger": ["notify", "alert", "briefing"],
    }

    def _detect_cross_module_need(self, task: dict[str, Any]) -> str | None:
        """Detect if a task hints at needing another module's tools."""
        try:
            text = str(task.get("input", "")).lower()
            if not text:
                return None
            for module_name, keywords in self._CROSS_MODULE_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in text:
                        return module_name
            return None
        except Exception:
            return None
