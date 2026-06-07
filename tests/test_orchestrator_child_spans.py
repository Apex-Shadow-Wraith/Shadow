"""
Orchestrator child-span instrumentation tests
==============================================

Session 46 — Track C extension. The @trace_interaction decorator
(modules/shadow/observability.py) emits a root shadow.process_input
observation; this test suite verifies the three intermediate child
spans nest correctly under it:

    shadow.router_decision   — wraps Step 2 (_step2_classify)
    shadow.module_dispatch   — wraps Step 5 (retry-engine or single)
    shadow.response_assembly — wraps Steps 6.5 + 6.7 (polish phase)

All tests mock the Langfuse client. No live backend is required.
Tests verify both safe-fallback semantics (client None ⇒ no-op) and
configured-client semantics (spans created with expected metadata).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from modules.base import BaseModule, ModuleStatus, ToolResult
from modules.shadow import observability
from modules.shadow.orchestrator import Orchestrator


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def _clear_langfuse_cache():
    """Each test starts with a fresh observability client cache."""
    observability._reset_client_cache()
    yield
    observability._reset_client_cache()


@pytest.fixture
def tmp_config(tmp_path: Path) -> dict[str, Any]:
    """Minimal orchestrator config rooted at tmp_path."""
    return {
        "system": {
            "state_file": str(tmp_path / "state.json"),
            "task_db": str(tmp_path / "tasks.db"),
            "growth_db": str(tmp_path / "growth.db"),
        },
        "models": {
            "ollama_base_url": "http://localhost:11434",
            "router": {"name": "phi4-mini"},
            "fast_brain": {"name": "phi4-mini"},
            "smart_brain": {"name": "phi4-mini"},
        },
        "decision_loop": {"context_memories": 3},
    }


class _MockWraith(BaseModule):
    """Minimal Wraith mock for temporal-record best-effort calls."""

    def __init__(self):
        super().__init__(name="wraith", description="Mock Wraith")

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, content="ok", tool_name=tool_name, module=self.name)

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": "temporal_record", "description": "Record temporal event",
             "parameters": {}, "permission_level": "autonomous"},
        ]


class _MockOmenMath(BaseModule):
    """Mock Omen exposing the absorbed Cipher math tools so the math
    fast-path → Omen step-planner finds a target."""

    ABSORBED = {"calculate", "percentage", "unit_convert", "financial",
                "statistics", "logic_check", "date_math"}

    def __init__(self):
        super().__init__(name="omen", description="Mock Omen (math)")

    async def initialize(self) -> None:
        self.status = ModuleStatus.ONLINE

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        if tool_name in self.ABSORBED:
            return ToolResult(
                success=True,
                content={"result": 862.0, "expression": "15 + 847"},
                tool_name=tool_name, module=self.name,
            )
        return ToolResult(success=False, content=None, tool_name=tool_name,
                          module=self.name, error=f"Unknown tool: {tool_name}")

    async def shutdown(self) -> None:
        self.status = ModuleStatus.OFFLINE

    def get_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": n, "description": f"Mock {n}", "parameters": {},
             "permission_level": "autonomous"}
            for n in self.ABSORBED
        ]


def _build_langfuse_mock() -> tuple[MagicMock, list[tuple[str, MagicMock, dict]]]:
    """Build a fake Langfuse client. start_as_current_observation
    returns a fresh context manager per call, each yielding a unique
    MagicMock span. Returns (client, captured_spans) so callers can
    assert on the names + metadata that flowed through.

    captured_spans entries are (name, span_mock, start_kwargs).
    """
    captured: list[tuple[str, MagicMock, dict]] = []

    def _start(name=None, **kwargs):
        span = MagicMock()
        captured.append((name, span, kwargs))
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=span)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    client = MagicMock()
    client.start_as_current_observation.side_effect = _start
    return client, captured


# ===================================================================
# Safe-fallback semantics — observability disabled
# ===================================================================

class TestSafeFallbackNoClient:
    """When Langfuse is disabled, the orchestrator must run identically
    and no span calls may surface on the hot path. The three new spans
    inherit this property from observed_span itself, but the test
    pins the contract so a future refactor can't silently regress it."""

    @pytest.mark.asyncio
    @patch("modules.shadow.observability.get_client")
    async def test_no_client_no_spans_no_crash(
        self, mock_get_client, tmp_config: dict
    ):
        """With get_client returning None, observed_span yields None
        and the orchestrator completes its decision loop normally."""
        mock_get_client.return_value = None

        orch = Orchestrator(tmp_config)
        wraith = _MockWraith()
        await wraith.initialize()
        orch.registry.register(wraith)

        # Greeting hits the fast_response fast-path: Step 2 still runs
        # (so router_decision span is attempted), but Steps 5/6.5/6.7
        # are skipped. observed_span must no-op cleanly in both cases.
        response = await orch.process_input("hello")
        assert response  # decision loop returned a non-empty response

    @pytest.mark.asyncio
    async def test_observability_import_optional(self):
        """The orchestrator must import even if observed_span is
        unavailable — the fallback definition in the try/except block
        kicks in. This is the import-time stub the safe-fallback rule
        depends on."""
        # Verify the symbol exists at module level (either real or stub)
        from modules.shadow import orchestrator as orch_mod
        assert hasattr(orch_mod, "observed_span")
        # Calling the stub directly must yield None and not raise
        with orch_mod.observed_span("test", x=1) as span:
            # Real observed_span returns None when client is None;
            # stub returns None unconditionally — both satisfy the contract.
            assert span is None or hasattr(span, "update")


# ===================================================================
# Spans emitted — Langfuse client configured
# ===================================================================

class TestSpansEmittedRouterDispatchAssembly:
    """With a configured (mock) client, the three child spans must
    be created with the right names and carry the expected metadata."""

    @pytest.mark.asyncio
    @patch("modules.shadow.observability.get_client")
    async def test_full_pipeline_emits_all_three_child_spans(
        self, mock_get_client, tmp_config: dict
    ):
        """Math fast-path → Omen takes the input past Step 5 and into
        the assembly polish phase. We expect all four span names in the
        captured list: root + router_decision + module_dispatch +
        response_assembly."""
        client, captured = _build_langfuse_mock()
        mock_get_client.return_value = client

        orch = Orchestrator(tmp_config)
        wraith = _MockWraith()
        await wraith.initialize()
        orch.registry.register(wraith)
        omen = _MockOmenMath()
        await omen.initialize()
        orch.registry.register(omen)

        # Stub the eval LLM so Step 6 doesn't try to reach Ollama.
        orch._ollama_chat = MagicMock(return_value="15 + 847 is 862.")

        response = await orch.process_input("what is 15 + 847")
        assert response and "862" in response

        names = [n for (n, _span, _kwargs) in captured]
        assert "shadow.process_input" in names, (
            f"root trace span missing — got {names}"
        )
        assert "shadow.router_decision" in names, (
            f"router_decision child span missing — got {names}"
        )
        assert "shadow.module_dispatch" in names, (
            f"module_dispatch child span missing — got {names}"
        )
        assert "shadow.response_assembly" in names, (
            f"response_assembly child span missing — got {names}"
        )

    @pytest.mark.asyncio
    @patch("modules.shadow.observability.get_client")
    async def test_router_span_metadata_includes_module_and_classify_path(
        self, mock_get_client, tmp_config: dict
    ):
        """The router_decision span must carry the routing decision —
        target module, task type, confidence, and the derived
        classify_path (fast_path / llm_router / fallback_keyword)."""
        client, captured = _build_langfuse_mock()
        mock_get_client.return_value = client

        orch = Orchestrator(tmp_config)
        wraith = _MockWraith()
        await wraith.initialize()
        orch.registry.register(wraith)

        await orch.process_input("hello")

        router_spans = [s for s in captured if s[0] == "shadow.router_decision"]
        assert len(router_spans) == 1, (
            f"expected exactly one router_decision span, got {len(router_spans)}"
        )
        _name, span_mock, _start_kwargs = router_spans[0]

        # span.update must have been called with metadata carrying the
        # routing decision. We don't care about ordering of multiple
        # update calls, just that one of them carries the expected keys.
        update_calls = span_mock.update.call_args_list
        assert update_calls, "router_span.update was never called"
        merged_metadata: dict[str, Any] = {}
        for call in update_calls:
            md = call.kwargs.get("metadata", {}) or {}
            merged_metadata.update(md)

        assert "target_module" in merged_metadata
        assert "task_type" in merged_metadata
        assert "classify_path" in merged_metadata
        assert "confidence" in merged_metadata
        # "hello" goes through the keyword fast-path → classify_path
        # should be fast_path, not llm_router.
        assert merged_metadata["classify_path"] == "fast_path"

    @pytest.mark.asyncio
    @patch("modules.shadow.observability.get_client")
    async def test_dispatch_span_carries_module_and_tool_count(
        self, mock_get_client, tmp_config: dict
    ):
        """The module_dispatch span must carry the target module and
        a tool count (either actual executed-tool count or plan-step
        count when the retry engine owns inner execution)."""
        client, captured = _build_langfuse_mock()
        mock_get_client.return_value = client

        orch = Orchestrator(tmp_config)
        wraith = _MockWraith()
        await wraith.initialize()
        orch.registry.register(wraith)
        omen = _MockOmenMath()
        await omen.initialize()
        orch.registry.register(omen)

        orch._ollama_chat = MagicMock(return_value="15 + 847 is 862.")
        await orch.process_input("what is 15 + 847")

        dispatch_spans = [s for s in captured if s[0] == "shadow.module_dispatch"]
        assert len(dispatch_spans) == 1, (
            f"expected exactly one module_dispatch span, got {len(dispatch_spans)}"
        )
        _name, span_mock, start_kwargs = dispatch_spans[0]

        # The start kwargs should include module in the initial metadata
        # (passed via observed_span's **metadata kwargs surface).
        assert start_kwargs.get("metadata", {}).get("module") == "omen"

        # And the post-execution update should carry tool_count + module.
        update_calls = span_mock.update.call_args_list
        assert update_calls, "dispatch_span.update was never called"
        merged: dict[str, Any] = {}
        for call in update_calls:
            merged.update(call.kwargs.get("metadata", {}) or {})
        assert merged.get("module") == "omen"
        assert "tool_count" in merged
        assert "retry_engine_used" in merged
        assert "response_length" in merged

    @pytest.mark.asyncio
    @patch("modules.shadow.observability.get_client")
    async def test_assembly_span_carries_confidence_and_source(
        self, mock_get_client, tmp_config: dict
    ):
        """The response_assembly span must carry final-response metadata —
        response length, source (module_direct / claude_api / fallback),
        and confidence (or None when the scorer is disabled)."""
        client, captured = _build_langfuse_mock()
        mock_get_client.return_value = client

        orch = Orchestrator(tmp_config)
        wraith = _MockWraith()
        await wraith.initialize()
        orch.registry.register(wraith)
        omen = _MockOmenMath()
        await omen.initialize()
        orch.registry.register(omen)

        orch._ollama_chat = MagicMock(return_value="15 + 847 is 862.")
        await orch.process_input("what is 15 + 847")

        assembly_spans = [s for s in captured if s[0] == "shadow.response_assembly"]
        assert len(assembly_spans) == 1, (
            f"expected exactly one response_assembly span, got {len(assembly_spans)}"
        )
        _name, span_mock, _start_kwargs = assembly_spans[0]

        update_calls = span_mock.update.call_args_list
        assert update_calls, "assembly_span.update was never called"
        merged: dict[str, Any] = {}
        for call in update_calls:
            merged.update(call.kwargs.get("metadata", {}) or {})

        assert merged.get("module") == "omen"
        assert "response_length" in merged
        assert "source" in merged
        assert merged["source"] in ("module_direct", "fallback", "claude_api")
        assert "self_review_improved" in merged
        # confidence key must be present (value may be None if scorer disabled)
        assert "confidence" in merged
        assert "used_fallback" in merged

    @pytest.mark.asyncio
    @patch("modules.shadow.observability.get_client")
    async def test_fast_response_path_skips_dispatch_and_assembly(
        self, mock_get_client, tmp_config: dict
    ):
        """The greeting fast_response path returns before Step 5 / Step
        6.5. The router_decision span still fires (Step 2 always runs)
        but module_dispatch and response_assembly must NOT — they're
        bypassed for canned responses."""
        client, captured = _build_langfuse_mock()
        mock_get_client.return_value = client

        orch = Orchestrator(tmp_config)
        wraith = _MockWraith()
        await wraith.initialize()
        orch.registry.register(wraith)

        await orch.process_input("hello")

        names = [n for (n, _span, _kw) in captured]
        assert "shadow.router_decision" in names
        assert "shadow.module_dispatch" not in names, (
            "dispatch span fired on the canned fast_response path — "
            "the with-block must stay below the fast_response early-return"
        )
        assert "shadow.response_assembly" not in names, (
            "assembly span fired on the canned fast_response path — "
            "the with-block must stay below the fast_response early-return"
        )

    @pytest.mark.asyncio
    @patch("modules.shadow.observability.get_client")
    async def test_child_spans_survive_span_update_failure(
        self, mock_get_client, tmp_config: dict
    ):
        """If span.update() raises (e.g., backend network blip), the
        decision loop must complete cleanly. We simulate by making
        every span's update() raise — the request must still return
        a response."""
        client, captured = _build_langfuse_mock()
        mock_get_client.return_value = client

        # Patch the side_effect so every span we hand out has a failing
        # update method. Capture happens BEFORE _start returns, so we
        # mutate the span post-creation.
        orig_start = client.start_as_current_observation.side_effect

        def _start_with_failing_update(name=None, **kwargs):
            cm = orig_start(name=name, **kwargs)
            span = cm.__enter__.return_value
            span.update.side_effect = RuntimeError("backend down")
            return cm

        client.start_as_current_observation.side_effect = _start_with_failing_update

        orch = Orchestrator(tmp_config)
        wraith = _MockWraith()
        await wraith.initialize()
        orch.registry.register(wraith)

        # Should NOT raise — every span.update is wrapped in defensive
        # try/except in the orchestrator.
        response = await orch.process_input("hello")
        assert response

    @pytest.mark.asyncio
    @patch("modules.shadow.observability.get_client")
    async def test_child_spans_nest_under_root_observation(
        self, mock_get_client, tmp_config: dict
    ):
        """The root trace span (shadow.process_input) opens first and
        the child spans (router/dispatch/assembly) open after it. We
        verify ordering of start_as_current_observation calls — the
        actual OTel parent linkage is implicit in the v4 SDK's
        current-observation context propagation."""
        client, captured = _build_langfuse_mock()
        mock_get_client.return_value = client

        orch = Orchestrator(tmp_config)
        wraith = _MockWraith()
        await wraith.initialize()
        orch.registry.register(wraith)
        omen = _MockOmenMath()
        await omen.initialize()
        orch.registry.register(omen)

        orch._ollama_chat = MagicMock(return_value="15 + 847 is 862.")
        await orch.process_input("what is 15 + 847")

        names_in_order = [n for (n, _span, _kw) in captured]
        # The root must come first
        assert names_in_order[0] == "shadow.process_input"
        # router_decision must precede module_dispatch (Step 2 < Step 5)
        i_router = names_in_order.index("shadow.router_decision")
        i_dispatch = names_in_order.index("shadow.module_dispatch")
        i_assembly = names_in_order.index("shadow.response_assembly")
        assert i_router < i_dispatch < i_assembly, (
            f"child-span ordering wrong: {names_in_order}"
        )
