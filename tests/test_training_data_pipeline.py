"""
Tests for Training Data Pipeline — LoRA-Ready Dataset from Apex Escalations
=============================================================================
Covers capture, save, daily rotation, export, stats, metadata, and
sensitive data sanitization.
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from modules.apex.training_data_pipeline import TrainingDataPipeline


@pytest.fixture
def pipeline(tmp_path: Path) -> TrainingDataPipeline:
    """Create a TrainingDataPipeline with a temp output directory."""
    return TrainingDataPipeline(output_dir=str(tmp_path / "training_out"))


@pytest.fixture
def sample_entry(pipeline: TrainingDataPipeline) -> dict:
    """Create a sample training entry via capture()."""
    return pipeline.capture(
        user_input="How do I reverse a linked list?",
        shadow_failed_response="I tried but got confused on pointers.",
        apex_response="To reverse a linked list, iterate through nodes...",
        module="omen",
        category="code_generation",
        metadata={
            "model_that_failed": "gemma4:26b",
            "model_that_answered": "claude-opus-4-6",
            "confidence_before": 0.3,
            "confidence_after": 0.95,
        },
    )


# --- Capture tests ---

class TestCapture:
    def test_capture_returns_dict(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="test input",
            shadow_failed_response="",
            apex_response="test response",
            module="cipher",
            category="math",
        )
        assert isinstance(entry, dict)

    def test_capture_has_conversations(self, sample_entry: dict):
        assert "conversations" in sample_entry
        convos = sample_entry["conversations"]
        assert len(convos) == 3
        assert convos[0]["role"] == "system"
        assert convos[0]["content"] == "You are Shadow."
        assert convos[1]["role"] == "user"
        assert convos[2]["role"] == "assistant"

    def test_capture_user_content_matches(self, sample_entry: dict):
        assert sample_entry["conversations"][1]["content"] == "How do I reverse a linked list?"

    def test_capture_assistant_content_matches(self, sample_entry: dict):
        assert "reverse a linked list" in sample_entry["conversations"][2]["content"]

    def test_capture_has_metadata(self, sample_entry: dict):
        meta = sample_entry["metadata"]
        assert meta["source"] == "apex_escalation"
        assert meta["module"] == "omen"
        assert meta["category"] == "code_generation"
        assert "timestamp" in meta
        assert meta["model_that_failed"] == "gemma4:26b"
        assert meta["model_that_answered"] == "claude-opus-4-6"
        assert meta["confidence_before"] == 0.3
        assert meta["confidence_after"] == 0.95

    def test_capture_all_metadata_fields_present(self, sample_entry: dict):
        required_fields = [
            "source", "module", "category", "timestamp",
            "model_that_failed", "model_that_answered",
            "confidence_before", "confidence_after",
        ]
        for field in required_fields:
            assert field in sample_entry["metadata"], f"Missing metadata field: {field}"

    def test_capture_includes_failed_response_in_metadata(self, sample_entry: dict):
        assert "shadow_failed_response" in sample_entry["metadata"]
        assert "pointers" in sample_entry["metadata"]["shadow_failed_response"]

    def test_capture_without_failed_response(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="test",
            shadow_failed_response="",
            apex_response="answer",
            module="reaper",
            category="research",
        )
        assert "shadow_failed_response" not in entry["metadata"]

    def test_capture_default_metadata(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="test",
            shadow_failed_response="",
            apex_response="answer",
            module="cipher",
            category="math",
        )
        assert entry["metadata"]["model_that_failed"] == ""
        assert entry["metadata"]["model_that_answered"] == ""
        assert entry["metadata"]["confidence_before"] == 0.0
        assert entry["metadata"]["confidence_after"] == 0.0


# --- Save tests ---

class TestSave:
    def test_save_creates_file(self, pipeline: TrainingDataPipeline, sample_entry: dict):
        filepath = pipeline.save(sample_entry)
        assert Path(filepath).exists()

    def test_save_returns_filepath_string(self, pipeline: TrainingDataPipeline, sample_entry: dict):
        filepath = pipeline.save(sample_entry)
        assert isinstance(filepath, str)
        assert "apex_training_" in filepath
        assert filepath.endswith(".jsonl")

    def test_save_appends_not_overwrites(self, pipeline: TrainingDataPipeline, sample_entry: dict):
        filepath = pipeline.save(sample_entry)
        pipeline.save(sample_entry)

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_save_valid_jsonl(self, pipeline: TrainingDataPipeline, sample_entry: dict):
        filepath = pipeline.save(sample_entry)
        pipeline.save(sample_entry)

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                parsed = json.loads(line.strip())
                assert "conversations" in parsed
                assert "metadata" in parsed

    def test_save_utf8_encoding(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="Wie kann ich eine Liste umkehren? \u00e4\u00f6\u00fc\u00df",
            shadow_failed_response="",
            apex_response="\u2713 Hier ist die L\u00f6sung: \u00e9\u00e8\u00ea",
            module="cipher",
            category="general",
        )
        filepath = pipeline.save(entry)

        with open(filepath, "r", encoding="utf-8") as f:
            parsed = json.loads(f.readline())
        assert "\u00e4\u00f6\u00fc" in parsed["conversations"][1]["content"]
        assert "\u00e9\u00e8\u00ea" in parsed["conversations"][2]["content"]

    def test_save_daily_filename_format(self, pipeline: TrainingDataPipeline, sample_entry: dict):
        filepath = pipeline.save(sample_entry)
        today = datetime.now().strftime("%Y-%m-%d")
        assert f"apex_training_{today}.jsonl" in filepath


# --- Daily rotation tests ---

class TestDailyRotation:
    def test_different_dates_different_files(self, pipeline: TrainingDataPipeline, sample_entry: dict):
        # Save with today's date
        filepath1 = pipeline.save(sample_entry)

        # Mock a different date for second save
        with patch("modules.apex.training_data_pipeline.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 12, 25, 10, 0, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            filepath2 = pipeline.save(sample_entry)

        assert filepath1 != filepath2
        assert "2026-12-25" in filepath2

    def test_same_date_same_file(self, pipeline: TrainingDataPipeline, sample_entry: dict):
        filepath1 = pipeline.save(sample_entry)
        filepath2 = pipeline.save(sample_entry)
        assert filepath1 == filepath2


# --- Export tests ---

class TestExportForLora:
    def test_export_merges_files(self, pipeline: TrainingDataPipeline, sample_entry: dict, tmp_path: Path):
        # Save entries on two "different days"
        pipeline.save(sample_entry)

        with patch("modules.apex.training_data_pipeline.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 12, 25, 10, 0, 0)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            pipeline.save(sample_entry)

        output_path = str(tmp_path / "merged.jsonl")
        count = pipeline.export_for_lora(output_path)
        assert count == 2

        with open(output_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_export_returns_count(self, pipeline: TrainingDataPipeline, sample_entry: dict, tmp_path: Path):
        pipeline.save(sample_entry)
        pipeline.save(sample_entry)
        pipeline.save(sample_entry)

        output_path = str(tmp_path / "merged.jsonl")
        count = pipeline.export_for_lora(output_path)
        assert count == 3

    def test_export_valid_jsonl(self, pipeline: TrainingDataPipeline, sample_entry: dict, tmp_path: Path):
        pipeline.save(sample_entry)

        output_path = str(tmp_path / "merged.jsonl")
        pipeline.export_for_lora(output_path)

        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                parsed = json.loads(line.strip())
                assert "conversations" in parsed

    def test_export_empty_returns_zero(self, pipeline: TrainingDataPipeline, tmp_path: Path):
        output_path = str(tmp_path / "merged.jsonl")
        count = pipeline.export_for_lora(output_path)
        assert count == 0

    def test_export_creates_parent_dirs(self, pipeline: TrainingDataPipeline, sample_entry: dict, tmp_path: Path):
        pipeline.save(sample_entry)
        output_path = str(tmp_path / "nested" / "dir" / "merged.jsonl")
        count = pipeline.export_for_lora(output_path)
        assert count == 1
        assert Path(output_path).exists()


# --- Stats tests ---

class TestStats:
    def test_stats_empty(self, pipeline: TrainingDataPipeline):
        stats = pipeline.get_stats()
        assert stats["total_examples"] == 0
        assert stats["examples_today"] == 0
        assert stats["by_category"] == {}
        assert stats["by_module"] == {}

    def test_stats_total_count(self, pipeline: TrainingDataPipeline, sample_entry: dict):
        pipeline.save(sample_entry)
        pipeline.save(sample_entry)
        pipeline.save(sample_entry)

        stats = pipeline.get_stats()
        assert stats["total_examples"] == 3

    def test_stats_today_count(self, pipeline: TrainingDataPipeline, sample_entry: dict):
        pipeline.save(sample_entry)
        pipeline.save(sample_entry)

        stats = pipeline.get_stats()
        assert stats["examples_today"] == 2

    def test_stats_by_category(self, pipeline: TrainingDataPipeline):
        entry1 = pipeline.capture("q1", "", "a1", "omen", "code_generation")
        entry2 = pipeline.capture("q2", "", "a2", "cipher", "math")
        entry3 = pipeline.capture("q3", "", "a3", "omen", "code_generation")
        pipeline.save(entry1)
        pipeline.save(entry2)
        pipeline.save(entry3)

        stats = pipeline.get_stats()
        assert stats["by_category"]["code_generation"] == 2
        assert stats["by_category"]["math"] == 1

    def test_stats_by_module(self, pipeline: TrainingDataPipeline):
        entry1 = pipeline.capture("q1", "", "a1", "omen", "code_generation")
        entry2 = pipeline.capture("q2", "", "a2", "cipher", "math")
        pipeline.save(entry1)
        pipeline.save(entry2)

        stats = pipeline.get_stats()
        assert stats["by_module"]["omen"] == 1
        assert stats["by_module"]["cipher"] == 1


# --- Sanitization tests ---

class TestSanitization:
    def test_strips_anthropic_api_key(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="My key is ANTHROPIC_API_KEY=sk-ant-abc123xyz",
            shadow_failed_response="",
            apex_response="You should not share API keys.",
            module="sentinel",
            category="security",
        )
        user_content = entry["conversations"][1]["content"]
        assert "sk-ant-" not in user_content
        assert "[REDACTED]" in user_content

    def test_strips_openai_api_key(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="Set OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuv",
            shadow_failed_response="",
            apex_response="Done.",
            module="sentinel",
            category="security",
        )
        user_content = entry["conversations"][1]["content"]
        assert "sk-proj-" not in user_content
        assert "[REDACTED]" in user_content

    def test_strips_bare_sk_ant_key(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="Use this key: sk-ant-api03-longkeyvalue123",
            shadow_failed_response="",
            apex_response="I see your key sk-ant-api03-longkeyvalue123 in the response.",
            module="sentinel",
            category="security",
        )
        assert "sk-ant-" not in entry["conversations"][1]["content"]
        assert "sk-ant-" not in entry["conversations"][2]["content"]

    def test_strips_config_env_reference(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="Load keys from config/.env file",
            shadow_failed_response="",
            apex_response="The config/.env file contains your secrets.",
            module="sentinel",
            category="security",
        )
        assert "config/.env" not in entry["conversations"][1]["content"]
        assert "config/.env" not in entry["conversations"][2]["content"]

    def test_strips_secret_key_assignment(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="SECRET_KEY=mysupersecretvalue123456",
            shadow_failed_response="",
            apex_response="Done.",
            module="sentinel",
            category="security",
        )
        assert "mysupersecretvalue" not in entry["conversations"][1]["content"]
        assert "[REDACTED]" in entry["conversations"][1]["content"]

    def test_sanitize_preserves_normal_text(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="How do I write a Python class?",
            shadow_failed_response="",
            apex_response="Here is how you write a Python class.",
            module="omen",
            category="code_generation",
        )
        assert entry["conversations"][1]["content"] == "How do I write a Python class?"
        assert entry["conversations"][2]["content"] == "Here is how you write a Python class."

    def test_sanitize_in_failed_response(self, pipeline: TrainingDataPipeline):
        entry = pipeline.capture(
            user_input="test",
            shadow_failed_response="I found ANTHROPIC_API_KEY=sk-ant-secret123 in the config",
            apex_response="answer",
            module="sentinel",
            category="security",
        )
        assert "sk-ant-" not in entry["metadata"]["shadow_failed_response"]
        assert "[REDACTED]" in entry["metadata"]["shadow_failed_response"]


# --- Init tests ---

class TestInit:
    def test_creates_output_dir(self, tmp_path: Path):
        out_dir = tmp_path / "new_dir" / "nested"
        pipeline = TrainingDataPipeline(output_dir=str(out_dir))
        assert out_dir.exists()

    def test_existing_dir_no_error(self, tmp_path: Path):
        out_dir = tmp_path / "existing"
        out_dir.mkdir()
        pipeline = TrainingDataPipeline(output_dir=str(out_dir))
        assert out_dir.exists()
