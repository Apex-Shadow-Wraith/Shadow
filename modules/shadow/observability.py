"""
Shadow Observability — Langfuse Tracing
==========================================
Provides a decorator that wraps the orchestrator's process_input()
to emit traces to Langfuse. Degrades gracefully if Langfuse is not
configured — Shadow never crashes because of observability.
"""

from __future__ import annotations

import functools
import logging
import os
import time
from typing import Any

logger = logging.getLogger("shadow.observability")

# Graceful import — observability is optional
try:
    from langfuse import Langfuse

    _LANGFUSE_AVAILABLE = True
except ImportError:
    _LANGFUSE_AVAILABLE = False
    logger.info("langfuse not installed — tracing disabled")


def _get_langfuse_client() -> Any | None:
    """Return a Langfuse client if credentials are configured, else None."""
    if not _LANGFUSE_AVAILABLE:
        return None

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        logger.debug("Langfuse keys not set — tracing disabled")
        return None

    try:
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
    except Exception as e:
        logger.warning("Failed to initialize Langfuse client: %s", e)
        return None


def trace_interaction(func):
    """Decorator for Orchestrator.process_input().

    Emits a Langfuse trace with input, output, module routing,
    tools called, latency, and whether Apex (external API) was used.
    Silently no-ops if Langfuse is unavailable or misconfigured.
    """

    @functools.wraps(func)
    async def wrapper(self, user_input: str, source: str = "user") -> str:
        client = _get_langfuse_client()

        if client is None:
            return await func(self, user_input, source)

        start = time.time()
        trace = None
        try:
            trace = client.trace(
                name="shadow.process_input",
                input={"user_input": user_input, "source": source},
                metadata={"interaction_count": self._state.interaction_count + 1},
            )
        except Exception as e:
            logger.debug("Failed to create Langfuse trace: %s", e)
            return await func(self, user_input, source)

        try:
            response = await func(self, user_input, source)
        except Exception:
            if trace is not None:
                try:
                    trace.update(
                        output={"error": "decision_loop_exception"},
                        metadata={"latency_ms": round((time.time() - start) * 1000)},
                        level="ERROR",
                    )
                    client.flush()
                except Exception:
                    pass
            raise

        latency_ms = round((time.time() - start) * 1000)

        # Extract metadata from the orchestrator's internal state
        try:
            metadata: dict[str, Any] = {
                "latency_ms": latency_ms,
                "source": source,
            }

            # Module used — pulled from the last classification if available
            # The orchestrator logs classification in step 2; we inspect
            # conversation history length as a proxy for execution path.
            if hasattr(self, "_last_classification"):
                cls = self._last_classification
                metadata["module_used"] = cls.target_module
                metadata["task_type"] = cls.task_type.value
                metadata["complexity"] = cls.complexity
                metadata["apex_used"] = cls.brain.value == "smart_brain"

            trace.update(
                output={"response": response[:500]},
                metadata=metadata,
            )
            client.flush()
        except Exception as e:
            logger.debug("Failed to update Langfuse trace: %s", e)

        return response

    return wrapper
