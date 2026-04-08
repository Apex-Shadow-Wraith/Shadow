"""
Pre-Execution Planning Pass
==============================
Before any multi-tool task, generate and evaluate an explicit
execution plan. Plans are stored in Grimoire as reusable workflows
so Shadow can learn from successful execution patterns.

Plans are advisory — execution can diverge, and that's okay.
Only successful plans are stored as reusable workflows.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("shadow.execution_planner")


@dataclass
class PlanStep:
    """A single step in an execution plan."""

    step_number: int
    tool: str
    action: str
    input_from: str  # "user_input" or "step_{N}"
    expected_output: str
    fallback: str


@dataclass
class ExecutionPlan:
    """A complete execution plan for a multi-tool task."""

    plan_id: str
    task_description: str
    task_type: str
    steps: list[PlanStep]
    estimated_duration: float  # seconds
    tools_required: list[str]
    preconditions: list[str]
    success_criteria: str
    created_at: float
    status: str  # "planned", "executing", "completed", "failed", "adapted"


_PLAN_PROMPT = """Create an execution plan for this task. List each step with:
- Which tool to use
- What action to take
- Where the input comes from (user or previous step)
- What the expected output is
- What to do if the step fails

Task: {task}
Available tools: {available_tools}
Context: {context}

Respond in this JSON format:
{{
  "task_type": "...",
  "steps": [
    {{
      "tool": "tool_name",
      "action": "what to do",
      "input_from": "user_input or step_N",
      "expected_output": "description",
      "fallback": "what to do on failure"
    }}
  ],
  "estimated_duration": 30,
  "preconditions": ["..."],
  "success_criteria": "how to know it worked"
}}"""

_ADAPT_PROMPT = """The execution plan below diverged from expectations.

Original plan:
{original_plan}

What went wrong:
{divergence}

Remaining steps (not yet executed):
{remaining_steps}

Generate an adapted plan that accounts for the divergence. Use the same JSON format."""


class ExecutionPlanner:
    """Generate, evaluate, and store execution plans for multi-tool tasks.

    Plans are advisory guides for multi-step execution. Successful
    plans are stored in Grimoire for reuse on similar future tasks.
    """

    def __init__(
        self,
        generate_fn: Callable | None = None,
        grimoire: Any | None = None,
        tool_registry: Any | None = None,
    ) -> None:
        self._generate_fn = generate_fn
        self._grimoire = grimoire
        self._tool_registry = tool_registry
        self._stats = {
            "plans_created": 0,
            "plans_reused": 0,
            "plans_adapted": 0,
            "total_steps": 0,
            "plans_succeeded": 0,
            "plans_failed": 0,
        }

    def create_plan(
        self,
        task: str,
        available_tools: list[str] | None = None,
        context: str = "",
    ) -> ExecutionPlan:
        """Create an execution plan for a task.

        Checks Grimoire for a reusable plan first. If found, adapts
        it to the current task. Otherwise generates a new plan via
        the local model.

        Args:
            task: Description of the task to plan.
            available_tools: Tools that can be used.
            context: Additional context for planning.

        Returns:
            An ExecutionPlan ready for evaluation and execution.
        """
        available_tools = available_tools or []

        # Check Grimoire for reusable plans
        existing = self._find_reusable_plan(task)
        if existing is not None:
            adapted = self._adapt_existing_plan(existing, task, available_tools)
            self._stats["plans_reused"] += 1
            self._stats["plans_created"] += 1
            self._stats["total_steps"] += len(adapted.steps)
            return adapted

        # Generate new plan via model
        plan = self._generate_new_plan(task, available_tools, context)
        self._stats["plans_created"] += 1
        self._stats["total_steps"] += len(plan.steps)
        return plan

    def evaluate_plan(
        self,
        plan: ExecutionPlan,
        available_tools: list[str] | None = None,
    ) -> dict:
        """Evaluate plan feasibility before execution.

        Checks:
        - All required tools are available
        - Step dependencies are valid (no forward references)
        - No circular dependencies
        - Estimated duration is reasonable (< 300 seconds)

        Returns:
            Dict with feasible (bool), issues (list), suggestions (list).
        """
        available_tools = available_tools or []
        issues: list[str] = []
        suggestions: list[str] = []

        # Check: plan must have at least one step
        if not plan.steps:
            issues.append("Plan has no steps")
            return {"feasible": False, "issues": issues, "suggestions": ["Add at least one step"]}

        # Check: all required tools are available
        if available_tools:
            for step in plan.steps:
                if step.tool and step.tool not in available_tools:
                    issues.append(f"Step {step.step_number}: tool '{step.tool}' is not available")

        # Check: step dependencies are valid (no forward references)
        step_numbers = {s.step_number for s in plan.steps}
        for step in plan.steps:
            if step.input_from and step.input_from.startswith("step_"):
                try:
                    ref_num = int(step.input_from.split("_")[1])
                    if ref_num >= step.step_number:
                        issues.append(
                            f"Step {step.step_number}: references future step {ref_num}"
                        )
                    if ref_num not in step_numbers:
                        issues.append(
                            f"Step {step.step_number}: references non-existent step {ref_num}"
                        )
                except (ValueError, IndexError):
                    issues.append(
                        f"Step {step.step_number}: invalid input_from '{step.input_from}'"
                    )

        # Check: circular dependencies
        circular = self._detect_circular_deps(plan.steps)
        if circular:
            issues.append(f"Circular dependency detected: {circular}")

        # Check: reasonable duration
        if plan.estimated_duration > 300:
            issues.append(
                f"Estimated duration {plan.estimated_duration}s exceeds 300s limit"
            )
            suggestions.append("Consider breaking this into smaller sub-plans")

        feasible = len(issues) == 0
        if not feasible and not suggestions:
            suggestions.append("Fix the listed issues and re-evaluate")

        return {"feasible": feasible, "issues": issues, "suggestions": suggestions}

    def adapt_plan(
        self,
        plan: ExecutionPlan,
        divergence: str,
    ) -> ExecutionPlan:
        """Adapt a plan when execution diverges from expectations.

        Takes the original plan and a description of what went wrong,
        then generates an adapted plan that accounts for the divergence.

        Args:
            plan: The original execution plan.
            divergence: Description of what went wrong.

        Returns:
            A new ExecutionPlan with status 'adapted'.
        """
        self._stats["plans_adapted"] += 1

        # Find remaining (not-yet-executed) steps — assume divergence
        # happens partway through, so we keep all steps but re-plan
        remaining = [
            {"step": s.step_number, "tool": s.tool, "action": s.action}
            for s in plan.steps
        ]

        if self._generate_fn is None:
            # Without a model, create a minimal adapted plan
            return ExecutionPlan(
                plan_id=str(uuid.uuid4()),
                task_description=plan.task_description,
                task_type=plan.task_type,
                steps=plan.steps,
                estimated_duration=plan.estimated_duration,
                tools_required=plan.tools_required,
                preconditions=plan.preconditions + [f"Divergence: {divergence}"],
                success_criteria=plan.success_criteria,
                created_at=time.time(),
                status="adapted",
            )

        prompt = _ADAPT_PROMPT.format(
            original_plan=plan.task_description,
            divergence=divergence,
            remaining_steps=json.dumps(remaining),
        )

        try:
            raw = self._generate_fn(prompt)
            parsed = self._parse_plan_response(raw)
            steps = parsed.get("steps", [])
            if not steps:
                # Keep original steps if adaptation parsing fails
                steps = plan.steps
            else:
                steps = self._build_steps(parsed["steps"])
        except Exception as e:
            logger.warning("Plan adaptation failed, keeping original steps: %s", e)
            steps = plan.steps

        return ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            task_description=plan.task_description,
            task_type=plan.task_type,
            steps=steps,
            estimated_duration=parsed.get("estimated_duration", plan.estimated_duration)
            if isinstance(steps, list) and steps != plan.steps
            else plan.estimated_duration,
            tools_required=list({s.tool for s in steps if s.tool}),
            preconditions=parsed.get("preconditions", plan.preconditions)
            if isinstance(steps, list) and steps != plan.steps
            else plan.preconditions,
            success_criteria=parsed.get("success_criteria", plan.success_criteria)
            if isinstance(steps, list) and steps != plan.steps
            else plan.success_criteria,
            created_at=time.time(),
            status="adapted",
        )

    def store_successful_plan(
        self,
        plan: ExecutionPlan,
        grimoire: Any | None = None,
    ) -> str:
        """Store a successful plan in Grimoire as a reusable workflow.

        Only stores plans with status 'completed'. Deduplicates
        against existing stored plans before writing.

        Args:
            plan: The successfully completed execution plan.
            grimoire: Grimoire instance (uses self._grimoire if None).

        Returns:
            Document ID of the stored plan, or empty string on failure.
        """
        store = grimoire or self._grimoire
        if store is None:
            logger.debug("No Grimoire available — plan not stored")
            return ""

        # Deduplicate: check for very similar existing plans
        try:
            existing = self.search_reusable_plans(plan.task_type, plan.task_description)
            for ex in existing:
                if self._plans_are_similar(plan, ex):
                    logger.debug("Similar plan already stored — skipping dedup")
                    return ""
        except Exception as e:
            logger.debug("Dedup check failed (non-critical): %s", e)

        # Serialize plan for storage
        plan_data = {
            "plan_id": plan.plan_id,
            "task_description": plan.task_description,
            "task_type": plan.task_type,
            "steps": [
                {
                    "step_number": s.step_number,
                    "tool": s.tool,
                    "action": s.action,
                    "input_from": s.input_from,
                    "expected_output": s.expected_output,
                    "fallback": s.fallback,
                }
                for s in plan.steps
            ],
            "estimated_duration": plan.estimated_duration,
            "tools_required": plan.tools_required,
            "preconditions": plan.preconditions,
            "success_criteria": plan.success_criteria,
        }

        try:
            doc_id = store.store(
                content=json.dumps(plan_data),
                metadata={
                    "category": "execution_plan",
                    "task_type": plan.task_type,
                    "tools_used": plan.tools_required,
                    "success_criteria": plan.success_criteria,
                    "created_at": plan.created_at,
                },
            )
            self._stats["plans_succeeded"] += 1
            return doc_id or ""
        except Exception as e:
            logger.warning("Failed to store plan in Grimoire: %s", e)
            return ""

    def search_reusable_plans(
        self,
        task_type: str,
        keywords: str = "",
    ) -> list[ExecutionPlan]:
        """Search Grimoire for stored execution plans matching task type.

        Args:
            task_type: The type of task to search for.
            keywords: Additional keywords to refine the search.

        Returns:
            List of ExecutionPlan objects found in storage.
        """
        if self._grimoire is None:
            return []

        query = f"{task_type} {keywords}".strip()

        try:
            results = self._grimoire.search(
                query=query,
                category="execution_plan",
            )
        except Exception as e:
            logger.debug("Grimoire search failed: %s", e)
            return []

        plans: list[ExecutionPlan] = []
        for result in results or []:
            try:
                content = result if isinstance(result, str) else result.get("content", "")
                data = json.loads(content)
                plan = self._dict_to_plan(data)
                if plan is not None:
                    plans.append(plan)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.debug("Failed to parse stored plan: %s", e)
                continue

        return plans

    def get_planning_stats(self) -> dict:
        """Return planning statistics for the Growth Engine.

        Returns:
            Dict with plans_created, plans_reused, plans_adapted,
            avg_steps_per_plan, and success_rate.
        """
        created = self._stats["plans_created"]
        succeeded = self._stats["plans_succeeded"]

        avg_steps = (
            self._stats["total_steps"] / created if created > 0 else 0.0
        )
        success_rate = succeeded / created if created > 0 else 0.0

        return {
            "plans_created": created,
            "plans_reused": self._stats["plans_reused"],
            "plans_adapted": self._stats["plans_adapted"],
            "avg_steps_per_plan": round(avg_steps, 2),
            "success_rate": round(success_rate, 3),
        }

    # --- Private helpers ---

    def _find_reusable_plan(self, task: str) -> ExecutionPlan | None:
        """Search Grimoire for a reusable plan matching this task."""
        if self._grimoire is None:
            return None

        try:
            results = self._grimoire.search(
                query=task,
                category="execution_plan",
            )
            if not results:
                return None

            # Take the best match
            first = results[0]
            content = first if isinstance(first, str) else first.get("content", "")
            data = json.loads(content)
            return self._dict_to_plan(data)
        except Exception as e:
            logger.debug("Reusable plan search failed: %s", e)
            return None

    def _adapt_existing_plan(
        self,
        existing: ExecutionPlan,
        task: str,
        available_tools: list[str],
    ) -> ExecutionPlan:
        """Adapt an existing reusable plan to a new task."""
        return ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            task_description=task,
            task_type=existing.task_type,
            steps=existing.steps,
            estimated_duration=existing.estimated_duration,
            tools_required=existing.tools_required,
            preconditions=existing.preconditions,
            success_criteria=existing.success_criteria,
            created_at=time.time(),
            status="planned",
        )

    def _generate_new_plan(
        self,
        task: str,
        available_tools: list[str],
        context: str,
    ) -> ExecutionPlan:
        """Generate a brand new plan using the model."""
        if self._generate_fn is None:
            # No model — return single-step direct execution plan
            return self._single_step_plan(task, available_tools)

        prompt = _PLAN_PROMPT.format(
            task=task,
            available_tools=", ".join(available_tools) if available_tools else "none specified",
            context=context or "none",
        )

        try:
            raw = self._generate_fn(prompt)
            parsed = self._parse_plan_response(raw)
        except Exception as e:
            logger.warning("Plan generation failed, using single-step fallback: %s", e)
            return self._single_step_plan(task, available_tools)

        steps = self._build_steps(parsed.get("steps", []))
        if not steps:
            return self._single_step_plan(task, available_tools)

        return ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            task_description=task,
            task_type=parsed.get("task_type", "general"),
            steps=steps,
            estimated_duration=float(parsed.get("estimated_duration", 30)),
            tools_required=list({s.tool for s in steps if s.tool}),
            preconditions=parsed.get("preconditions", []),
            success_criteria=parsed.get("success_criteria", "Task completed successfully"),
            created_at=time.time(),
            status="planned",
        )

    def _single_step_plan(
        self,
        task: str,
        available_tools: list[str],
    ) -> ExecutionPlan:
        """Create a minimal single-step fallback plan."""
        tool = available_tools[0] if available_tools else "direct"
        step = PlanStep(
            step_number=1,
            tool=tool,
            action=task,
            input_from="user_input",
            expected_output="Task completed",
            fallback="Report failure to user",
        )
        return ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            task_description=task,
            task_type="general",
            steps=[step],
            estimated_duration=30.0,
            tools_required=[tool] if tool != "direct" else [],
            preconditions=[],
            success_criteria="Task completed successfully",
            created_at=time.time(),
            status="planned",
        )

    def _parse_plan_response(self, raw: str) -> dict:
        """Parse JSON from model response, handling markdown fences."""
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", raw)
        cleaned = cleaned.strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

        # Try to find JSON object in the response
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]

        return json.loads(cleaned)

    def _build_steps(self, step_dicts: list[dict]) -> list[PlanStep]:
        """Convert a list of step dicts into PlanStep objects."""
        steps: list[PlanStep] = []
        for i, sd in enumerate(step_dicts):
            steps.append(
                PlanStep(
                    step_number=i + 1,
                    tool=sd.get("tool", ""),
                    action=sd.get("action", ""),
                    input_from=sd.get("input_from", "user_input"),
                    expected_output=sd.get("expected_output", ""),
                    fallback=sd.get("fallback", "Skip step"),
                )
            )
        return steps

    def _dict_to_plan(self, data: dict) -> ExecutionPlan | None:
        """Convert a stored dict back to an ExecutionPlan."""
        try:
            steps = [
                PlanStep(
                    step_number=s.get("step_number", i + 1),
                    tool=s.get("tool", ""),
                    action=s.get("action", ""),
                    input_from=s.get("input_from", "user_input"),
                    expected_output=s.get("expected_output", ""),
                    fallback=s.get("fallback", ""),
                )
                for i, s in enumerate(data.get("steps", []))
            ]
            return ExecutionPlan(
                plan_id=data.get("plan_id", str(uuid.uuid4())),
                task_description=data.get("task_description", ""),
                task_type=data.get("task_type", "general"),
                steps=steps,
                estimated_duration=float(data.get("estimated_duration", 30)),
                tools_required=data.get("tools_required", []),
                preconditions=data.get("preconditions", []),
                success_criteria=data.get("success_criteria", ""),
                created_at=data.get("created_at", 0),
                status=data.get("status", "planned"),
            )
        except Exception as e:
            logger.debug("Failed to reconstruct ExecutionPlan from dict: %s", e)
            return None

    def _plans_are_similar(self, a: ExecutionPlan, b: ExecutionPlan) -> bool:
        """Check if two plans are similar enough to be considered duplicates."""
        if a.task_type != b.task_type:
            return False
        if len(a.steps) != len(b.steps):
            return False
        # Check if same tools are used in same order
        a_tools = [s.tool for s in a.steps]
        b_tools = [s.tool for s in b.steps]
        return a_tools == b_tools

    def _detect_circular_deps(self, steps: list[PlanStep]) -> str:
        """Detect circular dependencies in step references.

        Returns a description of the cycle if found, empty string otherwise.
        """
        # Build dependency graph
        deps: dict[int, list[int]] = {}
        for step in steps:
            deps[step.step_number] = []
            if step.input_from and step.input_from.startswith("step_"):
                try:
                    ref = int(step.input_from.split("_")[1])
                    deps[step.step_number].append(ref)
                except (ValueError, IndexError):
                    pass

        # DFS cycle detection
        visited: set[int] = set()
        in_stack: set[int] = set()

        def dfs(node: int) -> str:
            visited.add(node)
            in_stack.add(node)
            for neighbor in deps.get(node, []):
                if neighbor in in_stack:
                    return f"step_{node} -> step_{neighbor}"
                if neighbor not in visited:
                    result = dfs(neighbor)
                    if result:
                        return result
            in_stack.discard(node)
            return ""

        for node in deps:
            if node not in visited:
                result = dfs(node)
                if result:
                    return result

        return ""
