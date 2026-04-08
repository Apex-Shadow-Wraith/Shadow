"""Tests for Pre-Execution Planning Pass."""

import json
import time
import uuid

import pytest

from modules.shadow.execution_planner import (
    ExecutionPlan,
    ExecutionPlanner,
    PlanStep,
)


# --- Helpers ---

def _make_step(num=1, tool="test_tool", action="do thing", input_from="user_input",
               expected_output="result", fallback="skip"):
    return PlanStep(
        step_number=num, tool=tool, action=action,
        input_from=input_from, expected_output=expected_output, fallback=fallback,
    )


def _make_plan(steps=None, status="planned", task_type="general", duration=30.0):
    steps = steps or [_make_step()]
    return ExecutionPlan(
        plan_id=str(uuid.uuid4()),
        task_description="Test task",
        task_type=task_type,
        steps=steps,
        estimated_duration=duration,
        tools_required=[s.tool for s in steps],
        preconditions=[],
        success_criteria="It works",
        created_at=time.time(),
        status=status,
    )


def _mock_generate_fn(response_data):
    """Return a generate_fn that returns a JSON plan response."""
    def generate(prompt):
        return json.dumps(response_data)
    return generate


_VALID_RESPONSE = {
    "task_type": "research",
    "steps": [
        {
            "tool": "reaper_search",
            "action": "Search the web",
            "input_from": "user_input",
            "expected_output": "search results",
            "fallback": "try alternate search",
        },
        {
            "tool": "grimoire_store",
            "action": "Store results",
            "input_from": "step_1",
            "expected_output": "stored document id",
            "fallback": "log warning",
        },
    ],
    "estimated_duration": 45,
    "preconditions": ["internet available"],
    "success_criteria": "Results stored in Grimoire",
}


# --- PlanStep and ExecutionPlan field tests ---

class TestDataClasses:
    def test_plan_step_has_all_fields(self):
        step = _make_step()
        assert step.step_number == 1
        assert step.tool == "test_tool"
        assert step.action == "do thing"
        assert step.input_from == "user_input"
        assert step.expected_output == "result"
        assert step.fallback == "skip"

    def test_execution_plan_has_all_fields(self):
        plan = _make_plan()
        assert plan.plan_id
        assert plan.task_description == "Test task"
        assert plan.task_type == "general"
        assert len(plan.steps) == 1
        assert isinstance(plan.estimated_duration, float)
        assert isinstance(plan.tools_required, list)
        assert isinstance(plan.preconditions, list)
        assert plan.success_criteria == "It works"
        assert plan.created_at > 0
        assert plan.status == "planned"


# --- create_plan tests ---

class TestCreatePlan:
    def test_generates_plan_with_valid_steps(self):
        planner = ExecutionPlanner(generate_fn=_mock_generate_fn(_VALID_RESPONSE))
        plan = planner.create_plan("Research AI safety", ["reaper_search", "grimoire_store"])

        assert plan.task_type == "research"
        assert len(plan.steps) == 2
        assert plan.steps[0].tool == "reaper_search"
        assert plan.steps[1].tool == "grimoire_store"
        assert plan.steps[1].input_from == "step_1"
        assert plan.status == "planned"

    def test_checks_grimoire_for_reusable_plan(self):
        """When Grimoire has a matching plan, reuse it."""
        stored_plan = {
            "plan_id": "existing-123",
            "task_description": "Research topic",
            "task_type": "research",
            "steps": [{"tool": "reaper_search", "action": "search", "input_from": "user_input",
                        "expected_output": "results", "fallback": "skip"}],
            "estimated_duration": 20,
            "tools_required": ["reaper_search"],
            "preconditions": [],
            "success_criteria": "Found results",
            "created_at": time.time(),
            "status": "completed",
        }

        class MockGrimoire:
            def search(self, query, category=None):
                return [json.dumps(stored_plan)]

        planner = ExecutionPlanner(grimoire=MockGrimoire())
        plan = planner.create_plan("Research quantum computing")

        # Should reuse the existing plan's structure
        assert len(plan.steps) == 1
        assert plan.steps[0].tool == "reaper_search"
        assert planner.get_planning_stats()["plans_reused"] == 1

    def test_adapts_existing_plan_when_found(self):
        """Adapted plan gets a new ID and updated task description."""
        stored = {
            "plan_id": "old-id",
            "task_description": "Old task",
            "task_type": "research",
            "steps": [{"tool": "search", "action": "go", "input_from": "user_input",
                        "expected_output": "r", "fallback": "s"}],
            "estimated_duration": 10,
            "tools_required": ["search"],
            "preconditions": [],
            "success_criteria": "done",
            "created_at": 1000,
            "status": "completed",
        }

        class MockGrimoire:
            def search(self, query, category=None):
                return [json.dumps(stored)]

        planner = ExecutionPlanner(grimoire=MockGrimoire())
        plan = planner.create_plan("New task description")

        assert plan.plan_id != "old-id"
        assert plan.task_description == "New task description"

    def test_generates_new_plan_when_none_found(self):
        """When Grimoire returns nothing, generate a new plan."""
        class EmptyGrimoire:
            def search(self, query, category=None):
                return []

        planner = ExecutionPlanner(
            generate_fn=_mock_generate_fn(_VALID_RESPONSE),
            grimoire=EmptyGrimoire(),
        )
        plan = planner.create_plan("Research AI safety", ["reaper_search", "grimoire_store"])

        assert len(plan.steps) == 2
        assert planner.get_planning_stats()["plans_reused"] == 0

    def test_parsing_failure_single_step_fallback(self):
        """If model returns unparseable response, fall back to single step."""
        def bad_generate(prompt):
            return "this is not json at all!!!"

        planner = ExecutionPlanner(generate_fn=bad_generate)
        plan = planner.create_plan("Do something", ["tool_a"])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool == "tool_a"
        assert plan.status == "planned"

    def test_graceful_when_generate_fn_is_none(self):
        """Without a model, returns a single-step fallback plan."""
        planner = ExecutionPlanner(generate_fn=None)
        plan = planner.create_plan("Do something", ["my_tool"])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool == "my_tool"

    def test_graceful_when_grimoire_is_none(self):
        """Without Grimoire, still generates plans via model."""
        planner = ExecutionPlanner(
            generate_fn=_mock_generate_fn(_VALID_RESPONSE),
            grimoire=None,
        )
        plan = planner.create_plan("Research AI", ["reaper_search", "grimoire_store"])
        assert len(plan.steps) == 2

    def test_empty_available_tools(self):
        """Empty tools list should produce a fallback plan gracefully."""
        planner = ExecutionPlanner(generate_fn=None)
        plan = planner.create_plan("Do something", [])

        assert len(plan.steps) == 1
        assert plan.steps[0].tool == "direct"
        assert plan.tools_required == []


# --- evaluate_plan tests ---

class TestEvaluatePlan:
    def test_all_tools_available_feasible(self):
        plan = _make_plan(steps=[
            _make_step(1, "tool_a"),
            _make_step(2, "tool_b", input_from="step_1"),
        ])
        planner = ExecutionPlanner()
        result = planner.evaluate_plan(plan, ["tool_a", "tool_b"])

        assert result["feasible"] is True
        assert result["issues"] == []

    def test_missing_tool_not_feasible(self):
        plan = _make_plan(steps=[_make_step(1, "missing_tool")])
        planner = ExecutionPlanner()
        result = planner.evaluate_plan(plan, ["other_tool"])

        assert result["feasible"] is False
        assert any("missing_tool" in i for i in result["issues"])

    def test_circular_dependency_detected(self):
        # Step 1 depends on step 2, step 2 depends on step 1
        steps = [
            _make_step(1, "t1", input_from="step_2"),
            _make_step(2, "t2", input_from="step_1"),
        ]
        plan = _make_plan(steps=steps)
        planner = ExecutionPlanner()
        result = planner.evaluate_plan(plan, ["t1", "t2"])

        assert result["feasible"] is False
        assert any("Circular" in i or "future step" in i for i in result["issues"])

    def test_forward_reference_invalid(self):
        """Step references a future step's output."""
        steps = [
            _make_step(1, "t1", input_from="step_2"),
            _make_step(2, "t2", input_from="user_input"),
        ]
        plan = _make_plan(steps=steps)
        planner = ExecutionPlanner()
        result = planner.evaluate_plan(plan, ["t1", "t2"])

        assert result["feasible"] is False
        assert any("future step" in i for i in result["issues"])

    def test_zero_steps_error(self):
        plan = _make_plan(steps=[])
        plan.steps = []
        planner = ExecutionPlanner()
        result = planner.evaluate_plan(plan)

        assert result["feasible"] is False
        assert any("no steps" in i.lower() for i in result["issues"])

    def test_single_step_valid(self):
        plan = _make_plan(steps=[_make_step()])
        planner = ExecutionPlanner()
        result = planner.evaluate_plan(plan, ["test_tool"])

        assert result["feasible"] is True

    def test_excessive_duration(self):
        plan = _make_plan(duration=500.0)
        planner = ExecutionPlanner()
        result = planner.evaluate_plan(plan)

        assert result["feasible"] is False
        assert any("300s" in i for i in result["issues"])


# --- adapt_plan tests ---

class TestAdaptPlan:
    def test_produces_adapted_status(self):
        plan = _make_plan()
        planner = ExecutionPlanner()
        adapted = planner.adapt_plan(plan, "Tool X failed")

        assert adapted.status == "adapted"
        assert adapted.plan_id != plan.plan_id

    def test_preserves_task_description(self):
        plan = _make_plan()
        planner = ExecutionPlanner()
        adapted = planner.adapt_plan(plan, "Something broke")

        assert adapted.task_description == plan.task_description

    def test_with_generate_fn_produces_new_steps(self):
        """When model is available, adaptation generates new steps."""
        adapted_response = {
            "task_type": "general",
            "steps": [
                {"tool": "fallback_tool", "action": "try alternate", "input_from": "user_input",
                 "expected_output": "recovery", "fallback": "abort"},
            ],
            "estimated_duration": 15,
            "preconditions": [],
            "success_criteria": "Recovered",
        }
        planner = ExecutionPlanner(generate_fn=_mock_generate_fn(adapted_response))
        plan = _make_plan()
        adapted = planner.adapt_plan(plan, "Original tool crashed")

        assert adapted.status == "adapted"
        assert len(adapted.steps) >= 1


# --- store_successful_plan tests ---

class TestStoreSuccessfulPlan:
    def test_stores_in_grimoire(self):
        stored_docs = []

        class MockGrimoire:
            def search(self, query, category=None):
                return []
            def store(self, content, metadata=None):
                stored_docs.append({"content": content, "metadata": metadata})
                return "doc-123"

        planner = ExecutionPlanner(grimoire=MockGrimoire())
        plan = _make_plan(status="completed")
        doc_id = planner.store_successful_plan(plan)

        assert doc_id == "doc-123"
        assert len(stored_docs) == 1
        assert stored_docs[0]["metadata"]["category"] == "execution_plan"

    def test_deduplicates_similar_plans(self):
        """Should not store a plan that's very similar to an existing one."""
        existing = {
            "plan_id": "existing",
            "task_description": "Test task",
            "task_type": "general",
            "steps": [{"step_number": 1, "tool": "test_tool", "action": "do thing",
                        "input_from": "user_input", "expected_output": "result",
                        "fallback": "skip"}],
            "estimated_duration": 30,
            "tools_required": ["test_tool"],
            "preconditions": [],
            "success_criteria": "done",
            "created_at": 1000,
            "status": "completed",
        }

        class MockGrimoire:
            def search(self, query, category=None):
                return [json.dumps(existing)]
            def store(self, content, metadata=None):
                return "should-not-be-called"

        planner = ExecutionPlanner(grimoire=MockGrimoire())
        plan = _make_plan(status="completed", task_type="general")
        doc_id = planner.store_successful_plan(plan)

        # Should be empty — duplicate detected
        assert doc_id == ""

    def test_no_grimoire_returns_empty(self):
        planner = ExecutionPlanner(grimoire=None)
        plan = _make_plan()
        assert planner.store_successful_plan(plan) == ""


# --- search_reusable_plans tests ---

class TestSearchReusablePlans:
    def test_returns_matching_plans(self):
        stored = {
            "plan_id": "found-1",
            "task_description": "Research AI",
            "task_type": "research",
            "steps": [{"tool": "search", "action": "go", "input_from": "user_input",
                        "expected_output": "r", "fallback": "s"}],
            "estimated_duration": 20,
            "tools_required": ["search"],
            "preconditions": [],
            "success_criteria": "found",
            "created_at": 1000,
            "status": "completed",
        }

        class MockGrimoire:
            def search(self, query, category=None):
                return [json.dumps(stored)]

        planner = ExecutionPlanner(grimoire=MockGrimoire())
        plans = planner.search_reusable_plans("research", "AI")

        assert len(plans) == 1
        assert plans[0].task_type == "research"

    def test_no_grimoire_returns_empty(self):
        planner = ExecutionPlanner(grimoire=None)
        assert planner.search_reusable_plans("research") == []


# --- get_planning_stats tests ---

class TestGetPlanningStats:
    def test_returns_valid_data(self):
        planner = ExecutionPlanner(generate_fn=_mock_generate_fn(_VALID_RESPONSE))
        planner.create_plan("task 1", ["reaper_search", "grimoire_store"])
        stats = planner.get_planning_stats()

        assert stats["plans_created"] >= 1
        assert "plans_reused" in stats
        assert "plans_adapted" in stats
        assert "avg_steps_per_plan" in stats
        assert "success_rate" in stats
        assert isinstance(stats["avg_steps_per_plan"], float)

    def test_initial_stats_are_zero(self):
        planner = ExecutionPlanner()
        stats = planner.get_planning_stats()

        assert stats["plans_created"] == 0
        assert stats["success_rate"] == 0.0
