"""
Reaper Module Adapter
======================
Wraps the existing Reaper implementation (reaper.py) with the
BaseModule interface so the orchestrator can route research tasks here.

Your existing reaper.py stays exactly as-is. This adapter translates
between the orchestrator's execute(tool_name, params) interface and
Reaper's actual methods.

Architecture: 'Reaper is the module that keeps Shadow informed.
Without Reaper, Shadow knows only what he was trained on.'
"""

import logging
import time
from datetime import datetime
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.reaper")


class ReaperModule(BaseModule):
    """BaseModule adapter for Reaper (research & intelligence).

    Architecture: 'On demand. Called during Step 5 for web research,
    scraping, data collection.'

    Note: Reaper's constructor requires a Grimoire instance because
    it stores research results directly into memory. Pass the
    GrimoireModule's internal _grimoire reference when creating this.
    """

    def __init__(self, config: dict[str, Any], grimoire_instance=None) -> None:
        super().__init__(
            name="reaper",
            description="Research & intelligence — web search, scraping, YouTube, Reddit",
        )
        self._config = config
        self._grimoire_instance = grimoire_instance  # Actual Grimoire object
        self._reaper = None  # Will hold the existing Reaper instance

    async def initialize(self) -> None:
        """Initialize the existing Reaper system."""
        self.status = ModuleStatus.STARTING
        try:
            # Import the existing Reaper class from your built code
            from modules.reaper.reaper import Reaper

            if self._grimoire_instance is None:
                raise ValueError(
                    "Reaper requires a Grimoire instance. "
                    "Pass grimoire_instance when creating ReaperModule."
                )

            self._reaper = Reaper(
                grimoire=self._grimoire_instance,
                data_dir=self._config.get("data_dir", "data/research"),
            )

            logger.info("Reaper initialized. Search backends ready.")
            self.status = ModuleStatus.ONLINE
            self._initialized_at = datetime.now()

        except ImportError as e:
            logger.error(
                "Could not import existing Reaper. "
                "Make sure modules/reaper/reaper.py exists: %s", e
            )
            self.status = ModuleStatus.ERROR
            raise

        except Exception as e:
            logger.error("Reaper initialization failed: %s", e)
            self.status = ModuleStatus.ERROR
            raise

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Route tool calls to the existing Reaper methods."""
        start = time.time()

        if self._reaper is None:
            return ToolResult(
                success=False,
                content=None,
                tool_name=tool_name,
                module=self.name,
                error="Reaper not initialized",
            )

        try:
            if tool_name == "web_search":
                query = params.get("query", "")
                max_results = params.get("max_results", 5)
                results = self._reaper.search(
                    query=query,
                    max_results=max_results,
                )
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=results,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "web_fetch":
                url = params.get("url", "")
                result = self._reaper.fetch_page(url)
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=result,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            elif tool_name == "youtube_transcribe":
                url = params.get("url", "")
                result = self._reaper.youtube_transcribe(url)
                self._record_call(True)
                return ToolResult(
                    success=True,
                    content=result,
                    tool_name=tool_name,
                    module=self.name,
                    execution_time_ms=(time.time() - start) * 1000,
                )

            else:
                self._record_call(False)
                return ToolResult(
                    success=False,
                    content=None,
                    tool_name=tool_name,
                    module=self.name,
                    error=f"Unknown Reaper tool: {tool_name}",
                    execution_time_ms=(time.time() - start) * 1000,
                )

        except Exception as e:
            self._record_call(False)
            logger.error("Reaper execution error: %s", e)
            return ToolResult(
                success=False,
                content=None,
                tool_name=tool_name,
                module=self.name,
                error=str(e),
                execution_time_ms=(time.time() - start) * 1000,
            )

    async def shutdown(self) -> None:
        """Reaper shutdown."""
        if self._reaper is not None:
            self._reaper.close()
        logger.info("Reaper shutting down.")
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        """Reaper's MCP tools."""
        return [
            {
                "name": "web_search",
                "description": "Search via SearXNG/DDG/Bing fallback chain",
                "parameters": {
                    "query": "str — search query",
                    "max_results": "int — max results (default 5)",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "web_fetch",
                "description": "Retrieve full page content from URL",
                "parameters": {
                    "url": "str — URL to fetch",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "youtube_transcribe",
                "description": "Download and process YouTube subtitles via yt-dlp",
                "parameters": {
                    "url": "str — YouTube URL",
                },
                "permission_level": "autonomous",
            },
        ]
