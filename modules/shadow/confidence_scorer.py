"""
Confidence Scorer — Response Quality Evaluation
=================================================
Rule-based scoring system that evaluates the quality of Shadow's outputs
and recommends whether to respond, retry, or escalate. No LLM calls —
must be fast (under 10ms per response).

Scoring factors (weighted average):
  - completeness (0.3): Response covers what the task asked for
  - relevance (0.25): Key terms from task appear in response
  - coherence (0.15): Well-formed sentences, no loops or cutoffs
  - specificity (0.15): Concrete details vs vague generalities
  - self_consistency (0.15): No contradictions, minimal hedging

Hard gate (not weighted — caps overall score):
  - factual_grounding: Detects confabulation — claims about actions
    that never occurred. If score <= 0.3, overall confidence is capped
    at 0.3 regardless of other factors. Checks response against
    execution metadata (which module ran, API calls, tools executed).

Feeds into: RetryEngine (retry decisions), Growth Engine (analytics),
Harbinger (briefing metrics).
"""

from __future__ import annotations

import ast
import logging
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.confidence_scorer")

# Words that indicate hedging / low confidence in the response
_HEDGING_WORDS = {
    "maybe", "possibly", "perhaps", "might", "could be",
    "i think", "i believe", "i guess", "not sure", "uncertain",
    "arguably", "supposedly", "it seems", "it appears",
}

# Common stop words to filter out when extracting key terms
_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "about", "up",
    "that", "this", "these", "those", "what", "which", "who", "whom",
    "it", "its", "i", "me", "my", "we", "our", "you", "your", "he",
    "she", "they", "them", "his", "her", "their",
}


# Phrases that claim Apex / external API involvement
_APEX_CLAIM_PHRASES = [
    "apex sent", "apex generated", "apex went", "apex produced",
    "apex returned", "escalation protocol", "frontier model",
    "api returned", "claude responded", "openai responded",
    "ran through apex", "apex validated", "stress-tested",
    "payload from apex", "apex confirmed", "apex analyzed",
]

# Phrases that claim tool execution
_TOOL_CLAIM_PHRASES = [
    "executed the code", "ran the script", "test results show",
    "benchmark results", "scan complete", "analysis complete",
    "ran this through omen", "ran this through sentinel",
]

# Phrases that claim async waiting / processing
_FAKE_ASYNC_PHRASES = [
    "waiting for", "processing your", "payload to clear",
    "data stream", "buffer", "standing by for results",
    "initiated the escalation",
]


class ConfidenceScorer:
    """Evaluates response quality using fast rule-based checks.

    No LLM calls. Pure heuristics for speed. Every response Shadow
    generates gets scored before delivery.
    """

    # Factor weights
    WEIGHTS = {
        "completeness": 0.30,
        "relevance": 0.25,
        "coherence": 0.15,
        "specificity": 0.15,
        "self_consistency": 0.15,
    }

    # Recommendation thresholds
    THRESHOLD_RESPOND = 0.8
    THRESHOLD_RETRY = 0.5
    THRESHOLD_RETRY_WITH_CONTEXT = 0.3

    def __init__(self, db_path: str | Path = "data/confidence_scores.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._initialize_db()

        # Optional calibration — adjusts raw scores based on historical accuracy
        self.calibrator = None
        try:
            from modules.shadow.confidence_calibration import ConfidenceCalibrator
            self.calibrator = ConfidenceCalibrator()
        except Exception:
            pass

    def _initialize_db(self) -> None:
        """Create the scoring history table."""
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS scoring_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                task TEXT NOT NULL,
                task_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                completeness REAL NOT NULL,
                relevance REAL NOT NULL,
                coherence REAL NOT NULL,
                specificity REAL NOT NULL,
                self_consistency REAL NOT NULL,
                recommendation TEXT NOT NULL,
                response_length INTEGER NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_scoring_timestamp
            ON scoring_history(timestamp)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_scoring_task_type
            ON scoring_history(task_type)
        """)
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ================================================================
    # MAIN SCORING
    # ================================================================

    def score_response(
        self,
        task: str,
        response: str,
        task_type: str,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate response quality using rule-based checks.

        Args:
            task: The original user task/question.
            response: The generated response text.
            task_type: Classification type (question, code, math, research, etc.).
            context: Optional additional context (e.g., tool results).
            metadata: Execution metadata for confabulation detection.
                Keys: target_module (str), used_fallback (bool),
                source (str), tools_executed (list[str]).

        Returns:
            Dict with confidence (0.0-1.0), factors dict, and recommendation.
        """
        context = context or {}

        # Score each factor
        factors = {
            "completeness": self._score_completeness(task, response, task_type),
            "relevance": self._score_relevance(task, response),
            "coherence": self._score_coherence(response),
            "specificity": self._score_specificity(response, task_type),
            "self_consistency": self._score_self_consistency(response),
        }

        # Factual grounding — confabulation detection (hard gate)
        factual_grounding = self._score_factual_grounding(response, metadata)
        factors["factual_grounding"] = factual_grounding

        # Weighted average (factual_grounding is NOT weighted — it's a hard gate)
        confidence = sum(
            factors[k] * self.WEIGHTS[k] for k in self.WEIGHTS
        )

        # Task-type-specific bonuses/penalties
        bonus = self._task_type_adjustments(response, task_type)
        confidence = max(0.0, min(1.0, confidence + bonus))

        # Hard gate: if factual_grounding <= 0.3, cap overall confidence at 0.3
        if factual_grounding <= 0.3:
            confidence = min(confidence, 0.3)

        # Determine recommendation
        recommendation = self._get_recommendation(confidence)

        result = {
            "confidence": round(confidence, 4),
            "factors": {k: round(v, 4) for k, v in factors.items()},
            "recommendation": recommendation,
            "bonus": round(bonus, 4),
            "task_type": task_type,
        }

        # Apply calibration if available
        if self.calibrator is not None:
            try:
                calibrated = self.calibrator.calibrate(confidence)
                result["calibrated_score"] = round(calibrated, 4)
            except Exception:
                pass

        # Persist to history
        self._record_score(task, task_type, result, len(response))

        logger.info(
            "Confidence score: %.3f (%s) — factors: %s",
            confidence, recommendation,
            ", ".join(f"{k}={v:.2f}" for k, v in factors.items()),
        )

        return result

    # ================================================================
    # SCORING FACTORS
    # ================================================================

    def _score_completeness(
        self, task: str, response: str, task_type: str,
    ) -> float:
        """Score how completely the response addresses the task."""
        if not response or not response.strip():
            return 0.0

        response_lower = response.lower().strip()
        word_count = len(response.split())

        # "I don't know" with no explanation
        if response_lower in ("i don't know", "i don't know.", "i'm not sure", "i'm not sure."):
            return 0.0

        # Empty-ish responses
        if word_count < 3:
            return 0.1

        # Score by task type
        if task_type in ("question", "conversation"):
            # Simple question: 10+ words = 1.0
            if word_count >= 10:
                return 1.0
            return word_count / 10.0

        if task_type in ("creation", "action") and "code" in task.lower():
            # Code request
            score = 0.3  # Base for having any response
            if "def " in response or "class " in response:
                score = 0.7
            if '"""' in response or "'''" in response or "# " in response:
                score += 0.1  # Has docstring or comments
            if "return " in response:
                score += 0.1
            if word_count > 20:
                score += 0.1
            return min(1.0, score)

        if task_type == "research":
            # Research: multiple points/facts
            # Count bullet points, numbered items, or sentence-ending periods
            bullets = response.count("\n- ") + response.count("\n* ")
            numbered = len(re.findall(r"\n\d+[\.\)]\s", response))
            sentences = len(re.findall(r"[.!?]\s", response))
            points = bullets + numbered + sentences

            if points >= 5:
                return 1.0
            if points >= 3:
                return 0.8
            if points >= 1:
                return 0.5
            if word_count >= 30:
                return 0.6
            return 0.3

        if task_type == "analysis":
            if word_count >= 50:
                return 1.0
            if word_count >= 20:
                return 0.7
            return max(0.3, word_count / 50.0)

        # Default: scale by word count
        if word_count >= 20:
            return 1.0
        return max(0.2, word_count / 20.0)

    def _score_relevance(self, task: str, response: str) -> float:
        """Score how relevant the response is to the task."""
        if not response or not task:
            return 0.0

        task_terms = self._extract_key_terms(task)
        if not task_terms:
            # Can't evaluate relevance without task terms — assume OK
            return 0.7

        response_lower = response.lower()
        matches = sum(1 for term in task_terms if term in response_lower)
        overlap = matches / len(task_terms)

        # Scale: 0% overlap = 0.0, 50% = 0.5, 100% = 1.0
        return min(1.0, overlap)

    def _score_coherence(self, response: str) -> float:
        """Score structural quality of the response."""
        if not response or not response.strip():
            return 0.0

        score = 1.0

        # Check for cut-off mid-sentence (ends without punctuation or code block)
        stripped = response.rstrip()
        if stripped and stripped[-1] not in ".!?\"'`)\n]}>":
            # Could be cut off — but only penalize if it's long enough to matter
            if len(stripped) > 50:
                score -= 0.2

        # Check for repeated paragraphs (loop detection)
        paragraphs = [p.strip() for p in response.split("\n\n") if p.strip()]
        if len(paragraphs) >= 2:
            seen = set()
            dupes = 0
            for p in paragraphs:
                # Normalize whitespace for comparison
                normalized = " ".join(p.split())
                if normalized in seen:
                    dupes += 1
                seen.add(normalized)
            if dupes > 0:
                score -= min(0.5, dupes * 0.25)

        # Check for repeated sentences within paragraphs
        sentences = re.split(r"[.!?]\s+", response)
        if len(sentences) >= 3:
            seen_sentences = set()
            sentence_dupes = 0
            for s in sentences:
                normalized = " ".join(s.lower().split())
                if len(normalized) > 10 and normalized in seen_sentences:
                    sentence_dupes += 1
                seen_sentences.add(normalized)
            if sentence_dupes > 0:
                score -= min(0.4, sentence_dupes * 0.2)

        # Unreasonable length (over 5000 words for non-code)
        word_count = len(response.split())
        if word_count > 5000 and "def " not in response and "class " not in response:
            score -= 0.2

        return max(0.0, score)

    def _score_specificity(self, response: str, task_type: str) -> float:
        """Score concrete details vs vague generalities."""
        if not response or not response.strip():
            return 0.0

        score = 0.5  # Base score

        # Check for numbers/quantities
        numbers = re.findall(r"\b\d+(?:\.\d+)?\b", response)
        if numbers:
            score += 0.15

        # Check for specific names, paths, or identifiers
        # Capitalized words (potential proper nouns, not sentence starts)
        proper_nouns = re.findall(r"(?<!\. )[A-Z][a-z]{2,}", response)
        if len(proper_nouns) >= 2:
            score += 0.1

        # Check for code-like content (specific implementations)
        code_indicators = ["def ", "class ", "import ", "return ", "= ", "->", "()"]
        code_matches = sum(1 for ci in code_indicators if ci in response)
        if code_matches >= 2:
            score += 0.15

        # Check for step-by-step instructions
        steps = re.findall(r"(?:step\s+\d|^\d+[\.\)]\s|\n-\s|\n\*\s)", response, re.IGNORECASE | re.MULTILINE)
        if len(steps) >= 2:
            score += 0.1

        # Penalty for vague phrases
        vague_phrases = [
            "various options", "several ways", "many approaches",
            "it depends", "in general", "typically", "usually",
            "consider various", "there are many",
        ]
        vague_count = sum(1 for vp in vague_phrases if vp in response.lower())
        score -= vague_count * 0.1

        return max(0.0, min(1.0, score))

    def _score_self_consistency(self, response: str) -> float:
        """Score internal consistency and detect excessive hedging."""
        if not response or not response.strip():
            return 0.0

        score = 1.0
        response_lower = response.lower()

        # Count hedging language
        hedge_count = 0
        for hedge in _HEDGING_WORDS:
            occurrences = response_lower.count(hedge)
            hedge_count += occurrences

        # 3+ hedging instances = lower confidence
        if hedge_count >= 5:
            score -= 0.4
        elif hedge_count >= 3:
            score -= 0.2
        elif hedge_count >= 2:
            score -= 0.1

        # Check for contradiction patterns
        contradiction_pairs = [
            (r"\bis\b", r"\bis not\b"),
            (r"\bshould\b", r"\bshould not\b"),
            (r"\byes\b", r"\bno\b"),
            (r"\balways\b", r"\bnever\b"),
            (r"\btrue\b", r"\bfalse\b"),
        ]
        for pos_pattern, neg_pattern in contradiction_pairs:
            pos_matches = re.findall(pos_pattern, response_lower)
            neg_matches = re.findall(neg_pattern, response_lower)
            # Both present in short response = possible contradiction
            if pos_matches and neg_matches and len(response.split()) < 100:
                score -= 0.1

        return max(0.0, score)

    # ================================================================
    # FACTUAL GROUNDING (CONFABULATION DETECTION)
    # ================================================================

    def _score_factual_grounding(
        self, response: str, metadata: dict[str, Any] | None,
    ) -> float:
        """Detect confabulation — claims about actions that never occurred.

        Checks the response text against execution metadata to catch lies
        about API calls, tool execution, and fake async processing.

        Args:
            response: The generated response text.
            metadata: Execution metadata with keys:
                target_module, used_fallback, source, tools_executed.
                If None or empty, returns 1.0 (can't verify, don't penalize).

        Returns:
            Score from 0.0 (confirmed confabulation) to 1.0 (grounded).
        """
        if not metadata or not response:
            return 1.0

        response_lower = response.lower()
        score = 1.0
        source = metadata.get("source", "")
        tools_executed = metadata.get("tools_executed", [])
        used_fallback = metadata.get("used_fallback", False)

        # --- Check 1: Claims Apex/API involvement but no API was called ---
        api_sources = {"claude_api", "openai_api"}
        if source not in api_sources:
            for phrase in _APEX_CLAIM_PHRASES:
                if phrase in response_lower:
                    actual_state = f"source='{source}', no API call made"
                    logger.warning(
                        "CONFABULATION DETECTED: Response claims '%s' but %s. "
                        "Factual grounding: 0.0",
                        phrase, actual_state,
                    )
                    return 0.0

        # --- Check 2: Claims tool execution but no tools actually ran ---
        if not tools_executed:
            for phrase in _TOOL_CLAIM_PHRASES:
                if phrase in response_lower:
                    actual_state = "tools_executed=[], no tools ran"
                    logger.warning(
                        "CONFABULATION DETECTED: Response claims '%s' but %s. "
                        "Factual grounding: %.1f",
                        phrase, actual_state, score * 0.3,
                    )
                    score *= 0.3

        # --- Check 3: Claims async waiting/processing that isn't happening ---
        for phrase in _FAKE_ASYNC_PHRASES:
            if phrase in response_lower:
                actual_state = "no async operation in progress"
                logger.warning(
                    "CONFABULATION DETECTED: Response claims '%s' but %s. "
                    "Factual grounding: %.1f",
                    phrase, actual_state, score * 0.2,
                )
                score *= 0.2

        # --- Check 4: Fallback response missing [Fallback] prefix ---
        if (used_fallback or source == "fallback") and "[fallback" not in response_lower:
            logger.warning(
                "CONFABULATION DETECTED: Response from fallback missing "
                "[Fallback] prefix. Factual grounding: %.1f",
                score * 0.4,
            )
            score *= 0.4

        return score

    # ================================================================
    # TASK-TYPE ADJUSTMENTS
    # ================================================================

    def _task_type_adjustments(self, response: str, task_type: str) -> float:
        """Apply task-type-specific bonuses and penalties."""
        bonus = 0.0

        if task_type == "analysis" and "math" in task_type.lower():
            # Math: must contain a number
            if not re.search(r"\b\d+(?:\.\d+)?\b", response):
                bonus -= 0.15

        # Explicit math check for task_type == "math" or similar
        if "math" in task_type.lower():
            if re.search(r"\b\d+(?:\.\d+)?\b", response):
                bonus += 0.05
            else:
                bonus -= 0.15

        # Code: try ast.parse for Python syntax validation
        if task_type in ("creation", "action") or "code" in task_type.lower():
            code_bonus = self._check_python_syntax(response)
            bonus += code_bonus

        # Ethics: check for scripture/principle references
        if task_type == "ethics" or "ethic" in task_type.lower():
            scripture_patterns = [
                r"(?:genesis|exodus|leviticus|numbers|deuteronomy|joshua|judges|ruth|samuel|kings|chronicles|ezra|nehemiah|esther|job|psalm|proverbs|ecclesiastes|song|isaiah|jeremiah|lamentations|ezekiel|daniel|hosea|joel|amos|obadiah|jonah|micah|nahum|habakkuk|zephaniah|haggai|zechariah|malachi|matthew|mark|luke|john|acts|romans|corinthians|galatians|ephesians|philippians|colossians|thessalonians|timothy|titus|philemon|hebrews|james|peter|jude|revelation)\s+\d+",
                r"\d+:\d+",  # Verse reference pattern
                r"(?:scripture|biblical|principle|commandment|proverb)",
            ]
            has_reference = any(
                re.search(p, response, re.IGNORECASE)
                for p in scripture_patterns
            )
            if has_reference:
                bonus += 0.05

        # Factual: acknowledging uncertainty is good
        if task_type in ("question", "research"):
            uncertainty_phrases = [
                "i'm not certain", "i'm not sure", "this may vary",
                "as of my last", "i don't have current",
            ]
            has_uncertainty = any(
                phrase in response.lower() for phrase in uncertainty_phrases
            )
            # Only a small bonus — we don't want to encourage hedging,
            # but honest uncertainty is better than false confidence
            if has_uncertainty:
                bonus += 0.02

        return bonus

    def _check_python_syntax(self, response: str) -> float:
        """Extract Python code blocks and validate syntax. Returns bonus/penalty."""
        # Try to find code blocks
        code_blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", response, re.DOTALL)

        if not code_blocks:
            # Try the whole response if it looks like code
            if "def " in response or "class " in response or "import " in response:
                code_blocks = [response]
            else:
                return 0.0

        valid = 0
        invalid = 0
        for block in code_blocks:
            try:
                ast.parse(block)
                valid += 1
            except SyntaxError:
                invalid += 1

        if valid > 0 and invalid == 0:
            return 0.2  # All code blocks valid
        if valid > 0 and invalid > 0:
            return 0.05  # Mixed
        if invalid > 0 and valid == 0:
            return 0.0  # All invalid — no bonus, no penalty (might not be Python)
        return 0.0

    # ================================================================
    # RECOMMENDATION
    # ================================================================

    def _get_recommendation(self, confidence: float) -> str:
        """Map confidence score to action recommendation."""
        if confidence >= self.THRESHOLD_RESPOND:
            return "respond"
        if confidence >= self.THRESHOLD_RETRY:
            return "retry"
        if confidence >= self.THRESHOLD_RETRY_WITH_CONTEXT:
            return "retry_with_context"
        return "escalate"

    # ================================================================
    # IMPROVEMENT TRACKING
    # ================================================================

    def score_improvement(
        self, previous_score: float, current_score: float,
    ) -> dict[str, Any]:
        """Compare two scores to evaluate retry effectiveness.

        Args:
            previous_score: Confidence from previous attempt.
            current_score: Confidence from current attempt.

        Returns:
            Dict with improved bool, delta, and recommendation.
        """
        delta = current_score - previous_score

        if delta < 0:
            recommendation = "degraded — revert to previous response"
            improved = False
        elif delta < 0.05:
            recommendation = "marginal improvement — consider escalating"
            improved = delta > 0
        elif delta >= 0.2:
            recommendation = "significant improvement — good retry"
            improved = True
        else:
            recommendation = "moderate improvement"
            improved = True

        return {
            "improved": improved,
            "delta": round(delta, 4),
            "previous_score": round(previous_score, 4),
            "current_score": round(current_score, 4),
            "recommendation": recommendation,
        }

    # ================================================================
    # ANALYTICS
    # ================================================================

    def get_scoring_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent scores for analytics.

        Feeds into Growth Engine: 'average confidence this week: 0.72'.
        """
        if self._conn is None:
            return []

        cursor = self._conn.execute(
            """
            SELECT timestamp, task, task_type, confidence,
                   completeness, relevance, coherence, specificity,
                   self_consistency, recommendation, response_length
            FROM scoring_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "timestamp": row[0],
                "task": row[1],
                "task_type": row[2],
                "confidence": row[3],
                "factors": {
                    "completeness": row[4],
                    "relevance": row[5],
                    "coherence": row[6],
                    "specificity": row[7],
                    "self_consistency": row[8],
                },
                "recommendation": row[9],
                "response_length": row[10],
            }
            for row in rows
        ]

    def get_task_type_averages(self) -> dict[str, float]:
        """Average confidence by task type.

        Identifies weak areas for targeted improvement.
        Returns: {task_type: average_confidence, ...}
        """
        if self._conn is None:
            return {}

        cursor = self._conn.execute(
            """
            SELECT task_type, AVG(confidence), COUNT(*)
            FROM scoring_history
            GROUP BY task_type
            ORDER BY AVG(confidence) ASC
            """,
        )
        return {
            row[0]: round(row[1], 4)
            for row in cursor.fetchall()
        }

    def get_average_confidence(self, days: int = 7) -> float:
        """Average confidence over the last N days."""
        if self._conn is None:
            return 0.0

        cursor = self._conn.execute(
            """
            SELECT AVG(confidence)
            FROM scoring_history
            WHERE timestamp >= datetime('now', ?)
            """,
            (f"-{days} days",),
        )
        row = cursor.fetchone()
        if row and row[0] is not None:
            return round(row[0], 4)
        return 0.0

    # ================================================================
    # INTERNALS
    # ================================================================

    def _extract_key_terms(self, text: str) -> list[str]:
        """Extract meaningful words from text for relevance matching."""
        # Tokenize: split on non-alphanumeric
        words = re.findall(r"[a-zA-Z]+", text.lower())
        # Filter stop words and short words
        return [w for w in words if w not in _STOP_WORDS and len(w) > 2]

    def _record_score(
        self,
        task: str,
        task_type: str,
        result: dict[str, Any],
        response_length: int,
    ) -> None:
        """Persist a score to the history database."""
        if self._conn is None:
            return
        try:
            self._conn.execute(
                """
                INSERT INTO scoring_history
                    (timestamp, task, task_type, confidence,
                     completeness, relevance, coherence, specificity,
                     self_consistency, recommendation, response_length)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    task[:500],  # Truncate long tasks
                    task_type,
                    result["confidence"],
                    result["factors"]["completeness"],
                    result["factors"]["relevance"],
                    result["factors"]["coherence"],
                    result["factors"]["specificity"],
                    result["factors"]["self_consistency"],
                    result["recommendation"],
                    response_length,
                ),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning("Failed to record confidence score: %s", e)
