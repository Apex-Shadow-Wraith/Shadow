"""Shadow centralized configuration.

Single source of truth for every setting and secret in the system.
Import the singleton:

    from shadow.config import config

Read typed values per module:

    config.apex.dry_run            # bool, from config.yaml
    config.apex.anthropic_api_key  # SecretStr | None, from .env (commit 2+)

Precedence (first wins):
    1. Explicit init kwargs (mainly for tests)
    2. OS environment variables
    3. `.env` at the repo root
    4. `config/config.local.yaml` (optional per-machine overrides)
    5. `config/config.yaml` (checked-in defaults, required)
    6. Pydantic field defaults

Environment variable conventions:
    - Nested:  APEX__DRY_RUN=true  →  config.apex.dry_run
    - Flat:    ANTHROPIC_API_KEY=… →  config.apex.anthropic_api_key
               (via `validation_alias` on the leaf field)

Secrets use `pydantic.SecretStr`; their `repr()` shows `**********` and
`.model_dump_json()` redacts them. Never log `.get_secret_value()`.

See `shadow/config/README.md` for the OS-env allowlist (PATH, SystemRoot,
SYSTEMDRIVE, LOCALAPPDATA, OLLAMA_LOG_LEVEL, GIN_MODE) — these OS-level
variables are NOT Shadow app config and legitimately stay as `os.environ`
reads/writes.

## Structure

The YAML file nests module settings under `modules:`. Settings flattens
this so every module is a top-level attribute on the singleton
(`config.apex`, `config.cerberus`, …) and env var routing stays intuitive
(`APEX__DRY_RUN`). The `YamlConfigSource` hoists `modules.<name>.*` to
`<name>.*` at load time. The legacy dict-bridge `_dump_for_legacy` reverses
the hoisting for modules that haven't migrated yet.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Type

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from modules.apex.config import ApexSettings
from modules.cerberus.config import CerberusSettings
from modules.grimoire.config import GrimoireSettings
from modules.harbinger.config import HarbingerSettings
from modules.morpheus.config import MorpheusSettings
from modules.nova.config import NovaSettings
from modules.omen.config import OmenSettings
from modules.reaper.reaper_settings import ReaperSettings
from modules.shadow.config import ShadowModuleSettings
from modules.shadow.observability_config import ObservabilitySettings
from daemons.void.config import VoidDaemonSettings
from modules.wraith.config import WraithSettings

from .sources import FlatEnvSource, YamlConfigSource

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# Module name → top-level attribute mapping. Most modules map 1:1; the
# YAML `modules.shadow` block goes to `shadow_module` to avoid colliding
# with the top-level `shadow` package name in imports.
_MODULE_FIELD_MAP: dict[str, str] = {
    "apex": "apex",
    "cerberus": "cerberus",
    "grimoire": "grimoire",
    "harbinger": "harbinger",
    "morpheus": "morpheus",
    "nova": "nova",
    "omen": "omen",
    "reaper": "reaper",
    "wraith": "wraith",
    "observability": "observability",
    "shadow": "shadow_module",
}


class SystemSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = "Shadow"
    version: str = "0.1.0"
    environment: str = "development"
    platform: str = "auto"
    log_level: str = "INFO"
    state_file: str = "data/shadow_state.json"
    timezone: str = "America/Chicago"
    tasks_db: str = "data/shadow_tasks.db"


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    purpose: str = ""
    always_loaded: bool = False


class ModelsSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    ollama_base_url: str = "http://localhost:11434"
    router: ModelSpec | None = None
    fast_brain: ModelSpec | None = None
    smart_brain: ModelSpec | None = None
    embedding: ModelSpec | None = None


class PathsSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    data_dir: str = "data"
    memory_dir: str = "data/memory"
    vector_dir: str = "data/vectors"
    logs_dir: str = "logs"
    config_dir: str = "config"
    modules_dir: str = "modules"


class DecisionLoopSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    max_retries: int = 12
    context_memories: int = 5
    router_timeout: int = 30
    tool_timeout: int = 60
    max_response_tokens: int = 2048
    persist_state: bool = True


class ContextLimitsSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    reserve_tokens: int = 4096
    model_context_limits: dict[str, int] = Field(default_factory=dict)


class PrioritiesSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    current_mode: str = "interactive"


class PersonalitySettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    system_prompt_override: str | None = None
    master_name: str = "Master"
    tone: str = "direct"


class MCPServerSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8100


class MCPSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    grimoire: MCPServerSettings = Field(default_factory=MCPServerSettings)
    reaper: MCPServerSettings = Field(default_factory=MCPServerSettings)


class Settings(BaseSettings):
    """Root Shadow configuration singleton.

    Module settings are top-level attributes (`config.apex`, `config.cerberus`)
    so env vars route naturally (`APEX__DRY_RUN=true`). The YAML source
    hoists `modules.<name>.*` into these top-level fields at load time.
    """

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    # Top-level YAML sections
    system: SystemSettings = Field(default_factory=SystemSettings)
    models: ModelsSettings = Field(default_factory=ModelsSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    decision_loop: DecisionLoopSettings = Field(default_factory=DecisionLoopSettings)
    context_limits: ContextLimitsSettings = Field(default_factory=ContextLimitsSettings)
    priorities: PrioritiesSettings = Field(default_factory=PrioritiesSettings)
    personality: PersonalitySettings = Field(default_factory=PersonalitySettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)

    # Per-module settings (hoisted from YAML `modules:` block)
    apex: ApexSettings = Field(default_factory=ApexSettings)
    cerberus: CerberusSettings = Field(default_factory=CerberusSettings)
    grimoire: GrimoireSettings = Field(default_factory=GrimoireSettings)
    harbinger: HarbingerSettings = Field(default_factory=HarbingerSettings)
    morpheus: MorpheusSettings = Field(default_factory=MorpheusSettings)
    nova: NovaSettings = Field(default_factory=NovaSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    omen: OmenSettings = Field(default_factory=OmenSettings)
    reaper: ReaperSettings = Field(default_factory=ReaperSettings)
    shadow_module: ShadowModuleSettings = Field(default_factory=ShadowModuleSettings)
    void: VoidDaemonSettings = Field(default_factory=VoidDaemonSettings)
    wraith: WraithSettings = Field(default_factory=WraithSettings)

    # Module load-order list (from YAML modules.load_on_startup)
    modules_to_load: list[str] = Field(default_factory=list)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_source = YamlConfigSource(
            settings_cls,
            base_path=REPO_ROOT / "config" / "config.yaml",
            local_path=REPO_ROOT / "config" / "config.local.yaml",
        )
        flat_env_source = FlatEnvSource(
            settings_cls, dotenv_path=REPO_ROOT / ".env"
        )
        # Precedence: init > env > dotenv > flat-env-alias > yaml > secret-files.
        # flat_env_source handles the legacy flat names (ANTHROPIC_API_KEY,
        # etc.) that predate the nested APEX__* convention.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            flat_env_source,
            yaml_source,
            file_secret_settings,
        )


# Set of top-level Settings field names that come from the YAML `modules:`
# section — used by `_dump_for_legacy` to re-nest these for legacy consumers.
_MODULE_FIELD_NAMES = set(_MODULE_FIELD_MAP.values())


def to_legacy_dict(settings: BaseModel | BaseSettings) -> Any:
    """Serialize settings to the legacy nested dict layout.

    The typed singleton is the source of truth for every module's config;
    this helper exists because the Orchestrator and a few unmigrated modules
    (Grimoire, Wraith, Nova, Omen, Morpheus) still
    read configuration via `config["modules"]["<name>"][...]` dict paths.

    Two transformations applied:
    - SecretStr values are unwrapped to raw strings. Consumers of the dict
      expect plain strings; leaving SecretStr in place would break
      string-typed call sites.
    - Top-level module fields (`apex`, `cerberus`, …) are re-nested under
      a top-level `modules` key to match the YAML layout before flattening.

    Once the Orchestrator and the remaining module constructors accept
    typed settings directly, this helper can be deleted.
    """

    def _walk(value: Any) -> Any:
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        if isinstance(value, BaseModel):
            return {
                name: _walk(getattr(value, name))
                for name in type(value).model_fields
            }
        if isinstance(value, dict):
            return {k: _walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_walk(item) for item in value]
        return value

    walked = _walk(settings)

    if not isinstance(walked, dict) or not isinstance(settings, Settings):
        return walked

    # Re-nest module fields under "modules" to match the pre-flatten YAML shape
    modules: dict[str, Any] = {}
    if "modules_to_load" in walked:
        modules["load_on_startup"] = walked.pop("modules_to_load")
    for field_name in list(walked.keys()):
        if field_name in _MODULE_FIELD_NAMES:
            # Preserve original YAML name ("shadow" not "shadow_module")
            yaml_name = next(
                (k for k, v in _MODULE_FIELD_MAP.items() if v == field_name),
                field_name,
            )
            modules[yaml_name] = walked.pop(field_name)
    walked["modules"] = modules
    return walked


config: Settings = Settings()


def reload_config() -> Settings:
    """Rebuild the singleton. Tests call this after mutating env/YAML fixtures."""
    global config
    config = Settings()
    return config


__all__ = [
    "Settings",
    "SystemSettings",
    "ModelsSettings",
    "PathsSettings",
    "DecisionLoopSettings",
    "ContextLimitsSettings",
    "PrioritiesSettings",
    "PersonalitySettings",
    "MCPSettings",
    "MCPServerSettings",
    "ModelSpec",
    "config",
    "reload_config",
    "to_legacy_dict",
    "REPO_ROOT",
]
