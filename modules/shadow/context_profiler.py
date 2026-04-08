"""
Context Window Profiler — Diagnostic Tool for LLM Context Usage
================================================================
Observation-only diagnostic that records how each LLM call uses the
context window. Identifies waste patterns (unused tool schemas, unreferenced
Grimoire context) and generates optimization suggestions.

Never modifies context — only records and analyses.

Author: Patrick (with Claude Opus 4.6)
Project: Shadow
Module: Shadow / Context Profiler
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.context_profiler")


@dataclass
class ContextProfile:
    """Token-level snapshot of a single LLM call's context window."""

    profile_id: str = ""
    timestamp: float = 0.0
    model: str = ""
    task_type: str = ""
    module: str = ""

    # Token breakdown
    system_prompt_tokens: int = 0
    grimoire_tokens: int = 0
    history_tokens: int = 0
    tool_schema_tokens: int = 0
    failure_pattern_tokens: int = 0
    user_input_tokens: int = 0
    response_headroom_tokens: int = 0
    total_tokens: int = 0
    token_limit: int = 0
    usage_percent: float = 0.0

    # Efficiency metrics
    grimoire_tokens_referenced: int = 0
    tool_schemas_used: int = 0
    tool_schemas_loaded: int = 0
    was_trimmed: bool = False
    trimmed_components: list[str] = field(default_factory=list)
    compression_ratio: float = 0.0


class ContextProfiler:
    """Records and analyses LLM context window usage over time.

    Observation-only — never modifies context, never blocks the pipeline.
    All SQLite operations are wrapped in try/except so profiling failures
    never affect the main request path.
    """

    def __init__(self, db_path: str = "data/context_profiles.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Database setup
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        try:
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS context_profiles (
                        profile_id TEXT PRIMARY KEY,
                        timestamp REAL NOT NULL,
                        model TEXT,
                        task_type TEXT,
                        module TEXT,
                        system_prompt_tokens INTEGER DEFAULT 0,
                        grimoire_tokens INTEGER DEFAULT 0,
                        history_tokens INTEGER DEFAULT 0,
                        tool_schema_tokens INTEGER DEFAULT 0,
                        failure_pattern_tokens INTEGER DEFAULT 0,
                        user_input_tokens INTEGER DEFAULT 0,
                        response_headroom_tokens INTEGER DEFAULT 0,
                        total_tokens INTEGER DEFAULT 0,
                        token_limit INTEGER DEFAULT 0,
                        usage_percent REAL DEFAULT 0.0,
                        grimoire_tokens_referenced INTEGER DEFAULT 0,
                        tool_schemas_used INTEGER DEFAULT 0,
                        tool_schemas_loaded INTEGER DEFAULT 0,
                        was_trimmed INTEGER DEFAULT 0,
                        trimmed_components TEXT DEFAULT '[]',
                        compression_ratio REAL DEFAULT 0.0
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.warning("Context profiler DB init failed: %s", e)

    def _get_conn(self) -> sqlite3.Connection:
        """Return a new connection with row_factory set."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_profile(self, profile: ContextProfile) -> str:
        """Store a ContextProfile in SQLite. Returns the profile_id."""
        try:
            if not profile.profile_id:
                profile.profile_id = str(uuid.uuid4())
            if profile.timestamp == 0.0:
                profile.timestamp = time.time()
            if profile.token_limit > 0 and profile.usage_percent == 0.0:
                profile.usage_percent = (
                    profile.total_tokens / profile.token_limit * 100
                )

            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO context_profiles (
                        profile_id, timestamp, model, task_type, module,
                        system_prompt_tokens, grimoire_tokens, history_tokens,
                        tool_schema_tokens, failure_pattern_tokens,
                        user_input_tokens, response_headroom_tokens,
                        total_tokens, token_limit, usage_percent,
                        grimoire_tokens_referenced, tool_schemas_used,
                        tool_schemas_loaded, was_trimmed, trimmed_components,
                        compression_ratio
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        profile.profile_id,
                        profile.timestamp,
                        profile.model,
                        profile.task_type,
                        profile.module,
                        profile.system_prompt_tokens,
                        profile.grimoire_tokens,
                        profile.history_tokens,
                        profile.tool_schema_tokens,
                        profile.failure_pattern_tokens,
                        profile.user_input_tokens,
                        profile.response_headroom_tokens,
                        profile.total_tokens,
                        profile.token_limit,
                        profile.usage_percent,
                        profile.grimoire_tokens_referenced,
                        profile.tool_schemas_used,
                        profile.tool_schemas_loaded,
                        1 if profile.was_trimmed else 0,
                        json.dumps(profile.trimmed_components),
                        profile.compression_ratio,
                    ),
                )
                conn.commit()
            return profile.profile_id
        except Exception as e:
            logger.warning("Failed to record context profile: %s", e)
            return profile.profile_id or ""

    def record_from_context_package(
        self,
        ctx_package: Any,
        task: dict,
        response: str = "",
    ) -> str:
        """Build a ContextProfile from a ContextPackage and record it.

        Auto-calculates referenced grimoire tokens by checking if grimoire
        content appears in the response, and tool usage from tool_schemas.
        """
        try:
            breakdown = getattr(ctx_package, "token_breakdown", {}) or {}

            # Estimate grimoire tokens referenced in the response
            grimoire_text = getattr(ctx_package, "grimoire_context", "") or ""
            grimoire_tokens = breakdown.get("grimoire", 0)
            grimoire_referenced = 0
            if response and grimoire_text:
                # Rough heuristic: check what fraction of grimoire sentences
                # appear in the response
                sentences = [
                    s.strip()
                    for s in grimoire_text.split(".")
                    if len(s.strip()) > 20
                ]
                if sentences:
                    hits = sum(1 for s in sentences if s in response)
                    grimoire_referenced = int(
                        grimoire_tokens * (hits / len(sentences))
                    )

            # Count tool schemas loaded vs used
            tool_schemas = getattr(ctx_package, "tool_schemas", []) or []
            schemas_loaded = len(tool_schemas)
            schemas_used = 0
            if response:
                for schema in tool_schemas:
                    name = schema.get("name", "")
                    if name and name in response:
                        schemas_used += 1

            # Compression ratio from compression_report
            comp_report = getattr(ctx_package, "compression_report", {}) or {}
            compression_ratio = comp_report.get("compression_ratio", 0.0)

            token_limit = getattr(ctx_package, "token_budget", 0)
            total_tokens = getattr(ctx_package, "total_tokens", 0)

            profile = ContextProfile(
                profile_id=str(uuid.uuid4()),
                timestamp=time.time(),
                model=task.get("model", ""),
                task_type=task.get("type", ""),
                module=task.get("module", "") or "",
                system_prompt_tokens=breakdown.get("system_prompt", 0),
                grimoire_tokens=grimoire_tokens,
                history_tokens=breakdown.get("history", 0),
                tool_schema_tokens=breakdown.get("tools", 0),
                failure_pattern_tokens=breakdown.get("failure_patterns", 0),
                user_input_tokens=breakdown.get("user_input", 0),
                response_headroom_tokens=max(0, token_limit - total_tokens),
                total_tokens=total_tokens,
                token_limit=token_limit,
                usage_percent=(
                    (total_tokens / token_limit * 100)
                    if token_limit > 0
                    else 0.0
                ),
                grimoire_tokens_referenced=grimoire_referenced,
                tool_schemas_used=schemas_used,
                tool_schemas_loaded=schemas_loaded,
                was_trimmed=getattr(ctx_package, "trimmed", False),
                trimmed_components=list(
                    getattr(ctx_package, "trimmed_details", []) or []
                ),
                compression_ratio=compression_ratio,
            )
            return self.record_profile(profile)
        except Exception as e:
            logger.warning("Failed to record profile from context package: %s", e)
            return ""

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def get_profile_count(self) -> int:
        """Total number of profiles stored."""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) FROM context_profiles"
                ).fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def get_waste_report(self, days: int = 7) -> dict:
        """Analyse profiles over the period and identify waste patterns."""
        try:
            cutoff = time.time() - days * 86400
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM context_profiles
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                    """,
                    (cutoff,),
                ).fetchall()

            if not rows:
                return {
                    "period_days": days,
                    "profile_count": 0,
                    "unused_tool_tokens": 0,
                    "unused_grimoire_tokens": 0,
                    "avg_usage_percent": 0.0,
                    "trim_frequency": 0.0,
                    "biggest_waste_component": "none",
                    "summary": "No profiles recorded in the last {} days.".format(
                        days
                    ),
                }

            count = len(rows)

            # Unused tool tokens: tokens spent on schemas for tools not called
            total_unused_tool = 0
            total_unused_grimoire = 0
            total_usage_pct = 0.0
            trim_count = 0

            # Component waste accumulators
            waste_by_component: dict[str, int] = {
                "tool_schemas": 0,
                "grimoire": 0,
                "history": 0,
                "system_prompt": 0,
            }

            for row in rows:
                # Tool waste: proportion of schemas loaded but not used
                loaded = row["tool_schemas_loaded"]
                used = row["tool_schemas_used"]
                schema_tokens = row["tool_schema_tokens"]
                if loaded > 0 and schema_tokens > 0:
                    unused_frac = (loaded - used) / loaded
                    total_unused_tool += int(schema_tokens * unused_frac)

                # Grimoire waste: tokens loaded minus tokens referenced
                grim_loaded = row["grimoire_tokens"]
                grim_ref = row["grimoire_tokens_referenced"]
                total_unused_grimoire += max(0, grim_loaded - grim_ref)

                total_usage_pct += row["usage_percent"]
                if row["was_trimmed"]:
                    trim_count += 1

                # Track per-component waste for biggest-waste detection
                if loaded > 0:
                    waste_by_component["tool_schemas"] += int(
                        schema_tokens * ((loaded - used) / loaded)
                    ) if loaded > used else 0
                waste_by_component["grimoire"] += max(
                    0, grim_loaded - grim_ref
                )

            avg_unused_tool = total_unused_tool // count
            avg_unused_grimoire = total_unused_grimoire // count
            avg_usage_pct = total_usage_pct / count
            trim_freq = (trim_count / count) * 100

            # Find biggest waste component
            biggest = max(waste_by_component, key=waste_by_component.get)  # type: ignore[arg-type]
            if waste_by_component[biggest] == 0:
                biggest = "none"

            # Build plain-English summary
            summaries: list[str] = []
            if avg_unused_tool > 0:
                summaries.append(
                    "Average {:,} tokens on unused tool schemas per request. "
                    "Consider tightening dynamic tool loading.".format(
                        avg_unused_tool
                    )
                )
            if avg_unused_grimoire > 0:
                summaries.append(
                    "Grimoire context used {:,} tokens on average but model "
                    "only referenced ~{:,}. Consider more aggressive staged "
                    "retrieval.".format(
                        total_unused_grimoire // count + (total_unused_grimoire // count - avg_unused_grimoire) if count else 0,
                        (total_unused_grimoire - total_unused_grimoire + avg_unused_grimoire) if count else 0,
                    )
                )
            if trim_freq > 30:
                summaries.append(
                    "Context trimming triggered on {:.0f}% of requests.".format(
                        trim_freq
                    )
                )
            if not summaries:
                summaries.append(
                    "Context usage looks healthy over the last {} days.".format(
                        days
                    )
                )

            return {
                "period_days": days,
                "profile_count": count,
                "unused_tool_tokens": avg_unused_tool,
                "unused_grimoire_tokens": avg_unused_grimoire,
                "avg_usage_percent": round(avg_usage_pct, 1),
                "trim_frequency": round(trim_freq, 1),
                "biggest_waste_component": biggest,
                "summary": " ".join(summaries),
            }
        except Exception as e:
            logger.warning("Waste report generation failed: %s", e)
            return {
                "period_days": days,
                "profile_count": 0,
                "unused_tool_tokens": 0,
                "unused_grimoire_tokens": 0,
                "avg_usage_percent": 0.0,
                "trim_frequency": 0.0,
                "biggest_waste_component": "none",
                "summary": "Waste report failed: {}".format(e),
            }

    def get_usage_trend(
        self, days: int = 30, granularity: str = "daily"
    ) -> list[dict]:
        """Token usage over time for dashboards / briefings.

        Returns [{date, avg_total_tokens, avg_usage_percent, request_count}].
        """
        try:
            cutoff = time.time() - days * 86400
            # SQLite date grouping
            if granularity == "hourly":
                fmt = "%Y-%m-%d %H:00"
            elif granularity == "weekly":
                fmt = "%Y-W%W"
            else:
                fmt = "%Y-%m-%d"

            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        strftime(?, timestamp, 'unixepoch') AS period,
                        AVG(total_tokens) AS avg_total_tokens,
                        AVG(usage_percent) AS avg_usage_percent,
                        COUNT(*) AS request_count
                    FROM context_profiles
                    WHERE timestamp >= ?
                    GROUP BY period
                    ORDER BY period ASC
                    """,
                    (fmt, cutoff),
                ).fetchall()

            return [
                {
                    "date": row["period"],
                    "avg_total_tokens": int(row["avg_total_tokens"]),
                    "avg_usage_percent": round(row["avg_usage_percent"], 1),
                    "request_count": row["request_count"],
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning("Usage trend generation failed: %s", e)
            return []

    def get_component_breakdown(self, days: int = 7) -> dict:
        """Average token allocation per component with percentages and trends."""
        try:
            cutoff = time.time() - days * 86400
            prev_cutoff = cutoff - days * 86400  # previous period of same length

            with self._get_conn() as conn:
                current = conn.execute(
                    """
                    SELECT
                        AVG(system_prompt_tokens) AS system_prompt,
                        AVG(grimoire_tokens) AS grimoire,
                        AVG(history_tokens) AS history,
                        AVG(tool_schema_tokens) AS tools,
                        AVG(failure_pattern_tokens) AS failure_patterns,
                        AVG(user_input_tokens) AS user_input,
                        AVG(response_headroom_tokens) AS response_headroom,
                        AVG(total_tokens) AS total,
                        COUNT(*) AS count
                    FROM context_profiles
                    WHERE timestamp >= ?
                    """,
                    (cutoff,),
                ).fetchone()

                previous = conn.execute(
                    """
                    SELECT
                        AVG(system_prompt_tokens) AS system_prompt,
                        AVG(grimoire_tokens) AS grimoire,
                        AVG(history_tokens) AS history,
                        AVG(tool_schema_tokens) AS tools,
                        AVG(failure_pattern_tokens) AS failure_patterns,
                        AVG(user_input_tokens) AS user_input,
                        AVG(response_headroom_tokens) AS response_headroom,
                        AVG(total_tokens) AS total,
                        COUNT(*) AS count
                    FROM context_profiles
                    WHERE timestamp >= ? AND timestamp < ?
                    """,
                    (prev_cutoff, cutoff),
                ).fetchone()

            if not current or current["count"] == 0:
                return {
                    "period_days": days,
                    "profile_count": 0,
                    "components": {},
                    "percentages": {},
                    "trends": {},
                }

            components = {
                "system_prompt": int(current["system_prompt"] or 0),
                "grimoire": int(current["grimoire"] or 0),
                "history": int(current["history"] or 0),
                "tools": int(current["tools"] or 0),
                "failure_patterns": int(current["failure_patterns"] or 0),
                "user_input": int(current["user_input"] or 0),
                "response_headroom": int(current["response_headroom"] or 0),
            }

            total = int(current["total"] or 0)
            percentages = {}
            for comp, tokens in components.items():
                percentages[comp] = (
                    round(tokens / total * 100, 1) if total > 0 else 0.0
                )

            # Trend vs previous period
            trends: dict[str, str] = {}
            if previous and previous["count"] and previous["count"] > 0:
                comp_keys = [
                    "system_prompt", "grimoire", "history", "tools",
                    "failure_patterns", "user_input", "response_headroom",
                ]
                for key in comp_keys:
                    prev_val = previous[key] or 0
                    curr_val = current[key] or 0
                    if prev_val == 0:
                        trends[key] = "new" if curr_val > 0 else "stable"
                    else:
                        change = (curr_val - prev_val) / prev_val * 100
                        if change > 10:
                            trends[key] = "growing"
                        elif change < -10:
                            trends[key] = "shrinking"
                        else:
                            trends[key] = "stable"
            else:
                trends = {k: "no_prior_data" for k in components}

            return {
                "period_days": days,
                "profile_count": current["count"],
                "components": components,
                "percentages": percentages,
                "trends": trends,
            }
        except Exception as e:
            logger.warning("Component breakdown failed: %s", e)
            return {
                "period_days": days,
                "profile_count": 0,
                "components": {},
                "percentages": {},
                "trends": {},
            }

    def get_optimization_suggestions(self) -> list[str]:
        """Rule-based suggestions derived from the waste report."""
        try:
            report = self.get_waste_report(days=7)
            breakdown = self.get_component_breakdown(days=7)
            suggestions: list[str] = []

            if report["profile_count"] == 0:
                return suggestions

            # High unused tool tokens
            unused_tools = report["unused_tool_tokens"]
            if unused_tools > 2000:
                suggestions.append(
                    "Tool schemas waste {:,} tokens/request on average. "
                    "Review DynamicToolLoader filtering.".format(unused_tools)
                )

            # High unused grimoire tokens
            if report["profile_count"] > 0:
                # Check if unused grimoire > 50% of loaded
                components = breakdown.get("components", {})
                avg_grimoire = components.get("grimoire", 0)
                unused_grim = report["unused_grimoire_tokens"]
                if avg_grimoire > 0 and unused_grim > avg_grimoire * 0.5:
                    suggestions.append(
                        "Grimoire retrieval returning too much unused context. "
                        "Tighten StagedRetrieval auto_select."
                    )

            # Frequent trimming
            trim_freq = report["trim_frequency"]
            if trim_freq > 30:
                suggestions.append(
                    "Context trimming too frequent ({:.0f}%). Consider lower "
                    "max results or more aggressive compression.".format(
                        trim_freq
                    )
                )

            # History consuming too much
            percentages = breakdown.get("percentages", {})
            history_pct = percentages.get("history", 0.0)
            if history_pct > 30:
                suggestions.append(
                    "Conversation history consuming {:.0f}% of context. "
                    "Consider more aggressive history compression.".format(
                        history_pct
                    )
                )

            return suggestions
        except Exception as e:
            logger.warning("Optimization suggestions failed: %s", e)
            return []
