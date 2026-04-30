"""System-metrics collection for the Void daemon.

Lifted from modules/void/void.py's _system_snapshot + _query_gpu.
Pure functions — no daemon state, no I/O beyond psutil / nvidia-smi
subprocess calls. Returns a dict the storage + thresholds layers can
consume directly.
"""

from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Path the nightly training-backup rsync timer writes a `current` symlink to.
# Pointing the symlink at the most recent dated snapshot is how we detect
# the timer is alive — if the symlink stops moving, the timer is broken.
_TRAINING_BACKUP_LINK = Path("/mnt/storage/backup/training-data/current")
_TRAINING_BACKUP_STALE_HOURS = 48.0


def query_gpu() -> dict[str, Any]:
    """Return GPU status via nvidia-smi, or {'available': False, ...} on failure."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"available": False, "reason": "nvidia-smi returned error"}

        gpus: list[dict[str, Any]] = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                gpus.append(
                    {
                        "name": parts[0],
                        "temperature_c": float(parts[1]),
                        "utilization_percent": float(parts[2]),
                        "memory_used_mb": float(parts[3]),
                        "memory_total_mb": float(parts[4]),
                    }
                )
        return {"available": True, "gpus": gpus}
    except FileNotFoundError:
        return {"available": False, "reason": "nvidia-smi not found"}
    except subprocess.TimeoutExpired:
        return {"available": False, "reason": "nvidia-smi timed out"}


def collect_backup_freshness(
    link: Path = _TRAINING_BACKUP_LINK,
    stale_hours: float = _TRAINING_BACKUP_STALE_HOURS,
) -> dict[str, Any]:
    """Check the training-data backup symlink and return its freshness state.

    The nightly rsync timer points `current` at the most recent dated
    snapshot. A stale or missing symlink means the timer hasn't fired —
    HDD unmounted, timer disabled, or rsync failing silently.

    Returns a dict with:
      - backup_status: "fresh" | "stale" | "missing" | "no_target" |
                       "not_configured" | "error"
      - backup_age_hours: float | None  (None unless status is fresh/stale)
      - backup_target: str | None       (resolved snapshot directory name)
      - backup_error: str | None        (only when status == "error")

    Pure function — no I/O beyond the symlink resolve and stat.
    """
    base = {
        "backup_status": "missing",
        "backup_age_hours": None,
        "backup_target": None,
        "backup_error": None,
    }
    if not link.is_symlink():
        # Distinguish "backup mount missing entirely" from "symlink missing"
        # so callers can warn appropriately (or stay silent on a system
        # where the backup HDD just isn't attached).
        if not link.parent.exists():
            base["backup_status"] = "not_configured"
        return base
    try:
        target = link.resolve()
        if not target.is_dir():
            base["backup_status"] = "no_target"
            base["backup_target"] = str(target)
            return base
        age_hours = (time.time() - target.stat().st_mtime) / 3600
        base["backup_age_hours"] = round(age_hours, 2)
        base["backup_target"] = target.name
        base["backup_status"] = "stale" if age_hours > stale_hours else "fresh"
        return base
    except OSError as e:
        base["backup_status"] = "error"
        base["backup_error"] = str(e)
        return base


def collect_snapshot() -> dict[str, Any]:
    """Collect CPU / RAM / disk / process / GPU metrics in a single snapshot."""
    import psutil

    timestamp = datetime.now().isoformat()

    cpu = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    process = psutil.Process(os.getpid())
    proc_mem = process.memory_info()
    proc_mem_mb = proc_mem.rss / (1024 ** 2)

    gpu_data = query_gpu()
    backup = collect_backup_freshness()

    return {
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
        "ram_total_gb": round(ram.total / (1024 ** 3), 2),
        "ram_used_gb": round(ram.used / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "disk_total_gb": round(disk.total / (1024 ** 3), 2),
        "disk_used_gb": round(disk.used / (1024 ** 3), 2),
        "process_memory_mb": round(proc_mem_mb, 2),
        "gpu": gpu_data,
        **backup,
        "timestamp": timestamp,
    }


def snapshot_to_metric_rows(snapshot: dict[str, Any]) -> list[tuple[str, float, str, str]]:
    """Flatten a snapshot dict into (metric_name, value, unit, timestamp) rows."""
    ts = snapshot["timestamp"]
    rows: list[tuple[str, float, str, str]] = [
        ("cpu_percent", snapshot["cpu_percent"], "percent", ts),
        ("ram_percent", snapshot["ram_percent"], "percent", ts),
        ("ram_used_gb", snapshot["ram_used_gb"], "GB", ts),
        ("disk_percent", snapshot["disk_percent"], "percent", ts),
        ("disk_used_gb", snapshot["disk_used_gb"], "GB", ts),
        ("process_memory_mb", snapshot["process_memory_mb"], "MB", ts),
    ]
    gpu = snapshot.get("gpu", {})
    if gpu.get("available"):
        for i, g in enumerate(gpu["gpus"]):
            rows.append((f"gpu_{i}_temp_c", g["temperature_c"], "celsius", ts))
            rows.append((f"gpu_{i}_util_percent", g["utilization_percent"], "percent", ts))
    return rows
