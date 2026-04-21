"""SQLite + latest.json storage for the Void daemon.

Schema matches the pre-demotion `modules/void/void.py` schema exactly
(same table name, same columns, same index) so existing
`data/void_metrics.db` files are readable without migration.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.daemons.void.storage")


class MetricStore:
    """Thin wrapper around the void_metrics SQLite DB."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        """Open the DB, enable WAL, create schema if missing."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS void_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_metric_time
            ON void_metrics(metric_name, timestamp)
            """
        )
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def insert_metrics(self, rows: list[tuple[str, float, str, str]]) -> None:
        if self._conn is None:
            raise RuntimeError("MetricStore is not open")
        self._conn.executemany(
            "INSERT INTO void_metrics (metric_name, value, unit, timestamp) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def prune_older_than(self, retention_days: int) -> int:
        """Delete metric rows older than `retention_days`. Returns rowcount."""
        if self._conn is None:
            raise RuntimeError("MetricStore is not open")
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        cursor = self._conn.execute(
            "DELETE FROM void_metrics WHERE timestamp < ?", (cutoff,)
        )
        self._conn.commit()
        return cursor.rowcount

    def row_count(self) -> int:
        if self._conn is None:
            raise RuntimeError("MetricStore is not open")
        row = self._conn.execute("SELECT COUNT(*) AS c FROM void_metrics").fetchone()
        return int(row["c"]) if row else 0


def write_latest_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    """Atomically overwrite `path` with `snapshot` serialized as JSON.

    Uses `tempfile.NamedTemporaryFile` + `os.replace` so readers never
    observe a partial write. The tempfile lives in the destination's
    directory so `os.replace` stays on the same filesystem.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        # Ensure we don't leak a temp file on failure.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
