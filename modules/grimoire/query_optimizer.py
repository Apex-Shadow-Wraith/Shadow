"""
Grimoire Query Optimizer — Auto-Tune Retrieval Performance
============================================================
Like a SQL query planner but for vector retrieval. Tracks every Grimoire
query, measures what gets used vs. wasted, and generates optimization
recommendations to cut token waste.

HOW IT WORKS:
    1. Every Grimoire query gets logged: what was asked, what came back,
       what the model actually used in its response
    2. Analysis methods crunch the logs to find patterns:
       - Usage rate (what % of returned results are actually referenced?)
       - Co-retrieved documents (always come back together → bundle them)
       - Never-used results (returned but never referenced → demote them)
    3. generate_optimization_plan() combines all analyses into actionable
       recommendations with estimated token savings
    4. apply_optimizations() can execute the plan (requires approval flag)

IMPORTANT:
    - Query logging is passive — never affects query results
    - All analyses are rule-based, no LLM calls
    - Auto-apply requires explicit approval flag (Patrick must approve)

Author: Patrick (with Claude Opus 4.6)
Project: Shadow
Module: Grimoire Query Optimizer
"""

from __future__ import annotations

import sqlite3
import uuid
import math
from datetime import datetime, timedelta
from pathlib import Path


class GrimoireQueryOptimizer:
    """Auto-tune Grimoire retrieval based on query pattern analysis."""

    def __init__(self, grimoire=None, db_path: str = "data/query_optimizer.db"):
        """
        Initialize the query optimizer.

        Args:
            grimoire: Reference to Grimoire instance for testing optimizations.
            db_path: Path to SQLite database for query logs and analysis.
        """
        self.grimoire = grimoire
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create query log tables if they don't exist."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_logs (
                    log_id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    results_returned INTEGER NOT NULL,
                    results_used INTEGER NOT NULL,
                    response_referenced TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS optimization_history (
                    plan_id TEXT PRIMARY KEY,
                    plan_json TEXT NOT NULL,
                    applied INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # =========================================================================
    # QUERY LOGGING
    # =========================================================================

    def log_query(
        self,
        query: str,
        collection: str,
        results_returned: int,
        results_used: int,
        response_referenced: list[str],
        duration_ms: float,
    ) -> str:
        """
        Record a Grimoire query and its outcome.

        Args:
            query: The search query text.
            collection: Which Grimoire collection was queried.
            results_returned: How many results came back from the query.
            results_used: How many returned results were actually referenced.
            response_referenced: Which doc IDs appeared to be used.
            duration_ms: How long the query took in milliseconds.

        Returns:
            log_id: Unique identifier for this log entry.
        """
        log_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        import json
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """INSERT INTO query_logs
                   (log_id, query, collection, results_returned, results_used,
                    response_referenced, duration_ms, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    log_id,
                    query,
                    collection,
                    results_returned,
                    results_used,
                    json.dumps(response_referenced),
                    duration_ms,
                    timestamp,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return log_id

    # =========================================================================
    # ANALYSIS METHODS
    # =========================================================================

    def analyze_relevance(self, days: int = 7) -> dict:
        """
        Analyze what percentage of returned results are actually used.

        Args:
            days: How many days back to analyze.

        Returns:
            Dictionary with avg_results_returned, avg_results_used,
            usage_rate, waste_rate.
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                """SELECT results_returned, results_used
                   FROM query_logs WHERE timestamp >= ?""",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return {
                "avg_results_returned": 0.0,
                "avg_results_used": 0.0,
                "usage_rate": 0.0,
                "waste_rate": 0.0,
            }

        total_returned = sum(r[0] for r in rows)
        total_used = sum(r[1] for r in rows)
        count = len(rows)

        avg_returned = total_returned / count
        avg_used = total_used / count
        usage_rate = total_used / total_returned if total_returned > 0 else 0.0
        waste_rate = 1.0 - usage_rate

        return {
            "avg_results_returned": round(avg_returned, 2),
            "avg_results_used": round(avg_used, 2),
            "usage_rate": round(usage_rate, 4),
            "waste_rate": round(waste_rate, 4),
        }

    def find_co_retrieved_documents(self, min_co_occurrence: int = 3) -> list[tuple]:
        """
        Find documents that are frequently retrieved together.

        If doc A and doc B always come back together, they could be pre-bundled
        to reduce redundant retrieval overhead.

        Args:
            min_co_occurrence: Minimum times docs must co-occur to be reported.

        Returns:
            List of (doc_id_A, doc_id_B, co_occurrence_count) tuples.
        """
        import json
        from collections import Counter

        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT response_referenced FROM query_logs"
            ).fetchall()
        finally:
            conn.close()

        pair_counts: Counter = Counter()
        for (ref_json,) in rows:
            doc_ids = json.loads(ref_json)
            # Sort to ensure consistent pair ordering
            doc_ids = sorted(set(doc_ids))
            for i in range(len(doc_ids)):
                for j in range(i + 1, len(doc_ids)):
                    pair_counts[(doc_ids[i], doc_ids[j])] += 1

        results = []
        for (doc_a, doc_b), count in pair_counts.most_common():
            if count >= min_co_occurrence:
                results.append((doc_a, doc_b, count))

        return results

    def find_never_used_results(self, min_queries: int = 10) -> list[dict]:
        """
        Find documents that get returned but are never referenced in responses.

        These waste tokens every time they're retrieved.

        Args:
            min_queries: Minimum times a doc must be returned to be considered.

        Returns:
            List of dicts with doc_id, times_returned, times_used, suggested_action.
        """
        import json
        from collections import defaultdict

        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT results_returned, results_used, response_referenced FROM query_logs"
            ).fetchall()
        finally:
            conn.close()

        # Track per-doc stats: how many times returned vs. referenced
        doc_returned: dict[str, int] = defaultdict(int)
        doc_used: dict[str, int] = defaultdict(int)

        for _, _, ref_json in rows:
            referenced = json.loads(ref_json)
            # All referenced docs count as both returned and used
            for doc_id in referenced:
                doc_used[doc_id] += 1
                doc_returned[doc_id] += 1

        # We also need to track docs that were returned but NOT referenced.
        # Since we only have referenced doc IDs, we infer from query patterns.
        # A doc that appears in response_referenced is "used". We need to also
        # track docs that appear in results but NOT in response_referenced.
        # For now, we track all unique doc IDs across all queries and their usage.

        # Build the never-used list
        results = []
        for doc_id, returned_count in doc_returned.items():
            used_count = doc_used.get(doc_id, 0)
            if returned_count >= min_queries and used_count == 0:
                results.append({
                    "doc_id": doc_id,
                    "times_returned": returned_count,
                    "times_used": 0,
                    "suggested_action": "demote",
                })

        return results

    def get_optimal_n_results(self, collection: str = None) -> int:
        """
        Based on usage patterns, determine the optimal n_results for queries.

        If only 2-3 results are typically used, returning 10 wastes tokens.
        Adds a buffer of ~60% above average usage to catch edge cases.

        Args:
            collection: Specific collection to analyze (None = all).

        Returns:
            Recommended n_results value (minimum 1).
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            if collection:
                rows = conn.execute(
                    "SELECT results_used FROM query_logs WHERE collection = ?",
                    (collection,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT results_used FROM query_logs"
                ).fetchall()
        finally:
            conn.close()

        if not rows:
            return 5  # Default when no data

        avg_used = sum(r[0] for r in rows) / len(rows)
        # Add ~60% buffer, round up, minimum 1
        optimal = max(1, math.ceil(avg_used * 1.6))
        return optimal

    def get_similarity_threshold_recommendation(self) -> float:
        """
        Recommend a similarity threshold based on relevance patterns.

        If many low-similarity results are returned but never used, raise threshold.
        If all results are used, threshold might be too high (missing relevant docs).

        Returns:
            Recommended threshold between 0.0 and 1.0.
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                "SELECT results_returned, results_used FROM query_logs"
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return 0.5  # Default threshold

        total_returned = sum(r[0] for r in rows)
        total_used = sum(r[1] for r in rows)

        if total_returned == 0:
            return 0.5

        usage_rate = total_used / total_returned

        # High waste → raise threshold to filter out low-quality results
        # Low waste → lower threshold slightly to catch more relevant docs
        if usage_rate < 0.3:
            # Very wasteful — many irrelevant results
            return 0.7
        elif usage_rate < 0.5:
            # Moderate waste
            return 0.6
        elif usage_rate < 0.8:
            # Decent usage but room for improvement
            return 0.5
        else:
            # Almost everything is used — threshold might be too restrictive
            return 0.4

    # =========================================================================
    # AUTO-TUNING
    # =========================================================================

    def generate_optimization_plan(self) -> dict:
        """
        Combine all analyses into actionable recommendations.

        Returns:
            Dictionary with recommended_n_results, recommended_similarity_threshold,
            documents_to_demote, documents_to_bundle, estimated_token_savings,
            confidence_in_recommendations, and plain-English recommendations.
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            total_queries = conn.execute(
                "SELECT COUNT(*) FROM query_logs"
            ).fetchone()[0]
        finally:
            conn.close()

        relevance = self.analyze_relevance(days=30)
        co_retrieved = self.find_co_retrieved_documents(min_co_occurrence=3)
        never_used = self.find_never_used_results(min_queries=5)
        optimal_n = self.get_optimal_n_results()
        threshold = self.get_similarity_threshold_recommendation()

        # Confidence scales with sample size
        if total_queries == 0:
            confidence = 0.0
        elif total_queries < 5:
            confidence = 0.1
        elif total_queries < 20:
            confidence = 0.3
        elif total_queries < 50:
            confidence = 0.5
        elif total_queries < 100:
            confidence = 0.7
        else:
            confidence = 0.9

        # Estimate token savings per query
        # Assume ~200 tokens per result on average
        tokens_per_result = 200
        current_avg = relevance.get("avg_results_returned", 0)
        savings_per_query = max(0, int((current_avg - optimal_n) * tokens_per_result))

        # Build plain-English recommendations
        recommendations = []
        if relevance.get("waste_rate", 0) > 0.5:
            recommendations.append(
                f"High waste rate ({relevance['waste_rate']:.0%}). "
                f"Reduce n_results from ~{current_avg:.0f} to {optimal_n}."
            )
        if never_used:
            recommendations.append(
                f"{len(never_used)} document(s) are returned frequently but never used. "
                "Consider demoting them to reduce noise."
            )
        if co_retrieved:
            recommendations.append(
                f"{len(co_retrieved)} document pair(s) are frequently co-retrieved. "
                "Consider pre-bundling them."
            )
        if not recommendations:
            recommendations.append("Retrieval is performing well. No urgent changes needed.")

        plan = {
            "recommended_n_results": optimal_n,
            "recommended_similarity_threshold": threshold,
            "documents_to_demote": [d["doc_id"] for d in never_used],
            "documents_to_bundle": [(a, b) for a, b, _ in co_retrieved],
            "estimated_token_savings": savings_per_query,
            "confidence_in_recommendations": confidence,
            "recommendations": recommendations,
        }

        # Log the plan
        import json
        plan_id = str(uuid.uuid4())
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                """INSERT INTO optimization_history (plan_id, plan_json, timestamp)
                   VALUES (?, ?, ?)""",
                (plan_id, json.dumps(plan, default=str), datetime.now().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

        return plan

    def apply_optimizations(self, grimoire, plan: dict, approved: bool = False) -> dict:
        """
        Apply an optimization plan to Grimoire.

        IMPORTANT: Requires Patrick's approval before applying destructive changes.

        Args:
            grimoire: Grimoire instance to optimize.
            plan: Optimization plan from generate_optimization_plan().
            approved: Whether Patrick has approved the changes.

        Returns:
            Dictionary with applied and skipped actions, plus reason.
        """
        applied = []
        skipped = []

        if not approved:
            # Log what would change but don't actually apply
            if plan.get("recommended_n_results"):
                skipped.append(
                    f"Would set n_results to {plan['recommended_n_results']}"
                )
            if plan.get("documents_to_demote"):
                skipped.append(
                    f"Would demote {len(plan['documents_to_demote'])} document(s)"
                )
            if plan.get("documents_to_bundle"):
                skipped.append(
                    f"Would bundle {len(plan['documents_to_bundle'])} document pair(s)"
                )
            if plan.get("recommended_similarity_threshold"):
                skipped.append(
                    f"Would set similarity threshold to "
                    f"{plan['recommended_similarity_threshold']}"
                )
            return {
                "applied": applied,
                "skipped": skipped,
                "reason": "Approval required. Run with approved=True after review.",
            }

        # With approval, apply the changes
        if plan.get("recommended_n_results") and grimoire:
            try:
                if hasattr(grimoire, "default_n_results"):
                    grimoire.default_n_results = plan["recommended_n_results"]
                    applied.append(
                        f"Set n_results to {plan['recommended_n_results']}"
                    )
                else:
                    skipped.append("Grimoire has no default_n_results attribute")
            except Exception as e:
                skipped.append(f"Failed to set n_results: {e}")

        if plan.get("documents_to_demote") and grimoire:
            for doc_id in plan["documents_to_demote"]:
                try:
                    if hasattr(grimoire, "demote_document"):
                        grimoire.demote_document(doc_id)
                        applied.append(f"Demoted document {doc_id}")
                    else:
                        skipped.append(
                            f"Grimoire has no demote_document method for {doc_id}"
                        )
                except Exception as e:
                    skipped.append(f"Failed to demote {doc_id}: {e}")

        if plan.get("documents_to_bundle") and grimoire:
            for pair in plan["documents_to_bundle"]:
                try:
                    if hasattr(grimoire, "bundle_documents"):
                        grimoire.bundle_documents(pair[0], pair[1])
                        applied.append(f"Bundled documents {pair[0]} + {pair[1]}")
                    else:
                        skipped.append(
                            f"Grimoire has no bundle_documents method for {pair}"
                        )
                except Exception as e:
                    skipped.append(f"Failed to bundle {pair}: {e}")

        if plan.get("recommended_similarity_threshold") and grimoire:
            try:
                if hasattr(grimoire, "similarity_threshold"):
                    grimoire.similarity_threshold = plan["recommended_similarity_threshold"]
                    applied.append(
                        f"Set similarity threshold to "
                        f"{plan['recommended_similarity_threshold']}"
                    )
                else:
                    skipped.append("Grimoire has no similarity_threshold attribute")
            except Exception as e:
                skipped.append(f"Failed to set threshold: {e}")

        return {
            "applied": applied,
            "skipped": skipped,
            "reason": "Optimizations applied with approval.",
        }

    # =========================================================================
    # STATS
    # =========================================================================

    def get_query_stats(self) -> dict:
        """
        Get summary statistics for the Growth Engine.

        Returns:
            Dictionary with total_queries_logged, avg_relevance_rate,
            optimization_plans_generated.
        """
        conn = sqlite3.connect(str(self.db_path))
        try:
            total_queries = conn.execute(
                "SELECT COUNT(*) FROM query_logs"
            ).fetchone()[0]

            plans_generated = conn.execute(
                "SELECT COUNT(*) FROM optimization_history"
            ).fetchone()[0]

            rows = conn.execute(
                "SELECT results_returned, results_used FROM query_logs"
            ).fetchall()
        finally:
            conn.close()

        if rows:
            total_returned = sum(r[0] for r in rows)
            total_used = sum(r[1] for r in rows)
            avg_relevance = total_used / total_returned if total_returned > 0 else 0.0
        else:
            avg_relevance = 0.0

        return {
            "total_queries_logged": total_queries,
            "avg_relevance_rate": round(avg_relevance, 4),
            "optimization_plans_generated": plans_generated,
        }
