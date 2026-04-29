# shadow.config — Centralized Configuration

Every setting and secret Shadow needs is loaded through a single
Pydantic-Settings singleton. Read values as typed attributes:

```python
from shadow.config import config

config.apex.dry_run               # bool
config.apex.anthropic_api_key     # SecretStr | None  (commit 2+)
config.grimoire.db_path           # str
```

## Precedence

First wins:

1. Explicit init kwargs (mostly for tests via `reload_config()`)
2. OS environment variables
3. `.env` file at the repo root
4. `config/config.local.yaml` — optional, gitignored, per-machine overrides
5. `config/config.yaml` — checked-in defaults, REQUIRED
6. Pydantic field defaults

Missing `config/config.yaml` is a hard error. Missing `.env` and missing
`config/config.local.yaml` are both fine.

## Environment variable names

Two routing conventions are supported simultaneously on every leaf field:

- **Nested** — `APEX__DRY_RUN=true` maps to `config.apex.dry_run` via
  `env_nested_delimiter="__"`.
- **Flat** — `ANTHROPIC_API_KEY=sk-…` maps to
  `config.apex.anthropic_api_key` via a `validation_alias=AliasChoices(…)`
  on the leaf field. This preserves every existing `.env` name in use
  today.

## Secrets

All sensitive fields are declared `SecretStr | None`. Guarantees:

- `repr(config.apex)` shows `anthropic_api_key=SecretStr('**********')` —
  never the raw value.
- `config.model_dump_json()` renders secrets as `"**********"`.
- To get the raw value for an SDK call, use `.get_secret_value()`. Never
  log that string.

A sanity check that runs after every deploy:

```bash
python -c "from shadow.config import config; print(config.model_dump_json(indent=2))"
```

Every API-key-like field must render as `"**********"` in that output.

## OS environment variable allowlist

A small set of `os.environ` reads/writes is NOT app configuration and
legitimately stays outside this system. They are either OS facts (facts
about the host that Shadow copies into a subprocess env dict) or env
vars Shadow SETS to configure a child process:

| Site | Variable | Purpose |
|---|---|---|
| [modules/omen/sandbox.py](../../modules/omen/sandbox.py) | `PATH`, `SystemRoot`, `SYSTEMDRIVE` | Copied into sandboxed subprocess `env=` dict so subprocesses inherit a minimal working shell. OS-level, not Shadow config. |
| [modules/reaper/reaper.py](../../modules/reaper/reaper.py) (line ~1585) | `LOCALAPPDATA` | Windows-only path lookup for a stealth browser profile. OS-level. |
| [main.py](../../main.py) (line ~530) | `OLLAMA_LOG_LEVEL`, `GIN_MODE` | `os.environ.setdefault` — configures the Ollama child process's own env. Not read by Shadow. |

Adding to the allowlist: document the site here *and* add a one-line
comment at the call site pointing at this file.

## Legacy dict-bridge

`to_legacy_dict(config)` serializes the typed singleton into the nested
dict layout expected by the Orchestrator (which uses
`config["modules"]["grimoire"]["db_path"]`-style access across 20+ call
sites) and by the few module constructors that still accept a `dict`
(Grimoire, Wraith, Nova, Omen, Morpheus). Once
those components accept typed settings directly, the helper can go
away. Apex, Cerberus, Harbinger, and Reaper already consume
`ApexSettings`/`CerberusSettings`/etc. instances and do not need the
bridge.

## Adding a new module slice

1. Create `modules/<name>/config.py` with a `class <Name>Settings(BaseModel)`.
   Keep it a plain `BaseModel`, not `BaseSettings` — only the root reads env.
2. Import it in `shadow/config/__init__.py` and register as a field on
   `ModulesSettings`.
3. Add a `@property` shortcut on `Settings` (e.g., `config.my_module`).
4. Add to `tests/test_config.py`: at minimum, a test that the module
   loads from YAML and the singleton exposes it.

For secret fields:

- Declare the field as `field_name: SecretStr | None = None`.
- Add `validation_alias=AliasChoices("FLAT_NAME", "<MODULE>__FIELD_NAME")`
  for both flat `.env` compatibility and nested env-var routing.
- If the module refuses to function without the secret, add a
  `@model_validator(mode="after")` that raises with a message naming
  the missing field AND the remediation.

## Testing

Tests live in [tests/test_config.py](../../tests/test_config.py). The
`reset_config` autouse fixture in `conftest.py` rebuilds the singleton
between tests so env/YAML mutations don't leak between cases.
