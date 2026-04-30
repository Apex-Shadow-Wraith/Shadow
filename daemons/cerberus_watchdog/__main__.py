"""Entry point: `python -m daemons.cerberus_watchdog`.

Mirrors `daemons/void/__main__.py`. Reads typed settings from the
Shadow config singleton when available; otherwise falls back to defaults.
"""

from __future__ import annotations

import logging
import sys

from daemons.cerberus_watchdog.config import CerberusWatchdogSettings
from daemons.cerberus_watchdog.watchdog import run


def _load_settings() -> CerberusWatchdogSettings:
    try:
        from shadow.config import config  # type: ignore

        cfg = getattr(config, "cerberus_watchdog", None)
        if isinstance(cfg, CerberusWatchdogSettings):
            return cfg
    except Exception:
        pass
    return CerberusWatchdogSettings()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-32s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )
    settings = _load_settings()
    return run(settings)


if __name__ == "__main__":
    sys.exit(main())
