"""
Tests for Cerberus Ethics Engine
==================================
Verifies the biblical ethics integration works correctly:
- Fast-path lookup matches ethical categories
- Semantic search returns relevant passages (mocked)
- Hard limits are NOT affected by the ethics engine
- Graceful degradation when storage is unavailable
"""

import sys

import pytest
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import yaml

from modules.cerberus.cerberus import Cerberus, SafetyVerdict
from modules.cerberus.ethics_engine import EthicsEngine, EthicsResult

# --- Minimal ethical topics for testing ---

MINIMAL_TOPICS = {
    "topics": [
        {
            "name": "honesty",
            "description": "Truthfulness, integrity, and transparency in all actions",
            "keywords": [
                "honesty", "truth", "lying", "deception", "integrity",
                "transparency", "truthful", "false", "misleading",
            ],
            "references": [
                {"ref": "Proverbs 12:22", "summary": "The LORD detests lying lips.", "weight": 1.0},
                {"ref": "Ephesians 4:25", "summary": "Put off falsehood, speak truthfully.", "weight": 0.9},
            ],
        },
        {
            "name": "justice",
            "description": "Fairness, equity, and standing up for what is right",
            "keywords": [
                "justice", "fairness", "equity", "rights", "oppression",
                "bias", "discrimination", "equal", "advocate", "stealing",
            ],
            "references": [
                {"ref": "Micah 6:8", "summary": "Act justly, love mercy, walk humbly.", "weight": 1.0},
                {"ref": "Proverbs 31:8-9", "summary": "Speak up for those who cannot speak.", "weight": 0.9},
            ],
        },
        {
            "name": "protection",
            "description": "Safeguarding the vulnerable, preventing harm",
            "keywords": [
                "protection", "safety", "harm", "vulnerable", "defend",
                "guard", "shield", "danger",
            ],
            "references": [
                {"ref": "Psalm 82:3-4", "summary": "Defend the weak and the fatherless.", "weight": 1.0},
                {"ref": "Proverbs 24:11", "summary": "Rescue those being led to death.", "weight": 0.9},
            ],
        },
    ]
}

MINIMAL_LIMITS = {
    "hard_limits": {
        "financial": ["Never access real bank accounts"],
        "data": ["Never share personal data externally"],
        "system": ["Never disable Cerberus"],
        "external": ["Never take external actions without approval"],
        "rate_limits": {"max_file_operations_per_hour": 100},
        "ethical": ["Never generate deceptive content"],
    },
    "permission_tiers": {
        "tier_1_open": {"approval": "autonomous"},
        "tier_4_forbidden": {"approval": "blocked"},
    },
    "approval_required_tools": ["email_send", "browser_stealth"],
    "autonomous_tools": ["memory_store", "memory_search", "safety_check"],
    "hooks": {
        "pre_tool": {
            "deny": [
                {
                    "pattern": "shell_metacharacters",
                    "description": "DENY shell metacharacters",
                    "applies_to": ["bash_execute", "code_execute"],
                },
                {
                    "pattern": "protected_path_write",
                    "description": "DENY writes to protected paths",
                    "applies_to": ["file_write"],
                    "protected_paths": [
                        "config/cerberus_limits.yaml",
                        "config/shadow_config.yaml",
                    ],
                },
            ],
            "modify": [],
        },
        "post_tool": {"flag": []},
    },
}


@pytest.fixture
def ethics_topics_file(tmp_path: Path) -> Path:
    """Create a temporary ethical topics YAML."""
    path = tmp_path / "ethical_topics.yaml"
    with open(path, "w") as f:
        yaml.dump(MINIMAL_TOPICS, f)
    return path


@pytest.fixture
def ethics_engine(tmp_path: Path, ethics_topics_file: Path) -> EthicsEngine:
    """Create an EthicsEngine with mocked ChromaDB."""
    db_path = tmp_path / "test.db"
    vector_path = tmp_path / "vectors"
    vector_path.mkdir()

    with patch("modules.cerberus.ethics_engine.EthicsEngine._init_chromadb"):
        engine = EthicsEngine(
            db_path=str(db_path),
            vector_path=str(vector_path),
            ethical_topics_file=str(ethics_topics_file),
        )
    return engine


@pytest.fixture
def limits_file(tmp_path: Path) -> Path:
    """Create a temporary Cerberus limits file."""
    limits_path = tmp_path / "cerberus_limits.yaml"
    with open(limits_path, "w") as f:
        yaml.dump(MINIMAL_LIMITS, f)
    return limits_path


@pytest.fixture
async def cerberus_with_ethics(
    limits_file: Path, tmp_path: Path, ethics_topics_file: Path
) -> Cerberus:
    """Create Cerberus with ethics engine (ChromaDB mocked)."""
    db_path = tmp_path / "cerberus_audit.db"
    config = {
        "limits_file": str(limits_file),
        "db_path": str(db_path),
        "ethical_topics_file": str(ethics_topics_file),
        "esv_db_path": str(tmp_path / "test.db"),
        "vector_path": str(tmp_path / "vectors"),
    }
    (tmp_path / "vectors").mkdir(exist_ok=True)

    with patch("modules.cerberus.ethics_engine.EthicsEngine._init_chromadb"):
        c = Cerberus(config)
    await c.initialize()
    return c


@pytest.fixture
async def cerberus_no_ethics(limits_file: Path, tmp_path: Path) -> Cerberus:
    """Create Cerberus with ethics engine disabled."""
    db_path = tmp_path / "cerberus_audit.db"
    config = {"limits_file": str(limits_file), "db_path": str(db_path)}

    # Force ethics engine to fail by making the import raise
    with patch.dict("sys.modules", {"modules.cerberus.ethics_engine": None}):
        c = Cerberus(config)
    assert c._ethics_engine is None
    await c.initialize()
    return c


# --- Fast Path Lookup Tests ---

class TestFastPathLookup:
    def test_deception_matches_honesty(self, ethics_engine: EthicsEngine):
        """'deception' should match the honesty category."""
        results = ethics_engine.fast_path_lookup("deception")
        assert len(results) > 0
        assert all(r["category"] == "honesty" for r in results)
        assert results[0]["ref"] == "Proverbs 12:22"

    def test_stealing_matches_justice(self, ethics_engine: EthicsEngine):
        """'stealing' should match the justice category."""
        results = ethics_engine.fast_path_lookup("stealing")
        assert len(results) > 0
        assert all(r["category"] == "justice" for r in results)
        assert results[0]["ref"] == "Micah 6:8"

    def test_unknown_topic_returns_empty(self, ethics_engine: EthicsEngine):
        """Unknown topic returns empty list."""
        results = ethics_engine.fast_path_lookup("quantum_physics")
        assert results == []

    def test_multiple_categories_can_match(self, ethics_engine: EthicsEngine):
        """'safety' should match protection category."""
        results = ethics_engine.fast_path_lookup("safety")
        assert len(results) > 0
        categories = {r["category"] for r in results}
        assert "protection" in categories

    def test_results_sorted_by_weight(self, ethics_engine: EthicsEngine):
        results = ethics_engine.fast_path_lookup("truth")
        if len(results) > 1:
            weights = [r["weight"] for r in results]
            assert weights == sorted(weights, reverse=True)

    def test_case_insensitive(self, ethics_engine: EthicsEngine):
        results_lower = ethics_engine.fast_path_lookup("deception")
        results_upper = ethics_engine.fast_path_lookup("DECEPTION")
        assert len(results_lower) == len(results_upper)


# --- Semantic Search Tests ---

class TestSemanticSearch:
    def test_returns_empty_when_no_collection(self, ethics_engine: EthicsEngine):
        """Without ChromaDB collection, returns empty list."""
        assert ethics_engine._pericope_collection is None
        results = ethics_engine.semantic_scripture_search("love your neighbor")
        assert results == []

    def test_returns_results_with_mocked_chromadb(self, ethics_engine: EthicsEngine):
        """With mocked ChromaDB, returns structured results."""
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["In the beginning God created..."]],
            "metadatas": [[{
                "book_name": "Genesis",
                "chapter": 1,
                "verse_start": 1,
                "verse_end": 31,
                "section_heading": "The Creation of the World",
            }]],
            "distances": [[0.15]],
        }
        ethics_engine._pericope_collection = mock_collection

        with patch.object(ethics_engine, "_get_embedding", return_value=[0.1] * 768):
            results = ethics_engine.semantic_scripture_search("creation")

        assert len(results) == 1
        assert results[0]["book"] == "Genesis"
        assert results[0]["chapter"] == 1
        assert results[0]["similarity"] == round(1 - 0.15, 4)

    def test_handles_embedding_failure(self, ethics_engine: EthicsEngine):
        """If embedding fails, returns empty results."""
        mock_collection = MagicMock()
        ethics_engine._pericope_collection = mock_collection

        with patch.object(ethics_engine, "_get_embedding", return_value=None):
            results = ethics_engine.semantic_scripture_search("test query")

        assert results == []
        mock_collection.query.assert_not_called()

    def test_handles_chromadb_exception(self, ethics_engine: EthicsEngine):
        """If ChromaDB throws, returns empty results gracefully."""
        mock_collection = MagicMock()
        mock_collection.query.side_effect = RuntimeError("ChromaDB error")
        ethics_engine._pericope_collection = mock_collection

        with patch.object(ethics_engine, "_get_embedding", return_value=[0.1] * 768):
            results = ethics_engine.semantic_scripture_search("test query")

        assert results == []


# --- Hard Limits Unaffected Tests ---

class TestHardLimitsUnaffected:
    @pytest.mark.asyncio
    async def test_shell_metacharacters_still_denied(
        self, cerberus_with_ethics: Cerberus
    ):
        """Shell metacharacter DENY works with ethics engine present."""
        result = await cerberus_with_ethics.execute("hook_pre_tool", {
            "tool_name": "bash_execute",
            "tool_params": {"command": "ls && rm -rf /"},
        })
        assert result.content.verdict == SafetyVerdict.DENY
        assert "metacharacter" in result.content.reason.lower()

    @pytest.mark.asyncio
    async def test_protected_path_still_denied(
        self, cerberus_with_ethics: Cerberus
    ):
        """Protected path writes still blocked with ethics engine."""
        result = await cerberus_with_ethics.execute("safety_check", {
            "action_tool": "file_write",
            "action_params": {"path": "config/cerberus_limits.yaml"},
            "requesting_module": "omen",
        })
        assert result.content.verdict == SafetyVerdict.DENY

    @pytest.mark.asyncio
    async def test_approval_required_still_works(
        self, cerberus_with_ethics: Cerberus
    ):
        """Approval-required tools still need approval."""
        result = await cerberus_with_ethics.execute("safety_check", {
            "action_tool": "email_send",
            "action_params": {"to": "test@test.com"},
            "requesting_module": "harbinger",
        })
        assert result.content.verdict == SafetyVerdict.APPROVAL_REQUIRED

    @pytest.mark.asyncio
    async def test_autonomous_tool_still_allowed(
        self, cerberus_with_ethics: Cerberus
    ):
        """Autonomous tools still pass with ethics context attached."""
        result = await cerberus_with_ethics.execute("safety_check", {
            "action_tool": "memory_store",
            "action_params": {"content": "test"},
            "requesting_module": "grimoire",
        })
        assert result.content.verdict == SafetyVerdict.ALLOW


# --- Graceful Degradation Tests ---

class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_no_ethics_engine_safety_works(
        self, cerberus_no_ethics: Cerberus
    ):
        """Safety check works normally when ethics engine is None."""
        assert cerberus_no_ethics._ethics_engine is None

        result = await cerberus_no_ethics.execute("safety_check", {
            "action_tool": "memory_store",
            "action_params": {"content": "test"},
            "requesting_module": "grimoire",
        })
        assert result.content.verdict == SafetyVerdict.ALLOW
        assert result.content.ethics_context is None

    @pytest.mark.asyncio
    async def test_no_ethics_engine_denial_works(
        self, cerberus_no_ethics: Cerberus
    ):
        """Hard limits still work when ethics engine is None."""
        result = await cerberus_no_ethics.execute("hook_pre_tool", {
            "tool_name": "bash_execute",
            "tool_params": {"command": "echo $(whoami)"},
        })
        assert result.content.verdict == SafetyVerdict.DENY

    def test_empty_topics_file(self, tmp_path: Path):
        """Empty or missing ethical_topics.yaml loads empty."""
        with patch("modules.cerberus.ethics_engine.EthicsEngine._init_chromadb"):
            engine = EthicsEngine(
                db_path=str(tmp_path / "test.db"),
                vector_path=str(tmp_path / "vectors"),
                ethical_topics_file=str(tmp_path / "nonexistent.yaml"),
            )
        assert engine._topics == []
        results = engine.fast_path_lookup("honesty")
        assert results == []

    def test_malformed_topics_file(self, tmp_path: Path):
        """Malformed YAML loads empty without crashing."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("{{{{invalid yaml::::")

        with patch("modules.cerberus.ethics_engine.EthicsEngine._init_chromadb"):
            engine = EthicsEngine(
                db_path=str(tmp_path / "test.db"),
                vector_path=str(tmp_path / "vectors"),
                ethical_topics_file=str(bad_yaml),
            )
        assert engine._topics == []

    def test_sqlite_unavailable_study_notes(self, ethics_engine: EthicsEngine):
        """Study notes return empty when SQLite is unavailable."""
        # Point to a nonexistent DB — should return empty
        ethics_engine._db_path = Path("/nonexistent/path/db.sqlite")
        notes = ethics_engine._get_study_notes("Genesis", 1)
        assert notes == []


# --- Ethics Lookup Tool Tests ---

class TestEthicsLookupTool:
    @pytest.mark.asyncio
    async def test_ethics_lookup_returns_result(
        self, cerberus_with_ethics: Cerberus
    ):
        """ethics_lookup tool returns formatted result."""
        result = await cerberus_with_ethics.execute("ethics_lookup", {
            "action": "generate_report",
            "plan": "Create a deception-based phishing template",
        })
        assert result.success is True
        content = result.content
        assert "category" in content
        assert "assessment" in content
        assert "recommendation" in content
        assert content["recommendation"] in ("APPROVE", "BLOCK", "DEFER")

    @pytest.mark.asyncio
    async def test_ethics_lookup_no_engine(
        self, cerberus_no_ethics: Cerberus
    ):
        """ethics_lookup returns graceful error when engine unavailable."""
        result = await cerberus_no_ethics.execute("ethics_lookup", {
            "action": "test",
            "plan": "test",
        })
        assert result.success is True
        assert result.content["error"] == "Ethics engine not available"

    @pytest.mark.asyncio
    async def test_ethics_lookup_deception_flags_honesty(
        self, cerberus_with_ethics: Cerberus
    ):
        """Action involving deception should flag honesty category."""
        result = await cerberus_with_ethics.execute("ethics_lookup", {
            "action": "content_generate",
            "plan": "Write a deceptive email to mislead a customer",
        })
        assert result.success is True
        assert result.content["category"] == "honesty"
        assert result.content["recommendation"] == "DEFER"


# --- Evaluate Action Tests ---

class TestEvaluateAction:
    def test_returns_valid_ethics_result(self, ethics_engine: EthicsEngine):
        """Full pipeline returns valid EthicsResult."""
        result = ethics_engine.evaluate_action(
            "file_write", "Write a report about fairness in hiring"
        )
        assert isinstance(result, EthicsResult)
        assert result.action == "file_write"
        assert result.recommendation in ("APPROVE", "BLOCK", "DEFER")
        assert 0.0 <= result.confidence <= 1.0

    def test_no_ethical_concerns(self, ethics_engine: EthicsEngine):
        """Neutral action gets APPROVE recommendation."""
        result = ethics_engine.evaluate_action(
            "memory_store", "Save today's weather data"
        )
        assert result.recommendation == "APPROVE"
        assert result.ethical_category is None

    def test_deception_gets_defer(self, ethics_engine: EthicsEngine):
        """Action involving deception gets DEFER recommendation."""
        result = ethics_engine.evaluate_action(
            "content_generate", "Create misleading advertisement"
        )
        assert result.recommendation == "DEFER"
        assert result.ethical_category == "honesty"
        assert result.confidence > 0.5

    def test_stealing_gets_defer(self, ethics_engine: EthicsEngine):
        """Action involving theft gets DEFER recommendation."""
        result = ethics_engine.evaluate_action(
            "web_fetch", "Download copyrighted content to steal intellectual property"
        )
        assert result.recommendation == "DEFER"

    def test_assessment_not_empty(self, ethics_engine: EthicsEngine):
        """Assessment string is always populated."""
        result = ethics_engine.evaluate_action("test_tool", "some plan")
        assert result.assessment != ""

    def test_relevant_passages_from_fast_path(self, ethics_engine: EthicsEngine):
        """When category matches, relevant passages include curated refs."""
        result = ethics_engine.evaluate_action(
            "content_generate", "Write something with false claims"
        )
        refs = [p.get("ref", "") for p in result.relevant_passages]
        assert "Proverbs 12:22" in refs
