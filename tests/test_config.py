"""Tests for the centralized config system at shadow.config."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Type

import pytest
import yaml
from pydantic import SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from shadow.config import (
    Settings,
    to_legacy_dict,
    config as live_config,
    reload_config,
)
from shadow.config.sources import YamlConfigSource, _deep_merge


def _build_settings(
    *,
    yaml_base: Path,
    yaml_local: Path | None = None,
    env_file: Path | None = None,
    **init_kwargs: Any,
) -> Settings:
    """Build a fresh Settings instance with test-controlled sources."""

    class TestSettings(Settings):
        model_config = SettingsConfigDict(
            env_file=str(env_file) if env_file else None,
            env_file_encoding="utf-8",
            env_nested_delimiter="__",
            extra="ignore",
            case_sensitive=False,
        )

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: Type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            yaml_src = YamlConfigSource(
                settings_cls, base_path=yaml_base, local_path=yaml_local
            )
            return (
                init_settings,
                env_settings,
                dotenv_settings,
                yaml_src,
                file_secret_settings,
            )

    return TestSettings(**init_kwargs)


def _minimal_yaml(tmp_path: Path, **overrides: Any) -> Path:
    """Write a minimal config.yaml with optional overrides.

    Sets apex.dry_run=True by default so ApexSettings' key validator doesn't
    fire when no .env fixture is present. Tests that want key-related
    behavior pass dry_run=False explicitly via overrides.
    """
    data: dict[str, Any] = {
        "system": {"timezone": "America/Chicago", "platform": "linux"},
        "modules": {
            "apex": {"dry_run": True, "claude_model": "claude-sonnet-4-20250514"},
            "grimoire": {"db_path": "data/memory/shadow_memory.db"},
        },
    }
    for key, value in overrides.items():
        data[key] = value
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Singleton identity & reload


def test_singleton_identity():
    """Two imports of `config` return the same instance."""
    from shadow.config import config as c1
    from shadow.config import config as c2

    assert c1 is c2


def test_reload_config_returns_fresh_instance():
    original = live_config
    rebuilt = reload_config()
    assert rebuilt is not original


# ---------------------------------------------------------------------------
# Precedence


def test_env_overrides_dotenv_overrides_yaml(tmp_path, monkeypatch):
    yaml_path = _minimal_yaml(
        tmp_path,
        modules={"apex": {"dry_run": True, "claude_model": "from-yaml"}},
    )
    env_file = tmp_path / ".env"
    env_file.write_text("APEX__CLAUDE_MODEL=from-dotenv\n", encoding="utf-8")

    # OS env wins over .env and YAML
    monkeypatch.setenv("APEX__CLAUDE_MODEL", "from-os-env")
    s = _build_settings(yaml_base=yaml_path, env_file=env_file)
    assert s.apex.claude_model == "from-os-env"

    # Without OS env, .env wins over YAML
    monkeypatch.delenv("APEX__CLAUDE_MODEL", raising=False)
    s = _build_settings(yaml_base=yaml_path, env_file=env_file)
    assert s.apex.claude_model == "from-dotenv"


def test_yaml_used_when_no_env(tmp_path, monkeypatch):
    yaml_path = _minimal_yaml(
        tmp_path,
        modules={"apex": {"dry_run": True, "claude_model": "from-yaml"}},
    )
    monkeypatch.delenv("APEX__CLAUDE_MODEL", raising=False)
    s = _build_settings(yaml_base=yaml_path)
    assert s.apex.claude_model == "from-yaml"


def test_local_yaml_overrides_base_yaml(tmp_path):
    base = tmp_path / "config.yaml"
    base.write_text(
        yaml.safe_dump(
            {"modules": {"apex": {"claude_model": "base-yaml", "dry_run": True}}}
        ),
        encoding="utf-8",
    )
    local = tmp_path / "config.local.yaml"
    local.write_text(
        yaml.safe_dump({"modules": {"apex": {"claude_model": "local-yaml"}}}),
        encoding="utf-8",
    )
    s = _build_settings(yaml_base=base, yaml_local=local)
    assert s.apex.claude_model == "local-yaml"
    # Non-overridden keys flow from base
    assert s.apex.dry_run is True


def test_deep_merge_preserves_untouched_subtrees():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    overlay = {"a": {"x": 9}, "c": 4}
    _deep_merge(base, overlay)
    assert base == {"a": {"x": 9, "y": 2}, "b": 3, "c": 4}


# ---------------------------------------------------------------------------
# Required / optional files


def test_missing_config_yaml_fails_loud(tmp_path):
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError, match="Required config file not found"):
        _build_settings(yaml_base=missing)


def test_invalid_yaml_fails_loud(tmp_path):
    bad = tmp_path / "config.yaml"
    bad.write_text("modules:\n  apex:\n  - this: is\n not: valid\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError, match=str(bad)):
        _build_settings(yaml_base=bad)


def test_missing_dotenv_is_ok(tmp_path):
    yaml_path = _minimal_yaml(tmp_path)
    # No env file; construction should succeed with YAML + defaults only
    s = _build_settings(yaml_base=yaml_path)
    assert s.apex.dry_run is True


def test_missing_local_yaml_is_ok(tmp_path):
    yaml_path = _minimal_yaml(tmp_path)
    nonexistent_local = tmp_path / "absent.yaml"
    s = _build_settings(yaml_base=yaml_path, yaml_local=nonexistent_local)
    assert s.apex.dry_run is True


# ---------------------------------------------------------------------------
# Env var conventions


def test_env_nested_delimiter_maps_to_nested_field(tmp_path, monkeypatch):
    yaml_path = _minimal_yaml(tmp_path)
    monkeypatch.setenv("APEX__CLAUDE_MODEL", "nested-env-value")
    s = _build_settings(yaml_base=yaml_path)
    assert s.apex.claude_model == "nested-env-value"


# ---------------------------------------------------------------------------
# SecretStr redaction (commit 1 has no SecretStr fields yet; test the helper)


def test_secretstr_redaction_in_repr():
    """repr() of a SecretStr never exposes the raw value."""
    secret = SecretStr("super-secret-value")
    r = repr(secret)
    assert "super-secret-value" not in r
    assert "**" in r


def test_secretstr_redaction_in_logs(caplog):
    """Logging a SecretStr does not leak the raw value."""
    secret = SecretStr("do-not-leak-me")
    with caplog.at_level(logging.INFO):
        logging.getLogger(__name__).info("value=%s", secret)
    assert "do-not-leak-me" not in caplog.text
    assert "**" in caplog.text


def test_to_legacy_dict_unwraps_secrets():
    """to_legacy_dict reveals SecretStr values so legacy dict consumers can use them."""
    from pydantic import BaseModel

    class HasSecret(BaseModel):
        token: SecretStr
        public: str = "ok"

    m = HasSecret(token=SecretStr("abc123"))
    dumped = to_legacy_dict(m)
    assert dumped["token"] == "abc123"
    assert dumped["public"] == "ok"


def test_to_legacy_dict_passes_through_non_secrets():
    from pydantic import BaseModel

    class Inner(BaseModel):
        value: int = 7

    class Outer(BaseModel):
        name: str = "ok"
        nested: Inner = Inner()
        items: list[str] = ["a", "b"]

    dumped = to_legacy_dict(Outer())
    assert dumped == {"name": "ok", "nested": {"value": 7}, "items": ["a", "b"]}


# ---------------------------------------------------------------------------
# Live singleton behavior (reads real config/config.yaml)


def test_live_singleton_loads_real_yaml():
    """The real singleton loads config/config.yaml successfully."""
    c = reload_config()
    # Fields present in the committed YAML
    assert c.system.timezone  # non-empty
    assert c.apex.claude_model  # non-empty default
    assert isinstance(c.apex.dry_run, bool)


def test_live_singleton_exposes_module_fields():
    """Each module's settings are accessible as a top-level attribute."""
    c = reload_config()
    # Each module has its own settings object at root
    assert c.apex.__class__.__name__ == "ApexSettings"
    assert c.cerberus.__class__.__name__ == "CerberusSettings"
    assert c.grimoire.__class__.__name__ == "GrimoireSettings"
    assert c.reaper.__class__.__name__ == "ReaperSettings"
    assert c.harbinger.__class__.__name__ == "HarbingerSettings"
    assert c.observability.__class__.__name__ == "ObservabilitySettings"
    assert c.shadow_module.__class__.__name__ == "ShadowModuleSettings"


def test_live_singleton_model_dump_json_no_secret_leak():
    """Sanity: dumping the live singleton to JSON contains no '*****' raw values.

    In commit 1 there are no SecretStr fields yet, but this test guards
    against regressions: dumping the full singleton as JSON must succeed
    and must not include any of the known secret env values (if set).
    """
    import os

    c = reload_config()
    dumped = c.model_dump_json()
    # If a real key is in os.environ, it must NOT appear in the JSON dump.
    for env_key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CREATOR_AUTH_TOKEN"):
        raw = os.environ.get(env_key)
        if raw and len(raw) > 10:
            assert raw not in dumped, (
                f"Raw secret from {env_key} leaked into model_dump_json output"
            )
