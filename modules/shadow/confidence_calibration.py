"""
Confidence Calibration Curve
============================
Calibrates Shadow's confidence predictions against actual outcomes.

When Shadow says 80% confident, does he succeed 80% of the time?
This module passively records prediction-outcome pairs and computes
calibration curves to adjust future confidence scores.
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("shadow.confidence_calibration")


@dataclass
class CalibrationRecord:
    """A single prediction-outcome pair."""

    record_id: str
    timestamp: float
    predicted_confidence: float
    actual_success: bool
    task_type: str
    module: str
    was_escalated: bool


class ConfidenceCalibrator:
    """Calibrates Shadow's confidence predictions against actual outcomes."""

    def __init__(
        self,
        db_path: str = "data/confidence_calibration.db",
        bucket_count: int = 10,
    ) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._bucket_count = bucket_count
        self._conn: sqlite3.Connection | None = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create the calibration records table."""
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS calibration_records (
                record_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                predicted_confidence REAL NOT NULL,
                actual_success INTEGER NOT NULL,
                task_type TEXT DEFAULT '',
                module TEXT DEFAULT '',
                was_escalated INTEGER DEFAULT 0
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS recalibration_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                record_count INTEGER NOT NULL,
                calibration_error REAL NOT NULL
            )
        """)
        self._conn.commit()

    def record(
        self,
        predicted_confidence: float,
        actual_success: bool,
        task_type: str = "",
        module: str = "",
        was_escalated: bool = False,
    ) -> str:
        """Store a prediction-outcome pair. Returns record_id."""
        try:
            record_id = str(uuid.uuid4())
            self._conn.execute(
                """INSERT INTO calibration_records
                   (record_id, timestamp, predicted_confidence, actual_success,
                    task_type, module, was_escalated)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    record_id,
                    time.time(),
                    float(predicted_confidence),
                    int(actual_success),
                    task_type,
                    module,
                    int(was_escalated),
                ),
            )
            self._conn.commit()
            logger.debug(
                "Recorded calibration: predicted=%.3f actual=%s type=%s module=%s",
                predicted_confidence, actual_success, task_type, module,
            )
            return record_id
        except Exception as e:
            logger.warning("Failed to record calibration data: %s", e)
            return ""

    def _get_bucket_index(self, confidence: float) -> int:
        """Map a confidence value to a bucket index."""
        idx = int(confidence * self._bucket_count)
        return min(idx, self._bucket_count - 1)

    def _get_bucket_range(self, index: int) -> tuple[float, float]:
        """Return (lower, upper) for a bucket index."""
        step = 1.0 / self._bucket_count
        lower = round(index * step, 2)
        upper = round((index + 1) * step, 2)
        return lower, upper

    def _build_curve_from_rows(self, rows: list[tuple]) -> dict:
        """Build calibration curve from (predicted_confidence, actual_success) rows."""
        step = 1.0 / self._bucket_count
        buckets: list[dict] = []
        total_error = 0.0
        total_weighted_diff = 0.0
        total_samples = 0

        for i in range(self._bucket_count):
            lower, upper = self._get_bucket_range(i)
            bucket_rows = [
                r for r in rows if lower <= r[0] < upper
                or (i == self._bucket_count - 1 and r[0] == 1.0)
            ]
            count = len(bucket_rows)
            if count > 0:
                predicted_avg = sum(r[0] for r in bucket_rows) / count
                actual_rate = sum(r[1] for r in bucket_rows) / count
            else:
                predicted_avg = lower + step / 2
                actual_rate = 0.0

            buckets.append({
                "bucket_range": f"{lower:.1f}-{upper:.1f}",
                "predicted_avg": round(predicted_avg, 4),
                "actual_success_rate": round(actual_rate, 4),
                "sample_count": count,
            })

            if count > 0:
                diff = predicted_avg - actual_rate
                total_error += abs(diff) * count
                total_weighted_diff += diff * count
                total_samples += count

        if total_samples > 0:
            overall_error = round(total_error / total_samples, 4)
            avg_diff = total_weighted_diff / total_samples
        else:
            overall_error = 0.0
            avg_diff = 0.0

        if overall_error <= 0.05:
            direction = "well_calibrated"
        elif avg_diff > 0:
            direction = "overconfident"
        else:
            direction = "underconfident"

        return {
            "buckets": buckets,
            "overall_calibration_error": overall_error,
            "direction": direction,
        }

    def get_calibration_curve(self) -> dict:
        """Build the calibration curve from all stored records."""
        try:
            cursor = self._conn.execute(
                "SELECT predicted_confidence, actual_success FROM calibration_records"
            )
            rows = cursor.fetchall()
            return self._build_curve_from_rows(rows)
        except Exception as e:
            logger.warning("Failed to build calibration curve: %s", e)
            return {
                "buckets": [],
                "overall_calibration_error": 0.0,
                "direction": "well_calibrated",
            }

    def get_adjustment_factor(self, predicted_confidence: float) -> float:
        """Return an adjusted confidence based on calibration curve.

        Uses linear interpolation between bucket midpoints.
        If insufficient data (< 10 records in bucket), returns unchanged.
        """
        try:
            curve = self.get_calibration_curve()
            buckets = curve["buckets"]
            if not buckets:
                return predicted_confidence

            # Build mapping: midpoint → actual_success_rate for buckets with enough data
            midpoints: list[tuple[float, float]] = []
            for b in buckets:
                if b["sample_count"] >= 10:
                    midpoints.append((b["predicted_avg"], b["actual_success_rate"]))

            if not midpoints:
                return predicted_confidence

            # If below lowest or above highest midpoint, use nearest
            midpoints.sort(key=lambda x: x[0])
            if predicted_confidence <= midpoints[0][0]:
                return midpoints[0][1]
            if predicted_confidence >= midpoints[-1][0]:
                return midpoints[-1][1]

            # Linear interpolation between adjacent midpoints
            for i in range(len(midpoints) - 1):
                x0, y0 = midpoints[i]
                x1, y1 = midpoints[i + 1]
                if x0 <= predicted_confidence <= x1:
                    if x1 == x0:
                        return y0
                    t = (predicted_confidence - x0) / (x1 - x0)
                    return y0 + t * (y1 - y0)

            return predicted_confidence
        except Exception as e:
            logger.warning("Failed to compute adjustment factor: %s", e)
            return predicted_confidence

    def calibrate(self, raw_confidence: float) -> float:
        """Apply adjustment factor to raw confidence score.

        This is what other systems should call instead of using raw scores.
        Returns adjusted confidence clamped to 0.0-1.0.
        """
        try:
            adjusted = self.get_adjustment_factor(raw_confidence)
            return max(0.0, min(1.0, adjusted))
        except Exception as e:
            logger.warning("Calibration failed, returning raw: %s", e)
            return max(0.0, min(1.0, raw_confidence))

    def get_calibration_by_type(
        self, task_type: str | None = None, module: str | None = None
    ) -> dict:
        """Calibration curve filtered by task_type or module."""
        try:
            conditions = []
            params = []
            if task_type is not None:
                conditions.append("task_type = ?")
                params.append(task_type)
            if module is not None:
                conditions.append("module = ?")
                params.append(module)

            query = "SELECT predicted_confidence, actual_success FROM calibration_records"
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            cursor = self._conn.execute(query, params)
            rows = cursor.fetchall()
            return self._build_curve_from_rows(rows)
        except Exception as e:
            logger.warning("Failed to build filtered calibration curve: %s", e)
            return {
                "buckets": [],
                "overall_calibration_error": 0.0,
                "direction": "well_calibrated",
            }

    def get_calibration_report(self) -> str:
        """Plain-English summary for Harbinger daily briefing."""
        try:
            curve = self.get_calibration_curve()
            error = curve["overall_calibration_error"]
            direction = curve["direction"]

            total_records = sum(b["sample_count"] for b in curve["buckets"])
            if total_records == 0:
                return "No calibration data available yet."

            if direction == "well_calibrated":
                severity = "well-calibrated"
                detail = "Predictions closely match outcomes."
            elif error > 0.15:
                severity = f"significantly {direction}"
            elif error > 0.08:
                severity = f"moderately {direction}"
            else:
                severity = f"slightly {direction}"
                detail = "Minor adjustments may help."

            # Find the 0.8 bucket for a concrete example
            example = ""
            for b in curve["buckets"]:
                if b["bucket_range"] == "0.8-0.9" and b["sample_count"] >= 5:
                    actual_pct = int(b["actual_success_rate"] * 100)
                    example = (
                        f" When predicting 80% confidence, actual success "
                        f"rate is {actual_pct}%."
                    )
                    break

            if direction == "well_calibrated":
                return (
                    f"Shadow is {severity} (error: {error:.2f}). "
                    f"{detail}{example} ({total_records} records)"
                )

            pct_error = int(error * 100)
            if direction == "overconfident":
                recommendation = f"Recommend lowering confidence thresholds by ~{pct_error}%."
            else:
                recommendation = f"Recommend raising confidence thresholds by ~{pct_error}%."

            return (
                f"Shadow is {severity} (calibration error: {error:.2f}).{example} "
                f"{recommendation} ({total_records} records)"
            )
        except Exception as e:
            logger.warning("Failed to generate calibration report: %s", e)
            return "Calibration report unavailable."

    def get_monthly_trend(self, months: int = 6) -> list[dict]:
        """Is calibration improving over time? Returns monthly data."""
        try:
            now = time.time()
            result = []

            for i in range(months - 1, -1, -1):
                # Approximate month boundaries
                month_end = now - (i * 30 * 86400)
                month_start = month_end - (30 * 86400)

                cursor = self._conn.execute(
                    """SELECT predicted_confidence, actual_success
                       FROM calibration_records
                       WHERE timestamp >= ? AND timestamp < ?""",
                    (month_start, month_end),
                )
                rows = cursor.fetchall()
                if not rows:
                    result.append({
                        "month": i,
                        "calibration_error": 0.0,
                        "direction": "well_calibrated",
                        "record_count": 0,
                    })
                    continue

                curve = self._build_curve_from_rows(rows)
                result.append({
                    "month": i,
                    "calibration_error": curve["overall_calibration_error"],
                    "direction": curve["direction"],
                    "record_count": len(rows),
                })

            return result
        except Exception as e:
            logger.warning("Failed to compute monthly trend: %s", e)
            return []

    def should_recalibrate(self) -> bool:
        """Return True if calibration error > 0.15 or > 100 new records since last check."""
        try:
            curve = self.get_calibration_curve()
            if curve["overall_calibration_error"] > 0.15:
                return True

            # Check records since last recalibration
            cursor = self._conn.execute(
                "SELECT MAX(record_count) FROM recalibration_log"
            )
            row = cursor.fetchone()
            last_count = row[0] if row and row[0] is not None else 0

            cursor = self._conn.execute(
                "SELECT COUNT(*) FROM calibration_records"
            )
            current_count = cursor.fetchone()[0]

            return (current_count - last_count) > 100
        except Exception as e:
            logger.warning("Failed to check recalibration status: %s", e)
            return False

    def mark_recalibrated(self) -> None:
        """Record that a recalibration was performed."""
        try:
            cursor = self._conn.execute(
                "SELECT COUNT(*) FROM calibration_records"
            )
            count = cursor.fetchone()[0]
            curve = self.get_calibration_curve()
            self._conn.execute(
                "INSERT INTO recalibration_log (timestamp, record_count, calibration_error) VALUES (?, ?, ?)",
                (time.time(), count, curve["overall_calibration_error"]),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning("Failed to mark recalibration: %s", e)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
