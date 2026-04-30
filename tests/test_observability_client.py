"""
Tests for the Langfuse client wrapper public surface.

Covers the safe-fallback semantics: trace_disabled / get_client must
silently no-op whenever observability is misconfigured, the SDK is
missing, or the kill-switch env var is set. Observability never
raises out of init — production paths must remain unaffected.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from modules.shadow import observability


@pytest.fixture(autouse=True)
def _clear_client_cache():
    """Each test starts with a fresh client cache."""
    observability._reset_client_cache()
    yield
    observability._reset_client_cache()


def test_trace_disabled_when_env_set(monkeypatch):
    """LANGFUSE_DISABLED truthy values disable observability."""
    for truthy in ("1", "true", "TRUE", "yes"):
        monkeypatch.setenv("LANGFUSE_DISABLED", truthy)
        assert observability.trace_disabled() is True

    monkeypatch.setenv("LANGFUSE_DISABLED", "0")
    # Falsy / unset -> not disabled by env (still subject to SDK availability)
    assert observability.trace_disabled() is False


def test_trace_disabled_when_sdk_missing(monkeypatch):
    """If the SDK didn't import, observability is disabled regardless of env."""
    monkeypatch.delenv("LANGFUSE_DISABLED", raising=False)
    with patch.object(observability, "_LANGFUSE_AVAILABLE", False):
        assert observability.trace_disabled() is True


def test_get_client_returns_none_when_disabled(monkeypatch):
    """When LANGFUSE_DISABLED is set, get_client never even attempts init."""
    monkeypatch.setenv("LANGFUSE_DISABLED", "1")
    assert observability.get_client() is None


def test_get_client_returns_none_when_keys_missing(monkeypatch):
    """Missing public/secret keys -> get_client returns None silently."""
    monkeypatch.delenv("LANGFUSE_DISABLED", raising=False)

    # Build a fake config singleton whose observability section has
    # both keys = None — emulates a deployment where Langfuse isn't
    # configured.
    class _ObsNoKeys:
        langfuse_public_key = None
        langfuse_secret_key = None
        langfuse_host = "http://localhost:3000"

    class _Cfg:
        observability = _ObsNoKeys()

    fake_module = type("_M", (), {"config": _Cfg()})
    with patch.dict("sys.modules", {"shadow.config": fake_module}):
        assert observability.get_client() is None


def test_get_client_caches_result(monkeypatch):
    """Successive get_client calls return the same cached instance."""
    monkeypatch.delenv("LANGFUSE_DISABLED", raising=False)

    class _ObsNoKeys:
        langfuse_public_key = None
        langfuse_secret_key = None
        langfuse_host = "http://localhost:3000"

    class _Cfg:
        observability = _ObsNoKeys()

    fake_module = type("_M", (), {"config": _Cfg()})
    with patch.dict("sys.modules", {"shadow.config": fake_module}):
        first = observability.get_client()
        second = observability.get_client()
        assert first is second  # both None, both from cache


def test_observed_span_no_op_when_disabled(monkeypatch):
    """observed_span yields None when observability is disabled."""
    monkeypatch.setenv("LANGFUSE_DISABLED", "1")
    with observability.observed_span("test_span", x=1) as span:
        assert span is None  # no client → no span emitted
