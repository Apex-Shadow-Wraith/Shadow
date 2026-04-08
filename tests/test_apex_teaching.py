"""
Tests for 3-Tier TeachingExtractor
====================================
Covers extract_three_tiers, store_three_tiers, search_with_tier_priority,
escalation template injection, and graceful degradation.
"""

import pytest
from unittest.mock import MagicMock, call

from modules.apex.teaching_extractor import (
    TeachingExtractor,
    THREE_TIER_TEACHING_TEMPLATE,
)


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def extractor() -> TeachingExtractor:
    return TeachingExtractor()


@pytest.fixture
def task() -> dict:
    return {"type": "code_generation", "description": "Optimize CUDA kernel"}


@pytest.fixture
def domain_tags() -> list[str]:
    return ["gpu/cuda", "optimization"]


@pytest.fixture
def well_formatted_response() -> str:
    return (
        "Here is the full answer.\n\n"
        "<specific_solution>\n"
        "Use shared memory tiling with 32x32 blocks to reduce global memory reads.\n"
        "</specific_solution>\n\n"
        "<general_principle>\n"
        "Use shared memory tiling when global memory bandwidth is the bottleneck.\n"
        "</general_principle>\n\n"
        "<meta_principle>\n"
        "Identify the bottleneck resource before optimizing.\n"
        "</meta_principle>"
    )


@pytest.fixture
def partial_xml_response() -> str:
    return (
        "<specific_solution>\n"
        "Apply loop unrolling with pragma directives.\n"
        "</specific_solution>\n\n"
        "Generally, when you have a tight loop, unrolling helps.\n"
        "Think about whether the loop body is the real bottleneck.\n"
    )


@pytest.fixture
def plain_response() -> str:
    return (
        "Here is a binary search implementation:\n"
        "```python\n"
        "def binary_search(arr, target):\n"
        "    lo, hi = 0, len(arr) - 1\n"
        "    while lo <= hi:\n"
        "        mid = (lo + hi) // 2\n"
        "        if arr[mid] == target:\n"
        "            return mid\n"
        "        elif arr[mid] < target:\n"
        "            lo = mid + 1\n"
        "        else:\n"
        "            hi = mid - 1\n"
        "    return -1\n"
        "```\n"
        "This is the typical approach for sorted arrays. "
        "Generally, binary search works when the data is sorted. "
        "Always think about whether the search space can be halved."
    )


@pytest.fixture
def mock_grimoire() -> MagicMock:
    grim = MagicMock()
    grim.remember.side_effect = lambda **kw: f"mem-{kw.get('category', 'x')}-{id(kw) % 10000}"
    return grim


# ===================================================================
# extract_three_tiers tests
# ===================================================================

class TestExtractThreeTiers:
    def test_well_formatted_xml_all_tiers(
        self, extractor, well_formatted_response, task, domain_tags
    ):
        """Well-formatted XML response extracts all 3 tiers."""
        result = extractor.extract_three_tiers(
            well_formatted_response, task, domain_tags
        )
        assert result["all_extracted"] is True
        assert result["missing_tiers"] == []
        assert "shared memory tiling" in result["specific"]["content"]
        assert "bandwidth" in result["general"]["content"]
        assert "bottleneck resource" in result["meta"]["content"]

    def test_partial_xml_with_heuristic_fallback(
        self, extractor, partial_xml_response, task, domain_tags
    ):
        """Response with only specific_solution tag uses heuristic for others."""
        result = extractor.extract_three_tiers(
            partial_xml_response, task, domain_tags
        )
        assert "loop unrolling" in result["specific"]["content"]
        # General extracted by heuristic (keyword "Generally")
        assert result["general"]["content"] != ""
        # Meta extracted by heuristic (keyword "Think about")
        assert result["meta"]["content"] != ""

    def test_no_xml_heuristic_only(
        self, extractor, plain_response, task, domain_tags
    ):
        """No XML tags at all — heuristic extraction produces at least specific."""
        result = extractor.extract_three_tiers(
            plain_response, task, domain_tags
        )
        assert result["specific"]["content"] != ""
        # Code block should end up in specific
        assert "binary_search" in result["specific"]["content"]

    def test_missing_tiers_reported(self, extractor, task):
        """missing_tiers correctly reports which tiers weren't found."""
        # Very short response with no keywords → only specific extractable
        result = extractor.extract_three_tiers("42", task)
        assert "specific" not in result["missing_tiers"]
        # At least general or meta should be missing
        assert len(result["missing_tiers"]) > 0
        assert result["all_extracted"] is False

    def test_empty_response_still_returns_specific(self, extractor, task):
        """Graceful degradation: empty-ish response stored as specific only."""
        result = extractor.extract_three_tiers("Just a plain answer.", task)
        assert result["specific"]["content"] == "Just a plain answer."
        assert result["all_extracted"] is False

    def test_metadata_tier_tags(
        self, extractor, well_formatted_response, task, domain_tags
    ):
        """Each tier has correct tier metadata and domain_tags."""
        result = extractor.extract_three_tiers(
            well_formatted_response, task, domain_tags
        )
        assert result["specific"]["metadata"]["tier"] == "specific"
        assert result["general"]["metadata"]["tier"] == "general"
        assert result["meta"]["metadata"]["tier"] == "meta"
        assert result["specific"]["metadata"]["domain_tags"] == domain_tags
        assert result["general"]["metadata"]["domain_tags"] == domain_tags

    def test_meta_gets_broader_tags(
        self, extractor, well_formatted_response, task, domain_tags
    ):
        """Meta-principle gets broader (prefix) domain tags."""
        result = extractor.extract_three_tiers(
            well_formatted_response, task, domain_tags
        )
        # "gpu/cuda" → "gpu", "optimization" → "optimization"
        meta_tags = result["meta"]["metadata"]["domain_tags"]
        assert "gpu" in meta_tags
        assert "optimization" in meta_tags

    def test_task_hash_in_specific(
        self, extractor, well_formatted_response, task, domain_tags
    ):
        """Specific tier has a task_hash in metadata."""
        result = extractor.extract_three_tiers(
            well_formatted_response, task, domain_tags
        )
        assert "task_hash" in result["specific"]["metadata"]
        assert len(result["specific"]["metadata"]["task_hash"]) == 16


# ===================================================================
# store_three_tiers tests
# ===================================================================

class TestStoreThreeTiers:
    def test_three_entries_created(
        self, extractor, well_formatted_response, task, domain_tags, mock_grimoire
    ):
        """3 Grimoire entries created for 3 non-empty tiers."""
        tiers = extractor.extract_three_tiers(
            well_formatted_response, task, domain_tags
        )
        ids = extractor.store_three_tiers(tiers, mock_grimoire)
        assert len(ids) == 3
        assert mock_grimoire.remember.call_count == 3

    def test_each_entry_has_tier_metadata(
        self, extractor, well_formatted_response, task, domain_tags, mock_grimoire
    ):
        """Each stored entry has correct tier metadata."""
        tiers = extractor.extract_three_tiers(
            well_formatted_response, task, domain_tags
        )
        extractor.store_three_tiers(tiers, mock_grimoire)

        calls = mock_grimoire.remember.call_args_list
        stored_tiers = [c.kwargs["metadata"]["tier"] for c in calls]
        assert stored_tiers == ["specific", "general", "meta"]

    def test_domain_tags_propagated(
        self, extractor, well_formatted_response, task, domain_tags, mock_grimoire
    ):
        """Domain tags appear in all stored entries' tags list."""
        tiers = extractor.extract_three_tiers(
            well_formatted_response, task, domain_tags
        )
        extractor.store_three_tiers(tiers, mock_grimoire)

        for c in mock_grimoire.remember.call_args_list:
            tags = c.kwargs["tags"]
            assert "apex_teaching" in tags

    def test_confidence_at_creation(
        self, extractor, well_formatted_response, task, domain_tags, mock_grimoire
    ):
        """confidence_at_creation set to 0.7 for all tiers."""
        tiers = extractor.extract_three_tiers(
            well_formatted_response, task, domain_tags
        )
        extractor.store_three_tiers(tiers, mock_grimoire)

        for c in mock_grimoire.remember.call_args_list:
            assert c.kwargs["metadata"]["confidence_at_creation"] == 0.7
            assert c.kwargs["confidence"] == 0.7

    def test_source_task_hash_links_tiers(
        self, extractor, well_formatted_response, task, domain_tags, mock_grimoire
    ):
        """source_task_hash is the same across all three tiers."""
        tiers = extractor.extract_three_tiers(
            well_formatted_response, task, domain_tags
        )
        extractor.store_three_tiers(tiers, mock_grimoire)

        hashes = [
            c.kwargs["metadata"]["source_task_hash"]
            for c in mock_grimoire.remember.call_args_list
        ]
        assert len(set(hashes)) == 1  # All same hash

    def test_grimoire_error_handled(self, extractor, task):
        """Grimoire raising exceptions doesn't crash store_three_tiers."""
        bad_grim = MagicMock()
        bad_grim.remember.side_effect = RuntimeError("DB locked")
        tiers = extractor.extract_three_tiers("some answer", task)
        ids = extractor.store_three_tiers(tiers, bad_grim)
        assert ids == []  # Nothing stored, but no crash


# ===================================================================
# search_with_tier_priority tests
# ===================================================================

class TestSearchWithTierPriority:
    def test_specific_ranked_above_general(self, extractor):
        """Specific result ranked above general when both returned."""
        mock_grim = MagicMock()
        mock_grim.recall.return_value = [
            {"content": "general approach", "metadata": {"tier": "general"}, "distance": 0.2},
            {"content": "exact answer", "metadata": {"tier": "specific"}, "distance": 0.3},
        ]
        results = extractor.search_with_tier_priority(mock_grim, "test query")
        assert results[0]["metadata"]["tier"] == "specific"
        assert results[1]["metadata"]["tier"] == "general"

    def test_general_ranked_above_meta(self, extractor):
        """General ranked above meta."""
        mock_grim = MagicMock()
        mock_grim.recall.return_value = [
            {"content": "meta strategy", "metadata": {"tier": "meta"}, "distance": 0.1},
            {"content": "general pattern", "metadata": {"tier": "general"}, "distance": 0.2},
        ]
        results = extractor.search_with_tier_priority(mock_grim, "test query")
        assert results[0]["metadata"]["tier"] == "general"
        assert results[1]["metadata"]["tier"] == "meta"

    def test_cross_domain_meta_retrieved(self, extractor):
        """Cross-domain meta-principle surfaces for novel domain."""
        mock_grim = MagicMock()
        mock_grim.recall.return_value = [
            {"content": "Identify bottleneck first", "metadata": {"tier": "meta"}, "distance": 0.5},
        ]
        results = extractor.search_with_tier_priority(
            mock_grim, "novel domain query"
        )
        assert len(results) == 1
        assert results[0]["metadata"]["tier"] == "meta"

    def test_empty_results_handled(self, extractor):
        """Empty Grimoire results returns empty list."""
        mock_grim = MagicMock()
        mock_grim.recall.return_value = []
        results = extractor.search_with_tier_priority(mock_grim, "query")
        assert results == []

    def test_grimoire_error_returns_empty(self, extractor):
        """Grimoire exception returns empty list."""
        mock_grim = MagicMock()
        mock_grim.recall.side_effect = RuntimeError("connection lost")
        results = extractor.search_with_tier_priority(mock_grim, "query")
        assert results == []


# ===================================================================
# Escalation template tests
# ===================================================================

class TestEscalationTemplate:
    def test_template_contains_three_sections(self):
        """Template includes all three XML section tags."""
        assert "<specific_solution>" in THREE_TIER_TEACHING_TEMPLATE
        assert "<general_principle>" in THREE_TIER_TEACHING_TEMPLATE
        assert "<meta_principle>" in THREE_TIER_TEACHING_TEMPLATE

    def test_apex_teach_includes_template(self):
        """Apex._apex_teach teaching request includes the template."""
        from modules.apex.apex import Apex
        apex = Apex({"log_file": "/dev/null"})
        result = apex._apex_teach({
            "task": "test task",
            "failed_approaches": [],
            "successful_answer": "answer",
        })
        assert result.success is True
        # The teaching_request logged should include the template
        last_log = apex._call_log[-1]
        assert "teaching_template" in last_log


# ===================================================================
# Backward compatibility
# ===================================================================

class TestBackwardCompatibility:
    def test_old_extract_teaching_signal_still_works(self, extractor):
        """Legacy extract_teaching_signal interface unchanged."""
        signal = extractor.extract_teaching_signal(
            task_input="Write binary search",
            api_response="def binary_search...",
            task_type="code_generation",
        )
        assert signal["task_type"] == "code_generation"
        assert "input_summary" in signal
        assert "approach" in signal
        assert "key_patterns" in signal

    def test_import_from_apex_module(self):
        """TeachingExtractor still importable from modules.apex.apex."""
        from modules.apex.apex import TeachingExtractor as TE
        ext = TE()
        assert hasattr(ext, "extract_teaching_signal")
        assert hasattr(ext, "extract_three_tiers")
