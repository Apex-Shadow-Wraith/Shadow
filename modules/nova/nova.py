"""
Nova — Content Creation
=========================
Documents, images, voice, and the last mile of presentation.

Design Principle: The last mile matters. A brilliant analysis
presented poorly is a failure. Nova makes everything look professional.

Phase 1: Markdown document generation, report templates, content
formatting. Image and voice are stubs for SDXL/FLUX and TTS.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.nova")

# Report templates
_TEMPLATES: dict[str, list[str]] = {
    "morning_briefing": [
        "Critical Alerts", "Decision Queue", "Today's Schedule",
        "Weather", "Email Summary", "Business Snapshot",
        "Research & Intel", "Morpheus Report", "Shadow Growth",
        "Pending Reminders",
    ],
    "evening_summary": [
        "Completed Today", "Pending Items", "Tomorrow Preview",
        "Shadow Activity", "Overnight Plan",
    ],
    "research_report": [
        "Executive Summary", "Methodology", "Findings",
        "Sources", "Confidence Assessment", "Recommendations",
    ],
    "status_report": [
        "System Health", "Module Status", "Performance Metrics",
        "Growth Engine Progress", "Issues & Alerts",
    ],
}


class Nova(BaseModule):
    """Content creation module. The last mile of presentation.

    Takes raw data from other modules and produces polished output:
    documents, formatted text, reports. Image and voice stubs for
    later phases.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Nova.

        Args:
            config: Module configuration.
        """
        super().__init__(
            name="nova",
            description="Content creation — documents, images, voice, last mile",
        )
        self._config = config or {}
        self._output_dir = Path(self._config.get("output_dir", "data/nova_output"))

    async def initialize(self) -> None:
        """Start Nova."""
        self.status = ModuleStatus.STARTING
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self.status = ModuleStatus.ONLINE
        logger.info("Nova online. Output dir: %s", self._output_dir)

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a Nova tool."""
        start = time.time()
        try:
            handlers = {
                "document_create": self._document_create,
                "content_format": self._content_format,
                "report_template": self._report_template,
                "image_generate": self._image_generate,
                "voice_generate": self._voice_generate,
            }

            handler = handlers.get(tool_name)
            if handler is None:
                result = ToolResult(
                    success=False, content=None, tool_name=tool_name,
                    module=self.name, error=f"Unknown tool: {tool_name}",
                )
            else:
                result = handler(params)

            result.execution_time_ms = (time.time() - start) * 1000
            self._record_call(result.success)
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._record_call(False)
            logger.error("Nova tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False, content=None, tool_name=tool_name,
                module=self.name, error=str(e), execution_time_ms=elapsed,
            )

    async def shutdown(self) -> None:
        """Shut down Nova."""
        self.status = ModuleStatus.OFFLINE
        logger.info("Nova offline.")

    def get_tools(self) -> list[dict[str, Any]]:
        """Return Nova's tool definitions."""
        return [
            {
                "name": "document_create",
                "description": "Generate formatted Markdown documents",
                "parameters": {"title": "str", "sections": "list", "save": "bool"},
                "permission_level": "autonomous",
            },
            {
                "name": "content_format",
                "description": "Format text for specific output type",
                "parameters": {"content": "str", "format_type": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "report_template",
                "description": "Apply a named template to structured data",
                "parameters": {"template_name": "str", "data": "dict"},
                "permission_level": "autonomous",
            },
            {
                "name": "image_generate",
                "description": "Create images (stub for SDXL/FLUX)",
                "parameters": {"prompt": "str", "style": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "voice_generate",
                "description": "Generate voice output (stub for TTS)",
                "parameters": {"text": "str", "voice": "str"},
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _document_create(self, params: dict[str, Any]) -> ToolResult:
        """Generate a Markdown document.

        Args:
            params: 'title', 'sections' (list of dicts with heading/content),
                    optional 'save' (bool).
        """
        title = params.get("title", "")
        sections = params.get("sections", [])
        save = params.get("save", False)

        if not title:
            return ToolResult(
                success=False, content=None, tool_name="document_create",
                module=self.name, error="Title is required",
            )

        # Build Markdown
        lines = [
            f"# {title}",
            "",
            f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
        ]

        for section in sections:
            if isinstance(section, dict):
                heading = section.get("heading", "Untitled")
                content = section.get("content", "")
                lines.append(f"## {heading}")
                lines.append("")
                lines.append(str(content))
                lines.append("")

        markdown = "\n".join(lines)

        result_content: dict[str, Any] = {
            "title": title,
            "markdown": markdown,
            "sections_count": len(sections),
            "char_count": len(markdown),
        }

        if save:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
            filename = f"{timestamp}_{safe_title.replace(' ', '_')}.md"
            filepath = self._output_dir / filename
            filepath.write_text(markdown, encoding="utf-8")
            result_content["saved_to"] = str(filepath)

        return ToolResult(
            success=True,
            content=result_content,
            tool_name="document_create",
            module=self.name,
        )

    def _content_format(self, params: dict[str, Any]) -> ToolResult:
        """Format content for a specific output type.

        Args:
            params: 'content' (str), 'format_type' (email/report/summary/list).
        """
        content = params.get("content", "")
        format_type = params.get("format_type", "summary")

        if not content:
            return ToolResult(
                success=False, content=None, tool_name="content_format",
                module=self.name, error="Content is required",
            )

        valid_types = ("email", "report", "summary", "list", "notification")
        if format_type not in valid_types:
            return ToolResult(
                success=False, content=None, tool_name="content_format",
                module=self.name,
                error=f"format_type must be one of: {', '.join(valid_types)}",
            )

        if format_type == "email":
            formatted = f"Subject: [Action Required]\n\n{content}\n\n---\nSent via Shadow"
        elif format_type == "report":
            formatted = f"--- REPORT ---\n\n{content}\n\n--- END REPORT ---"
        elif format_type == "summary":
            # Truncate to first 500 chars for summary
            formatted = content[:500] + ("..." if len(content) > 500 else "")
        elif format_type == "list":
            items = [line.strip() for line in content.split("\n") if line.strip()]
            formatted = "\n".join(f"- {item}" for item in items)
        elif format_type == "notification":
            formatted = content[:200]  # Two-line rule for notifications
        else:
            formatted = content

        return ToolResult(
            success=True,
            content={
                "original_length": len(content),
                "formatted": formatted,
                "format_type": format_type,
            },
            tool_name="content_format",
            module=self.name,
        )

    def _report_template(self, params: dict[str, Any]) -> ToolResult:
        """Apply a named template to structured data.

        Args:
            params: 'template_name' (str), 'data' (dict of section_name → content).
        """
        template_name = params.get("template_name", "")
        data = params.get("data", {})

        if not template_name:
            return ToolResult(
                success=False, content=None, tool_name="report_template",
                module=self.name, error="template_name is required",
            )

        if template_name not in _TEMPLATES:
            return ToolResult(
                success=False, content=None, tool_name="report_template",
                module=self.name,
                error=f"Unknown template: {template_name}. "
                      f"Available: {', '.join(_TEMPLATES.keys())}",
            )

        sections = _TEMPLATES[template_name]
        report_sections = []
        for section_name in sections:
            key = section_name.lower().replace(" ", "_").replace("&", "and")
            content = data.get(key, data.get(section_name, "No data available."))
            report_sections.append({
                "heading": section_name,
                "content": content,
            })

        return ToolResult(
            success=True,
            content={
                "template": template_name,
                "sections": report_sections,
                "available_templates": list(_TEMPLATES.keys()),
            },
            tool_name="report_template",
            module=self.name,
        )

    def _image_generate(self, params: dict[str, Any]) -> ToolResult:
        """Generate an image (stub for SDXL/FLUX).

        Args:
            params: 'prompt' (str), optional 'style'.
        """
        prompt = params.get("prompt", "")
        if not prompt:
            return ToolResult(
                success=False, content=None, tool_name="image_generate",
                module=self.name, error="Prompt is required",
            )

        return ToolResult(
            success=True,
            content={
                "status": "stub",
                "prompt": prompt,
                "style": params.get("style", "default"),
                "message": "Image generation requires SDXL/FLUX on Ubuntu with GPU. "
                           "Deferred to Phase 5.",
            },
            tool_name="image_generate",
            module=self.name,
        )

    def _voice_generate(self, params: dict[str, Any]) -> ToolResult:
        """Generate voice output (stub for TTS).

        Args:
            params: 'text' (str), optional 'voice'.
        """
        text = params.get("text", "")
        if not text:
            return ToolResult(
                success=False, content=None, tool_name="voice_generate",
                module=self.name, error="Text is required",
            )

        return ToolResult(
            success=True,
            content={
                "status": "stub",
                "text_length": len(text),
                "voice": params.get("voice", "default"),
                "message": "Voice output requires TTS engine (Coqui TTS or OpenVoice). "
                           "Deferred to Phase 5.",
            },
            tool_name="voice_generate",
            module=self.name,
        )
