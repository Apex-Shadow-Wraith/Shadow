"""Compilable LangGraph skeleton for the Track B cutover.

Bare ``StateGraph`` that compiles, persists a checkpoint, and ``ainvoke``s
end-to-end without touching any module or the live orchestrator path.

The state schema mirrors the design doc (§3.4 + §3.6):

- ``user_input``, ``classification``, ``plan``, ``response`` — request-scoped
  fields populated by later migration steps.
- ``tool_results`` — append-only via the ``add`` reducer so retry attempts and
  multi-tool plans accumulate naturally without overwriting each other.
- ``last_route`` — checkpointed cross-invocation routing memory. Replaces
  ``Orchestrator._last_route``; keyed by the LangGraph ``thread_id``
  (conversation ID) so resumes pick up where the prior turn left off.

Topology is a single pass-through node — Step 1 only validates that the
skeleton compiles, persists, and resumes. Module dispatch / routing / retry
land in later steps.

Naming note: the design doc uses ``last_route`` (not ``_last_route``). The
checkpointed state field drops the leading underscore because it is no longer
an orchestrator-private attribute; it is public graph state.
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from modules.base import ToolResult
from modules.shadow.orchestrator import ExecutionPlan, TaskClassification


class ShadowState(TypedDict, total=False):
    """Graph state schema for the Shadow orchestrator graph.

    ``total=False`` so nodes can return partial updates (only the fields they
    write). LangGraph merges partials into the running state; the ``add``
    reducer on ``tool_results`` appends rather than overwrites.
    """

    user_input: str
    classification: TaskClassification | None
    plan: ExecutionPlan | None
    tool_results: Annotated[list[ToolResult], add]
    response: str | None
    last_route: TaskClassification | None

    # --- Flip-step channels (Track B cutover) ---
    # ``source`` regularizes the de-facto undeclared key the dispatch node already
    # reads (dispatch_graph.py: ``state.get("source", "user")``); ``context`` is the
    # Step-3 loaded context the retry node needs to build its closures
    # (orchestrator._build_retry_closures). ``retry_result`` / ``status`` carry the
    # ``attempt_task`` session out of the retry node for the caller's response leg.
    # All four are JSON-primitives / plain dicts — they round-trip under the
    # JsonPlusSerializer (serde.py) with zero msgpack-allowlist involvement.
    source: str
    context: list[dict[str, Any]]
    retry_result: dict[str, Any]
    status: str


def _passthrough(state: ShadowState) -> ShadowState:
    """No-op node — returns no updates so state passes through unchanged."""
    return {}


def build_skeleton() -> StateGraph:
    """Construct the skeleton builder (not compiled — caller wires checkpointer).

    Returns the uncompiled ``StateGraph`` so tests can compile with whatever
    checkpointer / interrupt configuration they need.
    """
    builder = StateGraph(ShadowState)
    builder.add_node("passthrough", _passthrough)
    builder.add_edge(START, "passthrough")
    builder.add_edge("passthrough", END)
    return builder


def compile_skeleton(checkpointer: BaseCheckpointSaver):
    """Compile the skeleton with a caller-supplied async checkpointer.

    Caller is responsible for the checkpointer lifecycle. Use
    :func:`modules.shadow.graph.serde.open_async_sqlite_saver` to get a saver
    that already carries ``shadow_serde``.
    """
    return build_skeleton().compile(checkpointer=checkpointer)
