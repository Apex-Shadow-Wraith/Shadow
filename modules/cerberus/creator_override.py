"""
Creator Override System
========================
When Cerberus blocks an action, the creator (and ONLY the creator) can
issue one of two override commands:

1. creator_exception — one-time pass, no learning
2. creator_authorize — permanent reclassification with reasoning

Authentication: Phase 1 uses a simple token from .env.
Phase 2: cryptographic device signatures.
Phase 3: Face ID for creator_authorize.

ONLY external input sources (direct user input, Telegram) may call
these commands. Internal modules are forbidden.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.cerberus.config import CerberusSettings

logger = logging.getLogger("shadow.cerberus.override")

# Tier 4 forbidden actions — CANNOT be overridden even by the creator
TIER_4_FORBIDDEN = [
    "bank_login",
    "government_credential_access",
    "bank_credential_access",
    "government_login",
    "financial_credential_access",
    "ssn_access",
    "tax_credential_access",
]

# Modules that are considered internal — they cannot call override commands
INTERNAL_MODULES = [
    "shadow", "wraith", "cerberus", "apex", "grimoire",
    "harbinger", "reaper", "omen", "nova", "void", "morpheus",
]

# Valid external sources that may invoke overrides
EXTERNAL_SOURCES = ["user_input", "telegram", "discord"]


@dataclass
class OverrideResult:
    """Result of an override attempt."""
    success: bool
    action_id: str
    override_type: str  # "exception" or "authorize"
    reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class CreatorOverride:
    """Creator override system for Cerberus safety blocks.

    Only the creator, authenticated via token, can override Cerberus
    decisions. Internal modules cannot invoke overrides.
    """

    def __init__(
        self, settings: CerberusSettings | None = None
    ) -> None:
        """Initialize the creator override system.

        Args:
            settings: A CerberusSettings instance. If None, falls back to
                `shadow.config.config.cerberus`.
        """
        if settings is None:
            from shadow.config import config as _shadow_config
            settings = _shadow_config.cerberus
        self._settings = settings
        self._auth_token: str | None = (
            settings.creator_auth_token.get_secret_value()
            if settings.creator_auth_token
            else None
        )
        self._exception_log: list[dict[str, Any]] = []
        self._authorize_log: list[dict[str, Any]] = []
        self._exception_counts: dict[str, int] = {}  # category -> count
        self._authorized_categories: set[str] = set()

    def verify_hardware_auth(self, token: str) -> bool:
        """Verify creator authentication token.

        Phase 1: Simple token comparison against the configured value.
        # TODO: Phase 2 — add cryptographic device signatures
        # TODO: Phase 3 — add Face ID verification for creator_authorize

        Raises:
            RuntimeError: If no auth token is configured. The override system
                cannot function without one, and silently returning False
                would mask a misconfiguration.
        """
        if not self._auth_token:
            raise RuntimeError(
                "CREATOR_AUTH_TOKEN is not set. Creator override cannot "
                "function without it. Set CREATOR_AUTH_TOKEN in .env, "
                "or in config.yaml at modules.cerberus.creator_auth_token."
            )
        return token == self._auth_token

    def _validate_source(self, source: str) -> bool:
        """Reject calls from internal modules. Only external sources allowed."""
        if source in INTERNAL_MODULES:
            logger.warning(
                "REJECTED: Internal module '%s' attempted override — forbidden", source
            )
            return False
        if source not in EXTERNAL_SOURCES:
            logger.warning(
                "REJECTED: Unknown source '%s' attempted override", source
            )
            return False
        return True

    def _is_tier_4_forbidden(self, action_category: str) -> bool:
        """Check if the action falls under Tier 4 forbidden — no override possible."""
        return action_category in TIER_4_FORBIDDEN

    def creator_exception(
        self,
        blocked_action_id: str,
        auth_token: str,
        action_category: str = "unknown",
        action_details: dict[str, Any] | None = None,
        source: str = "user_input",
    ) -> OverrideResult:
        """One-time exception. Action executes THIS TIME ONLY.

        Cerberus does NOT learn from this. Rules remain unchanged.
        Next time the same action type is attempted, Cerberus blocks again.

        Args:
            blocked_action_id: ID of the blocked action from safety_check.
            auth_token: Creator's authentication token.
            action_category: Category of the blocked action.
            action_details: Optional details about the blocked action.
            source: Where the override request came from.

        Returns:
            OverrideResult indicating success or failure.
        """
        # Validate source — only external input allowed
        if not self._validate_source(source):
            return OverrideResult(
                success=False,
                action_id=blocked_action_id,
                override_type="exception",
                reason=f"Source '{source}' is not authorized to issue overrides",
            )

        # Check Tier 4 forbidden
        if self._is_tier_4_forbidden(action_category):
            return OverrideResult(
                success=False,
                action_id=blocked_action_id,
                override_type="exception",
                reason=(
                    f"TIER 4 FORBIDDEN: Category '{action_category}' cannot be "
                    "overridden — not even by the creator"
                ),
            )

        # Authenticate
        if not self.verify_hardware_auth(auth_token):
            return OverrideResult(
                success=False,
                action_id=blocked_action_id,
                override_type="exception",
                reason="Authentication failed — invalid token",
            )

        # Log the exception
        entry = {
            "action_id": blocked_action_id,
            "action_category": action_category,
            "action_details": action_details or {},
            "timestamp": datetime.now().isoformat(),
            "source": source,
        }
        self._exception_log.append(entry)

        # Track false positive counts per category
        self._exception_counts[action_category] = (
            self._exception_counts.get(action_category, 0) + 1
        )

        logger.info(
            "CREATOR EXCEPTION granted for action %s (category: %s)",
            blocked_action_id, action_category,
        )

        return OverrideResult(
            success=True,
            action_id=blocked_action_id,
            override_type="exception",
            reason=f"One-time exception granted for '{action_category}'",
        )

    def creator_authorize(
        self,
        blocked_action_id: str,
        auth_token: str,
        reasoning: str,
        action_category: str = "unknown",
        action_details: dict[str, Any] | None = None,
        source: str = "user_input",
    ) -> OverrideResult:
        """Permanent authorization. Cerberus LEARNS from this.

        The category is reclassified going forward. Creator must provide
        reasoning which is stored permanently.

        Args:
            blocked_action_id: ID of the blocked action from safety_check.
            auth_token: Creator's authentication token.
            reasoning: Creator's reasoning for the authorization (required).
            action_category: Category of the blocked action.
            action_details: Optional details about the blocked action.
            source: Where the override request came from.

        Returns:
            OverrideResult indicating success or failure.
        """
        # Validate source — only external input allowed
        if not self._validate_source(source):
            return OverrideResult(
                success=False,
                action_id=blocked_action_id,
                override_type="authorize",
                reason=f"Source '{source}' is not authorized to issue overrides",
            )

        # Check Tier 4 forbidden
        if self._is_tier_4_forbidden(action_category):
            return OverrideResult(
                success=False,
                action_id=blocked_action_id,
                override_type="authorize",
                reason=(
                    f"TIER 4 FORBIDDEN: Category '{action_category}' cannot be "
                    "authorized — not even by the creator"
                ),
            )

        # Authenticate
        if not self.verify_hardware_auth(auth_token):
            return OverrideResult(
                success=False,
                action_id=blocked_action_id,
                override_type="authorize",
                reason="Authentication failed — invalid token",
            )

        # Reasoning is required
        if not reasoning or not reasoning.strip():
            return OverrideResult(
                success=False,
                action_id=blocked_action_id,
                override_type="authorize",
                reason="Reasoning is required for creator_authorize",
            )

        # Log the authorization
        entry = {
            "action_id": blocked_action_id,
            "action_category": action_category,
            "action_details": action_details or {},
            "reasoning": reasoning,
            "timestamp": datetime.now().isoformat(),
            "source": source,
        }
        self._authorize_log.append(entry)

        # Mark category as permanently authorized
        self._authorized_categories.add(action_category)

        logger.info(
            "CREATOR AUTHORIZE: Category '%s' permanently reclassified. Reason: %s",
            action_category, reasoning,
        )

        return OverrideResult(
            success=True,
            action_id=blocked_action_id,
            override_type="authorize",
            reason=(
                f"Category '{action_category}' permanently authorized. "
                f"Reasoning: {reasoning}"
            ),
        )

    def is_category_authorized(self, category: str) -> bool:
        """Check if a category has been permanently authorized by the creator."""
        return category in self._authorized_categories

    def get_false_positive_report(self) -> dict[str, Any]:
        """Report on categories with frequent creator exceptions.

        Categories with high exception counts suggest Cerberus calibration
        is needed. This feeds into Harbinger's daily safety report.

        Returns:
            Dict with per-category exception counts and flagged categories.
        """
        flagged: list[dict[str, Any]] = []
        for category, count in sorted(
            self._exception_counts.items(), key=lambda x: x[1], reverse=True
        ):
            entry = {"category": category, "exception_count": count}
            if count >= 3:
                entry["recommendation"] = "calibration_needed"
                flagged.append(entry)

        return {
            "total_exceptions": sum(self._exception_counts.values()),
            "categories": dict(self._exception_counts),
            "flagged_for_calibration": flagged,
            "authorized_categories": sorted(self._authorized_categories),
        }

    def generate_blocked_action_id(self) -> str:
        """Generate a unique ID for a blocked action."""
        return f"blocked-{uuid.uuid4().hex[:12]}"
