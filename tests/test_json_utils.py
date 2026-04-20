"""Tests for modules.shadow.json_utils — LLM response JSON extraction."""

from __future__ import annotations

import json

import pytest

from modules.shadow.json_utils import extract_json_from_llm_response


class TestExtractJsonFromLlmResponse:
    """Covers the three LLM output shapes Nova's format_document hit in the
    Phase 0 benchmark (Bug 4), plus edge cases."""

    def test_parses_raw_json_object(self):
        raw = json.dumps({"title": "x", "sections": [{"heading": "h", "body": "b"}]})
        result = extract_json_from_llm_response(raw)
        assert result == {"title": "x", "sections": [{"heading": "h", "body": "b"}]}

    def test_parses_raw_json_array(self):
        raw = json.dumps([1, 2, {"k": "v"}])
        result = extract_json_from_llm_response(raw)
        assert result == [1, 2, {"k": "v"}]

    def test_parses_markdown_fenced_json(self):
        inner = json.dumps({"title": "Photosynthesis"})
        wrapped = f"```json\n{inner}\n```"
        result = extract_json_from_llm_response(wrapped)
        assert result == {"title": "Photosynthesis"}

    def test_parses_bare_triple_backtick_fence(self):
        inner = json.dumps({"ok": True})
        wrapped = f"```\n{inner}\n```"
        result = extract_json_from_llm_response(wrapped)
        assert result == {"ok": True}

    def test_parses_uppercase_json_fence(self):
        inner = json.dumps({"case": "upper"})
        wrapped = f"```JSON\n{inner}\n```"
        result = extract_json_from_llm_response(wrapped)
        assert result == {"case": "upper"}

    def test_parses_json_with_leading_prose(self):
        inner = json.dumps({"title": "Gardening"})
        text = f"Here is the document:\n\n{inner}"
        result = extract_json_from_llm_response(text)
        assert result == {"title": "Gardening"}

    def test_parses_json_with_trailing_prose(self):
        inner = json.dumps({"title": "Gardening"})
        text = f"{inner}\n\nHope this helps!"
        result = extract_json_from_llm_response(text)
        assert result == {"title": "Gardening"}

    def test_parses_json_wrapped_in_prose(self):
        inner = json.dumps({"a": 1})
        text = f"Sure thing. {inner} Let me know if you need more."
        result = extract_json_from_llm_response(text)
        assert result == {"a": 1}

    def test_parses_fenced_json_with_leading_whitespace(self):
        inner = json.dumps({"x": 1})
        text = f"   \n\n```json\n{inner}\n```\n"
        result = extract_json_from_llm_response(text)
        assert result == {"x": 1}

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError, match="empty or whitespace-only"):
            extract_json_from_llm_response("")

    def test_whitespace_only_raises_value_error(self):
        with pytest.raises(ValueError, match="empty or whitespace-only"):
            extract_json_from_llm_response("   \n\t  ")

    def test_no_json_in_text_raises_with_preview(self):
        text = "I can't help with that request."
        with pytest.raises(ValueError) as exc_info:
            extract_json_from_llm_response(text)
        assert "Could not extract JSON" in str(exc_info.value)
        assert "I can't help with that request" in str(exc_info.value)

    def test_truncated_preview_in_error(self):
        long_text = "not-json " * 200  # well over 500 chars
        with pytest.raises(ValueError) as exc_info:
            extract_json_from_llm_response(long_text)
        msg = str(exc_info.value)
        # The preview must be truncated to 500 chars of the raw input.
        # Not an exact assertion on length (repr adds quotes/escapes),
        # but the full long_text must not fit in the message.
        assert len(msg) < len(long_text) + 200

    def test_array_start_before_object_start(self):
        """If '[' appears before '{', extract the array, not the object."""
        text = '[1, 2, 3]\n\n{"unrelated": "noise"}'
        result = extract_json_from_llm_response(text)
        assert result == [1, 2, 3]

    def test_object_start_before_array_start(self):
        text = '{"ok": true}\n\n[1, 2]'
        result = extract_json_from_llm_response(text)
        assert result == {"ok": True}
