"""
Shadow Observability — Langfuse Tracing (v4 SDK)
=================================================

Single source of truth for trace export. Safe-fallback semantics:
observability calls swallow every exception and never raise out of
instrumentation paths. If Langfuse is uninstalled, disabled via the
``LANGFUSE_DISABLED`` env var, or missing keys, every helper here
no-ops cleanly.

Public surface:
    - trace_disabled() -> bool — True iff every emission should be skipped.
    - get_client()     -> Langfuse | None — cached client or None.
    - observed_span(name, **md) — context manager emitting one span.
    - trace_interaction(func) — async decorator wrapping the orchestrator's
      seven-step decision loop with a parent trace.

Bias / alignment disclosure: Langfuse is observability-only — no model
or alignment surface. MIT-licensed. The deploy/langfuse/ self-hosted
instance runs with TELEMETRY_ENABLED=false (no phone-home).
"""

from __future__ import annotations

import functools
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger("shadow.observability")

try:
    from langfuse import Langfuse

    _LANGFUSE_AVAILABLE = True
except ImportError:
    Langfuse = None  # type: ignore[assignment,misc]
    _LANGFUSE_AVAILABLE = False
    logger.info("langfuse not installed — tracing disabled")


def trace_disabled() -> bool:
    """Return True iff observability emissions should be a no-op.

    Reasons to disable:
        - SDK not installed
        - LANGFUSE_DISABLED env var set to a truthy string
    """
    if not _LANGFUSE_AVAILABLE:
        return True
    if os.environ.get("LANGFUSE_DISABLED", "").lower() in ("1", "true", "yes"):
        return True
    return False


# Cached client, populated on first get_client() call after the global
# config has been imported. Keyed by a single sentinel so _reset_client_cache
# can clear it cleanly in tests.
_client_cache: dict[str, Any] = {}


def get_client() -> Any | None:
    """Return cached Langfuse client, or None if disabled / misconfigured.

    Reads keys from the centralized ``shadow.config`` singleton — does not
    bypass the typed config layer. Falls back to None silently on any
    failure; observability never raises out of init.
    """
    if trace_disabled():
        return None
    if "client" in _client_cache:
        return _client_cache["client"]

    try:
        from shadow.config import config as _shadow_config
    except ImportError:
        logger.debug("shadow.config not importable — observability disabled")
        _client_cache["client"] = None
        return None

    obs = _shadow_config.observability
    public_key = (
        obs.langfuse_public_key.get_secret_value()
        if obs.langfuse_public_key
        else None
    )
    secret_key = (
        obs.langfuse_secret_key.get_secret_value()
        if obs.langfuse_secret_key
        else None
    )

    if not public_key or not secret_key:
        logger.debug("Langfuse keys not set — tracing disabled")
        _client_cache["client"] = None
        return None

    try:
        client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=obs.langfuse_host,
        )
    except Exception as e:
        logger.warning("Failed to initialize Langfuse client: %s", e)
        _client_cache["client"] = None
        return None

    _client_cache["client"] = client
    return client


# Backward-compat alias — older tests and call sites still reference this.
_get_langfuse_client = get_client


def _reset_client_cache() -> None:
    """Test-only hook: clear the cached client so the next get_client()
    call re-reads config (e.g., after patching env vars in a test)."""
    _client_cache.clear()


def _safe_span_update(span: Any, **kwargs: Any) -> None:
    if span is None:
        return
    try:
        span.update(**kwargs)
    except Exception as e:
        logger.debug("Langfuse span update failed: %s", e)


def _safe_flush(client: Any) -> None:
    if client is None:
        return
    try:
        client.flush()
    except Exception as e:
        logger.debug("Langfuse client flush failed: %s", e)


@contextmanager
def observed_span(name: str, **metadata: Any) -> Iterator[Any]:
    """Emit a Langfuse span, swallowing every observability error.

    Uses ``start_as_current_observation`` so that any nested
    ``observed_span`` calls (or other Langfuse-instrumented code) become
    children of this span via OpenTelemetry context propagation.

    Yields the span object on success, or None when observability is
    disabled. Callers should null-check before adding metadata::

        with observed_span("router_decision", chosen_module="wraith") as span:
            ...
            if span is not None:
                span.update(metadata={"latency_ms": 12})
    """
    client = get_client()
    if client is None:
        yield None
        return

    cm: Any = None
    span: Any = None
    try:
        cm = client.start_as_current_observation(
            name=name,
            metadata=metadata or None,
        )
        span = cm.__enter__()
    except Exception as e:
        logger.debug("Langfuse span start failed (%s): %s", name, e)
        cm = None
        span = None

    try:
        yield span
    except BaseException:
        if cm is not None:
            try:
                import sys
                cm.__exit__(*sys.exc_info())
            except Exception as inner:
                logger.debug("Langfuse span exit-on-error failed (%s): %s", name, inner)
            cm = None
        raise
    finally:
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception as e:
                logger.debug("Langfuse span end failed (%s): %s", name, e)


def trace_interaction(func):
    """Decorator wrapping ``Orchestrator.process_input`` with a Langfuse trace.

    Emits one parent observation per request. Child spans created via
    ``observed_span`` (e.g., from retry_engine) nest under this parent
    automatically through OpenTelemetry context propagation.

    Trace metadata captured:
        - input.user_input, input.source
        - interaction_count
        - latency_ms
        - module_used, task_type, complexity, apex_used (when classification ran)
        - output.response (truncated to 500 chars)

    Silently no-ops if Langfuse is unavailable or misconfigured.
    """

    @functools.wraps(func)
    async def wrapper(self, user_input: str, source: str = "user") -> str:
        client = get_client()
        if client is None:
            return await func(self, user_input, source)

        start = time.time()

        # start_as_current_observation returns a context manager that pushes
        # the span onto the OTel current-span stack so nested observed_span
        # calls become children automatically.
        try:
            observation_cm = client.start_as_current_observation(
                name="shadow.process_input",
                input={"user_input": user_input, "source": source},
                metadata={"interaction_count": self._state.interaction_count + 1},
            )
        except Exception as e:
            logger.debug("Failed to start Langfuse observation: %s", e)
            return await func(self, user_input, source)

        try:
            with observation_cm as span:
                try:
                    response = await func(self, user_input, source)
                except Exception:
                    _safe_span_update(
                        span,
                        output={"error": "decision_loop_exception"},
                        metadata={"latency_ms": round((time.time() - start) * 1000)},
                    )
                    raise

                latency_ms = round((time.time() - start) * 1000)
                metadata: dict[str, Any] = {
                    "latency_ms": latency_ms,
                    "source": source,
                }
                if hasattr(self, "_last_classification"):
                    cls = self._last_classification
                    metadata["module_used"] = cls.target_module
                    metadata["task_type"] = cls.task_type.value
                    metadata["complexity"] = cls.complexity
                    metadata["apex_used"] = cls.brain.value == "smart_brain"

                _safe_span_update(
                    span,
                    output={"response": response[:500]},
                    metadata=metadata,
                )
                return response
        finally:
            _safe_flush(client)

    return wrapper
