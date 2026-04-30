"""
Tests for RetryEngine — 12-Attempt Strategy Rotation with Apex Escalation-Learning
====================================================================================
Tests the full retry cycle, strategy rotation, escalation, teaching,
Grimoire storage, and session history.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from modules.shadow.retry_engine import (
    RetryEngine,
    RetrySession,
    Attempt,
    STRATEGY_CATEGORIES,
    FailureType,
    classify_failure,
)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """Fresh RetryEngine instance."""
    return RetryEngine(registry=None, config={})


def make_evaluate_fn(succeed_on: int | None = None):
    """Create an evaluate_fn that succeeds on a specific attempt number.

    Args:
        succeed_on: Attempt number (1-based) to succeed on. None = always fail.
    """
    call_count = {"n": 0}

    def evaluate(result):
        call_count["n"] += 1
        if succeed_on is not None and call_count["n"] >= succeed_on:
            return {"success": True, "confidence": 0.9, "reason": "looks good"}
        return {"success": False, "confidence": 0.2, "reason": "not sufficient"}

    return evaluate


async def mock_execute_fn(task, strategy_context):
    """Mock execute function that returns a basic result."""
    return {
        "response": f"Result for strategy: {strategy_context.get('strategy', 'unknown')}",
        "strategy_used": strategy_context.get("strategy", "unknown"),
    }


async def mock_execute_fn_error(task, strategy_context):
    """Mock execute function that always raises."""
    raise RuntimeError("execution failed")


# ── Test: First attempt succeeds ─────────────────────────────────────

@pytest.mark.asyncio
async def test_first_attempt_succeeds(engine):
    """First attempt succeeds — returns immediately, no retries."""
    result = await engine.attempt_task(
        task="What is 2+2?",
        module="cipher",
        context={"task_type": "math"},
        evaluate_fn=make_evaluate_fn(succeed_on=1),
        execute_fn=mock_execute_fn,
    )

    assert result["status"] == "succeeded"
    assert len(result["attempts"]) == 1
    assert result["attempts"][0]["success"] is True
    assert result["attempts"][0]["strategy"] == "direct"
    assert result["final_result"] is not None


# ── Test: Failed attempts use different strategies ────────────────────

@pytest.mark.asyncio
async def test_different_strategies_each_attempt(engine):
    """Each failed attempt uses a different strategy category."""
    result = await engine.attempt_task(
        task="Complex task",
        module="wraith",
        context={"task_type": "analysis"},
        evaluate_fn=make_evaluate_fn(succeed_on=None),  # Always fail
        execute_fn=mock_execute_fn,
    )

    strategies_used = [a["strategy"] for a in result["attempts"]]
    # All 12 should be unique
    assert len(strategies_used) == 12
    assert len(set(strategies_used)) == 12


# ── Test: All 12 strategy categories used before exhaustion ──────────

@pytest.mark.asyncio
async def test_all_12_categories_used(engine):
    """All 12 strategy categories are used before declaring exhaustion."""
    result = await engine.attempt_task(
        task="Unsolvable task",
        module="cipher",
        context={"task_type": "logic"},
        evaluate_fn=make_evaluate_fn(succeed_on=None),
        execute_fn=mock_execute_fn,
    )

    strategies_used = set(a["strategy"] for a in result["attempts"])
    expected = set(name for name, _ in STRATEGY_CATEGORIES)
    assert strategies_used == expected
    assert result["status"] == "exhausted"
    assert result["exhausted"] is True
    assert result["ready_to_escalate"] is True


# ── Test: Failure patterns loaded from Grimoire ──────────────────────

@pytest.mark.asyncio
async def test_failure_patterns_loaded_from_grimoire(engine):
    """Previous failure patterns are loaded from Grimoire before first attempt."""
    grimoire_patterns = [
        {"content": "When doing math, always check units first"},
        {"content": "Avoid floating point comparison for equality"},
    ]

    def mock_grimoire_search(query):
        assert "failure_pattern" in query
        return grimoire_patterns

    contexts_seen = []
    original_execute = mock_execute_fn

    async def capture_execute(task, strategy_context):
        contexts_seen.append(strategy_context)
        return await original_execute(task, strategy_context)

    result = await engine.attempt_task(
        task="Calculate area",
        module="cipher",
        context={"task_type": "math"},
        evaluate_fn=make_evaluate_fn(succeed_on=1),
        execute_fn=capture_execute,
        grimoire_search_fn=mock_grimoire_search,
    )

    assert result["status"] == "succeeded"
    # The failure context should have been passed to the strategy context
    assert len(contexts_seen) >= 1
    ctx = contexts_seen[0]
    assert "failure_context" in ctx
    assert "check units" in ctx["failure_context"]


# ── Test: Progress notifications at attempts 4, 8, 12 ────────────────

@pytest.mark.asyncio
async def test_progress_notifications(engine):
    """Progress notifications fire at attempts 4, 8, and 12."""
    notifications = []

    async def mock_notify(msg):
        notifications.append(msg)

    result = await engine.attempt_task(
        task="Hard task",
        module="wraith",
        context={"task_type": "research"},
        evaluate_fn=make_evaluate_fn(succeed_on=None),
        execute_fn=mock_execute_fn,
        notify_fn=mock_notify,
    )

    assert len(notifications) == 3
    assert "Tried 3 approaches" in notifications[0]
    assert "Tried 7 approaches" in notifications[1]
    assert "Exhausted 12 approaches" in notifications[2]


# ── Test: No notifications when succeeding early ──────────────────────

@pytest.mark.asyncio
async def test_no_notifications_on_early_success(engine):
    """No progress notifications when task succeeds before attempt 4."""
    notifications = []

    async def mock_notify(msg):
        notifications.append(msg)

    await engine.attempt_task(
        task="Easy task",
        module="wraith",
        context={"task_type": "question"},
        evaluate_fn=make_evaluate_fn(succeed_on=2),
        execute_fn=mock_execute_fn,
        notify_fn=mock_notify,
    )

    assert len(notifications) == 0


# ── Test: Escalation sends task + failures to Apex ────────────────────

@pytest.mark.asyncio
async def test_escalation_sends_to_apex(engine):
    """Escalation sends the original task and failure summary to Apex."""
    apex_queries = []
    apex_teach_calls = []

    async def mock_apex_query(task):
        apex_queries.append(task)
        return "The answer is 42."

    async def mock_apex_teach(prompt):
        apex_teach_calls.append(prompt)
        return "You were overcomplicating it. The key principle is simplicity."

    # Build a session that's been exhausted
    session = RetrySession(
        original_task="What is the meaning of life?",
        task_type="philosophy",
        module="cipher",
        status="exhausted",
    )
    for i in range(12):
        session.attempts.append(Attempt(
            attempt_number=i + 1,
            strategy=STRATEGY_CATEGORIES[i][0],
            approach_description=STRATEGY_CATEGORIES[i][1],
            tools_used=[],
            error=f"Failed approach {i + 1}",
            success=False,
            duration_seconds=1.0,
        ))

    result = await engine.escalate_to_apex(
        session=session,
        apex_query_fn=mock_apex_query,
        apex_teach_fn=mock_apex_teach,
    )

    assert result["success"] is True
    assert result["answer"] == "The answer is 42."
    assert len(apex_queries) == 1
    assert apex_queries[0] == "What is the meaning of life?"


# ── Test: Teaching follow-up asks "how did you solve this" ────────────

@pytest.mark.asyncio
async def test_escalation_teaching_followup(engine):
    """The teaching follow-up asks Apex to explain its approach vs our failures."""
    teach_prompts = []

    async def mock_apex_query(task):
        return "Answer here."

    async def mock_apex_teach(prompt):
        teach_prompts.append(prompt)
        return "Teaching explanation."

    session = RetrySession(
        original_task="Hard problem",
        task_type="analysis",
        module="wraith",
        status="exhausted",
    )
    session.attempts.append(Attempt(
        attempt_number=1,
        strategy="direct",
        approach_description="Direct attempt",
        tools_used=[],
        error="Failed",
        success=False,
        duration_seconds=0.5,
    ))

    await engine.escalate_to_apex(
        session=session,
        apex_query_fn=mock_apex_query,
        apex_teach_fn=mock_apex_teach,
    )

    assert len(teach_prompts) == 1
    prompt = teach_prompts[0]
    assert "Hard problem" in prompt
    assert "failed approaches" in prompt.lower() or "12 failed" in prompt
    assert "successful answer" in prompt.lower()
    assert "what I was doing wrong" in prompt


# ── Test: Three Grimoire entries stored after escalation ──────────────

@pytest.mark.asyncio
async def test_three_grimoire_entries_stored(engine):
    """After escalation, three entries are stored: answer, teaching, failure_pattern."""
    stored_entries = []

    async def mock_apex_query(task):
        return "Apex answer"

    async def mock_apex_teach(prompt):
        return "Apex teaching"

    def mock_grimoire_store(content, tags, trust_level):
        stored_entries.append({
            "content": content,
            "tags": tags,
            "trust_level": trust_level,
        })
        return f"entry_{len(stored_entries)}"

    session = RetrySession(
        original_task="Test task",
        task_type="code_generation",
        module="omen",
        status="exhausted",
    )
    session.attempts.append(Attempt(
        attempt_number=1, strategy="direct",
        approach_description="Direct", tools_used=[],
        error="Failed", success=False, duration_seconds=0.1,
    ))

    result = await engine.escalate_to_apex(
        session=session,
        apex_query_fn=mock_apex_query,
        apex_teach_fn=mock_apex_teach,
        grimoire_store_fn=mock_grimoire_store,
    )

    assert len(stored_entries) == 3

    # Entry 1: answer (apex_sourced)
    assert "apex_sourced" in stored_entries[0]["tags"]
    assert stored_entries[0]["trust_level"] == 0.7
    assert "Apex answer" in stored_entries[0]["content"]

    # Entry 2: teaching (apex_learning)
    assert "apex_learning" in stored_entries[1]["tags"]
    assert stored_entries[1]["trust_level"] == 0.7
    assert "Apex teaching" in stored_entries[1]["content"]

    # Entry 3: failure pattern
    assert "failure_pattern" in stored_entries[2]["tags"]
    assert stored_entries[2]["trust_level"] == 0.7

    assert len(result["grimoire_ids"]) == 3


# ── Test: Local re-verification attempted after learning ──────────────

@pytest.mark.asyncio
async def test_local_reverification(engine):
    """After escalation, a local re-verification attempt is made."""
    verify_calls = []

    async def mock_apex_query(task):
        return "The answer"

    async def mock_apex_teach(prompt):
        return "The teaching"

    async def mock_verify_execute(task, context):
        verify_calls.append({"task": task, "context": context})
        return {"response": "verified result"}

    session = RetrySession(
        original_task="Verify this",
        task_type="test",
        module="wraith",
        status="exhausted",
    )

    result = await engine.escalate_to_apex(
        session=session,
        apex_query_fn=mock_apex_query,
        apex_teach_fn=mock_apex_teach,
        execute_fn=mock_verify_execute,
    )

    assert len(verify_calls) == 1
    assert result["local_verification_passed"] is True


# ── Test: should_escalate returns False before 12 attempts ────────────

def test_should_escalate_false_before_12(engine):
    """should_escalate returns False when fewer than 12 attempts have been made."""
    session = RetrySession(
        original_task="Test",
        status="attempting",
    )
    for i in range(11):
        session.attempts.append(Attempt(
            attempt_number=i + 1, strategy=f"strat_{i}",
            approach_description="test", tools_used=[],
            error="failed", success=False, duration_seconds=0.1,
        ))

    assert engine.should_escalate(session) is False


def test_should_escalate_true_at_12(engine):
    """should_escalate returns True when all 12 attempts are exhausted."""
    session = RetrySession(
        original_task="Test",
        status="exhausted",
    )
    for i in range(12):
        session.attempts.append(Attempt(
            attempt_number=i + 1, strategy=f"strat_{i}",
            approach_description="test", tools_used=[],
            error="failed", success=False, duration_seconds=0.1,
        ))

    assert engine.should_escalate(session) is True


# ── Test: should_escalate True for hardware impossibility ─────────────

def test_should_escalate_true_for_hardware_impossibility(engine):
    """should_escalate returns True for hardware impossibility even before 12."""
    session = RetrySession(
        original_task="GPU task",
        status="attempting",
    )
    session.attempts.append(Attempt(
        attempt_number=1, strategy="direct",
        approach_description="Direct GPU attempt", tools_used=[],
        error="CUDA out of memory — need more VRAM",
        success=False, duration_seconds=0.5,
    ))

    assert engine.should_escalate(session) is True


def test_should_escalate_impossibility_network(engine):
    """should_escalate returns True for network impossibility."""
    session = RetrySession(original_task="Web task", status="attempting")
    session.attempts.append(Attempt(
        attempt_number=1, strategy="direct",
        approach_description="Web request", tools_used=[],
        error="Network unreachable — no internet connection",
        success=False, duration_seconds=0.1,
    ))

    assert engine.should_escalate(session) is True


# ── Test: should_escalate works with dict input ───────────────────────

def test_should_escalate_with_dict(engine):
    """should_escalate works with dict representation of session."""
    session_dict = {
        "attempts": [{"error": "failed"} for _ in range(12)],
        "max_attempts": 12,
        "status": "exhausted",
    }
    assert engine.should_escalate(session_dict) is True

    partial_dict = {
        "attempts": [{"error": "failed"} for _ in range(5)],
        "max_attempts": 12,
        "status": "attempting",
    }
    assert engine.should_escalate(partial_dict) is False


# ── Test: get_strategy_for_attempt never returns repeated strategy ────

def test_get_strategy_never_repeats(engine):
    """get_strategy_for_attempt never returns a repeated strategy within a session."""
    attempts = []
    seen = set()

    for i in range(1, 13):
        name, desc = engine.get_strategy_for_attempt(i, attempts)
        assert name not in seen, f"Strategy '{name}' repeated at attempt {i}"
        seen.add(name)
        attempts.append(Attempt(
            attempt_number=i, strategy=name,
            approach_description=desc, tools_used=[],
            error="failed", success=False, duration_seconds=0.1,
        ))

    assert len(seen) == 12


# ── Test: Session history records all attempts ────────────────────────

@pytest.mark.asyncio
async def test_session_history(engine):
    """Session history records completed sessions with all attempts."""
    # Run two tasks
    await engine.attempt_task(
        task="Task 1",
        module="wraith",
        context={"task_type": "question"},
        evaluate_fn=make_evaluate_fn(succeed_on=1),
        execute_fn=mock_execute_fn,
    )
    await engine.attempt_task(
        task="Task 2",
        module="cipher",
        context={"task_type": "math"},
        evaluate_fn=make_evaluate_fn(succeed_on=2),
        execute_fn=mock_execute_fn,
    )

    history = engine.get_session_history(limit=20)
    assert len(history) == 2

    # Most recent first
    assert history[0]["original_task"] == "Task 2"
    assert history[1]["original_task"] == "Task 1"

    # Task 2 took 2 attempts
    assert len(history[0]["attempts"]) == 2
    # Task 1 took 1 attempt
    assert len(history[1]["attempts"]) == 1


# ── Test: Exception in execute_fn doesn't crash ──────────────────────

@pytest.mark.asyncio
async def test_execute_fn_exception_handled(engine):
    """Exceptions in execute_fn are caught and recorded as failures."""
    result = await engine.attempt_task(
        task="Crashy task",
        module="wraith",
        context={"task_type": "test"},
        evaluate_fn=make_evaluate_fn(succeed_on=None),
        execute_fn=mock_execute_fn_error,
    )

    assert result["status"] == "exhausted"
    for attempt in result["attempts"]:
        assert attempt["success"] is False
        assert "execution failed" in attempt["error"]


# ── Test: Succeed on later attempt ────────────────────────────────────

@pytest.mark.asyncio
async def test_succeed_on_fifth_attempt(engine):
    """Task succeeds on the 5th attempt after 4 failures."""
    result = await engine.attempt_task(
        task="Moderate task",
        module="cipher",
        context={"task_type": "math"},
        evaluate_fn=make_evaluate_fn(succeed_on=5),
        execute_fn=mock_execute_fn,
    )

    assert result["status"] == "succeeded"
    assert len(result["attempts"]) == 5
    assert result["attempts"][4]["success"] is True
    # First 4 should have failed
    for i in range(4):
        assert result["attempts"][i]["success"] is False


# ── Test: Hardware impossibility causes early exit ────────────────────

@pytest.mark.asyncio
async def test_hardware_impossibility_early_exit(engine):
    """Hardware impossibility detected in error causes early exit."""
    call_count = {"n": 0}

    async def oom_execute(task, ctx):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("CUDA out of memory")
        return {"response": "ok"}

    result = await engine.attempt_task(
        task="GPU task",
        module="omen",
        context={"task_type": "code"},
        evaluate_fn=make_evaluate_fn(succeed_on=None),
        execute_fn=oom_execute,
    )

    assert result["status"] == "exhausted"
    assert result["impossibility_detected"] is True
    assert len(result["attempts"]) == 2  # Stopped early


# ── Test: Escalation with dict session ────────────────────────────────

@pytest.mark.asyncio
async def test_escalation_with_dict_session(engine):
    """escalate_to_apex works when given a dict instead of RetrySession."""
    session_dict = {
        "session_id": "test-123",
        "original_task": "Dict task",
        "task_type": "general",
        "module": "wraith",
        "attempts": [
            {
                "attempt_number": 1,
                "strategy": "direct",
                "approach_description": "Direct attempt",
                "tools_used": [],
                "error": "Failed",
                "success": False,
                "duration_seconds": 0.5,
            }
        ],
    }

    async def mock_apex_query(task):
        return "Answer from dict session"

    async def mock_apex_teach(prompt):
        return "Teaching from dict session"

    result = await engine.escalate_to_apex(
        session=session_dict,
        apex_query_fn=mock_apex_query,
        apex_teach_fn=mock_apex_teach,
    )

    assert result["success"] is True
    assert result["answer"] == "Answer from dict session"


# ── Test: Strategy categories count ───────────────────────────────────

def test_strategy_categories_count():
    """Verify there are exactly 12 strategy categories."""
    assert len(STRATEGY_CATEGORIES) == 12
    names = [name for name, _ in STRATEGY_CATEGORIES]
    assert len(set(names)) == 12  # All unique


# ── Test: Grimoire search failure doesn't crash ───────────────────────

@pytest.mark.asyncio
async def test_grimoire_search_failure_graceful(engine):
    """Grimoire search failure is handled gracefully."""
    def broken_search(query):
        raise ConnectionError("Grimoire offline")

    result = await engine.attempt_task(
        task="Task with broken grimoire",
        module="wraith",
        context={"task_type": "test"},
        evaluate_fn=make_evaluate_fn(succeed_on=1),
        execute_fn=mock_execute_fn,
        grimoire_search_fn=broken_search,
    )

    assert result["status"] == "succeeded"


# ── Test: Infrastructure failure does NOT increment fatigue ──────────

@pytest.mark.asyncio
async def test_infrastructure_failure_no_fatigue(engine):
    """Infrastructure failures (tool_loader empty) do NOT increment fatigue."""
    assert engine.fatigue_counter == 0

    async def infra_fail_execute(task, ctx):
        return {
            "response": "",
            "results": [],
            "tool_loader_empty": True,
            "infrastructure_error": True,
        }

    def infra_evaluate(result):
        if result.get("tool_loader_empty"):
            return {
                "success": False,
                "confidence": 0.0,
                "reason": "Tool loader empty — infrastructure issue",
            }
        return {"success": False, "confidence": 0.0, "reason": "failed"}

    result = await engine.attempt_task(
        task="Task with empty tool loader",
        module="wraith",
        context={"task_type": "test"},
        evaluate_fn=infra_evaluate,
        execute_fn=infra_fail_execute,
    )

    # Fatigue counter should NOT have incremented
    assert engine.fatigue_counter == 0
    assert result.get("infrastructure_failure") is True


# ── Test: Model failure DOES increment fatigue ──────────────────────

@pytest.mark.asyncio
async def test_model_failure_increments_fatigue(engine):
    """Model failures (bad LLM output) DO increment fatigue."""
    assert engine.fatigue_counter == 0

    result = await engine.attempt_task(
        task="Task that model fails",
        module="wraith",
        context={"task_type": "test"},
        evaluate_fn=make_evaluate_fn(succeed_on=None),  # Always fail
        execute_fn=mock_execute_fn,
    )

    # All 12 attempts should have incremented fatigue
    assert engine.fatigue_counter == 12
    assert result["status"] == "exhausted"


# ── Test: Early exit on empty tool_loader (1 attempt, not 12) ────────

@pytest.mark.asyncio
async def test_early_exit_on_tool_loader_empty(engine):
    """When tool_loader returns empty on first attempt, skip ALL remaining retries."""
    call_count = {"n": 0}

    async def counting_execute(task, ctx):
        call_count["n"] += 1
        return {
            "response": "",
            "results": [],
            "tool_loader_empty": True,
            "infrastructure_error": True,
        }

    def infra_evaluate(result):
        if result.get("tool_loader_empty"):
            return {
                "success": False,
                "confidence": 0.0,
                "reason": "Tool loader empty — infrastructure issue",
            }
        return {"success": False, "confidence": 0.0, "reason": "failed"}

    result = await engine.attempt_task(
        task="Task with tool loader down",
        module="wraith",
        context={"task_type": "test"},
        evaluate_fn=infra_evaluate,
        execute_fn=counting_execute,
    )

    # Only 1 attempt, not 12
    assert call_count["n"] == 1
    assert len(result["attempts"]) == 1
    assert result.get("infrastructure_failure") is True
    assert result["status"] == "exhausted"
    # Should NOT be ready to escalate (infrastructure problem, not model problem)
    assert result.get("ready_to_escalate") is False


# ── Test: Marker-classified infra failure with populated loader retries ──
# Bug 3: if an error string matches _INFRASTRUCTURE_MARKERS but the loader
# is NOT genuinely empty (no tool_loader_empty flag in result), the retry
# engine must rotate strategies instead of bailing on attempt 1.

@pytest.mark.asyncio
async def test_marker_classified_infra_failure_does_not_bail(engine):
    """Bug 3: a marker-matched 'infrastructure' error with no
    tool_loader_empty signal must let the retry loop continue.
    Regression for Phase 0 benchmark where single-module failures caused
    immediate bail-out instead of strategy rotation."""
    call_count = {"n": 0}

    async def module_level_failure_execute(task, ctx):
        # The loader is populated, but this module's tools happen to
        # fail. The error text happens to match an infra marker.
        call_count["n"] += 1
        return {
            "response": "",
            "results": [],
            # Notably: NO tool_loader_empty flag — loader is healthy,
            # this is a single-module issue.
        }

    def marker_evaluate(result):
        # "tool execution errors" is in _INFRASTRUCTURE_MARKERS, so
        # classify_failure will return INFRASTRUCTURE even though
        # tool_loader_empty is False.
        return {
            "success": False,
            "confidence": 0.0,
            "reason": "Tool execution errors on module 'nova'",
        }

    result = await engine.attempt_task(
        task="Module-level failure",
        module="nova",
        context={"task_type": "content"},
        evaluate_fn=marker_evaluate,
        execute_fn=module_level_failure_execute,
    )

    # Must retry — not bail on attempt 1.
    assert call_count["n"] > 1, (
        f"Bug 3: retry engine bailed after {call_count['n']} attempt(s) "
        f"when loader was populated but error looked like infrastructure; "
        f"should have rotated strategies."
    )
    # Multiple attempt records should exist.
    assert len(result["attempts"]) > 1


@pytest.mark.asyncio
async def test_empty_loader_still_bails_on_first_attempt(engine):
    """Bug 3: preserves the existing bail-out for genuinely empty index.
    When result explicitly signals tool_loader_empty=True, we must NOT
    retry — that would waste 12 attempts on identical infrastructure
    failures. This is the existing contract the fix must preserve."""
    call_count = {"n": 0}

    async def empty_loader_execute(task, ctx):
        call_count["n"] += 1
        return {
            "response": "",
            "results": [],
            "tool_loader_empty": True,  # explicit signal from orchestrator
            "infrastructure_error": True,
        }

    def evaluate(result):
        return {
            "success": False,
            "confidence": 0.0,
            "reason": "Tool loader empty — infrastructure issue",
        }

    result = await engine.attempt_task(
        task="All modules offline",
        module="wraith",
        context={"task_type": "test"},
        evaluate_fn=evaluate,
        execute_fn=empty_loader_execute,
    )

    assert call_count["n"] == 1
    assert result["status"] == "exhausted"
    assert result.get("infrastructure_failure") is True
    assert result.get("ready_to_escalate") is False


# ── Test: /reset fatigue command works ───────────────────────────────

@pytest.mark.asyncio
async def test_reset_fatigue_command(engine):
    """/reset fatigue resets the fatigue counter to 0."""
    # Accumulate some fatigue from model failures
    await engine.attempt_task(
        task="Failing task",
        module="wraith",
        context={"task_type": "test"},
        evaluate_fn=make_evaluate_fn(succeed_on=None),
        execute_fn=mock_execute_fn,
    )
    assert engine.fatigue_counter > 0

    # Reset
    engine.reset_fatigue()
    assert engine.fatigue_counter == 0


# ── Test: classify_failure correctly identifies infrastructure ────────

def test_classify_failure_infrastructure_markers():
    """classify_failure identifies infrastructure errors from error strings."""
    assert classify_failure("Tool loader empty") == FailureType.INFRASTRUCTURE
    assert classify_failure("Network timeout on request") == FailureType.INFRASTRUCTURE
    assert classify_failure("Ollama not responding") == FailureType.INFRASTRUCTURE
    assert classify_failure("ChromaDB connection error") == FailureType.INFRASTRUCTURE
    assert classify_failure("Connection timed out") == FailureType.INFRASTRUCTURE


def test_classify_failure_model_markers():
    """classify_failure defaults to model failure for non-infrastructure errors."""
    assert classify_failure("not sufficient") == FailureType.MODEL
    assert classify_failure("Empty response") == FailureType.MODEL
    assert classify_failure("Low confidence score") == FailureType.MODEL
    assert classify_failure(None) == FailureType.MODEL


def test_classify_failure_from_result_dict():
    """classify_failure reads tool_loader_empty from result dict."""
    result = {"tool_loader_empty": True, "response": ""}
    assert classify_failure(None, result) == FailureType.INFRASTRUCTURE

    result = {"tool_loader_empty": False, "response": "some output"}
    assert classify_failure("bad format", result) == FailureType.MODEL


# ── Test: Failure type recorded in attempt data ──────────────────────

@pytest.mark.asyncio
async def test_failure_type_recorded_in_attempts(engine):
    """Each failed attempt records its failure_type classification."""
    result = await engine.attempt_task(
        task="Model-failing task",
        module="wraith",
        context={"task_type": "test"},
        evaluate_fn=make_evaluate_fn(succeed_on=None),
        execute_fn=mock_execute_fn,
    )

    for attempt in result["attempts"]:
        assert attempt["failure_type"] == FailureType.MODEL


# ── Test: Mixed infrastructure and model failures ────────────────────

@pytest.mark.asyncio
async def test_mixed_failure_types_fatigue(engine):
    """Only model failures increment fatigue, not infrastructure failures."""
    call_count = {"n": 0}

    async def mixed_execute(task, ctx):
        call_count["n"] += 1
        # First attempt succeeds to avoid early exit, then alternate
        return {
            "response": f"attempt {call_count['n']}",
            "results": [],
        }

    def mixed_evaluate(result):
        # Always fail but with different reasons
        resp = result.get("response", "")
        attempt_n = int(resp.split()[-1]) if resp else 0
        if attempt_n % 2 == 0:
            return {
                "success": False,
                "confidence": 0.0,
                "reason": "Ollama not responding",
            }
        return {
            "success": False,
            "confidence": 0.0,
            "reason": "Bad format from model",
        }

    result = await engine.attempt_task(
        task="Mixed failure task",
        module="wraith",
        context={"task_type": "test"},
        evaluate_fn=mixed_evaluate,
        execute_fn=mixed_execute,
    )

    # 12 attempts total: odd attempts (1,3,5,7,9,11) = model failures = 6
    # Even attempts (2,4,6,8,10,12) = infrastructure failures = 6
    assert engine.fatigue_counter == 6


# ── Test: "Tool execution errors" classified as infrastructure ────────

def test_classify_failure_tool_execution_errors():
    """Tool execution errors should be classified as infrastructure, not model.

    When the model generates a response but the tool framework rejects it
    (e.g. malformed tool-call JSON from Gemma 4), the model is not at fault.
    """
    assert classify_failure("Tool execution errors") == FailureType.INFRASTRUCTURE
    assert classify_failure(
        "Tool execution errors: invalid JSON in tool call"
    ) == FailureType.INFRASTRUCTURE


# ── Test: classify_failure identifies deterministic validation errors ─

def test_classify_failure_deterministic_markers():
    """B2: validation/schema errors classify as DETERMINISTIC."""
    # Wraith reminder_create validation failures
    assert classify_failure(
        "Reminder content is required"
    ) == FailureType.DETERMINISTIC
    assert classify_failure(
        "Importance must be an integer between 1 and 5"
    ) == FailureType.DETERMINISTIC
    assert classify_failure(
        "due_time must be a valid ISO datetime string"
    ) == FailureType.DETERMINISTIC
    assert classify_failure(
        "delay_minutes cannot be negative"
    ) == FailureType.DETERMINISTIC
    # General validation patterns
    assert classify_failure("Schema validation failed") == FailureType.DETERMINISTIC
    assert classify_failure("422 Unprocessable Entity") == FailureType.DETERMINISTIC


def test_classify_failure_deterministic_takes_priority_over_infrastructure():
    """Wraith errors propagated through orchestrator's evaluate_fn arrive as
    'Tool execution errors: <field> is required'.  DETERMINISTIC must win
    so retries short-circuit instead of rotating strategies on a permanent
    validation error."""
    assert classify_failure(
        "Tool execution errors: Reminder content is required"
    ) == FailureType.DETERMINISTIC


def test_classify_failure_regression_infrastructure_still_works():
    """Existing infrastructure markers still classify correctly after the
    DETERMINISTIC layer was added."""
    assert classify_failure("Network timeout") == FailureType.INFRASTRUCTURE
    assert classify_failure("Ollama unreachable") == FailureType.INFRASTRUCTURE


def test_classify_failure_regression_model_still_default():
    """Generic model failures still fall through to MODEL."""
    assert classify_failure("LLM returned malformed JSON") == FailureType.MODEL
    assert classify_failure("Low confidence on the answer") == FailureType.MODEL


# ── Test: DETERMINISTIC short-circuits the retry loop ────────────────

@pytest.mark.asyncio
async def test_deterministic_failure_short_circuits_retry():
    """B2: a deterministic failure on attempt 1 must not trigger 12 attempts.

    Mirrors the existing tool_loader_empty short-circuit but with
    ready_to_escalate=True (the input is fixable, just not by retrying)."""
    engine = RetryEngine(registry=None, config={})
    call_count = {"n": 0}

    async def execute_validation_error(task, ctx):
        call_count["n"] += 1
        return {
            "response": "",
            "results": [{
                "success": False,
                "error": "Reminder content is required",
            }],
        }

    def evaluate_validation_error(result):
        # Mirror orchestrator.evaluate_fn shape: tool error becomes
        # "Tool execution errors: <error>"
        tool_results = result.get("results", [])
        error_details = "; ".join(
            r.get("error", "") for r in tool_results
            if r.get("error") and not r.get("success", True)
        )
        reason = f"Tool execution errors: {error_details}"
        return {"success": False, "confidence": 0.0, "reason": reason}

    result = await engine.attempt_task(
        task="Create reminder with no content",
        module="wraith",
        context={"task_type": "action"},
        evaluate_fn=evaluate_validation_error,
        execute_fn=execute_validation_error,
    )

    assert call_count["n"] == 1, "Should short-circuit after first attempt"
    assert result["status"] == "deterministic_failure"
    assert result["ready_to_escalate"] is True
    assert result.get("deterministic_failure") is True
