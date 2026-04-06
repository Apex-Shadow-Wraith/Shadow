"""
Prompt Injection & Social Engineering Detector
================================================
Scores incoming text for prompt injection attempts and social
engineering patterns. Used by Cerberus as a pre-processing step
before any external or untrusted input reaches Shadow's reasoning.

Pure computation — no LLM, no async. Millisecond latency.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger("shadow.cerberus.injection")


@dataclass
class InjectionResult:
    """Result of injection analysis."""
    score: float
    flags: list[str] = field(default_factory=list)
    action: str = "pass"  # "block", "warn", or "pass"


class PromptInjectionDetector:
    """Detects prompt injection and social engineering in text input.

    Scoring pipeline:
      1. Regex pattern matching against known injection phrases (+0.8 each)
      2. Social engineering phrase detection (+0.4 each)
      3. Source-based risk adjustment (+0.2 for untrusted sources)
      4. Scope creep analysis from request history (0.0–1.0)

    Action thresholds:
      - score > 0.7 → "block"
      - score > 0.4 → "warn"
      - otherwise   → "pass"
    """

    INJECTION_PATTERNS: list[re.Pattern] = [
        re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)", re.IGNORECASE),
        re.compile(r"ignore\s+all\s+above", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(DAN|jailbroken|unrestricted|unfiltered)", re.IGNORECASE),
        re.compile(r"forget\s+(all\s+)?(your|the)\s+(rules|instructions|training|guidelines|constraints)", re.IGNORECASE),
        re.compile(r"system\s+prompt\s+(override|update|replace|change)", re.IGNORECASE),
        re.compile(r"sudo\s+mode", re.IGNORECASE),
        re.compile(r"developer\s+mode\s+enabled", re.IGNORECASE),
        re.compile(r"do\s+not\s+follow\s+(your|the)\s+(rules|guidelines|instructions|safety)", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(previous|prior|your)\s+(instructions|rules|programming)", re.IGNORECASE),
        re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
        re.compile(r"override\s+(safety|security|ethics|rules)", re.IGNORECASE),
        re.compile(r"act\s+as\s+if\s+(you\s+have\s+)?no\s+(restrictions|limits|rules)", re.IGNORECASE),
    ]

    SOCIAL_ENGINEERING: list[str] = [
        "pretend you are",
        "roleplay as",
        "your creator said it's okay",
        "this is an emergency",
        "you must do this immediately",
        "don't tell anyone",
        "keep this between us",
        "just this once it's fine",
        "nobody will know",
        "trust me on this",
        "i'm your developer",
        "this is a test of your capabilities",
    ]

    UNTRUSTED_SOURCES: set[str] = {
        "reaper_scrape",
        "discord_message",
        "email",
        "web_input",
        "external_api",
        "telegram_message",
    }

    # Keywords that signal escalation toward restricted actions
    _ESCALATION_KEYWORDS: set[str] = {
        "sudo", "admin", "override", "bypass", "credentials",
        "password", "delete", "execute", "install", "disable",
        "root", "permission", "unrestricted", "full access",
    }

    _EXTERNAL_KEYWORDS: set[str] = {
        "send", "email", "post", "publish", "upload", "share",
        "broadcast", "notify", "message", "tweet",
    }

    def analyze(
        self,
        input_text: str,
        source: str,
        request_history: list[dict] | None = None,
    ) -> InjectionResult:
        """Run the full injection detection pipeline.

        Args:
            input_text: The text to analyze.
            source: Where this input came from (e.g., "user", "reaper_scrape").
            request_history: Recent request dicts for scope creep detection.
                Each dict should have at least a "text" key.

        Returns:
            InjectionResult with score, flags, and recommended action.
        """
        if request_history is None:
            request_history = []

        score = 0.0
        flags: list[str] = []
        text_lower = input_text.lower()

        # 1. Pattern matching against injection regexes
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(input_text):
                score += 0.8
                flags.append(f"injection_pattern: {pattern.pattern[:60]}")

        # 2. Social engineering phrase check
        for phrase in self.SOCIAL_ENGINEERING:
            if phrase in text_lower:
                score += 0.4
                flags.append(f"social_engineering: {phrase}")

        # 3. Source-based risk
        if source in self.UNTRUSTED_SOURCES:
            score += 0.2
            flags.append(f"untrusted_source: {source}")

        # 4. Scope creep detection
        if request_history:
            creep_score = self.check_scope_creep(request_history)
            if creep_score > 0.0:
                score += creep_score
                flags.append(f"scope_creep: {creep_score:.2f}")

        # Cap at 1.0
        score = min(score, 1.0)

        # Determine action
        if score > 0.7:
            action = "block"
        elif score > 0.4:
            action = "warn"
        else:
            action = "pass"

        result = InjectionResult(score=score, flags=flags, action=action)
        if action == "block":
            logger.warning("Injection BLOCKED (%.2f): %s", score, flags)
        elif action == "warn":
            logger.info("Injection WARNING (%.2f): %s", score, flags)

        return result

    def check_scope_creep(self, request_history: list[dict]) -> float:
        """Analyze recent requests for escalation patterns.

        Looks for three signals:
          - Increasing use of escalation keywords over time (+0.4)
          - Increasing number of external-facing requests (+0.3)
          - Requests gradually pushing toward restricted actions (+0.3)

        Args:
            request_history: List of request dicts, each with a "text" key.
                Ordered chronologically (oldest first).

        Returns:
            Risk score between 0.0 and 1.0.
        """
        if len(request_history) < 3:
            return 0.0

        score = 0.0
        texts = [r.get("text", "").lower() for r in request_history]

        # Split history into halves for trend comparison
        mid = len(texts) // 2
        first_half = texts[:mid]
        second_half = texts[mid:]

        # Signal 1: Escalation keywords increasing
        early_escalation = sum(
            1 for t in first_half
            for kw in self._ESCALATION_KEYWORDS
            if kw in t
        )
        late_escalation = sum(
            1 for t in second_half
            for kw in self._ESCALATION_KEYWORDS
            if kw in t
        )
        if late_escalation > early_escalation and late_escalation >= 2:
            score += 0.4

        # Signal 2: External-facing requests increasing
        early_external = sum(
            1 for t in first_half
            for kw in self._EXTERNAL_KEYWORDS
            if kw in t
        )
        late_external = sum(
            1 for t in second_half
            for kw in self._EXTERNAL_KEYWORDS
            if kw in t
        )
        if late_external > early_external and late_external >= 2:
            score += 0.3

        # Signal 3: Permission tier references increasing
        tier_keywords = {"tier 2", "tier 3", "tier 4", "restricted", "forbidden", "blocked"}
        early_tier = sum(
            1 for t in first_half
            for kw in tier_keywords
            if kw in t
        )
        late_tier = sum(
            1 for t in second_half
            for kw in tier_keywords
            if kw in t
        )
        if late_tier > early_tier and late_tier >= 1:
            score += 0.3

        return min(score, 1.0)
