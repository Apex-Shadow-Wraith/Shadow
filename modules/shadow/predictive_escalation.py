"""Predictive Escalation — predict which tasks will likely need Apex BEFORE attempting them.

CRITICAL: Prediction affects PREPARATION only. Shadow still always tries locally first.
The no-pre-emptive-escalation rule is preserved. This makes the local attempt BETTER,
not skipped.
"""

import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EscalationPrediction:
    """Prediction of whether a task will need Apex escalation."""

    prediction_id: str
    task_description: str
    task_type: str
    predicted_probability: float  # 0.0-1.0 likelihood of needing escalation
    confidence_in_prediction: float  # how sure we are about this prediction
    risk_factors: list[str] = field(default_factory=list)
    preparation_actions: list[str] = field(default_factory=list)
    actual_escalated: bool | None = None  # None until known
    timestamp: float = 0.0


# Domain keywords historically associated with higher escalation rates
_HIGH_ESCALATION_KEYWORDS = {
    "cuda", "gpu", "tensorflow", "pytorch", "machine learning",
    "security analysis", "penetration", "exploit", "cryptography",
    "distributed", "kubernetes", "docker compose", "microservices",
    "compiler", "assembly", "kernel", "driver", "firmware",
    "neural network", "deep learning", "transformer", "fine-tune",
    "reverse engineer", "decompile", "binary analysis",
}

# Multi-step indicators
_MULTI_STEP_KEYWORDS = {
    "then", "after that", "next", "finally", "step",
    "first", "second", "third", "pipeline", "workflow",
    "chain", "sequence", "batch", "multiple",
}


class PredictiveEscalation:
    """Predict escalation probability and recommend preparation actions.

    Predictions are advisory — they improve resource allocation but NEVER
    cause Shadow to skip the local attempt.
    """

    def __init__(self, grimoire=None, db_path: str = "data/escalation_predictions.db"):
        self._grimoire = grimoire
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create tables if they don't exist."""
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.row_factory = sqlite3.Row

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                task_description TEXT NOT NULL,
                task_type TEXT NOT NULL DEFAULT '',
                predicted_probability REAL NOT NULL,
                confidence_in_prediction REAL NOT NULL,
                risk_factors TEXT NOT NULL DEFAULT '[]',
                preparation_actions TEXT NOT NULL DEFAULT '[]',
                actual_escalated INTEGER,
                timestamp REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_predictions_task_type
            ON predictions(task_type)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_predictions_timestamp
            ON predictions(timestamp)
        """)
        self._conn.commit()

    def predict(
        self,
        task: str,
        task_type: str | None = None,
        module: str | None = None,
    ) -> EscalationPrediction:
        """Predict escalation probability for a task.

        Uses Grimoire history, task complexity signals, and knowledge depth
        to estimate the likelihood of needing Apex escalation.
        """
        import json

        task = task or ""
        task_type = task_type or ""
        task_lower = task.lower()

        risk_factors: list[str] = []
        scores: dict[str, float] = {}

        # --- 1. Grimoire escalation history ---
        history_score = self._score_from_history(task, task_type)
        scores["history"] = history_score
        if history_score > 0.5:
            risk_factors.append(f"Historical escalation rate for similar tasks: {history_score:.0%}")

        # --- 2. Task complexity signals ---
        complexity_score, complexity_factors = self._score_complexity(task, task_lower)
        scores["complexity"] = complexity_score
        risk_factors.extend(complexity_factors)

        # --- 3. Domain keyword matching ---
        domain_score, domain_factors = self._score_domain_keywords(task_lower)
        scores["domain"] = domain_score
        risk_factors.extend(domain_factors)

        # --- 4. Grimoire knowledge depth ---
        depth_score, depth_factors = self._score_knowledge_depth(task, task_type)
        scores["knowledge_depth"] = depth_score
        risk_factors.extend(depth_factors)

        # --- Weighted combination ---
        weights = {
            "history": 0.35,
            "complexity": 0.20,
            "domain": 0.20,
            "knowledge_depth": 0.25,
        }
        predicted_probability = sum(
            scores[k] * weights[k] for k in weights
        )
        predicted_probability = max(0.0, min(1.0, predicted_probability))

        # Confidence in the prediction depends on how much data we have
        confidence = self._calculate_prediction_confidence(task_type)

        prediction = EscalationPrediction(
            prediction_id=str(uuid.uuid4()),
            task_description=task,
            task_type=task_type,
            predicted_probability=round(predicted_probability, 4),
            confidence_in_prediction=round(confidence, 4),
            risk_factors=risk_factors,
            preparation_actions=[],
            actual_escalated=None,
            timestamp=time.time(),
        )

        # Fill in preparation actions
        prediction.preparation_actions = self.get_preparation_actions(prediction)

        # Store prediction
        self._store_prediction(prediction)

        return prediction

    def _score_from_history(self, task: str, task_type: str) -> float:
        """Score based on past escalation history from DB and Grimoire."""
        score = 0.5  # neutral default

        # Check local DB for past predictions with outcomes
        try:
            if self._conn is None:
                return score
            cursor = self._conn.execute(
                """SELECT actual_escalated FROM predictions
                   WHERE task_type = ? AND actual_escalated IS NOT NULL
                   ORDER BY timestamp DESC LIMIT 20""",
                (task_type,),
            )
            rows = cursor.fetchall()
            if rows:
                escalated_count = sum(1 for r in rows if r["actual_escalated"])
                score = escalated_count / len(rows)
        except Exception:
            pass

        # Check Grimoire for escalation patterns
        try:
            if self._grimoire is not None and hasattr(self._grimoire, "recall"):
                results = self._grimoire.recall(
                    f"escalation {task_type} {task[:50]}",
                    n_results=5,
                    category="apex_sourced",
                )
                if results:
                    # More apex_sourced entries for this domain = higher history
                    grimoire_signal = min(len(results) / 5.0, 1.0)
                    score = (score + grimoire_signal) / 2.0
        except Exception:
            pass

        return score

    def _score_complexity(self, task: str, task_lower: str) -> tuple[float, list[str]]:
        """Score task complexity based on text signals."""
        factors: list[str] = []
        score = 0.0

        # Task length — longer tasks tend to be more complex
        length = len(task)
        if length > 500:
            score += 0.4
            factors.append(f"Long task description ({length} chars)")
        elif length > 200:
            score += 0.2
            factors.append(f"Moderate task length ({length} chars)")
        elif length > 50:
            score += 0.1

        # Multi-step indicators
        multi_step_count = sum(1 for kw in _MULTI_STEP_KEYWORDS if kw in task_lower)
        if multi_step_count >= 3:
            score += 0.4
            factors.append(f"Multi-step task ({multi_step_count} indicators)")
        elif multi_step_count >= 1:
            score += 0.2
            factors.append("Contains multi-step indicators")

        # Question complexity — multiple questions
        question_count = task.count("?")
        if question_count >= 3:
            score += 0.2
            factors.append(f"Multiple questions ({question_count})")

        return min(score, 1.0), factors

    def _score_domain_keywords(self, task_lower: str) -> tuple[float, list[str]]:
        """Score based on presence of historically high-escalation domain keywords."""
        factors: list[str] = []
        matched = [kw for kw in _HIGH_ESCALATION_KEYWORDS if kw in task_lower]

        if not matched:
            return 0.0, factors

        score = min(len(matched) * 0.25, 1.0)
        factors.append(f"High-escalation domain keywords: {', '.join(matched[:3])}")
        return score, factors

    def _score_knowledge_depth(self, task: str, task_type: str) -> tuple[float, list[str]]:
        """Score based on Grimoire knowledge depth for this domain."""
        factors: list[str] = []

        if self._grimoire is None:
            # No Grimoire = can't assess depth, assume moderate risk
            return 0.5, ["Grimoire unavailable — cannot assess knowledge depth"]

        try:
            if hasattr(self._grimoire, "recall"):
                results = self._grimoire.recall(
                    f"{task_type} {task[:80]}",
                    n_results=10,
                )
                entry_count = len(results) if results else 0
            else:
                entry_count = 0

            if entry_count == 0:
                factors.append("No Grimoire entries for this domain — novel territory")
                return 0.9, factors
            elif entry_count <= 2:
                factors.append(f"Only {entry_count} Grimoire entries — shallow coverage")
                return 0.6, factors
            elif entry_count <= 5:
                return 0.3, factors
            else:
                factors.append(f"{entry_count} Grimoire entries — well-covered domain")
                return 0.1, factors
        except Exception:
            return 0.5, ["Grimoire search failed — cannot assess depth"]

    def _calculate_prediction_confidence(self, task_type: str) -> float:
        """How confident are we in this prediction? Based on data volume."""
        try:
            if self._conn is None:
                return 0.3

            cursor = self._conn.execute(
                """SELECT COUNT(*) as total,
                          SUM(CASE WHEN actual_escalated IS NOT NULL THEN 1 ELSE 0 END) as with_outcome
                   FROM predictions WHERE task_type = ?""",
                (task_type,),
            )
            row = cursor.fetchone()
            if row is None:
                return 0.3

            with_outcome = row["with_outcome"] or 0
            if with_outcome >= 50:
                return 0.9
            elif with_outcome >= 20:
                return 0.7
            elif with_outcome >= 5:
                return 0.5
            else:
                return 0.3
        except Exception:
            return 0.3

    def get_preparation_actions(self, prediction: EscalationPrediction) -> list[str]:
        """Recommend preparation actions based on prediction probability.

        Higher probability → more aggressive pre-loading of resources.
        """
        prob = prediction.predicted_probability
        actions: list[str] = []

        if prob > 0.7:
            actions.append("Pre-fetch all Grimoire context for this domain")
            actions.append("Load domain-specific LoRA if available")
            actions.append("Queue Apex API call (don't send yet)")
            actions.append("Pre-load all relevant tools for this task type")
        elif prob > 0.5:
            actions.append("Pre-fetch top 5 Grimoire entries")
            actions.append("Ensure relevant tools loaded")
            actions.append("Prepare escalation context summary")
        elif prob > 0.3:
            actions.append("Standard preparation")
            actions.append("Load basic domain context")
        else:
            actions.append("Minimal preparation — likely solvable locally")

        return actions

    def batch_predictions(self, tasks: list[dict]) -> list[EscalationPrediction]:
        """Predict escalation for multiple tasks at once.

        Tasks predicted > 0.7 can be batched for a single efficient Apex call
        if they all escalate. Returns sorted by probability descending.
        """
        if not tasks:
            return []

        predictions: list[EscalationPrediction] = []
        for task_info in tasks:
            pred = self.predict(
                task=task_info.get("task", ""),
                task_type=task_info.get("task_type"),
                module=task_info.get("module"),
            )
            predictions.append(pred)

        predictions.sort(key=lambda p: p.predicted_probability, reverse=True)
        return predictions

    def record_outcome(self, prediction_id: str, actually_escalated: bool) -> bool:
        """Record whether a prediction was correct.

        Updates the prediction's actual_escalated field for accuracy tracking.
        """
        try:
            if self._conn is None:
                return False

            cursor = self._conn.execute(
                """UPDATE predictions SET actual_escalated = ?
                   WHERE prediction_id = ?""",
                (int(actually_escalated), prediction_id),
            )
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False

    def get_prediction_accuracy(self) -> dict:
        """Calculate prediction accuracy metrics.

        Returns breakdown by probability bucket with false positive/negative rates.
        """
        try:
            if self._conn is None:
                return self._empty_accuracy()

            cursor = self._conn.execute(
                """SELECT predicted_probability, actual_escalated
                   FROM predictions
                   WHERE actual_escalated IS NOT NULL"""
            )
            rows = cursor.fetchall()

            if not rows:
                return self._empty_accuracy()

            total = len(rows)
            correct = 0
            false_positives = 0  # predicted high, didn't escalate
            false_negatives = 0  # predicted low, did escalate
            true_positives = 0
            true_negatives = 0

            for row in rows:
                prob = row["predicted_probability"]
                actual = bool(row["actual_escalated"])
                predicted_escalate = prob >= 0.5

                if predicted_escalate and actual:
                    correct += 1
                    true_positives += 1
                elif not predicted_escalate and not actual:
                    correct += 1
                    true_negatives += 1
                elif predicted_escalate and not actual:
                    false_positives += 1
                else:
                    false_negatives += 1

            predicted_positive = true_positives + false_positives
            predicted_negative = true_negatives + false_negatives

            return {
                "total_predictions": total,
                "correct": correct,
                "incorrect": total - correct,
                "accuracy": round(correct / total, 4) if total > 0 else 0.0,
                "false_positive_rate": (
                    round(false_positives / predicted_positive, 4)
                    if predicted_positive > 0
                    else 0.0
                ),
                "false_negative_rate": (
                    round(false_negatives / predicted_negative, 4)
                    if predicted_negative > 0
                    else 0.0
                ),
                "true_positives": true_positives,
                "true_negatives": true_negatives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
            }
        except Exception:
            return self._empty_accuracy()

    def get_escalation_forecast(self, task_types: list[str] | None = None) -> dict:
        """Forecast escalation rates and identify highest-ROI knowledge investments.

        For Harbinger briefing integration — shows where targeted knowledge
        documents would most reduce Apex dependency.
        """
        try:
            if self._conn is None:
                return {"forecasts": [], "recommendations": []}

            if task_types:
                placeholders = ",".join("?" for _ in task_types)
                query = f"""
                    SELECT task_type,
                           COUNT(*) as total,
                           SUM(CASE WHEN actual_escalated = 1 THEN 1 ELSE 0 END) as escalated,
                           AVG(predicted_probability) as avg_probability
                    FROM predictions
                    WHERE task_type IN ({placeholders})
                    GROUP BY task_type
                """
                cursor = self._conn.execute(query, task_types)
            else:
                cursor = self._conn.execute("""
                    SELECT task_type,
                           COUNT(*) as total,
                           SUM(CASE WHEN actual_escalated = 1 THEN 1 ELSE 0 END) as escalated,
                           AVG(predicted_probability) as avg_probability
                    FROM predictions
                    WHERE task_type != ''
                    GROUP BY task_type
                """)

            rows = cursor.fetchall()
            forecasts = []
            recommendations = []

            for row in rows:
                task_type = row["task_type"]
                total = row["total"]
                escalated = row["escalated"] or 0
                rate = escalated / total if total > 0 else 0.0

                forecast_entry = {
                    "task_type": task_type,
                    "total_tasks": total,
                    "escalated": escalated,
                    "escalation_rate": round(rate, 4),
                    "avg_predicted_probability": round(row["avg_probability"] or 0.0, 4),
                }
                forecasts.append(forecast_entry)

                # Generate recommendations for high-escalation domains
                if rate > 0.4 and total >= 3:
                    estimated_reduction = min(rate * 0.6, 0.5)  # Knowledge could reduce by ~60%
                    recommendations.append({
                        "task_type": task_type,
                        "current_rate": round(rate, 4),
                        "estimated_reduced_rate": round(rate - estimated_reduction, 4),
                        "suggestion": (
                            f"{task_type} tasks: ~{rate:.0%} escalation rate. "
                            f"3 targeted knowledge documents would reduce to "
                            f"~{rate - estimated_reduction:.0%}."
                        ),
                    })

            # Sort forecasts by escalation rate descending
            forecasts.sort(key=lambda f: f["escalation_rate"], reverse=True)
            recommendations.sort(key=lambda r: r["current_rate"], reverse=True)

            return {
                "forecasts": forecasts,
                "recommendations": recommendations,
            }
        except Exception:
            return {"forecasts": [], "recommendations": []}

    def get_cost_forecast(self, daily_task_count: int = 50) -> dict:
        """Estimate daily Apex API cost based on current escalation rates.

        Uses average cost per Apex call and current escalation patterns
        to project spending.
        """
        # Average cost per Apex API call (Claude/GPT)
        avg_cost_per_call = 0.03  # ~$0.03 per typical Apex query

        try:
            if self._conn is None:
                return self._empty_cost_forecast(daily_task_count, avg_cost_per_call)

            cursor = self._conn.execute("""
                SELECT task_type,
                       COUNT(*) as total,
                       SUM(CASE WHEN actual_escalated = 1 THEN 1 ELSE 0 END) as escalated
                FROM predictions
                WHERE actual_escalated IS NOT NULL AND task_type != ''
                GROUP BY task_type
                ORDER BY escalated DESC
            """)
            rows = cursor.fetchall()

            if not rows:
                return self._empty_cost_forecast(daily_task_count, avg_cost_per_call)

            # Calculate overall escalation rate
            total_all = sum(r["total"] for r in rows)
            escalated_all = sum(r["escalated"] or 0 for r in rows)
            overall_rate = escalated_all / total_all if total_all > 0 else 0.0

            estimated_daily_escalations = daily_task_count * overall_rate
            estimated_daily_cost = estimated_daily_escalations * avg_cost_per_call
            estimated_monthly_cost = estimated_daily_cost * 30

            top_cost_drivers = []
            for row in rows[:5]:
                task_type = row["task_type"]
                esc = row["escalated"] or 0
                tot = row["total"]
                rate = esc / tot if tot > 0 else 0.0
                top_cost_drivers.append({
                    "task_type": task_type,
                    "escalation_rate": round(rate, 4),
                    "estimated_daily_cost": round(
                        (daily_task_count * rate * avg_cost_per_call) / max(len(rows), 1), 4
                    ),
                })

            return {
                "daily_task_count": daily_task_count,
                "overall_escalation_rate": round(overall_rate, 4),
                "estimated_daily_escalations": round(estimated_daily_escalations, 1),
                "estimated_daily_cost": round(estimated_daily_cost, 4),
                "estimated_monthly_cost": round(estimated_monthly_cost, 2),
                "top_cost_drivers": top_cost_drivers,
            }
        except Exception:
            return self._empty_cost_forecast(daily_task_count, avg_cost_per_call)

    def _store_prediction(self, prediction: EscalationPrediction) -> None:
        """Persist a prediction to SQLite."""
        import json

        try:
            if self._conn is None:
                return

            self._conn.execute(
                """INSERT INTO predictions
                   (prediction_id, task_description, task_type,
                    predicted_probability, confidence_in_prediction,
                    risk_factors, preparation_actions, actual_escalated, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    prediction.prediction_id,
                    prediction.task_description,
                    prediction.task_type,
                    prediction.predicted_probability,
                    prediction.confidence_in_prediction,
                    json.dumps(prediction.risk_factors),
                    json.dumps(prediction.preparation_actions),
                    None,
                    prediction.timestamp,
                ),
            )
            self._conn.commit()
        except Exception:
            pass

    @staticmethod
    def _empty_accuracy() -> dict:
        """Return empty accuracy metrics."""
        return {
            "total_predictions": 0,
            "correct": 0,
            "incorrect": 0,
            "accuracy": 0.0,
            "false_positive_rate": 0.0,
            "false_negative_rate": 0.0,
            "true_positives": 0,
            "true_negatives": 0,
            "false_positives": 0,
            "false_negatives": 0,
        }

    @staticmethod
    def _empty_cost_forecast(daily_task_count: int, avg_cost: float) -> dict:
        """Return empty cost forecast."""
        return {
            "daily_task_count": daily_task_count,
            "overall_escalation_rate": 0.0,
            "estimated_daily_escalations": 0.0,
            "estimated_daily_cost": 0.0,
            "estimated_monthly_cost": 0.0,
            "top_cost_drivers": [],
        }

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
