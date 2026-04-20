# pytest configuration - ensures modules are importable

import pytest


@pytest.fixture(autouse=True)
def _reset_shadow_config():
    """Rebuild the `shadow.config.config` singleton around each test.

    pydantic-settings reads env + `.env` + YAML once at Settings() construction.
    Any test that mutates env vars or YAML fixtures needs a fresh singleton
    afterwards, otherwise later tests see the mutated state. Running this
    autouse fixture both before and after each test keeps the singleton
    aligned with the current environment.
    """
    try:
        from shadow.config import reload_config
    except Exception:
        yield
        return

    reload_config()
    yield
    reload_config()
