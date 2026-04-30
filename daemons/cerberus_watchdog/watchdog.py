"""Cerberus Watchdog daemon — external heartbeat monitor.

Reads `data/cerberus_heartbeat.json` on a schedule. If the heartbeat is
missing or stale for `consecutive_failures_to_emergency` consecutive
checks, fires the emergency response: log + Telegram alert + pkill.

Runs as a separate process from Shadow so a Cerberus deadlock or
Shadow-side crash can't take the watchdog down with it. Logging goes
to journald via systemd (StandardOutput=journal) — no separate log file.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from daemons.cerberus_watchdog.config import CerberusWatchdogSettings

logger = logging.getLogger("shadow.daemons.cerberus_watchdog")


def load_env(env_path: Path) -> dict[str, str]:
    """Load environment variables from a .env file."""
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def send_telegram_alert(message: str, env: dict[str, str]) -> bool:
    """Send emergency alert via Telegram bot. Returns True on success."""
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.warning("Telegram not configured — skipping alert")
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
        urlopen(req, timeout=10)
        logger.info("Telegram alert sent")
        return True
    except Exception as e:
        logger.error("Failed to send Telegram alert: %s", e)
        return False


def kill_shadow_process() -> None:
    """Attempt to kill the Shadow main process via pkill on the entry-point name."""
    try:
        subprocess.run(["pkill", "-f", "shadow_core"], capture_output=True)
        logger.warning("Attempted to kill Shadow process via pkill")
    except Exception as e:
        logger.error("Failed to kill Shadow process: %s", e)


def check_heartbeat(
    heartbeat_path: Path, max_age_seconds: int
) -> bool:
    """Return True if Cerberus heartbeat is fresh, False otherwise."""
    if not heartbeat_path.exists():
        logger.warning("Heartbeat file not found: %s", heartbeat_path)
        return False

    try:
        with open(heartbeat_path, "r", encoding="utf-8") as f:
            heartbeat: dict[str, Any] = json.load(f)
        timestamp = heartbeat.get("timestamp", 0)
        age = time.time() - timestamp
        if age > max_age_seconds:
            logger.warning(
                "Heartbeat stale! Age: %.1fs (max: %ds). Status: %s",
                age, max_age_seconds, heartbeat.get("status", "unknown"),
            )
            return False
        return True
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Heartbeat file corrupted: %s", e)
        return False


def emergency_response(env_path: Path) -> None:
    """Full emergency response when Cerberus is down."""
    timestamp = datetime.now().isoformat()
    message = (
        f"[EMERGENCY] Cerberus heartbeat lost at {timestamp}. "
        "Shadow safety gate is DOWN. Emergency shutdown initiated."
    )
    logger.critical(message)
    send_telegram_alert(message, load_env(env_path))
    kill_shadow_process()


def run(settings: CerberusWatchdogSettings) -> int:
    """Run the watchdog poll loop until killed. Returns an exit code."""
    if not settings.enabled:
        logger.info(
            "Cerberus Watchdog disabled (config.cerberus_watchdog.enabled=False); "
            "exiting cleanly."
        )
        return 0

    logger.info(
        "Cerberus Watchdog started — heartbeat=%s interval=%ds max_age=%ds",
        settings.heartbeat_path,
        settings.check_interval_seconds,
        settings.max_heartbeat_age_seconds,
    )
    consecutive_failures = 0

    while True:
        if check_heartbeat(
            settings.heartbeat_path, settings.max_heartbeat_age_seconds
        ):
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= settings.consecutive_failures_to_emergency:
                emergency_response(settings.env_path)
                consecutive_failures = 0
                time.sleep(settings.cooldown_seconds)
                continue

        time.sleep(settings.check_interval_seconds)
