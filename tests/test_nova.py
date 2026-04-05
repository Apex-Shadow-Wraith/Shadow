"""
Tests for Nova — Content Creation
====================================
"""

import pytest
from pathlib import Path
from typing import Any

from modules.base import ModuleStatus, ToolResult
from modules.nova.nova import Nova


@pytest.fixture
def nova(tmp_path: Path) -> Nova:
    config = {"output_dir": str(tmp_path / "nova_output")}
    return Nova(config)


@pytest.fixture
async def online_nova(nova: Nova) -> Nova:
    await nova.initialize()
    return nova


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
        assert len(tools) == 5
        names = [t["name"] for t in tools]
        assert "document_create" in names
        assert "image_generate" in names
        assert "voice_generate" in names


class TestDocumentCreate:
    @pytest.mark.asyncio
    async def test_basic_document(self, online_nova: Nova):
        r = await online_nova.execute("document_create", {
            "title": "Test Report",
            "sections": [
                {"heading": "Summary", "content": "Everything is good."},
                {"heading": "Details", "content": "Detailed info here."},
            ],
        })
        assert r.success is True
        assert "# Test Report" in r.content["markdown"]
        assert r.content["sections_count"] == 2

    @pytest.mark.asyncio
    async def test_save_to_file(self, online_nova: Nova, tmp_path: Path):
        r = await online_nova.execute("document_create", {
            "title": "Saved Doc",
            "sections": [{"heading": "A", "content": "B"}],
            "save": True,
        })
        assert r.success is True
        assert "saved_to" in r.content
        saved = Path(r.content["saved_to"])
        assert saved.exists()

    @pytest.mark.asyncio
    async def test_no_title_fails(self, online_nova: Nova):
        r = await online_nova.execute("document_create", {"title": ""})
        assert r.success is False


class TestContentFormat:
    @pytest.mark.asyncio
    async def test_email_format(self, online_nova: Nova):
        r = await online_nova.execute("content_format", {
            "content": "Please review the attached.", "format_type": "email",
        })
        assert r.success is True
        assert "Subject:" in r.content["formatted"]

    @pytest.mark.asyncio
    async def test_summary_truncation(self, online_nova: Nova):
        long_text = "A" * 1000
        r = await online_nova.execute("content_format", {
            "content": long_text, "format_type": "summary",
        })
        assert len(r.content["formatted"]) < len(long_text)

    @pytest.mark.asyncio
    async def test_list_format(self, online_nova: Nova):
        r = await online_nova.execute("content_format", {
            "content": "item1\nitem2\nitem3", "format_type": "list",
        })
        assert r.content["formatted"].startswith("- ")

    @pytest.mark.asyncio
    async def test_invalid_type_fails(self, online_nova: Nova):
        r = await online_nova.execute("content_format", {
            "content": "test", "format_type": "invalid",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_empty_content_fails(self, online_nova: Nova):
        r = await online_nova.execute("content_format", {
            "content": "", "format_type": "summary",
        })
        assert r.success is False


class TestReportTemplate:
    @pytest.mark.asyncio
    async def test_morning_briefing(self, online_nova: Nova):
        r = await online_nova.execute("report_template", {
            "template_name": "morning_briefing",
            "data": {"critical_alerts": "No alerts."},
        })
        assert r.success is True
        assert len(r.content["sections"]) == 10

    @pytest.mark.asyncio
    async def test_status_report(self, online_nova: Nova):
        r = await online_nova.execute("report_template", {
            "template_name": "status_report",
            "data": {},
        })
        assert r.success is True

    @pytest.mark.asyncio
    async def test_unknown_template_fails(self, online_nova: Nova):
        r = await online_nova.execute("report_template", {
            "template_name": "nonexistent",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_empty_name_fails(self, online_nova: Nova):
        r = await online_nova.execute("report_template", {"template_name": ""})
        assert r.success is False


class TestImageGenerate:
    @pytest.mark.asyncio
    async def test_stub_response(self, online_nova: Nova):
        r = await online_nova.execute("image_generate", {
            "prompt": "A mountain landscape",
        })
        assert r.success is True
        assert r.content["status"] == "stub"
        assert "SDXL" in r.content["message"]

    @pytest.mark.asyncio
    async def test_empty_prompt_fails(self, online_nova: Nova):
        r = await online_nova.execute("image_generate", {"prompt": ""})
        assert r.success is False


class TestVoiceGenerate:
    @pytest.mark.asyncio
    async def test_stub_response(self, online_nova: Nova):
        r = await online_nova.execute("voice_generate", {
            "text": "Good morning, Master.",
        })
        assert r.success is True
        assert r.content["status"] == "stub"

    @pytest.mark.asyncio
    async def test_empty_text_fails(self, online_nova: Nova):
        r = await online_nova.execute("voice_generate", {"text": ""})
        assert r.success is False


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool(self, online_nova: Nova):
        r = await online_nova.execute("nonexistent", {})
        assert r.success is False
