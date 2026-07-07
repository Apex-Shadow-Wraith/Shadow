"""
Tests for Ethical Topics Integration in Cerberus
==================================================
Verifies that Cerberus can look up biblical ethical guidance
for concepts using the curated topical index.
"""

import logging

import pytest
from pathlib import Path

import yaml

from modules.cerberus.cerberus import Cerberus


MINIMAL_LIMITS = {
    "hard_limits": {"financial": [], "data": [], "system": [], "external": [],
                    "rate_limits": {}, "ethical": []},
    "approval_required_tools": [],
    "autonomous_tools": ["safety_check"],
    "hooks": {"pre_tool": {"deny": [], "modify": []}, "post_tool": {"flag": []}},
}

SAMPLE_TOPICS = {
    "topics": [
        {
            "name": "honesty",
            "description": "Truthfulness, integrity, and transparency",
            "keywords": ["truth", "lying", "deception", "integrity"],
            "references": [
                {"ref": "Proverbs 12:22", "summary": "The LORD detests lying lips.", "weight": 1.0},
                {"ref": "Ephesians 4:25", "summary": "Speak truthfully to your neighbor.", "weight": 0.9},
            ],
        },
        {
            "name": "privacy",
            "description": "Protecting personal information and boundaries",
            "keywords": ["private", "confidential", "personal data", "surveillance"],
            "references": [
                {"ref": "Proverbs 11:13", "summary": "A trustworthy person keeps a secret.", "weight": 1.0},
                {"ref": "Matthew 6:1-4", "summary": "Do not practice righteousness to be seen.", "weight": 0.8},
            ],
        },
        {
            "name": "justice",
            "description": "Fairness, equity, and standing up for what is right",
            "keywords": ["fairness", "equity", "bias", "discrimination"],
            "references": [
                {"ref": "Micah 6:8", "summary": "Act justly, love mercy, walk humbly.", "weight": 1.0},
            ],
        },
    ],
}


@pytest.fixture
def ethics_setup(tmp_path: Path):
    """Create temp limits and ethics files, return initialized Cerberus."""
    limits_path = tmp_path / "limits.yaml"
    ethics_path = tmp_path / "ethics.yaml"
    with open(limits_path, "w") as f:
        yaml.dump(MINIMAL_LIMITS, f)
    with open(ethics_path, "w") as f:
        yaml.dump(SAMPLE_TOPICS, f)
    return {
        "limits_file": str(limits_path),
        "ethical_topics_file": str(ethics_path),
    }


@pytest.fixture
async def cerberus(ethics_setup: dict) -> Cerberus:
    c = Cerberus(ethics_setup)
    await c.initialize()
    return c


class TestEthicalTopicsLoading:
    @pytest.mark.asyncio
    async def test_loads_topics(self, cerberus: Cerberus):
        assert len(cerberus._ethical_topics) == 3

    @pytest.mark.asyncio
    async def test_graceful_without_file(self, tmp_path: Path):
        limits_path = tmp_path / "limits.yaml"
        with open(limits_path, "w") as f:
            yaml.dump(MINIMAL_LIMITS, f)
        config = {
            "limits_file": str(limits_path),
            "ethical_topics_file": str(tmp_path / "nonexistent.yaml"),
        }
        c = Cerberus(config)
        await c.initialize()
        assert c._ethical_topics == []


class TestFailLoudDegradedMode:
    """S54 closeout: missing/empty topics escalate to an unmissable ERROR.

    Non-vacuous: assertions target the actual signal (an ERROR-level
    record carrying the `ETHICAL TOPICS UNAVAILABLE` marker), not merely
    the absence of an exception. Boot must still succeed in every case.
    """

    @staticmethod
    def _degraded_errors(caplog) -> list[logging.LogRecord]:
        return [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "ETHICAL TOPICS UNAVAILABLE" in r.getMessage()
        ]

    @pytest.mark.asyncio
    async def test_missing_file_logs_error_and_boots(self, tmp_path: Path, caplog):
        limits_path = tmp_path / "limits.yaml"
        with open(limits_path, "w") as f:
            yaml.dump(MINIMAL_LIMITS, f)
        c = Cerberus({
            "limits_file": str(limits_path),
            "ethical_topics_file": str(tmp_path / "nonexistent.yaml"),
        })
        with caplog.at_level(logging.ERROR):
            await c.initialize()
        errors = self._degraded_errors(caplog)
        assert errors, "missing topics file must log an ERROR-level degraded-mode record"
        assert "not found" in errors[0].getMessage()
        assert c._ethical_topics == []  # boot continued, degraded

    @pytest.mark.asyncio
    async def test_wrong_schema_zero_topics_logs_error(self, tmp_path: Path, caplog):
        """The real F-1 near-miss: concept-keyed source schema parses fine
        but yields 0 topics — that must be as loud as a missing file."""
        limits_path = tmp_path / "limits.yaml"
        ethics_path = tmp_path / "ethics.yaml"
        with open(limits_path, "w") as f:
            yaml.dump(MINIMAL_LIMITS, f)
        with open(ethics_path, "w") as f:
            yaml.dump({"honesty": {"description": "x", "passages": []}}, f)
        c = Cerberus({
            "limits_file": str(limits_path),
            "ethical_topics_file": str(ethics_path),
        })
        with caplog.at_level(logging.ERROR):
            await c.initialize()
        errors = self._degraded_errors(caplog)
        assert errors, "0-topic load must log an ERROR-level degraded-mode record"
        assert "0 topics" in errors[0].getMessage()
        assert c._ethical_topics == []

    @pytest.mark.asyncio
    async def test_empty_file_does_not_crash_init(self, tmp_path: Path, caplog):
        """An empty YAML file (safe_load -> None) previously AttributeError'd
        inside Cerberus init; now it is the same loud degraded condition."""
        limits_path = tmp_path / "limits.yaml"
        ethics_path = tmp_path / "ethics.yaml"
        with open(limits_path, "w") as f:
            yaml.dump(MINIMAL_LIMITS, f)
        ethics_path.write_text("")
        c = Cerberus({
            "limits_file": str(limits_path),
            "ethical_topics_file": str(ethics_path),
        })
        with caplog.at_level(logging.ERROR):
            await c.initialize()  # must not raise
        assert self._degraded_errors(caplog)
        assert c._ethical_topics == []

    @pytest.mark.asyncio
    async def test_healthy_file_stays_quiet(self, ethics_setup: dict, caplog):
        """Guard against an always-firing alarm: a good file must NOT
        produce the degraded-mode ERROR."""
        c = Cerberus(ethics_setup)
        with caplog.at_level(logging.ERROR):
            await c.initialize()
        assert self._degraded_errors(caplog) == []
        assert len(c._ethical_topics) == 3

    def test_ethics_engine_missing_file_logs_error(self, tmp_path: Path, caplog):
        from modules.cerberus.ethics_engine import EthicsEngine
        with caplog.at_level(logging.ERROR):
            EthicsEngine(
                db_path=tmp_path / "mem.db",
                vector_path=tmp_path / "vectors",
                ethical_topics_file=tmp_path / "nonexistent.yaml",
            )
        errors = self._degraded_errors(caplog)
        assert errors, "EthicsEngine must escalate a missing topics file to ERROR"
        assert "not found" in errors[0].getMessage()

    def test_ethics_engine_zero_topics_logs_error(self, tmp_path: Path, caplog):
        from modules.cerberus.ethics_engine import EthicsEngine
        ethics_path = tmp_path / "ethics.yaml"
        with open(ethics_path, "w") as f:
            yaml.dump({"honesty": {"description": "x", "passages": []}}, f)
        with caplog.at_level(logging.ERROR):
            engine = EthicsEngine(
                db_path=tmp_path / "mem.db",
                vector_path=tmp_path / "vectors",
                ethical_topics_file=ethics_path,
            )
        errors = self._degraded_errors(caplog)
        assert errors
        assert "0 topics" in errors[0].getMessage()
        assert engine._topics == []


class TestEthicalGuidanceLookup:
    @pytest.mark.asyncio
    async def test_exact_name_match(self, cerberus: Cerberus):
        results = cerberus.lookup_ethical_guidance("honesty")
        assert len(results) == 2
        assert results[0]["ref"] == "Proverbs 12:22"

    @pytest.mark.asyncio
    async def test_keyword_match(self, cerberus: Cerberus):
        results = cerberus.lookup_ethical_guidance("deception")
        assert len(results) >= 1
        # Should match honesty topic via keyword
        refs = [r["ref"] for r in results]
        assert "Proverbs 12:22" in refs

    @pytest.mark.asyncio
    async def test_case_insensitive(self, cerberus: Cerberus):
        results = cerberus.lookup_ethical_guidance("PRIVACY")
        assert len(results) >= 1
        refs = [r["ref"] for r in results]
        assert "Proverbs 11:13" in refs

    @pytest.mark.asyncio
    async def test_sorted_by_weight(self, cerberus: Cerberus):
        results = cerberus.lookup_ethical_guidance("honesty")
        weights = [r["weight"] for r in results]
        assert weights == sorted(weights, reverse=True)

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, cerberus: Cerberus):
        results = cerberus.lookup_ethical_guidance("quantum physics")
        assert results == []

    @pytest.mark.asyncio
    async def test_description_match(self, cerberus: Cerberus):
        results = cerberus.lookup_ethical_guidance("fairness")
        assert len(results) >= 1
        # Should match justice topic via keyword "fairness"
        refs = [r["ref"] for r in results]
        assert "Micah 6:8" in refs

    @pytest.mark.asyncio
    async def test_via_execute(self, cerberus: Cerberus):
        result = await cerberus.execute("ethical_guidance", {"concept": "honesty"})
        assert result.success
        assert len(result.content) == 2
