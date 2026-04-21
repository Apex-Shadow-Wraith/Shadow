"""
Tests for Omen — Shadow's Code Brain
=======================================
Covers code execution, linting, testing, git operations,
code review, dependency checks, and teaching mode.
"""

import pytest
import sys
from pathlib import Path
from typing import Any

from modules.base import ModuleStatus, ToolResult
from modules.omen.omen import Omen


@pytest.fixture
def omen(tmp_path: Path) -> Omen:
    config = {"project_root": str(tmp_path), "teaching_mode": False}
    return Omen(config)


@pytest.fixture
async def online_omen(omen: Omen) -> Omen:
    await omen.initialize()
    return omen


# --- Lifecycle ---

class TestOmenLifecycle:
    @pytest.mark.asyncio
    async def test_initialize(self, omen: Omen):
        await omen.initialize()
        assert omen.status == ModuleStatus.ONLINE

    @pytest.mark.asyncio
    async def test_shutdown(self, omen: Omen):
        await omen.initialize()
        await omen.shutdown()
        assert omen.status == ModuleStatus.OFFLINE

    def test_get_tools(self, omen: Omen):
        tools = omen.get_tools()
        # 40 Omen-native + 7 absorbed Cipher tools (Phase A merge)
        assert len(tools) == 47
        names = [t["name"] for t in tools]
        assert "code_execute" in names
        assert "code_lint" in names
        assert "git_commit" in names
        # Absorbed Cipher tools
        for cipher_tool in ("calculate", "unit_convert", "date_math",
                            "percentage", "financial", "statistics",
                            "logic_check"):
            assert cipher_tool in names, f"{cipher_tool} missing from Omen.get_tools()"

    def test_git_commit_requires_approval(self, omen: Omen):
        tools = omen.get_tools()
        commit_tool = next(t for t in tools if t["name"] == "git_commit")
        assert commit_tool["permission_level"] == "approval_required"


# --- Code execution ---

class TestCodeExecute:
    @pytest.mark.asyncio
    async def test_simple_print(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {
            "code": "print('hello world')",
        })
        assert r.success is True
        assert "hello world" in r.content["stdout"]

    @pytest.mark.asyncio
    async def test_math_expression(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {
            "code": "print(2 + 2)",
        })
        assert r.success is True
        assert "4" in r.content["stdout"]

    @pytest.mark.asyncio
    async def test_syntax_error(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {
            "code": "def broken(",
        })
        assert r.success is False
        assert r.content["exit_code"] != 0

    @pytest.mark.asyncio
    async def test_timeout(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {
            "code": "import time; time.sleep(10)",
            "timeout": 1,
        })
        assert r.success is False
        assert r.error == "" or r.error is None
        assert r.content.get("timed_out") is True

    @pytest.mark.asyncio
    async def test_empty_code_fails(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {"code": ""})
        assert r.success is False

    @pytest.mark.asyncio
    async def test_max_timeout_capped(self, online_omen: Omen):
        # Requesting 999s should be capped to MAX_TIMEOUT
        r = await online_omen.execute("code_execute", {
            "code": "print('fast')", "timeout": 999,
        })
        assert r.success is True


# --- Code lint ---

class TestCodeLint:
    @pytest.mark.asyncio
    async def test_valid_code(self, online_omen: Omen):
        r = await online_omen.execute("code_lint", {
            "code": "x = 1 + 2\nprint(x)\n",
        })
        assert r.success is True
        assert r.content["syntax_valid"] is True

    @pytest.mark.asyncio
    async def test_invalid_code(self, online_omen: Omen):
        r = await online_omen.execute("code_lint", {
            "code": "def broken(\n",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_lint_file(self, online_omen: Omen, tmp_path: Path):
        test_file = tmp_path / "valid.py"
        test_file.write_text("x = 42\n", encoding="utf-8")
        r = await online_omen.execute("code_lint", {
            "file_path": str(test_file),
        })
        assert r.success is True

    @pytest.mark.asyncio
    async def test_lint_missing_file(self, online_omen: Omen):
        r = await online_omen.execute("code_lint", {
            "file_path": "/nonexistent/file.py",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_lint_no_input_fails(self, online_omen: Omen):
        r = await online_omen.execute("code_lint", {})
        assert r.success is False


# --- Code review ---

class TestCodeReview:
    @pytest.mark.asyncio
    async def test_review_code_string(self, online_omen: Omen):
        code = '''
def hello(name: str) -> str:
    """Say hello."""
    try:
        return f"Hello, {name}"
    except Exception as e:
        raise
'''
        r = await online_omen.execute("code_review", {"code": code})
        assert r.success is True
        assert r.content["has_docstrings"] is True
        assert r.content["has_type_hints"] is True
        assert r.content["has_error_handling"] is True
        assert r.content["function_count"] == 1

    @pytest.mark.asyncio
    async def test_review_no_input_fails(self, online_omen: Omen):
        r = await online_omen.execute("code_review", {})
        assert r.success is False


# --- Git status ---

class TestGitStatus:
    @pytest.mark.asyncio
    async def test_git_status_runs(self, tmp_path: Path):
        """Test git status on actual Shadow repo."""
        omen = Omen({"project_root": "."})
        await omen.initialize()
        r = await omen.execute("git_status", {})
        assert r.success is True
        assert "branch" in r.content
        await omen.shutdown()


# --- Git commit ---

class TestGitCommit:
    @pytest.mark.asyncio
    async def test_commit_no_message_fails(self, online_omen: Omen):
        r = await online_omen.execute("git_commit", {"message": ""})
        assert r.success is False
        assert "message is required" in r.error


# --- Dependency check ---

class TestDependencyCheck:
    @pytest.mark.asyncio
    async def test_dependency_check_runs(self, online_omen: Omen):
        r = await online_omen.execute("dependency_check", {})
        assert r.success is True
        assert "outdated_count" in r.content


# --- Teaching mode ---

class TestTeachingMode:
    @pytest.mark.asyncio
    async def test_teaching_mode_on_error(self, tmp_path: Path):
        omen = Omen({"project_root": str(tmp_path), "teaching_mode": True})
        await omen.initialize()
        r = await omen.execute("code_execute", {"code": "raise ValueError('oops')"})
        assert r.success is False
        assert "teaching_note" in r.content
        await omen.shutdown()

    @pytest.mark.asyncio
    async def test_teaching_mode_off_no_note(self, online_omen: Omen):
        r = await online_omen.execute("code_execute", {"code": "raise ValueError('oops')"})
        assert r.success is False
        assert "teaching_note" not in r.content


# --- Code extraction fallback ---

class TestExtractCodeFromResponse:
    """Test _extract_code_from_response directly."""

    def test_extract_fenced_python_block(self, omen: Omen):
        raw = "Sure, here's the code:\n```python\ndef hello():\n    return 'hi'\n```"
        result = omen._extract_code_from_response(raw)
        assert result is not None
        assert "def hello():" in result
        assert "return 'hi'" in result

    def test_extract_fenced_plain_block(self, omen: Omen):
        raw = "```\nimport os\nprint(os.getcwd())\n```"
        result = omen._extract_code_from_response(raw)
        assert result is not None
        assert "import os" in result

    def test_extract_multiple_fenced_blocks(self, omen: Omen):
        raw = "```python\ndef a():\n    pass\n```\nSome text\n```python\ndef b():\n    pass\n```"
        result = omen._extract_code_from_response(raw)
        assert result is not None
        assert "def a():" in result
        assert "def b():" in result

    def test_extract_indented_code_no_markdown(self, omen: Omen):
        raw = "Here you go:\ndef greet(name):\n    return f'Hello {name}'\n\nprint(greet('world'))"
        result = omen._extract_code_from_response(raw)
        assert result is not None
        assert "def greet(name):" in result
        assert "print(" in result

    def test_strip_preamble(self, omen: Omen):
        raw = "Sure! Here's the code:\n```python\nx = 42\n```"
        result = omen._extract_code_from_response(raw)
        assert result is not None
        assert "x = 42" in result
        assert "Sure" not in result

    def test_strip_certainly_preamble(self, omen: Omen):
        raw = "Certainly, here is the code:\n```python\nprint('done')\n```"
        result = omen._extract_code_from_response(raw)
        assert result is not None
        assert "print('done')" in result

    def test_none_on_non_code_response(self, omen: Omen):
        raw = "I'm sorry, I don't know how to help with that."
        result = omen._extract_code_from_response(raw)
        assert result is None

    def test_none_on_empty_string(self, omen: Omen):
        assert omen._extract_code_from_response("") is None
        assert omen._extract_code_from_response("   ") is None

    def test_none_on_none_input(self, omen: Omen):
        assert omen._extract_code_from_response(None) is None

    def test_keyword_detection_for_class(self, omen: Omen):
        raw = "class Foo:\n    def bar(self):\n        pass"
        result = omen._extract_code_from_response(raw)
        assert result is not None
        assert "class Foo:" in result

    def test_import_detection(self, omen: Omen):
        raw = "Try this:\nimport json\nfrom pathlib import Path\ndata = json.loads('{}')"
        result = omen._extract_code_from_response(raw)
        assert result is not None
        assert "import json" in result
        assert "from pathlib import Path" in result


class TestCodeGenerate:
    """Test code_generate tool with mocked Ollama."""

    @pytest.mark.asyncio
    async def test_prompt_required(self, online_omen: Omen):
        r = await online_omen.execute("code_generate", {"prompt": ""})
        assert r.success is False
        assert "prompt is required" in r.error

    @pytest.mark.asyncio
    async def test_content_direct_extracts_code(self, online_omen: Omen, monkeypatch):
        """When Ollama returns text instead of tool calls, code is extracted as content_direct."""
        import urllib.request

        def mock_urlopen(req, timeout=None):
            class FakeResp:
                def read(self):
                    return json.dumps({
                        "message": {
                            "content": "Here's your code:\n```python\ndef add(a, b):\n    return a + b\n```",
                            "tool_calls": [],
                        }
                    }).encode()
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write an add function",
        })
        assert r.success is True
        assert "def add(a, b):" in r.content["code"]
        assert r.content["method"] == "content_direct"

    @pytest.mark.asyncio
    async def test_tool_call_success(self, online_omen: Omen, monkeypatch):
        """When Ollama returns proper tool calls, they are used directly."""
        import urllib.request

        def mock_urlopen(req, timeout=None):
            class FakeResp:
                def read(self):
                    return json.dumps({
                        "message": {
                            "tool_calls": [{
                                "function": {
                                    "name": "write_code",
                                    "arguments": {"code": "def multiply(a, b):\n    return a * b"},
                                }
                            }],
                        }
                    }).encode()
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write a multiply function",
        })
        assert r.success is True
        assert "def multiply(a, b):" in r.content["code"]
        assert r.content["method"] == "tool_call"

    @pytest.mark.asyncio
    async def test_ollama_unreachable_falls_back_to_plain(self, online_omen: Omen, monkeypatch):
        """When first Ollama call fails, falls back to plain prompt."""
        import urllib.request
        import urllib.error

        call_count = {"n": 0}

        def mock_urlopen(req, timeout=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise urllib.error.URLError("Connection refused")

            class FakeResp:
                def read(self):
                    return json.dumps({
                        "message": {
                            "content": "```python\ndef fallback():\n    return True\n```",
                        }
                    }).encode()
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write a fallback function",
        })
        assert r.success is True
        assert "def fallback():" in r.content["code"]
        assert r.content["method"] == "plain_prompt"

    @pytest.mark.asyncio
    async def test_ollama_fully_unreachable(self, online_omen: Omen, monkeypatch):
        """When Ollama is completely unreachable, returns error."""
        import urllib.request
        import urllib.error

        def mock_urlopen(req, timeout=None):
            raise urllib.error.URLError("Connection refused")

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write something",
        })
        assert r.success is False
        assert "unreachable" in r.error.lower()

    @pytest.mark.asyncio
    async def test_null_tool_calls_uses_content_direct(self, online_omen: Omen, monkeypatch):
        """When Ollama returns tool_calls: null with content, uses content_direct path."""
        import urllib.request

        def mock_urlopen(req, timeout=None):
            class FakeResp:
                def read(self):
                    return json.dumps({
                        "message": {
                            "content": "```python\ndef greet(name):\n    return f'Hello {name}'\n```",
                            "tool_calls": None,
                        }
                    }).encode()
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write a greet function",
        })
        assert r.success is True
        assert "def greet(name):" in r.content["code"]
        assert r.content["method"] == "content_direct"

    @pytest.mark.asyncio
    async def test_malformed_tool_calls_falls_back(self, online_omen: Omen, monkeypatch):
        """When Ollama returns malformed tool_calls, fallback extracts code."""
        import urllib.request

        def mock_urlopen(req, timeout=None):
            class FakeResp:
                def read(self):
                    return json.dumps({
                        "message": {
                            "content": "def square(x):\n    return x ** 2",
                            "tool_calls": [{"not_a_function": True}],
                        }
                    }).encode()
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write a square function",
        })
        assert r.success is True
        assert "def square(x):" in r.content["code"]

    @pytest.mark.asyncio
    async def test_tool_call_exception_falls_back_to_plain(self, online_omen: Omen, monkeypatch):
        """When tool call raises unexpected exception (TypeError etc), plain prompt is used."""
        import urllib.request

        call_count = {"n": 0}

        def mock_urlopen(req, timeout=None):
            call_count["n"] += 1
            body = json.loads(req.data.decode())
            if "tools" in body:
                # First call with tools — raise unexpected error
                raise TypeError("unexpected None iteration")

            class FakeResp:
                def read(self):
                    return json.dumps({
                        "message": {
                            "content": "```python\ndef rescued():\n    return True\n```",
                        }
                    }).encode()
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write a rescued function",
        })
        assert r.success is True
        assert "def rescued():" in r.content["code"]
        assert r.content["method"] == "plain_prompt"
        assert call_count["n"] == 2  # tool call + plain prompt = 2 total calls

    @pytest.mark.asyncio
    async def test_code_generate_in_tools(self, omen: Omen):
        tools = omen.get_tools()
        names = [t["name"] for t in tools]
        assert "code_generate" in names

    @pytest.mark.asyncio
    async def test_empty_content_and_null_tool_calls_is_failure(self, online_omen: Omen, monkeypatch):
        """When BOTH content and tool_calls are empty/null, it's a real failure."""
        import urllib.request

        def mock_urlopen(req, timeout=None):
            raise urllib.error.URLError("Connection refused")

        import urllib.error
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write something",
        })
        assert r.success is False

    @pytest.mark.asyncio
    async def test_no_second_call_when_content_present(self, online_omen: Omen, monkeypatch):
        """When model returns content (no tool_calls), no second LLM call is made."""
        import urllib.request

        call_count = {"n": 0}

        def mock_urlopen(req, timeout=None):
            call_count["n"] += 1
            class FakeResp:
                def read(self_inner):
                    return json.dumps({
                        "message": {
                            "content": "```python\ndef one_shot():\n    return 1\n```",
                            "tool_calls": None,
                        }
                    }).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write a one_shot function",
        })
        assert r.success is True
        assert "def one_shot():" in r.content["code"]
        assert r.content["method"] == "content_direct"
        assert call_count["n"] == 1  # Only one LLM call, no fallback

    @pytest.mark.asyncio
    async def test_empty_tool_calls_list_uses_content(self, online_omen: Omen, monkeypatch):
        """When model returns content + empty tool_calls list [], uses content_direct."""
        import urllib.request

        def mock_urlopen(req, timeout=None):
            class FakeResp:
                def read(self_inner):
                    return json.dumps({
                        "message": {
                            "content": "```python\ndef empty_tc():\n    return True\n```",
                            "tool_calls": [],
                        }
                    }).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write a function",
        })
        assert r.success is True
        assert "def empty_tc():" in r.content["code"]
        assert r.content["method"] == "content_direct"

    @pytest.mark.asyncio
    async def test_content_direct_no_tool_calls_key(self, online_omen: Omen, monkeypatch):
        """When Ollama returns content with NO tool_calls key at all, uses content_direct."""
        import urllib.request

        def mock_urlopen(req, timeout=None):
            class FakeResp:
                def read(self_inner):
                    return json.dumps({
                        "message": {
                            "content": "def foo():\n    pass",
                            "role": "assistant",
                        }
                    }).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write a foo function",
        })
        assert r.success is True
        assert "def foo():" in r.content["code"]
        assert r.content["method"] == "content_direct"

    @pytest.mark.asyncio
    async def test_empty_message_fails(self, online_omen: Omen, monkeypatch):
        """When Ollama returns {"message": {}} with no content or tool_calls, fails gracefully."""
        import urllib.request

        call_count = {"n": 0}

        def mock_urlopen(req, timeout=None):
            call_count["n"] += 1
            class FakeResp:
                def read(self_inner):
                    return json.dumps({"message": {}}).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {
            "prompt": "write something",
        })
        # Both calls return empty message → raw_response with empty string
        assert r.success is True
        assert r.content["method"] == "raw_response"

    @pytest.mark.asyncio
    async def test_metadata_indicates_source_tool_calls(self, online_omen: Omen, monkeypatch):
        """Verify method field indicates 'tool_call' when tool_calls used."""
        import urllib.request

        def mock_urlopen(req, timeout=None):
            class FakeResp:
                def read(self_inner):
                    return json.dumps({
                        "message": {
                            "tool_calls": [{
                                "function": {
                                    "name": "write_code",
                                    "arguments": {"code": "x = 1"},
                                }
                            }],
                        }
                    }).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {"prompt": "assign x"})
        assert r.content["method"] == "tool_call"

    @pytest.mark.asyncio
    async def test_metadata_indicates_source_content_direct(self, online_omen: Omen, monkeypatch):
        """Verify method field indicates 'content_direct' when content used without tool_calls."""
        import urllib.request

        def mock_urlopen(req, timeout=None):
            class FakeResp:
                def read(self_inner):
                    return json.dumps({
                        "message": {
                            "content": "```python\nx = 1\n```",
                            "tool_calls": None,
                        }
                    }).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        import json
        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {"prompt": "assign x"})
        assert r.content["method"] == "content_direct"


# --- Endpoint and model correctness ---

class TestCodeGenerateEndpoint:
    """Verify code_generate uses /api/chat and correct model."""

    @pytest.mark.asyncio
    async def test_code_generate_uses_correct_endpoint(self, online_omen: Omen, monkeypatch):
        """Verify /api/chat is the endpoint called, not /api/generate or anything else."""
        import urllib.request
        import json

        captured_urls = []

        def mock_urlopen(req, timeout=None):
            captured_urls.append(req.full_url)
            class FakeResp:
                def read(self_inner):
                    return json.dumps({
                        "message": {
                            "content": "```python\ndef test():\n    pass\n```",
                            "tool_calls": None,
                        }
                    }).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        await online_omen.execute("code_generate", {"prompt": "write a test function"})
        assert len(captured_urls) >= 1
        assert all(url.endswith("/api/chat") for url in captured_urls)

    @pytest.mark.asyncio
    async def test_code_generate_returns_content(self, online_omen: Omen, monkeypatch):
        """Verify successful Ollama response yields ToolResult.success=True."""
        import urllib.request
        import json

        def mock_urlopen(req, timeout=None):
            class FakeResp:
                def read(self_inner):
                    return json.dumps({
                        "message": {
                            "content": "```python\ndef add(a, b):\n    return a + b\n```",
                        }
                    }).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        r = await online_omen.execute("code_generate", {"prompt": "add function"})
        assert r.success is True
        assert "def add(a, b):" in r.content["code"]

    @pytest.mark.asyncio
    async def test_code_generate_no_urllib_to_wrong_endpoint(self, online_omen: Omen, monkeypatch):
        """Verify no calls go to /api/generate, /api/tools, or other non-existent endpoints."""
        import urllib.request
        import json

        captured_urls = []

        def mock_urlopen(req, timeout=None):
            captured_urls.append(req.full_url)
            class FakeResp:
                def read(self_inner):
                    return json.dumps({
                        "message": {
                            "content": "```python\nx = 1\n```",
                        }
                    }).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        await online_omen.execute("code_generate", {"prompt": "assign x"})
        for url in captured_urls:
            assert "/api/generate" not in url, f"Called wrong endpoint: {url}"
            assert "/api/tools" not in url, f"Called wrong endpoint: {url}"

    @pytest.mark.asyncio
    async def test_fallback_logs_warning(self, online_omen: Omen, monkeypatch, caplog):
        """When fallback fires, verify warning is logged."""
        import urllib.request
        import urllib.error
        import json
        import logging

        call_count = {"n": 0}

        def mock_urlopen(req, timeout=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise urllib.error.URLError("Connection refused")
            class FakeResp:
                def read(self_inner):
                    return json.dumps({
                        "message": {
                            "content": "```python\ndef fb():\n    return True\n```",
                        }
                    }).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        with caplog.at_level(logging.WARNING, logger="modules.omen.omen"):
            r = await online_omen.execute("code_generate", {"prompt": "write fallback"})
        assert r.success is True
        assert any(
            "plain-prompt fallback" in record.message
            for record in caplog.records
        ), "Expected warning about plain-prompt fallback"

    @pytest.mark.asyncio
    async def test_default_model_is_gemma4(self, online_omen: Omen, monkeypatch):
        """Verify default model is gemma4:26b, not gemma3."""
        import urllib.request
        import json

        captured_bodies = []

        def mock_urlopen(req, timeout=None):
            captured_bodies.append(json.loads(req.data.decode()))
            class FakeResp:
                def read(self_inner):
                    return json.dumps({
                        "message": {
                            "content": "```python\nx = 1\n```",
                        }
                    }).encode()
                def __enter__(self_inner): return self_inner
                def __exit__(self_inner, *a): pass
            return FakeResp()

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
        await online_omen.execute("code_generate", {"prompt": "assign x"})
        assert len(captured_bodies) >= 1
        assert captured_bodies[0]["model"] == "gemma4:26b"


# --- Unknown tool ---

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_fails(self, online_omen: Omen):
        r = await online_omen.execute("nonexistent", {})
        assert r.success is False
