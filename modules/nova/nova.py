"""
Nova — Content Creation
=========================
Documents, reports, emails, briefings — the last mile of presentation.

Design Principle: The last mile matters. A brilliant analysis
presented poorly is a failure. Nova makes everything look professional.

Phase 1: Template-based formatting. No LLM calls — all output is
rule-driven. Density over length: every word earns its place.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.nova")

# Words stripped during briefing compression
FILLER_WORDS: set[str] = {
    "just", "really", "very", "basically", "actually", "simply",
    "quite", "rather", "somewhat", "perhaps", "maybe", "probably",
    "certainly", "definitely", "literally", "essentially", "honestly",
}

# ---------------------------------------------------------------------------
# Template definitions
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, Any]] = {
    "document": {
        "name": "document",
        "description": "Structured Markdown document with optional table of contents",
        "required_fields": ["title", "sections"],
        "optional_fields": ["metadata"],
        "format_function_name": "_format_document",
        "example": {
            "title": "Project Status",
            "sections": [{"heading": "Overview", "body": "Project is on track."}],
        },
    },
    "report": {
        "name": "report",
        "description": "Formal report with executive summary, findings, and recommendations",
        "required_fields": [
            "title", "date", "executive_summary",
            "findings", "recommendations", "conclusion",
        ],
        "optional_fields": [],
        "format_function_name": "_format_report",
        "example": {
            "title": "Q1 Analysis",
            "date": "2026-04-01",
            "executive_summary": "Revenue up 12%.",
            "findings": [{"finding": "Growth", "detail": "Steady increase", "source": "Internal"}],
            "recommendations": ["Continue current strategy"],
            "conclusion": "Strong quarter overall.",
        },
    },
    "email": {
        "name": "email",
        "description": "Tone-aware email formatting (does not send)",
        "required_fields": ["to", "subject", "body", "tone"],
        "optional_fields": [],
        "format_function_name": "_format_email",
        "example": {
            "to": "team@company.com",
            "subject": "Weekly Update",
            "body": "Here are this week's highlights.",
            "tone": "professional",
        },
    },
    "briefing_section": {
        "name": "briefing_section",
        "description": "Compressed, scannable briefing section with priority ranking",
        "required_fields": ["title", "content", "priority"],
        "optional_fields": [],
        "format_function_name": "_format_briefing_section",
        "example": {
            "title": "Critical Alert",
            "content": "Server load exceeding 90% threshold.",
            "priority": 1,
        },
    },
    "business_estimate": {
        "name": "business_estimate",
        "description": "Cost/time estimate for a business project or job",
        "required_fields": ["project_name", "line_items", "timeline"],
        "optional_fields": ["assumptions", "risks", "notes"],
        "format_function_name": "_format_business_estimate",
        "example": {
            "project_name": "Spring Cleanup",
            "line_items": [
                {"item": "Mulch & delivery", "cost": 800},
                {"item": "Labor (4 hrs)", "cost": 360},
            ],
            "timeline": "1 day",
        },
    },
    "meeting_notes": {
        "name": "meeting_notes",
        "description": "Structured meeting notes with attendees, decisions, and action items",
        "required_fields": ["title", "date", "attendees", "discussion"],
        "optional_fields": ["decisions", "action_items"],
        "format_function_name": "_format_meeting_notes",
        "example": {
            "title": "Sprint Planning",
            "date": "2026-04-05",
            "attendees": ["Alice", "Bob"],
            "discussion": "Reviewed backlog priorities.",
            "decisions": ["Move to biweekly sprints"],
            "action_items": [{"owner": "Alice", "task": "Update board", "due": "2026-04-07"}],
        },
    },
}


class Nova(BaseModule):
    """Content creation module. The last mile of presentation.

    Takes raw data from other modules and produces polished, formatted
    output: documents, reports, emails, briefings. All formatting is
    template/rule-based — no LLM calls in Phase 1.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Nova.

        Args:
            config: Module configuration.
        """
        super().__init__(
            name="nova",
            description="Content creation — documents, templates, formatting",
        )
        self._config = config or {}

    async def initialize(self) -> None:
        """Start Nova."""
        self.status = ModuleStatus.STARTING
        self.status = ModuleStatus.ONLINE
        logger.info("Nova online.")

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a Nova tool."""
        start = time.time()
        try:
            handlers = {
                "format_document": self._format_document,
                "format_report": self._format_report,
                "format_email": self._format_email,
                "format_briefing_section": self._format_briefing_section,
                "template_list": self._template_list,
                "template_apply": self._template_apply,
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
                "name": "format_document",
                "description": "Format structured data into a Markdown document",
                "parameters": {"title": "str", "sections": "list", "metadata": "dict"},
                "permission_level": "autonomous",
            },
            {
                "name": "format_report",
                "description": "Format findings into a structured Markdown report",
                "parameters": {
                    "title": "str", "date": "str",
                    "executive_summary": "str", "findings": "list",
                    "recommendations": "list", "conclusion": "str",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "format_email",
                "description": "Format a tone-appropriate email (does not send)",
                "parameters": {"to": "str", "subject": "str", "body": "str", "tone": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "format_briefing_section",
                "description": "Compress content into a scannable briefing section",
                "parameters": {"title": "str", "content": "str", "priority": "int"},
                "permission_level": "autonomous",
            },
            {
                "name": "template_list",
                "description": "List all available formatting templates",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "template_apply",
                "description": "Apply a named template to provided data",
                "parameters": {"template_name": "str", "data": "dict"},
                "permission_level": "autonomous",
            },
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_required_fields(
        self, template_name: str, data: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check that all required fields for a template are present.

        Returns:
            (valid, error_message) — error_message is empty when valid.
        """
        template = TEMPLATES.get(template_name)
        if template is None:
            available = ", ".join(TEMPLATES.keys())
            return False, f"Unknown template: {template_name}. Available: {available}"

        for field in template["required_fields"]:
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value):
                return False, f"Missing required field: {field}"

        return True, ""

    @staticmethod
    def _compress_text(text: str) -> str:
        """Strip filler words and collapse whitespace for briefing density."""
        words = text.split()
        compressed = [w for w in words if w.lower().strip(".,;:!?") not in FILLER_WORDS]
        result = " ".join(compressed)
        # Collapse multiple spaces
        result = re.sub(r" {2,}", " ", result)
        return result.strip()

    @staticmethod
    def _heading_slug(heading: str) -> str:
        """Convert a heading to a Markdown anchor slug."""
        slug = heading.lower().replace(" ", "-")
        slug = re.sub(r"[^a-z0-9\-]", "", slug)
        return slug

    # ------------------------------------------------------------------
    # Direct tool handlers
    # ------------------------------------------------------------------

    def _format_document(self, params: dict[str, Any]) -> ToolResult:
        """Format structured data into a Markdown document.

        Args:
            params: title (str), sections (list of {heading, body}),
                    optional metadata (dict).
        """
        title = params.get("title", "")
        sections = params.get("sections", [])
        metadata = params.get("metadata")

        if not title:
            return ToolResult(
                success=False, content=None, tool_name="format_document",
                module=self.name, error="title is required",
            )

        lines: list[str] = [f"# {title}", ""]

        # Metadata block
        if metadata and isinstance(metadata, dict):
            for key, value in metadata.items():
                lines.append(f"**{key}**: {value}")
            lines.append("")

        # Table of contents for 3+ sections
        if len(sections) >= 3:
            lines.append("## Table of Contents")
            lines.append("")
            for section in sections:
                if isinstance(section, dict):
                    heading = section.get("heading", "Untitled")
                    slug = self._heading_slug(heading)
                    lines.append(f"- [{heading}](#{slug})")
            lines.append("")

        # Sections
        for section in sections:
            if isinstance(section, dict):
                heading = section.get("heading", "Untitled")
                body = section.get("body", "")
                lines.append(f"## {heading}")
                lines.append("")
                if body:
                    lines.append(str(body))
                    lines.append("")

        markdown = "\n".join(lines)

        return ToolResult(
            success=True,
            content={
                "markdown": markdown,
                "title": title,
                "section_count": len(sections),
                "char_count": len(markdown),
            },
            tool_name="format_document",
            module=self.name,
        )

    def _format_report(self, params: dict[str, Any]) -> ToolResult:
        """Format findings into a structured Markdown report.

        Args:
            params: title, date, executive_summary, findings (list of
                    {finding, detail, source}), recommendations (list of str),
                    conclusion.
        """
        required = ["title", "date", "executive_summary",
                     "findings", "recommendations", "conclusion"]
        for field in required:
            value = params.get(field)
            if value is None or (isinstance(value, str) and not value):
                return ToolResult(
                    success=False, content=None, tool_name="format_report",
                    module=self.name, error=f"Missing required field: {field}",
                )

        title = params["title"]
        date = params["date"]
        executive_summary = params["executive_summary"]
        findings = params["findings"]
        recommendations = params["recommendations"]
        conclusion = params["conclusion"]

        lines: list[str] = [
            f"# {title}",
            "",
            f"*Date: {date}*",
            "",
            "## Executive Summary",
            "",
            executive_summary,
            "",
            "## Findings",
            "",
        ]

        for f in findings:
            if isinstance(f, dict):
                lines.append(f"### {f.get('finding', 'Untitled')}")
                lines.append("")
                lines.append(f.get("detail", ""))
                lines.append("")
                source = f.get("source", "")
                if source:
                    lines.append(f"*Source: {source}*")
                    lines.append("")

        lines.append("## Recommendations")
        lines.append("")
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

        lines.append("## Conclusion")
        lines.append("")
        lines.append(conclusion)
        lines.append("")

        markdown = "\n".join(lines)

        return ToolResult(
            success=True,
            content={
                "markdown": markdown,
                "title": title,
                "finding_count": len(findings),
                "char_count": len(markdown),
            },
            tool_name="format_report",
            module=self.name,
        )

    def _format_email(self, params: dict[str, Any]) -> ToolResult:
        """Format a tone-appropriate email.

        Args:
            params: to, subject, body, tone (professional|casual|formal).
        """
        required = ["to", "subject", "body", "tone"]
        for field in required:
            value = params.get(field)
            if not value:
                return ToolResult(
                    success=False, content=None, tool_name="format_email",
                    module=self.name, error=f"Missing required field: {field}",
                )

        to = params["to"]
        subject = params["subject"]
        body = params["body"]
        tone = params["tone"]

        valid_tones = {"professional", "casual", "formal"}
        if tone not in valid_tones:
            return ToolResult(
                success=False, content=None, tool_name="format_email",
                module=self.name,
                error=f"tone must be one of: {', '.join(sorted(valid_tones))}",
            )

        if tone == "professional":
            greeting = f"Dear {to},"
            closing = "Best regards"
        elif tone == "casual":
            greeting = f"Hi {to},"
            closing = "Cheers"
        else:  # formal
            greeting = "Dear Sir/Madam,"
            closing = "Yours faithfully"

        formatted = f"{greeting}\n\n{body}\n\n{closing}"

        return ToolResult(
            success=True,
            content={"formatted": formatted, "tone": tone, "subject": subject},
            tool_name="format_email",
            module=self.name,
        )

    def _format_briefing_section(self, params: dict[str, Any]) -> ToolResult:
        """Compress content into a scannable briefing section.

        Args:
            params: title, content, priority (int 1-5).
        """
        title = params.get("title", "")
        content = params.get("content", "")
        priority = params.get("priority")

        if not title:
            return ToolResult(
                success=False, content=None, tool_name="format_briefing_section",
                module=self.name, error="title is required",
            )
        if not content:
            return ToolResult(
                success=False, content=None, tool_name="format_briefing_section",
                module=self.name, error="content is required",
            )

        try:
            priority = int(priority)
        except (TypeError, ValueError):
            return ToolResult(
                success=False, content=None, tool_name="format_briefing_section",
                module=self.name, error="priority must be an integer 1-5",
            )

        if priority < 1 or priority > 5:
            return ToolResult(
                success=False, content=None, tool_name="format_briefing_section",
                module=self.name, error="priority must be between 1 and 5",
            )

        original_length = len(content)
        compressed = self._compress_text(content)
        compressed_length = len(compressed)

        formatted = f"[P{priority}] **{title}**\n\n{compressed}"

        return ToolResult(
            success=True,
            content={
                "formatted": formatted,
                "title": title,
                "priority": priority,
                "original_length": original_length,
                "compressed_length": compressed_length,
            },
            tool_name="format_briefing_section",
            module=self.name,
        )

    # ------------------------------------------------------------------
    # Template-only handlers (reachable via template_apply)
    # ------------------------------------------------------------------

    def _format_business_estimate(self, params: dict[str, Any]) -> ToolResult:
        """Format a cost/time estimate for a business project.

        Args:
            params: project_name, line_items [{item, cost}], timeline,
                    optional assumptions, risks, notes.
        """
        project_name = params["project_name"]
        line_items = params["line_items"]
        timeline = params["timeline"]

        lines: list[str] = [
            f"# Business Estimate: {project_name}",
            "",
            "## Timeline",
            "",
            str(timeline),
            "",
            "## Line Items",
            "",
            "| Item | Cost |",
            "|------|------|",
        ]

        total = 0.0
        for item in line_items:
            if isinstance(item, dict):
                name = item.get("item", "Unnamed")
                try:
                    cost = float(item.get("cost", 0))
                except (TypeError, ValueError):
                    cost = 0.0
                total += cost
                lines.append(f"| {name} | ${cost:,.2f} |")

        lines.append(f"| **Total** | **${total:,.2f}** |")
        lines.append("")

        # Optional sections
        assumptions = params.get("assumptions")
        if assumptions and isinstance(assumptions, list):
            lines.append("## Assumptions")
            lines.append("")
            for a in assumptions:
                lines.append(f"- {a}")
            lines.append("")

        risks = params.get("risks")
        if risks and isinstance(risks, list):
            lines.append("## Risks")
            lines.append("")
            for r in risks:
                lines.append(f"- {r}")
            lines.append("")

        notes = params.get("notes")
        if notes:
            lines.append("## Notes")
            lines.append("")
            lines.append(str(notes))
            lines.append("")

        markdown = "\n".join(lines)

        return ToolResult(
            success=True,
            content={
                "markdown": markdown,
                "project_name": project_name,
                "total_cost": total,
                "item_count": len(line_items),
                "char_count": len(markdown),
            },
            tool_name="format_business_estimate",
            module=self.name,
        )

    def _format_meeting_notes(self, params: dict[str, Any]) -> ToolResult:
        """Format structured meeting notes.

        Args:
            params: title, date, attendees (list), discussion,
                    optional decisions (list), action_items [{owner, task, due}].
        """
        title = params["title"]
        date = params["date"]
        attendees = params["attendees"]
        discussion = params["discussion"]

        lines: list[str] = [
            f"# Meeting Notes: {title}",
            "",
            f"*Date: {date}*",
            "",
            "## Attendees",
            "",
        ]

        for a in attendees:
            lines.append(f"- {a}")
        lines.append("")

        lines.append("## Discussion")
        lines.append("")
        lines.append(str(discussion))
        lines.append("")

        decisions = params.get("decisions")
        if decisions and isinstance(decisions, list):
            lines.append("## Decisions")
            lines.append("")
            for d in decisions:
                lines.append(f"- {d}")
            lines.append("")

        action_items = params.get("action_items")
        if action_items and isinstance(action_items, list):
            lines.append("## Action Items")
            lines.append("")
            lines.append("| Owner | Task | Due |")
            lines.append("|-------|------|-----|")
            for ai in action_items:
                if isinstance(ai, dict):
                    owner = ai.get("owner", "TBD")
                    task = ai.get("task", "")
                    due = ai.get("due", "TBD")
                    lines.append(f"| {owner} | {task} | {due} |")
            lines.append("")

        markdown = "\n".join(lines)

        return ToolResult(
            success=True,
            content={
                "markdown": markdown,
                "title": title,
                "attendee_count": len(attendees),
                "char_count": len(markdown),
            },
            tool_name="format_meeting_notes",
            module=self.name,
        )

    # ------------------------------------------------------------------
    # Meta tools
    # ------------------------------------------------------------------

    def _template_list(self, params: dict[str, Any]) -> ToolResult:
        """List all available formatting templates."""
        templates = []
        for t in TEMPLATES.values():
            templates.append({
                "name": t["name"],
                "description": t["description"],
                "required_fields": t["required_fields"],
                "example": t["example"],
            })

        return ToolResult(
            success=True,
            content={"templates": templates, "count": len(templates)},
            tool_name="template_list",
            module=self.name,
        )

    def _template_apply(self, params: dict[str, Any]) -> ToolResult:
        """Apply a named template to provided data.

        Args:
            params: template_name (str), data (dict).
        """
        template_name = params.get("template_name", "")
        data = params.get("data", {})

        if not template_name:
            return ToolResult(
                success=False, content=None, tool_name="template_apply",
                module=self.name, error="template_name is required",
            )

        valid, error = self._validate_required_fields(template_name, data)
        if not valid:
            return ToolResult(
                success=False, content=None, tool_name="template_apply",
                module=self.name, error=error,
            )

        template = TEMPLATES[template_name]
        handler = getattr(self, template["format_function_name"])
        result = handler(data)

        # Override tool_name so the caller sees template_apply
        result.tool_name = "template_apply"
        return result
