"""
Tests for Synthetic Training Data Generator
=============================================
Covers batch generation, category validation, anti-sycophancy,
personality examples, save/stats, and API mocking.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from modules.apex.synthetic_data_generator import (
    SyntheticDataGenerator,
    CATEGORIES,
    DIFFICULTIES,
    HEDGING_PHRASES,
    PUSHBACK_INDICATORS,
    SHADOW_SYSTEM_PROMPT,
)


# --- Fixtures ---

@pytest.fixture
def generator(tmp_path: Path) -> SyntheticDataGenerator:
    """Create a SyntheticDataGenerator with a temp output directory."""
    return SyntheticDataGenerator(
        output_dir=str(tmp_path / "synthetic_out"),
        api_key="sk-test-fake-key",
    )


def _mock_claude_response(examples: list[dict]) -> str:
    """Build a fake Claude API response containing the given examples."""
    return json.dumps(examples)


def _make_examples(count: int, category: str = "code_generation") -> list[dict]:
    """Build a list of raw example dicts (as Claude would return)."""
    return [
        {
            "user": f"Test question {i} about {category}",
            "assistant": f"Master, here is test answer {i} for {category}.",
            "difficulty": "medium",
        }
        for i in range(count)
    ]


def _make_anti_sycophancy_examples(count: int) -> list[dict]:
    """Build raw anti-sycophancy examples with pushback language."""
    templates = [
        ("Is Python the best language?", "No, Master. That's not how it works. The best language depends on the task."),
        ("I think we should rewrite in Rust.", "I disagree, Master. That won't work for your use case — the ecosystem isn't there yet."),
        ("What's the population of Mars?", "I don't know, Master. No confirmed census exists for Mars."),
        ("Just deploy it to prod, it'll be fine.", "Hold on, Master. That's a bad idea without running the test suite first."),
        ("AI will replace all developers by next year.", "That's incorrect, Master. You're mistaken about the timeline."),
    ]
    return [
        {"user": templates[i % len(templates)][0], "assistant": templates[i % len(templates)][1], "difficulty": "medium"}
        for i in range(count)
    ]


def _make_personality_examples(count: int) -> list[dict]:
    """Build raw personality examples that use 'Master' and avoid hedging."""
    templates = [
        ("What's the weather like?", "Master, I'd need to check your local forecast. Give me your zip code and I'll pull it."),
        ("How's my schedule today?", "You've got three jobs booked today, Master. First crew rolls out at 7 AM."),
        ("Tell me a joke.", "Master, a SQL query walks into a bar, sees two tables, and asks... 'Can I join you?'"),
        ("Should I raise my prices?", "Yes, Master. Your rates are below market for the quality you deliver. Bump residential by 10-15%."),
        ("What do you think about React?", "Solid framework, Master. Overkill for simple sites, but the ecosystem is unmatched for complex UIs."),
    ]
    return [
        {"user": templates[i % len(templates)][0], "assistant": templates[i % len(templates)][1], "difficulty": "medium"}
        for i in range(count)
    ]


# --- Category validation tests ---

class TestCategoryValidation:
    def test_all_categories_accepted(self, generator: SyntheticDataGenerator):
        """Every defined category should be accepted without ValueError."""
        for cat in CATEGORIES:
            # Just test the prompt builds without error
            prompt = generator._build_generation_prompt(cat, 3, "mixed")
            assert cat in prompt

    def test_invalid_category_raises(self, generator: SyntheticDataGenerator):
        with pytest.raises(ValueError, match="Unknown category"):
            generator.generate_batch("nonexistent_category", count=1)

    def test_invalid_difficulty_raises(self, generator: SyntheticDataGenerator):
        with pytest.raises(ValueError, match="Unknown difficulty"):
            generator.generate_batch("math", count=1, difficulty="impossible")

    def test_all_difficulties_accepted(self, generator: SyntheticDataGenerator):
        for diff in DIFFICULTIES:
            prompt = generator._build_generation_prompt("math", 3, diff)
            assert isinstance(prompt, str)


# --- Batch generation tests ---

class TestGenerateBatch:
    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_returns_valid_entries(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(_make_examples(3))
        results = generator.generate_batch("code_generation", count=3)

        assert len(results) == 3
        for entry in results:
            assert "conversations" in entry
            assert "metadata" in entry
            assert len(entry["conversations"]) == 3
            assert entry["conversations"][0]["role"] == "system"
            assert entry["conversations"][1]["role"] == "user"
            assert entry["conversations"][2]["role"] == "assistant"

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_metadata_fields(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(_make_examples(1))
        results = generator.generate_batch("math", count=1)

        meta = results[0]["metadata"]
        assert meta["source"] == "synthetic"
        assert meta["category"] == "math"
        assert meta["difficulty"] == "medium"
        assert "generator_model" in meta
        assert "timestamp" in meta

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_system_prompt_included(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(_make_examples(1))
        results = generator.generate_batch("research", count=1)

        system_msg = results[0]["conversations"][0]["content"]
        assert system_msg == SHADOW_SYSTEM_PROMPT

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_rate_limit_max_5_calls(self, mock_call, generator):
        """Even for large counts, max 5 API calls."""
        mock_call.return_value = _mock_claude_response(_make_examples(3))
        generator.generate_batch("code_generation", count=100)
        assert mock_call.call_count <= 5

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_count_respected(self, mock_call, generator):
        """Should not return more examples than requested."""
        mock_call.return_value = _mock_claude_response(_make_examples(3))
        results = generator.generate_batch("math", count=5)
        assert len(results) <= 5

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_empty_api_response(self, mock_call, generator):
        mock_call.return_value = "[]"
        results = generator.generate_batch("math", count=3)
        assert results == []

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_malformed_json_response(self, mock_call, generator):
        mock_call.return_value = "not valid json at all"
        results = generator.generate_batch("math", count=3)
        assert results == []

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_markdown_fenced_response(self, mock_call, generator):
        """Claude sometimes wraps JSON in markdown fences."""
        examples = _make_examples(2)
        mock_call.return_value = f"```json\n{json.dumps(examples)}\n```"
        results = generator.generate_batch("code_generation", count=2)
        assert len(results) == 2

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_conversations_are_chatml_format(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(_make_examples(1))
        results = generator.generate_batch("general_knowledge", count=1)
        entry = results[0]
        roles = [c["role"] for c in entry["conversations"]]
        assert roles == ["system", "user", "assistant"]


# --- Anti-sycophancy tests ---

class TestAntiSycophancy:
    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_returns_entries(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(
            _make_anti_sycophancy_examples(3)
        )
        results = generator.generate_anti_sycophancy(count=3)
        assert len(results) == 3

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_contains_pushback_language(self, mock_call, generator):
        """Anti-sycophancy examples should contain pushback indicators."""
        mock_call.return_value = _mock_claude_response(
            _make_anti_sycophancy_examples(5)
        )
        results = generator.generate_anti_sycophancy(count=5)

        for entry in results:
            assistant_text = entry["conversations"][2]["content"].lower()
            has_pushback = any(
                indicator in assistant_text for indicator in PUSHBACK_INDICATORS
            )
            assert has_pushback, (
                f"Anti-sycophancy example lacks pushback language: "
                f"{assistant_text[:100]}"
            )

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_no_hedging_phrases(self, mock_call, generator):
        """Anti-sycophancy examples should not contain hedging phrases."""
        mock_call.return_value = _mock_claude_response(
            _make_anti_sycophancy_examples(3)
        )
        results = generator.generate_anti_sycophancy(count=3)

        for entry in results:
            assistant_text = entry["conversations"][2]["content"].lower()
            for phrase in HEDGING_PHRASES:
                assert phrase not in assistant_text, (
                    f"Anti-sycophancy example contains hedging phrase '{phrase}': "
                    f"{assistant_text[:100]}"
                )

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_metadata_source(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(
            _make_anti_sycophancy_examples(1)
        )
        results = generator.generate_anti_sycophancy(count=1)
        assert results[0]["metadata"]["source"] == "synthetic_anti_sycophancy"
        assert results[0]["metadata"]["category"] == "anti_sycophancy"

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_rate_limited(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(
            _make_anti_sycophancy_examples(3)
        )
        generator.generate_anti_sycophancy(count=100)
        assert mock_call.call_count <= 5


# --- Personality tests ---

class TestPersonalityExamples:
    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_returns_entries(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(
            _make_personality_examples(3)
        )
        results = generator.generate_personality_examples(count=3)
        assert len(results) == 3

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_contains_master(self, mock_call, generator):
        """Personality examples should contain 'Master'."""
        mock_call.return_value = _mock_claude_response(
            _make_personality_examples(5)
        )
        results = generator.generate_personality_examples(count=5)

        for entry in results:
            assistant_text = entry["conversations"][2]["content"]
            assert "Master" in assistant_text, (
                f"Personality example missing 'Master': {assistant_text[:100]}"
            )

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_no_hedging_phrases(self, mock_call, generator):
        """Personality examples should not contain hedging phrases."""
        mock_call.return_value = _mock_claude_response(
            _make_personality_examples(3)
        )
        results = generator.generate_personality_examples(count=3)

        for entry in results:
            assistant_text = entry["conversations"][2]["content"].lower()
            for phrase in HEDGING_PHRASES:
                assert phrase not in assistant_text, (
                    f"Personality example contains hedging phrase '{phrase}'"
                )

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_metadata_source(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(
            _make_personality_examples(1)
        )
        results = generator.generate_personality_examples(count=1)
        assert results[0]["metadata"]["source"] == "synthetic_personality"
        assert results[0]["metadata"]["category"] == "personality"

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_rate_limited(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(
            _make_personality_examples(3)
        )
        generator.generate_personality_examples(count=100)
        assert mock_call.call_count <= 5


# --- Save tests ---

class TestSaveBatch:
    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_creates_file(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(_make_examples(2))
        examples = generator.generate_batch("math", count=2)
        filepath = generator.save_batch(examples, "math")
        assert Path(filepath).exists()

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_correct_filepath_format(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(_make_examples(1))
        examples = generator.generate_batch("code_generation", count=1)
        filepath = generator.save_batch(examples, "code_generation")
        today = datetime.now().strftime("%Y-%m-%d")
        assert f"code_generation_{today}.jsonl" in filepath

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_valid_jsonl_output(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(_make_examples(3))
        examples = generator.generate_batch("research", count=3)
        filepath = generator.save_batch(examples, "research")

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                parsed = json.loads(line.strip())
                assert "conversations" in parsed
                assert "metadata" in parsed

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_appends_not_overwrites(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(_make_examples(2))
        examples = generator.generate_batch("math", count=2)
        filepath = generator.save_batch(examples, "math")
        generator.save_batch(examples, "math")

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 4  # 2 + 2

    def test_save_empty_batch(self, generator):
        filepath = generator.save_batch([], "math")
        assert Path(filepath).exists()
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert content == ""


# --- Stats tests ---

class TestStats:
    def test_stats_empty(self, generator):
        stats = generator.get_stats()
        assert stats["total_examples"] == 0
        assert stats["by_category"] == {}
        assert stats["by_source"] == {}
        assert stats["file_count"] == 0

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_stats_after_save(self, mock_call, generator):
        mock_call.return_value = _mock_claude_response(_make_examples(3, "math"))
        examples = generator.generate_batch("math", count=3)
        generator.save_batch(examples, "math")

        stats = generator.get_stats()
        assert stats["total_examples"] == 3
        assert stats["by_category"]["math"] == 3
        assert stats["by_source"]["synthetic"] == 3
        assert stats["file_count"] == 1

    @patch.object(SyntheticDataGenerator, "_call_claude")
    def test_stats_multiple_categories(self, mock_call, generator):
        # Save math examples
        mock_call.return_value = _mock_claude_response(_make_examples(2, "math"))
        examples = generator.generate_batch("math", count=2)
        generator.save_batch(examples, "math")

        # Save code examples
        mock_call.return_value = _mock_claude_response(_make_examples(3, "code_generation"))
        examples = generator.generate_batch("code_generation", count=3)
        generator.save_batch(examples, "code_generation")

        stats = generator.get_stats()
        assert stats["total_examples"] == 5
        assert stats["by_category"]["math"] == 2
        assert stats["by_category"]["code_generation"] == 3
        assert stats["file_count"] == 2


# --- Init tests ---

class TestInit:
    def test_creates_output_dir(self, tmp_path: Path):
        out_dir = tmp_path / "new_dir" / "nested"
        gen = SyntheticDataGenerator(output_dir=str(out_dir), api_key="fake")
        assert out_dir.exists()

    def test_existing_dir_no_error(self, tmp_path: Path):
        out_dir = tmp_path / "existing"
        out_dir.mkdir()
        gen = SyntheticDataGenerator(output_dir=str(out_dir), api_key="fake")
        assert out_dir.exists()

    def test_default_model(self, tmp_path: Path):
        gen = SyntheticDataGenerator(output_dir=str(tmp_path), api_key="fake")
        assert "claude" in gen._model


# --- Prompt building tests ---

class TestPromptBuilding:
    def test_generation_prompt_includes_category(self, generator):
        prompt = generator._build_generation_prompt("landscaping_business", 5, "hard")
        assert "landscaping" in prompt.lower()
        assert "5" in prompt

    def test_generation_prompt_includes_difficulty(self, generator):
        prompt = generator._build_generation_prompt("math", 3, "hard")
        assert "HARD" in prompt

    def test_anti_sycophancy_prompt_includes_pushback(self, generator):
        prompt = generator._build_anti_sycophancy_prompt(5)
        assert "push" in prompt.lower() or "disagree" in prompt.lower()

    def test_personality_prompt_includes_master(self, generator):
        prompt = generator._build_personality_prompt(5)
        assert "Master" in prompt

    def test_generation_prompt_includes_shadow_identity(self, generator):
        prompt = generator._build_generation_prompt("math", 3, "mixed")
        assert "Shadow" in prompt

    def test_mixed_difficulty_prompt(self, generator):
        prompt = generator._build_generation_prompt("math", 3, "mixed")
        assert "Mix" in prompt


# --- Response parsing tests ---

class TestParsing:
    def test_parse_valid_json(self, generator):
        data = [{"user": "q", "assistant": "a"}]
        result = generator._parse_response(json.dumps(data))
        assert len(result) == 1

    def test_parse_with_markdown_fences(self, generator):
        data = [{"user": "q", "assistant": "a"}]
        raw = f"```json\n{json.dumps(data)}\n```"
        result = generator._parse_response(raw)
        assert len(result) == 1

    def test_parse_invalid_json(self, generator):
        result = generator._parse_response("not json")
        assert result == []

    def test_parse_filters_invalid_entries(self, generator):
        data = [
            {"user": "q", "assistant": "a"},
            {"missing_keys": True},
            {"user": "q2", "assistant": "a2"},
        ]
        result = generator._parse_response(json.dumps(data))
        assert len(result) == 2

    def test_parse_non_array(self, generator):
        result = generator._parse_response('{"not": "an array"}')
        assert result == []


# --- API key resolution tests ---

class TestApiKey:
    def test_uses_init_key(self, tmp_path: Path):
        gen = SyntheticDataGenerator(
            output_dir=str(tmp_path), api_key="sk-test-key"
        )
        assert gen._get_api_key() == "sk-test-key"

    def test_falls_back_to_config_singleton(self, tmp_path: Path, monkeypatch):
        """Without init api_key, SyntheticDataGenerator reads from shadow.config."""
        from pydantic import SecretStr
        from shadow.config import config
        monkeypatch.setattr(
            config.apex, "anthropic_api_key", SecretStr("sk-from-singleton")
        )
        gen = SyntheticDataGenerator(output_dir=str(tmp_path))
        assert gen._get_api_key() == "sk-from-singleton"

    def test_raises_without_key(self, tmp_path: Path, monkeypatch):
        from shadow.config import config
        monkeypatch.setattr(config.apex, "anthropic_api_key", None)
        gen = SyntheticDataGenerator(output_dir=str(tmp_path))
        with pytest.raises(RuntimeError, match="No Anthropic API key"):
            gen._get_api_key()
