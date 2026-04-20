"""YAML settings source for pydantic-settings.

Loads `config/config.yaml` (required) and `config/config.local.yaml`
(optional per-machine overrides), deep-merges them, hoists each
`modules.<name>.*` subtree up to top-level `<name>.*`, and returns the
result as a nested dict that pydantic-settings consumes.

Hoisting is what makes env vars like `APEX__DRY_RUN=true` route naturally
to `config.apex.dry_run`: the root Settings has flat module fields, not a
nested `modules` wrapper, so the env source walks them directly.

The YAML on disk keeps its historical `modules:` nesting — the hoisting
is a one-way transformation at load time, invisible to anyone editing the
file.

Precedence inside the YAML layer: local overrides base. Outer precedence
(env vars, .env, YAML, defaults) is wired in `shadow/config/__init__.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


# Module YAML name → Settings field name. Mirrors `_MODULE_FIELD_MAP` in
# shadow.config.__init__; kept here in parallel to avoid an import cycle.
_MODULE_YAML_TO_FIELD: dict[str, str] = {
    "apex": "apex",
    "cerberus": "cerberus",
    "cipher": "cipher",
    "grimoire": "grimoire",
    "harbinger": "harbinger",
    "morpheus": "morpheus",
    "nova": "nova",
    "omen": "omen",
    "reaper": "reaper",
    "sentinel": "sentinel",
    "void": "void",
    "wraith": "wraith",
    "observability": "observability",
    "shadow": "shadow_module",
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    """In-place deep merge: overlay wins on conflicts, dicts recurse."""
    for key, value in overlay.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _hoist_modules(data: dict[str, Any]) -> dict[str, Any]:
    """Lift `modules.<name>.*` subtrees up to top-level `<field>.*`.

    Also promotes `modules.load_on_startup` → top-level `modules_to_load`.
    Unknown module names are hoisted under their own name as-is, letting
    `extra="ignore"` on the root Settings silently drop them.
    """
    if "modules" not in data or not isinstance(data["modules"], dict):
        return data

    modules = data.pop("modules")

    load_on_startup = modules.pop("load_on_startup", None)
    if load_on_startup is not None:
        data["modules_to_load"] = load_on_startup

    for yaml_name, subdata in modules.items():
        target = _MODULE_YAML_TO_FIELD.get(yaml_name, yaml_name)
        if (
            target in data
            and isinstance(data[target], dict)
            and isinstance(subdata, dict)
        ):
            _deep_merge(data[target], subdata)
        else:
            data[target] = subdata
    return data


class YamlConfigSource(PydanticBaseSettingsSource):
    """Settings source reading one required YAML + one optional local YAML."""

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        base_path: Path,
        local_path: Path | None = None,
    ) -> None:
        super().__init__(settings_cls)
        self._base_path = base_path
        self._local_path = local_path
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self._base_path.exists():
            raise FileNotFoundError(
                f"Required config file not found: {self._base_path}. "
                "This file holds Shadow's non-secret defaults and must exist."
            )
        try:
            with open(self._base_path, "r", encoding="utf-8") as f:
                merged: dict[str, Any] = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise yaml.YAMLError(
                f"Invalid YAML in {self._base_path}: {e}"
            ) from e

        if self._local_path and self._local_path.exists():
            try:
                with open(self._local_path, "r", encoding="utf-8") as f:
                    local_data = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise yaml.YAMLError(
                    f"Invalid YAML in {self._local_path}: {e}"
                ) from e
            if local_data:
                _deep_merge(merged, local_data)

        return _hoist_modules(merged)

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> tuple[Any, str, bool]:
        value = self._data.get(field_name)
        return value, field_name, value is not None and isinstance(value, (dict, list))

    def __call__(self) -> dict[str, Any]:
        return self._data
