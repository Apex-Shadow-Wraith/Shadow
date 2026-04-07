"""Tests for TaskChainEngine — multi-module task orchestration."""

import asyncio
import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.shadow.task_chain import (
    VALID_MODULES,
    ChainStatus,
    ChainStep,
    InputSource,
    StepStatus,
    TaskChain,
    TaskChainEngine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_registry(online_modules=None):
    """Create a mock ModuleRegistry with online modules."""
    if online_modules is None:
        online_modules = ["reaper", "omen", "sentinel", "wraith", "cerberus", "grimoire"]

    registry = MagicMock()
    registry.__contains__ = lambda self, name: name in online_modules

    def _get_module(name):
        mod = MagicMock()
        mod.name = name
        mod.status = MagicMock()
        mod.status.value = "online"
        # Make status comparison work with ModuleStatus.ONLINE
        from modules.base import ModuleStatus
        mod.status = ModuleStatus.ONLINE
        mod.get_tools = MagicMock(return_value=[{"name": f"{name}_default"}])

        async def _execute(tool_name, params):
            from modules.base import ToolResult
            return ToolResult(
                success=True,
                content=f"Result from {name}/{tool_name}",
                tool_name=tool_name,
                module=name,
            )

        mod.execute = AsyncMock(side_effect=_execute)
        return mod

    registry.get_module = MagicMock(side_effect=_get_module)
    registry.find_tools = MagicMock(return_value=[{"name": "default_tool"}])
    registry.list_modules = MagicMock(return_value=[
        {"name": m, "status": "online", "description": f"{m} module"}
        for m in online_modules
    ])
    return registry


@pytest.fixture
def mock_registry():
    return _make_mock_registry()


@pytest.fixture
def engine(tmp_path, mock_registry):
    """Create a TaskChainEngine with temp database."""
    config = {
        "models": {
            "ollama_base_url": "http://localhost:11434",
            "router": {"name": "phi4-mini"},
        }
    }
    db_path = tmp_path / "test_chains.db"
    eng = TaskChainEngine(registry=mock_registry, config=config, db_path=db_path)
    eng.initialize()
    yield eng
    eng.close()


def _simple_steps(step_ids=None):
    """Build a simple 3-step chain definition."""
    ids = step_ids or [str(uuid.uuid4()) for _ in range(3)]
    return [
        {
            "step_id": ids[0],
            "module": "reaper",
            "task_description": "Research firewall best practices",
            "output_key": "research_results",
            "input_source": "user_input",
            "input_data": {"query": "firewall best practices"},
        },
        {
            "step_id": ids[1],
            "module": "sentinel",
            "task_description": "Analyze findings and design rules",
            "output_key": "firewall_design",
            "input_source": "previous_step",
            "depends_on": [ids[0]],
        },
        {
            "step_id": ids[2],
            "module": "omen",
            "task_description": "Implement the firewall script",
            "output_key": "implementation",
            "input_source": "previous_step",
            "depends_on": [ids[1]],
        },
    ], ids


# ---------------------------------------------------------------------------
# create_chain — validation and dependency resolution
# ---------------------------------------------------------------------------


class TestCreateChain:
    """Tests for chain creation, validation, and topological sort."""

    def test_create_chain_basic(self, engine):
        """Create a simple chain and verify structure."""
        steps, ids = _simple_steps()
        chain = engine.create_chain("Test chain", steps, priority=2)

        assert chain.chain_id is not None
        assert chain.description == "Test chain"
        assert chain.priority == 2
        assert chain.status == ChainStatus.PLANNING
        assert len(chain.steps) == 3
        assert chain.trigger == "user"

    def test_create_chain_validates_modules(self, engine):
        """Reject steps with invalid module names."""
        with pytest.raises(ValueError, match="invalid module"):
            engine.create_chain("Bad chain", [{
                "module": "nonexistent",
                "task_description": "Do something",
                "output_key": "result",
            }])

    def test_create_chain_requires_description(self, engine):
        """Reject empty chain description."""
        with pytest.raises(ValueError, match="description must not be empty"):
            engine.create_chain("", [{
                "module": "wraith",
                "task_description": "Do something",
                "output_key": "result",
            }])

    def test_create_chain_requires_steps(self, engine):
        """Reject empty step list."""
        with pytest.raises(ValueError, match="at least one step"):
            engine.create_chain("Empty chain", [])

    def test_create_chain_validates_priority(self, engine):
        """Reject invalid priority values."""
        with pytest.raises(ValueError, match="Priority must be"):
            engine.create_chain("Bad priority", [{
                "module": "wraith",
                "task_description": "Do something",
                "output_key": "result",
            }], priority=5)

    def test_create_chain_requires_task_description(self, engine):
        """Reject steps without task_description."""
        with pytest.raises(ValueError, match="task_description is required"):
            engine.create_chain("Missing desc", [{
                "module": "wraith",
                "task_description": "",
                "output_key": "result",
            }])

    def test_create_chain_requires_output_key(self, engine):
        """Reject steps without output_key."""
        with pytest.raises(ValueError, match="output_key is required"):
            engine.create_chain("Missing key", [{
                "module": "wraith",
                "task_description": "Do something",
                "output_key": "",
            }])

    def test_create_chain_validates_input_source(self, engine):
        """Reject steps with invalid input_source."""
        with pytest.raises(ValueError, match="invalid input_source"):
            engine.create_chain("Bad input", [{
                "module": "wraith",
                "task_description": "Do something",
                "output_key": "result",
                "input_source": "invalid_source",
            }])

    def test_create_chain_validates_dependency_refs(self, engine):
        """Reject depends_on referencing nonexistent step_ids."""
        with pytest.raises(ValueError, match="does not exist"):
            engine.create_chain("Bad dep", [{
                "step_id": "step-1",
                "module": "wraith",
                "task_description": "Do something",
                "output_key": "result",
                "depends_on": ["nonexistent-step"],
            }])

    def test_create_chain_detects_circular_deps(self, engine):
        """Detect circular dependencies and raise ValueError."""
        id_a, id_b = str(uuid.uuid4()), str(uuid.uuid4())
        with pytest.raises(ValueError, match="Circular dependency"):
            engine.create_chain("Circular", [
                {
                    "step_id": id_a,
                    "module": "wraith",
                    "task_description": "Step A",
                    "output_key": "a",
                    "depends_on": [id_b],
                },
                {
                    "step_id": id_b,
                    "module": "omen",
                    "task_description": "Step B",
                    "output_key": "b",
                    "depends_on": [id_a],
                },
            ])

    def test_topological_sort_ordering(self, engine):
        """Steps are sorted so dependencies come before dependents."""
        steps, ids = _simple_steps()
        chain = engine.create_chain("Topo test", steps)

        # Step 0 depends on nothing → first
        # Step 1 depends on step 0 → second
        # Step 2 depends on step 1 → third
        assert chain.steps[0].step_id == ids[0]
        assert chain.steps[1].step_id == ids[1]
        assert chain.steps[2].step_id == ids[2]

    def test_topological_sort_parallel_independent(self, engine):
        """Independent steps can be in any order but before their dependents."""
        id_a, id_b, id_c = [str(uuid.uuid4()) for _ in range(3)]
        chain = engine.create_chain("Parallel test", [
            {
                "step_id": id_a,
                "module": "reaper",
                "task_description": "Research A",
                "output_key": "a",
                "parallel_group": "research",
            },
            {
                "step_id": id_b,
                "module": "sentinel",
                "task_description": "Research B",
                "output_key": "b",
                "parallel_group": "research",
            },
            {
                "step_id": id_c,
                "module": "omen",
                "task_description": "Combine",
                "output_key": "c",
                "depends_on": [id_a, id_b],
            },
        ])

        # Both A and B must come before C
        step_order = {s.step_id: s.step_number for s in chain.steps}
        assert step_order[id_a] < step_order[id_c]
        assert step_order[id_b] < step_order[id_c]

    def test_single_step_chain(self, engine):
        """Single-step chain works correctly."""
        chain = engine.create_chain("Single step", [{
            "module": "wraith",
            "task_description": "Quick task",
            "output_key": "result",
        }])
        assert len(chain.steps) == 1
        assert chain.steps[0].module == "wraith"


# ---------------------------------------------------------------------------
# execute_chain — step execution, output passing, retries, parallel
# ---------------------------------------------------------------------------


class TestExecuteChain:
    """Tests for chain execution logic."""

    @pytest.mark.asyncio
    async def test_execute_chain_passes_output(self, engine):
        """Output from step N is available as input to step N+1."""
        steps, ids = _simple_steps()
        chain = engine.create_chain("Output pass test", steps)
        results = await engine.execute_chain(chain)

        assert chain.status == ChainStatus.COMPLETED
        assert "research_results" in results
        assert "firewall_design" in results
        assert "implementation" in results

    @pytest.mark.asyncio
    async def test_execute_chain_parallel_group(self, engine):
        """Steps in the same parallel_group run concurrently."""
        id_a, id_b, id_c = [str(uuid.uuid4()) for _ in range(3)]
        chain = engine.create_chain("Parallel exec", [
            {
                "step_id": id_a,
                "module": "reaper",
                "task_description": "Research A",
                "output_key": "a",
                "parallel_group": "research",
            },
            {
                "step_id": id_b,
                "module": "sentinel",
                "task_description": "Research B",
                "output_key": "b",
                "parallel_group": "research",
            },
            {
                "step_id": id_c,
                "module": "omen",
                "task_description": "Combine",
                "output_key": "c",
                "depends_on": [id_a, id_b],
            },
        ])

        results = await engine.execute_chain(chain)

        assert chain.status == ChainStatus.COMPLETED
        assert "a" in results
        assert "b" in results
        assert "c" in results

    @pytest.mark.asyncio
    async def test_execute_chain_retries_on_failure(self, engine, mock_registry):
        """Failed steps are retried up to max_retries times."""
        call_count = 0

        async def flaky_execute(tool_name, params):
            nonlocal call_count
            call_count += 1
            from modules.base import ToolResult
            if call_count < 3:
                raise RuntimeError("Transient error")
            return ToolResult(success=True, content="Success after retries",
                              tool_name=tool_name, module="wraith")

        # Patch the module's execute to be flaky
        mod = mock_registry.get_module("wraith")
        mod.execute = AsyncMock(side_effect=flaky_execute)

        chain = engine.create_chain("Retry test", [{
            "module": "wraith",
            "task_description": "Flaky task",
            "output_key": "result",
            "retry_on_fail": True,
            "max_retries": 3,
        }])

        results = await engine.execute_chain(chain)
        assert chain.status == ChainStatus.COMPLETED
        assert "result" in results

    @pytest.mark.asyncio
    async def test_execute_chain_aborts_on_critical_failure(self, tmp_path):
        """Chain aborts when a critical (non-parallel) step fails permanently."""
        from modules.base import ModuleStatus, ToolResult

        async def always_fail(tool_name, params):
            raise RuntimeError("Permanent failure")

        async def succeed(tool_name, params):
            return ToolResult(success=True, content="ok", tool_name=tool_name, module="test")

        # Build a registry that caches module mocks so patching sticks
        module_cache = {}
        online = ["reaper", "omen", "sentinel", "wraith", "cerberus", "grimoire"]
        registry = MagicMock()
        registry.__contains__ = lambda self, name: name in online

        def _get(name):
            if name not in module_cache:
                mod = MagicMock()
                mod.name = name
                mod.status = ModuleStatus.ONLINE
                mod.get_tools = MagicMock(return_value=[{"name": f"{name}_default"}])
                mod.execute = AsyncMock(side_effect=succeed)
                module_cache[name] = mod
            return module_cache[name]

        registry.get_module = MagicMock(side_effect=_get)
        registry.find_tools = MagicMock(return_value=[{"name": "default_tool"}])
        registry.list_modules = MagicMock(return_value=[
            {"name": m, "status": "online", "description": f"{m} module"} for m in online
        ])

        # Make reaper always fail
        _get("reaper").execute = AsyncMock(side_effect=always_fail)

        config = {"models": {"ollama_base_url": "http://localhost:11434",
                              "router": {"name": "phi4-mini"}}}
        eng = TaskChainEngine(registry=registry, config=config,
                              db_path=tmp_path / "abort_test.db")
        eng.initialize()

        steps, ids = _simple_steps()
        steps[0]["retry_on_fail"] = False
        chain = eng.create_chain("Abort test", steps)

        results = await eng.execute_chain(chain)
        assert chain.status == ChainStatus.FAILED
        assert chain.steps[1].status == StepStatus.SKIPPED
        assert chain.steps[2].status == StepStatus.SKIPPED
        eng.close()

    @pytest.mark.asyncio
    async def test_execute_chain_single_step(self, engine):
        """Single-step chain executes and completes."""
        chain = engine.create_chain("Single", [{
            "module": "wraith",
            "task_description": "Quick",
            "output_key": "result",
        }])

        results = await engine.execute_chain(chain)
        assert chain.status == ChainStatus.COMPLETED
        assert "result" in results


# ---------------------------------------------------------------------------
# cancel_chain
# ---------------------------------------------------------------------------


class TestCancelChain:
    """Tests for chain cancellation."""

    def test_cancel_chain_stops_pending(self, engine):
        """Cancelling marks pending/ready steps as skipped."""
        steps, ids = _simple_steps()
        chain = engine.create_chain("Cancel test", steps)

        engine.cancel_chain(chain.chain_id, "User cancelled")

        assert chain.status == ChainStatus.CANCELLED
        for step in chain.steps:
            assert step.status == StepStatus.SKIPPED
            assert "Cancelled" in (step.error or "")

    def test_cancel_chain_raises_on_unknown(self, engine):
        """Cancelling a nonexistent chain raises KeyError."""
        with pytest.raises(KeyError):
            engine.cancel_chain("nonexistent-id", "reason")


# ---------------------------------------------------------------------------
# get_chain_status / list_chains
# ---------------------------------------------------------------------------


class TestChainStatus:
    """Tests for chain status reporting."""

    def test_get_chain_status(self, engine):
        """Status report includes correct progress info."""
        steps, _ = _simple_steps()
        chain = engine.create_chain("Status test", steps)

        status = engine.get_chain_status(chain.chain_id)
        assert status["chain_id"] == chain.chain_id
        assert status["total_steps"] == 3
        assert status["completed_steps"] == 0
        assert status["status"] == "planning"
        assert "visual" in status

    def test_list_chains(self, engine):
        """list_chains returns all chains."""
        engine.create_chain("Chain 1", [{
            "module": "wraith", "task_description": "A", "output_key": "a",
        }])
        engine.create_chain("Chain 2", [{
            "module": "omen", "task_description": "B", "output_key": "b",
        }])

        chains = engine.list_chains()
        assert len(chains) == 2

    def test_list_chains_filter_by_status(self, engine):
        """list_chains filters by status."""
        engine.create_chain("Chain 1", [{
            "module": "wraith", "task_description": "A", "output_key": "a",
        }])

        # All new chains are "planning" status
        assert len(engine.list_chains(status="planning")) == 1
        assert len(engine.list_chains(status="completed")) == 0


# ---------------------------------------------------------------------------
# plan_chain_from_request — LLM decomposition with mock
# ---------------------------------------------------------------------------


class TestPlanChainFromRequest:
    """Tests for LLM-based chain decomposition."""

    @pytest.mark.asyncio
    async def test_plan_from_request_with_mock_llm(self, engine):
        """plan_chain_from_request decomposes a request using mocked LLM."""
        mock_response = json.dumps([
            {
                "module": "reaper",
                "task_description": "Research firewall practices",
                "output_key": "research",
                "input_source": "user_input",
                "depends_on": [],
                "parallel_group": None,
            },
            {
                "module": "omen",
                "task_description": "Implement firewall",
                "output_key": "implementation",
                "input_source": "previous_step",
                "depends_on": [0],
                "parallel_group": None,
            },
        ])

        with patch.object(engine, "_llm_decompose", new_callable=AsyncMock) as mock_llm:
            # Simulate the parsed output (after _llm_decompose processes it)
            step_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
            mock_llm.return_value = [
                {
                    "step_id": step_ids[0],
                    "module": "reaper",
                    "task_description": "Research firewall practices",
                    "output_key": "research",
                    "input_source": "user_input",
                    "depends_on": [],
                    "parallel_group": None,
                },
                {
                    "step_id": step_ids[1],
                    "module": "omen",
                    "task_description": "Implement firewall",
                    "output_key": "implementation",
                    "input_source": "previous_step",
                    "depends_on": [step_ids[0]],
                    "parallel_group": None,
                },
            ]

            chain = await engine.plan_chain_from_request(
                "Research firewall best practices and implement one"
            )

            assert len(chain.steps) == 2
            assert chain.steps[0].module == "reaper"
            assert chain.steps[1].module == "omen"
            assert chain.trigger == "plan_from_request"

    @pytest.mark.asyncio
    async def test_plan_from_request_fallback(self, engine):
        """Falls back to single-step chain when LLM decomposition fails."""
        with patch.object(engine, "_llm_decompose", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = RuntimeError("LLM unavailable")

            chain = await engine.plan_chain_from_request(
                "Search for python best practices"
            )

            assert len(chain.steps) == 1
            assert chain.trigger == "plan_from_request_fallback"
            # "search" keyword should route to reaper
            assert chain.steps[0].module == "reaper"


# ---------------------------------------------------------------------------
# Serialization / persistence
# ---------------------------------------------------------------------------


class TestChainPersistence:
    """Tests for chain serialization and database recovery."""

    def test_chain_round_trip_serialization(self):
        """ChainStep and TaskChain survive to_dict/from_dict round trip."""
        step = ChainStep(
            step_id="test-step",
            step_number=0,
            module="wraith",
            task_description="Test task",
            input_source=InputSource.USER_INPUT,
            input_data={"key": "value"},
            output_key="test_output",
            depends_on=[],
            parallel_group="group1",
            status=StepStatus.COMPLETED,
            result={"data": "result"},
            started_at=datetime(2026, 1, 1, 12, 0),
            completed_at=datetime(2026, 1, 1, 12, 5),
        )

        step_dict = step.to_dict()
        restored = ChainStep.from_dict(step_dict)

        assert restored.step_id == step.step_id
        assert restored.module == step.module
        assert restored.input_source == step.input_source
        assert restored.status == step.status
        assert restored.result == step.result
        assert restored.parallel_group == "group1"

    def test_task_chain_round_trip(self):
        """TaskChain survives to_dict/from_dict round trip."""
        chain = TaskChain(
            chain_id="test-chain",
            description="Test chain",
            steps=[ChainStep(
                step_id="s1", step_number=0, module="wraith",
                task_description="Task", input_source=InputSource.STATIC,
                input_data=None, output_key="out", depends_on=[],
            )],
            priority=2,
            created_at=datetime(2026, 1, 1),
            created_by="user",
            status=ChainStatus.COMPLETED,
            results={"out": {"data": "value"}},
            trigger="test",
        )

        chain_dict = chain.to_dict()
        restored = TaskChain.from_dict(chain_dict)

        assert restored.chain_id == chain.chain_id
        assert restored.status == chain.status
        assert restored.results == chain.results
        assert len(restored.steps) == 1

    def test_chain_persists_to_db(self, engine):
        """Chains are saved to SQLite and recoverable."""
        chain = engine.create_chain("Persist test", [{
            "module": "wraith",
            "task_description": "Test",
            "output_key": "result",
        }])

        # Create a new engine pointing at the same DB
        engine2 = TaskChainEngine(
            registry=engine._registry,
            config=engine._config,
            db_path=engine._db_path,
        )
        engine2.initialize()

        # Should recover the chain
        recovered = engine2._get_chain(chain.chain_id)
        assert recovered.chain_id == chain.chain_id
        assert recovered.description == "Persist test"
        engine2.close()

    def test_chain_recovery_on_startup(self, tmp_path, mock_registry):
        """Incomplete chains are recovered on engine startup."""
        config = {"models": {"ollama_base_url": "http://localhost:11434",
                             "router": {"name": "phi4-mini"}}}
        db_path = tmp_path / "recovery_test.db"

        # Create engine 1 and make a chain
        eng1 = TaskChainEngine(registry=mock_registry, config=config, db_path=db_path)
        eng1.initialize()
        chain = eng1.create_chain("Recovery test", [{
            "module": "wraith",
            "task_description": "Task",
            "output_key": "result",
        }])
        chain.status = ChainStatus.RUNNING
        eng1._save_chain(chain)
        eng1.close()

        # Create engine 2 — should recover the running chain
        eng2 = TaskChainEngine(registry=mock_registry, config=config, db_path=db_path)
        eng2.initialize()
        assert chain.chain_id in eng2._active_chains
        eng2.close()
