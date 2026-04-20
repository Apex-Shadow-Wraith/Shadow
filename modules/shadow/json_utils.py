"""JSON extraction helpers for LLM responses.

LLMs returning structured output often wrap JSON in markdown code fences
or emit leading/trailing prose ("Here is the document: {...}"). A bare
``json.loads`` on that text fails with an opaque JSONDecodeError. This
module centralises the extraction logic so modules can parse LLM
responses consistently and surface a more diagnosable error on failure.

Created for Bug 4 (Nova format_document). Other modules currently do
ad-hoc extraction (Apex synthetic_data_generator, Morpheus
cross_module_dreaming, Omen model_evaluator) and can migrate to this
helper in follow-up work.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger("shadow.json_utils")

_FENCE_RE = re.compile(
    r"^```(?:json|JSON)?\s*\n(.*?)\n```\s*$",
    re.DOTALL,
)


def _strip_markdown_fence(text: str) -> str:
    """Return text with an outer ```json ... ``` fence removed, if any.

    Handles ```json, ```JSON, and bare ``` fences. Leaves text unchanged
    if no fence is detected.
    """
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _extract_outermost_json(text: str) -> str | None:
    """Find the outermost JSON object or array substring in text.

    Walks from the first '{' or '[' to the last matching '}' or ']',
    choosing whichever starts earlier. Returns the substring or None
    if no plausible JSON span is found. Does not validate that the
    substring parses — the caller runs json.loads on it.
    """
    first_obj = text.find("{")
    first_arr = text.find("[")
    candidates = [i for i in (first_obj, first_arr) if i != -1]
    if not candidates:
        return None
    start = min(candidates)

    open_char = text[start]
    close_char = "}" if open_char == "{" else "]"
    end = text.rfind(close_char)
    if end <= start:
        return None

    return text[start : end + 1]


def extract_json_from_llm_response(text: str) -> Any:
    """Extract a JSON object or array from an LLM response.

    Tries in order:
      1. Strip outer markdown code fence and parse the remainder
      2. Parse the raw text directly
      3. Isolate the outermost {...} or [...] span and parse that

    Args:
        text: Raw LLM response text.

    Returns:
        The parsed JSON value (usually dict or list).

    Raises:
        ValueError: If no strategy yields valid JSON. The error message
            includes the first 500 chars of the raw response so future
            failures are diagnosable.
    """
    if not text or not text.strip():
        raise ValueError("LLM response was empty or whitespace-only")

    stripped = _strip_markdown_fence(text)

    # Try the fence-stripped text first (covers the common ```json ... ``` case).
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Fall back to locating the outermost JSON span within the stripped text.
    span = _extract_outermost_json(stripped)
    if span is not None:
        try:
            return json.loads(span)
        except json.JSONDecodeError:
            pass

    # All strategies failed — surface the raw text (truncated) for diagnosis.
    preview = text[:500]
    raise ValueError(
        f"Could not extract JSON from LLM response. Raw response "
        f"(truncated to 500 chars): {preview!r}"
    )
