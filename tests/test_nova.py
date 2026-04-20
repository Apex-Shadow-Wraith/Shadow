"""
Tests for Nova — Content Creation (Phase 1 + Ollama generation)
================================================================
6 tools, template system, document formatting, raw content generation.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from pathlib import Path
from typing import Any

from modules.base import ModuleStatus, ToolResult
from modules.nova.nova import Nova, TEMPLATES


@pytest.fixture
def nova() -> Nova:
    return Nova({})


@pytest.fixture
async def online_nova(nova: Nova) -> Nova:
    await nova.initialize()
    return nova


# ---------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------

class TestNovaLifecycle:
    @pytest.mark.asyncio
    async def test_initialize(self, nova: Nova):
        await nova.initialize()
        assert nova.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown(self, nova: Nova):
        await nova.initialize()
        await nova.shutdown()
        assert nova.status == ModuleStatus.OFFLINE

    def test_get_tools(self, nova: Nova):
        tools = nova.get_tools()
        assert len(tools) == 6
        names = [t["name"] for t in tools]
        assert "format_document" in names
        assert "format_report" in names
        assert "format_email" in names
        assert "format_briefing_section" in names
        assert "template_list" in names
        assert "template_apply" in names

    def test_all_tools_autonomous(self, nova: Nova):
        for tool in nova.get_tools():
            assert tool["permission_level"] == "autonomous"

    @pytest.mark.asyncio
    async def test_unknown_tool(self, online_nova: Nova):
        r = await online_nova.execute("nonexistent", {})
        assert r.success is False
        assert "Unknown tool" in r.error


# ---------------------------------------------------------------
# format_document
# ---------------------------------------------------------------

class TestFormatDocument:
    @pytest.mark.asyncio
    async def test_basic_document(self, online_nova: Nova):
        r = await online_nova.execute("format_document", {
            "title": "Test Report",
            "sections": [
                {"heading": "Summary", "body": "Everything is good."},
                {"heading": "Details", "body": "Detailed info here."},
            ],
        })
        assert r.success is True
        assert "# Test Report" in r.content["markdown"]
        assert "## Summary" in r.content["markdown"]
        assert "## Details" in r.content["markdown"]
        assert r.content["section_count"] == 2

    @pytest.mark.asyncio
    async def test_table_of_contents_three_plus(self, online_nova: Nova):
        r = await online_nova.execute("format_document", {
            "title": "Big Doc",
            "sections": [
                {"heading": "One", "body": "A"},
                {"heading": "Two", "body": "B"},
                {"heading": "Three", "body": "C"},
            ],
        })
        assert r.success is True
        assert "## Table of Contents" in r.content["markdown"]
        assert "[One](#one)" in r.content["markdown"]

    @pytest.mark.asyncio
    async def test_no_toc_under_three(self, online_nova: Nova):
        r = await online_nova.execute("format_document", {
            "title": "Small Doc",
            "sections": [
                {"heading": "One", "body": "A"},
                {"heading": "Two", "body": "B"},
            ],
        })
        assert r.success is True
        assert "Table of Contents" not in r.content["markdown"]

    @pytest.mark.asyncio
    async def test_empty_sections(self, online_nova: Nova):
        r = await online_nova.execute("format_document", {
            "title": "Empty",
            "sections": [],
        })
        assert r.success is True
        assert r.content["section_count"] == 0

    @pytest.mark.asyncio
    async def test_no_title_fails(self, online_nova: Nova):
        r = await online_nova.execute("format_document", {"title": ""})
        assert r.success is False
        assert "title" in r.error

    @pytest.mark.asyncio
    async def test_metadata_included(self, online_nova: Nova):
        r = await online_nova.execute("format_document", {
            "title": "With Meta",
            "sections": [],
            "metadata": {"Author": "Shadow", "Version": "1.0"},
        })
        assert r.success is True
        assert "**Author**: Shadow" in r.content["markdown"]
        assert "**Version**: 1.0" in r.content["markdown"]


# ---------------------------------------------------------------
# format_report
# ---------------------------------------------------------------

class TestFormatReport:
    def _full_params(self, **overrides: Any) -> dict[str, Any]:
        base = {
            "title": "Q1 Report",
            "date": "2026-04-01",
            "executive_summary": "Revenue up 12%.",
            "findings": [
                {"finding": "Growth", "detail": "Steady increase", "source": "Internal"},
            ],
            "recommendations": ["Continue current strategy"],
            "conclusion": "Strong quarter.",
        }
        base.update(overrides)
        return base

    @pytest.mark.asyncio
    async def test_full_report(self, online_nova: Nova):
        r = await online_nova.execute("format_report", self._full_params())
        assert r.success is True
        md = r.content["markdown"]
        assert "# Q1 Report" in md
        assert "## Executive Summary" in md
        assert "## Findings" in md
        assert "### Growth" in md
        assert "## Recommendations" in md
        assert "1. Continue current strategy" in md
        assert "## Conclusion" in md
        assert r.content["finding_count"] == 1

    @pytest.mark.asyncio
    async def test_multiple_findings(self, online_nova: Nova):
        findings = [
            {"finding": "A", "detail": "D1", "source": "S1"},
            {"finding": "B", "detail": "D2", "source": "S2"},
            {"finding": "C", "detail": "D3", "source": "S3"},
        ]
        r = await online_nova.execute("format_report", self._full_params(findings=findings))
        assert r.success is True
        assert r.content["finding_count"] == 3
        assert "### A" in r.content["markdown"]
        assert "### C" in r.content["markdown"]

    @pytest.mark.asyncio
    async def test_missing_field_fails(self, online_nova: Nova):
        params = self._full_params()
        del params["executive_summary"]
        r = await online_nova.execute("format_report", params)
        assert r.success is False
        assert "executive_summary" in r.error

    @pytest.mark.asyncio
    async def test_empty_findings_list(self, online_nova: Nova):
        r = await online_nova.execute("format_report", self._full_params(findings=[]))
        assert r.success is True
        assert r.content["finding_count"] == 0


# ---------------------------------------------------------------
# format_email
# ---------------------------------------------------------------

class TestFormatEmail:
    @pytest.mark.asyncio
    async def test_professional_tone(self, online_nova: Nova):
        r = await online_nova.execute("format_email", {
            "to": "John", "subject": "Update", "body": "Here is the update.", "tone": "professional",
        })
        assert r.success is True
        assert "Dear John," in r.content["formatted"]
        assert "Best regards" in r.content["formatted"]
        assert r.content["tone"] == "professional"
        assert r.content["subject"] == "Update"

    @pytest.mark.asyncio
    async def test_casual_tone(self, online_nova: Nova):
        r = await online_nova.execute("format_email", {
            "to": "Jane", "subject": "Hey", "body": "Quick note.", "tone": "casual",
        })
        assert r.success is True
        assert "Hi Jane," in r.content["formatted"]
        assert "Cheers" in r.content["formatted"]

    @pytest.mark.asyncio
    async def test_formal_tone(self, online_nova: Nova):
        r = await online_nova.execute("format_email", {
            "to": "Board", "subject": "Notice", "body": "Formal communication.", "tone": "formal",
        })
        assert r.success is True
        assert "Dear Sir/Madam," in r.content["formatted"]
        assert "Yours faithfully" in r.content["formatted"]

    @pytest.mark.asyncio
    async def test_unknown_tone_fails(self, online_nova: Nova):
        r = await online_nova.execute("format_email", {
            "to": "X", "subject": "Y", "body": "Z", "tone": "angry",
        })
        assert r.success is False
        assert "tone" in r.error

    @pytest.mark.asyncio
    async def test_missing_field_fails(self, online_nova: Nova):
        r = await online_nova.execute("format_email", {
            "to": "X", "body": "Z", "tone": "casual",
        })
        assert r.success is False
        assert "subject" in r.error


# ---------------------------------------------------------------
# format_briefing_section
# ---------------------------------------------------------------

class TestFormatBriefingSection:
    @pytest.mark.asyncio
    async def test_basic_briefing(self, online_nova: Nova):
        r = await online_nova.execute("format_briefing_section", {
            "title": "Alert", "content": "Server load is high.", "priority": 1,
        })
        assert r.success is True
        assert "[P1]" in r.content["formatted"]
        assert "**Alert**" in r.content["formatted"]
        assert r.content["priority"] == 1

    @pytest.mark.asyncio
    async def test_filler_word_removal(self, online_nova: Nova):
        r = await online_nova.execute("format_briefing_section", {
            "title": "Test",
            "content": "This is just really very basically a simple test.",
            "priority": 3,
        })
        assert r.success is True
        formatted = r.content["formatted"]
        assert "just" not in formatted.lower().split()
        assert "really" not in formatted.lower().split()
        assert "very" not in formatted.lower().split()
        assert "basically" not in formatted.lower().split()
        assert r.content["compressed_length"] < r.content["original_length"]

    @pytest.mark.asyncio
    async def test_priority_zero_fails(self, online_nova: Nova):
        r = await online_nova.execute("format_briefing_section", {
            "title": "X", "content": "Y", "priority": 0,
        })
        assert r.success is False
        assert "1" in r.error and "5" in r.error

    @pytest.mark.asyncio
    async def test_priority_six_fails(self, online_nova: Nova):
        r = await online_nova.execute("format_briefing_section", {
            "title": "X", "content": "Y", "priority": 6,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_empty_content_fails(self, online_nova: Nova):
        r = await online_nova.execute("format_briefing_section", {
            "title": "X", "content": "", "priority": 1,
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_priority_boundaries(self, online_nova: Nova):
        r1 = await online_nova.execute("format_briefing_section", {
            "title": "Low", "content": "Data.", "priority": 1,
        })
        r5 = await online_nova.execute("format_briefing_section", {
            "title": "High", "content": "Data.", "priority": 5,
        })
        assert r1.success is True
        assert r5.success is True
        assert "[P1]" in r1.content["formatted"]
        assert "[P5]" in r5.content["formatted"]


# ---------------------------------------------------------------
# template_list
# ---------------------------------------------------------------

class TestTemplateList:
    @pytest.mark.asyncio
    async def test_returns_all_templates(self, online_nova: Nova):
        r = await online_nova.execute("template_list", {})
        assert r.success is True
        assert r.content["count"] == 6
        names = [t["name"] for t in r.content["templates"]]
        assert "document" in names
        assert "report" in names
        assert "email" in names
        assert "briefing_section" in names
        assert "business_estimate" in names
        assert "meeting_notes" in names

    @pytest.mark.asyncio
    async def test_template_structure(self, online_nova: Nova):
        r = await online_nova.execute("template_list", {})
        for t in r.content["templates"]:
            assert "name" in t
            assert "description" in t
            assert "required_fields" in t
            assert "example" in t


# ---------------------------------------------------------------
# template_apply
# ---------------------------------------------------------------

class TestTemplateApply:
    @pytest.mark.asyncio
    async def test_apply_document(self, online_nova: Nova):
        r = await online_nova.execute("template_apply", {
            "template_name": "document",
            "data": {
                "title": "Via Template",
                "sections": [{"heading": "Intro", "body": "Hello."}],
            },
        })
        assert r.success is True
        assert r.tool_name == "template_apply"
        assert "# Via Template" in r.content["markdown"]

    @pytest.mark.asyncio
    async def test_apply_email(self, online_nova: Nova):
        r = await online_nova.execute("template_apply", {
            "template_name": "email",
            "data": {
                "to": "Bob", "subject": "Hi", "body": "Test.", "tone": "casual",
            },
        })
        assert r.success is True
        assert r.tool_name == "template_apply"
        assert "Hi Bob," in r.content["formatted"]

    @pytest.mark.asyncio
    async def test_unknown_template_fails(self, online_nova: Nova):
        r = await online_nova.execute("template_apply", {
            "template_name": "nonexistent",
            "data": {},
        })
        assert r.success is False
        assert "Unknown template" in r.error
        assert "Available" in r.error

    @pytest.mark.asyncio
    async def test_missing_required_field(self, online_nova: Nova):
        r = await online_nova.execute("template_apply", {
            "template_name": "report",
            "data": {"title": "Incomplete"},
        })
        assert r.success is False
        assert "Missing required field" in r.error

    @pytest.mark.asyncio
    async def test_empty_template_name_fails(self, online_nova: Nova):
        r = await online_nova.execute("template_apply", {
            "template_name": "",
            "data": {},
        })
        assert r.success is False
        assert "template_name" in r.error

    @pytest.mark.asyncio
    async def test_apply_business_estimate(self, online_nova: Nova):
        r = await online_nova.execute("template_apply", {
            "template_name": "business_estimate",
            "data": {
                "project_name": "Spring Cleanup",
                "line_items": [
                    {"item": "Mulch", "cost": 800},
                    {"item": "Labor", "cost": 360},
                ],
                "timeline": "1 day",
            },
        })
        assert r.success is True
        assert r.tool_name == "template_apply"
        md = r.content["markdown"]
        assert "# Business Estimate: Spring Cleanup" in md
        assert "| Mulch | $800.00 |" in md
        assert "$1,160.00" in md
        assert r.content["total_cost"] == 1160.0

    @pytest.mark.asyncio
    async def test_business_estimate_optional_fields(self, online_nova: Nova):
        r = await online_nova.execute("template_apply", {
            "template_name": "business_estimate",
            "data": {
                "project_name": "Job",
                "line_items": [{"item": "X", "cost": 100}],
                "timeline": "2 days",
                "assumptions": ["Good weather"],
                "risks": ["Rain delay"],
                "notes": "Bring extra crew.",
            },
        })
        assert r.success is True
        md = r.content["markdown"]
        assert "## Assumptions" in md
        assert "Good weather" in md
        assert "## Risks" in md
        assert "Rain delay" in md
        assert "## Notes" in md
        assert "Bring extra crew." in md

    @pytest.mark.asyncio
    async def test_business_estimate_no_optional(self, online_nova: Nova):
        r = await online_nova.execute("template_apply", {
            "template_name": "business_estimate",
            "data": {
                "project_name": "Simple",
                "line_items": [{"item": "Work", "cost": 500}],
                "timeline": "3 hours",
            },
        })
        assert r.success is True
        md = r.content["markdown"]
        assert "Assumptions" not in md
        assert "Risks" not in md
        assert "Notes" not in md

    @pytest.mark.asyncio
    async def test_apply_meeting_notes(self, online_nova: Nova):
        r = await online_nova.execute("template_apply", {
            "template_name": "meeting_notes",
            "data": {
                "title": "Sprint Planning",
                "date": "2026-04-05",
                "attendees": ["Alice", "Bob"],
                "discussion": "Reviewed priorities.",
            },
        })
        assert r.success is True
        assert r.tool_name == "template_apply"
        md = r.content["markdown"]
        assert "# Meeting Notes: Sprint Planning" in md
        assert "- Alice" in md
        assert "- Bob" in md
        assert r.content["attendee_count"] == 2

    @pytest.mark.asyncio
    async def test_meeting_notes_with_action_items(self, online_nova: Nova):
        r = await online_nova.execute("template_apply", {
            "template_name": "meeting_notes",
            "data": {
                "title": "Standup",
                "date": "2026-04-05",
                "attendees": ["Alice"],
                "discussion": "Quick sync.",
                "decisions": ["Ship by Friday"],
                "action_items": [
                    {"owner": "Alice", "task": "Update board", "due": "2026-04-07"},
                ],
            },
        })
        assert r.success is True
        md = r.content["markdown"]
        assert "## Decisions" in md
        assert "Ship by Friday" in md
        assert "## Action Items" in md
        assert "| Alice | Update board | 2026-04-07 |" in md


# ---------------------------------------------------------------
# Raw content generation (orchestrator sends {"content": ...})
# ---------------------------------------------------------------

class TestRawContentGeneration:
    """Tests for the Ollama-backed raw content generation path."""

    def test_is_raw_content_request_true(self):
        nova = Nova({})
        assert nova._is_raw_content_request({"content": "write an article"}) is True

    def test_is_raw_content_request_false_with_title(self):
        nova = Nova({})
        assert nova._is_raw_content_request({"title": "X", "content": "Y"}) is False

    def test_is_raw_content_request_false_with_sections(self):
        nova = Nova({})
        assert nova._is_raw_content_request({"sections": [], "content": "Y"}) is False

    def test_is_raw_content_request_false_no_content(self):
        nova = Nova({})
        assert nova._is_raw_content_request({"title": "X"}) is False

    @pytest.mark.asyncio
    async def test_format_document_raw_content(self, online_nova: Nova):
        """format_document with raw content calls Ollama and formats the result."""
        ollama_response = {
            "title": "Guide to Gardening",
            "sections": [
                {"heading": "Introduction", "body": "Gardening is rewarding."},
                {"heading": "Tools", "body": "You need a shovel and rake."},
            ],
        }
        with patch.object(
            online_nova, "_generate_via_ollama", return_value=ollama_response,
        ) as mock_ollama:
            r = await online_nova.execute(
                "format_document", {"content": "write a guide to gardening"},
            )

        assert r.success is True
        assert "# Guide to Gardening" in r.content["markdown"]
        assert "## Introduction" in r.content["markdown"]
        assert r.content["section_count"] == 2
        mock_ollama.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_email_raw_content(self, online_nova: Nova):
        """format_email with raw content calls Ollama and formats the result."""
        ollama_response = {
            "to": "John",
            "subject": "Project Update",
            "body": "The project is on track.",
            "tone": "professional",
        }
        with patch.object(
            online_nova, "_generate_via_ollama", return_value=ollama_response,
        ) as mock_ollama:
            r = await online_nova.execute(
                "format_email", {"content": "write a project update email to John"},
            )

        assert r.success is True
        assert "Dear John," in r.content["formatted"]
        assert "Best regards" in r.content["formatted"]
        assert r.content["tone"] == "professional"
        mock_ollama.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_report_raw_content(self, online_nova: Nova):
        """format_report with raw content calls Ollama and formats the result."""
        ollama_response = {
            "title": "Q1 Analysis",
            "date": "2026-04-01",
            "executive_summary": "Revenue increased by 12%.",
            "findings": [
                {"finding": "Growth", "detail": "Steady increase", "source": "Internal"},
            ],
            "recommendations": ["Continue current strategy"],
            "conclusion": "Strong quarter overall.",
        }
        with patch.object(
            online_nova, "_generate_via_ollama", return_value=ollama_response,
        ) as mock_ollama:
            r = await online_nova.execute(
                "format_report", {"content": "write a Q1 analysis report"},
            )

        assert r.success is True
        md = r.content["markdown"]
        assert "# Q1 Analysis" in md
        assert "## Executive Summary" in md
        assert r.content["finding_count"] == 1
        mock_ollama.assert_called_once()

    @pytest.mark.asyncio
    async def test_ollama_failure_returns_error(self, online_nova: Nova):
        """Ollama exception produces success=False with error message."""
        with patch.object(
            online_nova, "_generate_via_ollama",
            side_effect=ConnectionError("Ollama unreachable"),
        ):
            r = await online_nova.execute(
                "format_document", {"content": "write something"},
            )

        assert r.success is False
        assert "Content generation failed" in r.error
        assert "Ollama unreachable" in r.error

    @pytest.mark.asyncio
    async def test_ollama_invalid_json_returns_error(self, online_nova: Nova):
        """Non-JSON Ollama response produces success=False."""
        with patch.object(
            online_nova, "_generate_via_ollama",
            side_effect=ValueError("Expecting value: line 1"),
        ):
            r = await online_nova.execute(
                "format_document", {"content": "write something"},
            )

        assert r.success is False
        assert "Content generation failed" in r.error

    # --- Bug 4: robust JSON extraction from LLM responses ---------------

    @staticmethod
    def _mock_ollama_http(online_nova: Nova, llm_content: str) -> MagicMock:
        """Patch online_nova's ollama_client.post to return a single LLM
        response with the given raw content. Returns the mock so tests
        can assert on it if needed."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "message": {"content": llm_content},
        }
        mock_post = MagicMock(return_value=mock_resp)
        online_nova._ollama_client.post = mock_post
        return mock_post

    @pytest.mark.asyncio
    async def test_format_document_parses_raw_json(self, online_nova: Nova):
        """Bug 4: LLM returns pure JSON (no fence, no prose) — must succeed."""
        raw_json = json.dumps({
            "title": "Photosynthesis",
            "sections": [
                {"heading": "What is it", "body": "Plants make food from sunlight."},
            ],
        })
        self._mock_ollama_http(online_nova, raw_json)

        r = await online_nova.execute(
            "format_document", {"content": "Explain photosynthesis to a 10-year-old"},
        )

        assert r.success is True, f"Raw JSON should parse; error: {r.error}"
        assert "Photosynthesis" in r.content["markdown"]

    @pytest.mark.asyncio
    async def test_format_document_parses_markdown_wrapped_json(
        self, online_nova: Nova,
    ):
        """Bug 4: LLM wraps JSON in ```json ... ``` — must succeed.
        This is the exact failure mode from the Phase 0 benchmark at
        interaction #71 (Explain photosynthesis to a 10-year-old)."""
        inner = json.dumps({
            "title": "Photosynthesis for Kids",
            "sections": [
                {"heading": "The Basics", "body": "Plants eat sunshine."},
            ],
        })
        wrapped = f"```json\n{inner}\n```"
        self._mock_ollama_http(online_nova, wrapped)

        r = await online_nova.execute(
            "format_document", {"content": "Explain photosynthesis to a 10-year-old"},
        )

        assert r.success is True, (
            f"Markdown-wrapped JSON should parse; error: {r.error}"
        )
        assert "Photosynthesis for Kids" in r.content["markdown"]

    @pytest.mark.asyncio
    async def test_format_document_parses_prose_plus_json(self, online_nova: Nova):
        """Bug 4: LLM prepends prose then emits JSON — must succeed by
        extracting the outermost {...} span."""
        inner = json.dumps({
            "title": "Gardening Guide",
            "sections": [
                {"heading": "Soil", "body": "Good soil matters."},
            ],
        })
        prose_prefixed = f"Here is the document you requested:\n\n{inner}"
        self._mock_ollama_http(online_nova, prose_prefixed)

        r = await online_nova.execute(
            "format_document", {"content": "write a gardening guide"},
        )

        assert r.success is True, f"Prose+JSON should parse; error: {r.error}"
        assert "Gardening Guide" in r.content["markdown"]

    @pytest.mark.asyncio
    async def test_format_document_logs_raw_response_on_unparseable(
        self, online_nova: Nova, caplog,
    ):
        """Bug 4: when extraction genuinely fails, the raw LLM response
        must be logged (truncated) so future failures are diagnosable."""
        import logging as _stdlib_logging

        self._mock_ollama_http(
            online_nova,
            "I can't help with that request.",  # no JSON at all
        )
        caplog.set_level(_stdlib_logging.ERROR, logger="shadow.nova")

        r = await online_nova.execute(
            "format_document", {"content": "write something"},
        )

        assert r.success is False
        # The raw response preview must appear in the error log.
        assert any(
            "I can't help with that request" in record.message
            for record in caplog.records
        ), (
            f"Raw LLM response should be logged on parse failure; "
            f"records: {[r.message for r in caplog.records]}"
        )

    @pytest.mark.asyncio
    async def test_structured_params_bypass_ollama(self, online_nova: Nova):
        """Structured params still work without calling Ollama (regression check)."""
        with patch.object(
            online_nova, "_generate_via_ollama",
            side_effect=AssertionError("Should not be called"),
        ):
            r = await online_nova.execute("format_document", {
                "title": "Direct Doc",
                "sections": [{"heading": "Intro", "body": "Hello."}],
            })

        assert r.success is True
        assert "# Direct Doc" in r.content["markdown"]
