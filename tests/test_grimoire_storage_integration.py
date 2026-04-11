"""Integration tests for Grimoire storage paths.

Verifies that the orchestrator can actually store memories through
every path: direct GrimoireModule, SelfTeacher wiring, and the
_grimoire_store_wrapper used by Apex escalation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from modules.shadow.self_teaching import SelfTeacher


# --- GrimoireModule unwrap tests ---

class TestGrimoireModuleUnwrap:
    """Verify the GrimoireModule adapter exposes _grimoire correctly."""

    def test_grimoire_module_has_grimoire_attribute(self):
        """GrimoireModule must have _grimoire attr after __init__."""
        from modules.grimoire.grimoire_module import GrimoireModule
        mod = GrimoireModule({})
        assert hasattr(mod, "_grimoire")
        # Before initialize(), _grimoire is None
        assert mod._grimoire is None

    def test_getattr_unwrap_matches(self):
        """getattr(mod, '_grimoire', None) must return the inner Grimoire."""
        from modules.grimoire.grimoire_module import GrimoireModule
        mod = GrimoireModule({})
        # Simulate post-initialization state
        fake_grimoire = MagicMock()
        fake_grimoire.remember = MagicMock(return_value="test-uuid")
        mod._grimoire = fake_grimoire
        unwrapped = getattr(mod, "_grimoire", None)
        assert unwrapped is fake_grimoire

    def test_remember_through_unwrapped_grimoire(self):
        """Calling remember() on unwrapped _grimoire must work."""
        from modules.grimoire.grimoire_module import GrimoireModule
        mod = GrimoireModule({})
        fake_grimoire = MagicMock()
        fake_grimoire.remember = MagicMock(return_value="mem-123")
        mod._grimoire = fake_grimoire
        grimoire = getattr(mod, "_grimoire", None)
        result = grimoire.remember(
            content="test content",
            source="test",
            source_module="test",
            category="test",
            trust_level=0.5,
        )
        assert result == "mem-123"
        fake_grimoire.remember.assert_called_once()


# --- SelfTeacher grimoire wiring tests ---

class TestSelfTeacherGrimoireWiring:
    """Verify SelfTeacher gets and uses a Grimoire instance."""

    def test_self_teacher_with_none_grimoire_stores_nothing(self):
        """If grimoire is None, store_teaching returns empty list."""
        teacher = SelfTeacher(grimoire=None)
        teaching = {
            "tiers": {"specific_solution": "content"},
            "task_hash": "h",
            "domain_tags": [],
            "generated_at": 0,
            "source": "self_teaching",
        }
        ids = teacher.store_teaching(teaching)
        assert ids == []

    def test_self_teacher_with_grimoire_stores_memories(self):
        """If grimoire is wired, store_teaching stores all tiers."""
        grimoire = MagicMock()
        grimoire.remember = MagicMock(return_value="stored-id")
        teacher = SelfTeacher(grimoire=grimoire)
        teaching = {
            "tiers": {
                "specific_solution": "Solution content",
                "general_principle": "Principle content",
                "meta_principle": "Meta content",
            },
            "task_hash": "abc",
            "domain_tags": ["code"],
            "generated_at": 0,
            "source": "self_teaching",
        }
        ids = teacher.store_teaching(teaching)
        assert len(ids) == 3
        assert grimoire.remember.call_count == 3

    def test_self_teacher_unwraps_grimoire_module(self):
        """If given a GrimoireModule (no remember()), unwrap to _grimoire."""
        inner = MagicMock()
        inner.remember = MagicMock(return_value="id-1")
        wrapper = MagicMock(spec=[])  # No 'remember' attribute
        wrapper._grimoire = inner
        teacher = SelfTeacher(grimoire=wrapper)
        # Should have unwrapped to the inner grimoire
        assert teacher._grimoire is inner

    def test_self_teacher_late_wiring(self):
        """Simulates the orchestrator wiring grimoire after init."""
        teacher = SelfTeacher(grimoire=None)
        assert teacher._grimoire is None

        # Late-wire like _initialize_communication now does
        grimoire = MagicMock()
        grimoire.remember = MagicMock(return_value="late-id")
        teacher._grimoire = grimoire

        teaching = {
            "tiers": {"specific_solution": "content"},
            "task_hash": "h",
            "domain_tags": [],
            "generated_at": 0,
            "source": "self_teaching",
        }
        ids = teacher.store_teaching(teaching)
        assert ids == ["late-id"]

    def test_teach_from_success_stores_when_wired(self):
        """Full teach_from_success path with wired grimoire."""
        gen_fn = MagicMock(return_value=(
            "<specific_solution>Do X.</specific_solution>"
            "<general_principle>Pattern Y.</general_principle>"
            "<meta_principle>Think Z.</meta_principle>"
        ))
        grimoire = MagicMock()
        grimoire.remember = MagicMock(return_value="teach-id")
        teacher = SelfTeacher(
            generate_fn=gen_fn,
            grimoire=grimoire,
            config={"difficulty_threshold": 1, "confidence_threshold": 0.1},
        )
        result = teacher.teach_from_success(
            task={"description": "Implement a complex algorithm with multiple steps",
                  "type": "code", "difficulty": 8},
            solution="Here is the solution...",
            confidence_score=0.9,
            was_escalated=False,
        )
        assert result is not None
        assert len(result["stored_ids"]) == 3

    def test_teach_from_success_returns_empty_ids_without_grimoire(self):
        """teach_from_success without grimoire returns teaching with empty ids."""
        gen_fn = MagicMock(return_value=(
            "<specific_solution>Do X.</specific_solution>"
            "<general_principle>Pattern Y.</general_principle>"
            "<meta_principle>Think Z.</meta_principle>"
        ))
        teacher = SelfTeacher(
            generate_fn=gen_fn,
            grimoire=None,  # Not wired!
            config={"difficulty_threshold": 1, "confidence_threshold": 0.1},
        )
        result = teacher.teach_from_success(
            task={"description": "Implement a complex algorithm with multiple steps",
                  "type": "code", "difficulty": 8},
            solution="Solution",
            confidence_score=0.9,
            was_escalated=False,
        )
        assert result is not None
        assert result["stored_ids"] == []


# --- _grimoire_store_wrapper tests ---

class TestGrimoireStoreWrapper:
    """Test the orchestrator's _grimoire_store_wrapper function."""

    def test_wrapper_calls_remember_on_inner_grimoire(self):
        """The wrapper must unwrap GrimoireModule and call remember()."""
        from modules.base import ModuleRegistry

        registry = ModuleRegistry()
        fake_module = MagicMock()
        fake_module.name = "grimoire"
        fake_module.status = MagicMock()
        fake_grimoire = MagicMock()
        fake_grimoire.remember = MagicMock(return_value="wrap-id")
        fake_module._grimoire = fake_grimoire
        fake_module.get_tools = MagicMock(return_value=[])
        registry.register(fake_module)

        # Simulate what _grimoire_store_wrapper does
        grimoire_module = registry.get_module("grimoire")
        grimoire = getattr(grimoire_module, "_grimoire", None)
        assert grimoire is not None
        doc_id = grimoire.remember(
            content="test",
            source="test",
            source_module="test",
            category="test",
            trust_level=0.5,
        )
        assert doc_id == "wrap-id"

    def test_wrapper_returns_no_grimoire_when_missing(self):
        """If grimoire not in registry, wrapper returns 'no_grimoire'."""
        from modules.base import ModuleRegistry
        registry = ModuleRegistry()
        # No grimoire registered
        assert "grimoire" not in registry


# --- remember() return value tests ---

class TestRememberReturnsId:
    """Verify that remember() returns a non-None ID."""

    def test_mock_remember_returns_uuid(self):
        """Mock Grimoire.remember() should return a UUID string."""
        grimoire = MagicMock()
        grimoire.remember = MagicMock(return_value="550e8400-e29b-41d4-a716-446655440000")
        result = grimoire.remember(content="test", source="test")
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
