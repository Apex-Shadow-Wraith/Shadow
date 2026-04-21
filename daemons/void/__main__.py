"""Entry point: `python -m daemons.void`.

Reads typed settings from the Shadow config singleton when that field
is a `VoidDaemonSettings` instance; otherwise falls back to defaults.
The fallback lets this entry point run before the singleton switchover
commit lands.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from daemons.void.config import VoidDaemonSettings
from daemons.void.monitor import run


def _load_settings() -> VoidDaemonSettings:
    try:
        from shadow.config import config  # type: ignore

        cfg = getattr(config, "void", None)
        if isinstance(cfg, VoidDaemonSettings):
            return cfg
    except Exception:
        pass
    return VoidDaemonSettings()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-28s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    settings = _load_settings()
    return asyncio.run(run(settings))


if __name__ == "__main__":
    sys.exit(main())
