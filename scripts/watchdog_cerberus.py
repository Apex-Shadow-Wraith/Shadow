"""
Cerberus External Watchdog — Standalone Monitoring Script
==========================================================
This script runs as a COMPLETELY SEPARATE PROCESS from Shadow.
It monitors the Cerberus heartbeat file and takes emergency action
if Cerberus stops responding.

SETUP (Windows Task Scheduler):
  1. Open Task Scheduler → Create Basic Task
  2. Name: "Shadow Cerberus Watchdog"
  3. Trigger: "When the computer starts" (or "When I log on")
  4. Action: Start a program
     - Program: C:\\Shadow\\shadow_env\\Scripts\\pythonw.exe
     - Arguments: C:\\Shadow\\scripts\\watchdog_cerberus.py
     - Start in: C:\\Shadow
  5. In Properties → Settings:
     - Check "Run whether user is logged on or not"
     - Check "Restart the task if it fails" (every 1 minute, up to 3 times)
  6. Apply and enter your password when prompted.

SETUP (Ubuntu systemd — future):
  Create /etc/systemd/system/shadow-watchdog.service:
    [Unit]
    Description=Shadow Cerberus Watchdog
    After=network.target

    [Service]
    ExecStart=/path/to/shadow_env/bin/python /path/to/scripts/watchdog_cerberus.py
    Restart=always
    RestartSec=5

    [Install]
    WantedBy=multi-user.target

  Then: systemctl enable shadow-watchdog && systemctl start shadow-watchdog

EMERGENCY ACTIONS (in order):
  1. Log to C:\\Shadow\\EMERGENCY.log
  2. Attempt Telegram alert (if token configured in .env)
  3. Kill the Shadow main process
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

# --- Configuration ---
HEARTBEAT_PATH = Path("C:/Shadow/data/cerberus_heartbeat.json")
EMERGENCY_LOG = Path("C:/Shadow/EMERGENCY.log")
CHECK_INTERVAL = 10  # seconds
MAX_HEARTBEAT_AGE = 30  # seconds before Cerberus is presumed dead
ENV_PATH = Path("C:/Shadow/config/.env")

# --- Logging Setup ---
logging.basicConfig(
    filename=str(EMERGENCY_LOG),
    level=logging.WARNING,
    format="%(asctime)s [WATCHDOG] %(levelname)s: %(message)s",
)
logger = logging.getLogger("shadow.watchdog")

# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logger.addHandler(console)


def load_env() -> dict[str, str]:
    """Load environment variables from .env file."""
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def send_telegram_alert(message: str, env: dict[str, str]) -> bool:
    """Send emergency alert via Telegram bot."""
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
    """Attempt to kill the Shadow main process."""
    try:
        if sys.platform == "win32":
            # Kill all Python processes with "shadow" in the command line
            subprocess.run(
                ["taskkill", "/F", "/FI", "WINDOWTITLE eq Shadow*"],
                capture_output=True,
            )
            logger.warning("Attempted to kill Shadow process via taskkill")
        else:
            # Linux: use pkill
            subprocess.run(["pkill", "-f", "shadow_core"], capture_output=True)
            logger.warning("Attempted to kill Shadow process via pkill")
    except Exception as e:
        logger.error("Failed to kill Shadow process: %s", e)


def check_heartbeat() -> bool:
    """Check if Cerberus heartbeat is fresh.

    Returns True if Cerberus is alive, False if dead or missing.
    """
    if not HEARTBEAT_PATH.exists():
        logger.warning("Heartbeat file not found: %s", HEARTBEAT_PATH)
        return False

    try:
        with open(HEARTBEAT_PATH, "r", encoding="utf-8") as f:
            heartbeat = json.load(f)

        timestamp = heartbeat.get("timestamp", 0)
        age = time.time() - timestamp

        if age > MAX_HEARTBEAT_AGE:
            logger.warning(
                "Heartbeat stale! Age: %.1fs (max: %ds). Status: %s",
                age, MAX_HEARTBEAT_AGE, heartbeat.get("status", "unknown"),
            )
            return False

        return True

    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Heartbeat file corrupted: %s", e)
        return False


def emergency_response() -> None:
    """Full emergency response when Cerberus is down."""
    timestamp = datetime.now().isoformat()
    message = (
        f"[EMERGENCY] Cerberus heartbeat lost at {timestamp}. "
        "Shadow safety gate is DOWN. Emergency shutdown initiated."
    )

    # 1. Log
    logger.critical(message)

    # 2. Telegram alert
    env = load_env()
    send_telegram_alert(message, env)

    # 3. Kill Shadow
    kill_shadow_process()


def main() -> None:
    """Main watchdog loop. Runs forever."""
    logger.info("Cerberus Watchdog started. Monitoring: %s", HEARTBEAT_PATH)
    consecutive_failures = 0

    while True:
        if check_heartbeat():
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            # Require 2 consecutive failures before emergency response
            # to avoid false positives during startup or brief stalls
            if consecutive_failures >= 2:
                emergency_response()
                consecutive_failures = 0
                # Wait longer after emergency to avoid rapid-fire alerts
                time.sleep(60)
                continue

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
