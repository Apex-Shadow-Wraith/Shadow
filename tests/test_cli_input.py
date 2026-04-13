"""
Tests for CLI input sanitization, fuzzy command matching, and quit handling.

Covers:
  - sanitize_input stripping GIN log garbage
  - fuzzy_match_command correcting typos
  - /quit and /exit caught before reaching orchestrator
"""

import pytest

from main import sanitize_input, fuzzy_match_command, KNOWN_COMMANDS


# ── sanitize_input ──────────────────────────────────────────────────

class TestSanitizeInput:
    """Verify that GIN noise and leading garbage are stripped."""

    def test_clean_input_unchanged(self):
        assert sanitize_input("/tasks") == "/tasks"

    def test_double_slash(self):
        assert sanitize_input("//tasks") == "/tasks"

    def test_triple_slash(self):
        assert sanitize_input("///tasks") == "/tasks"

    def test_gin_log_prefix(self):
        """Simulates Ollama GIN debug output bleeding into the buffer."""
        raw = "[GIN] 2024/12/01 - 10:30:00 | 200 |/tasks"
        result = sanitize_input(raw)
        assert result == "/tasks"

    def test_gin_garbage_with_spaces(self):
        raw = "  [GIN] debug /history 20  "
        result = sanitize_input(raw)
        assert result.startswith("/history")

    def test_random_prefix_chars(self):
        raw = "abc123/status"
        assert sanitize_input(raw) == "/status"

    def test_leading_whitespace(self):
        assert sanitize_input("   /help   ") == "/help"

    def test_plain_text_no_slash(self):
        """Non-command input should pass through stripped."""
        assert sanitize_input("  hello world  ") == "hello world"

    def test_empty_string(self):
        assert sanitize_input("") == ""

    def test_whitespace_only(self):
        assert sanitize_input("   ") == ""

    def test_only_slashes(self):
        assert sanitize_input("///") == "/"

    def test_quit_with_garbage(self):
        """Plain 'quit' preceded by garbage — no slash, so just strips."""
        result = sanitize_input("  quit  ")
        assert result == "quit"


# ── fuzzy_match_command ─────────────────────────────────────────────

class TestFuzzyMatchCommand:
    """Verify that typos resolve to the correct command."""

    def test_exact_match(self):
        assert fuzzy_match_command("tasks") == "tasks"

    def test_typo_taks(self):
        assert fuzzy_match_command("taks") == "tasks"

    def test_typo_takss(self):
        assert fuzzy_match_command("takss") == "tasks"

    def test_typo_historry(self):
        assert fuzzy_match_command("historry") == "history"

    def test_typo_failuers(self):
        assert fuzzy_match_command("failuers") == "failures"

    def test_typo_satus(self):
        assert fuzzy_match_command("satus") == "status"

    def test_typo_hlep(self):
        assert fuzzy_match_command("hlep") == "help"

    def test_typo_quiit(self):
        assert fuzzy_match_command("quiit") == "quit"

    def test_no_match_gibberish(self):
        assert fuzzy_match_command("xyzzy") is None

    def test_no_match_empty(self):
        assert fuzzy_match_command("") is None

    def test_all_known_commands_match_exactly(self):
        for cmd in KNOWN_COMMANDS:
            assert fuzzy_match_command(cmd) == cmd


# ── quit/exit handling ──────────────────────────────────────────────

class TestQuitDetection:
    """Verify that quit variants are caught before orchestrator."""

    @pytest.mark.parametrize("raw", [
        "quit", "  quit  ", "QUIT", "/quit", "/exit", "exit", "q",
    ])
    def test_quit_variants_detected(self, raw):
        """All quit forms should be caught by the main loop's lower check."""
        cleaned = sanitize_input(raw)
        lower = cleaned.lower().strip()
        assert lower in ("quit", "exit", "q", "/quit", "/exit")

    def test_slash_quit_with_garbage(self):
        """GIN-polluted /quit should sanitize to /quit."""
        cleaned = sanitize_input("[GIN] 200 /quit")
        assert cleaned == "/quit"


# ── /task <id> integration (smoke test for command recognition) ─────

class TestTaskCommand:
    """Verify that /task <id> is handled by handle_command."""

    @pytest.mark.asyncio
    async def test_task_command_recognized(self):
        """handle_command should recognize '/task abc123' and return True.

        We use a minimal mock orchestrator with a None async_task_queue
        to avoid full startup.
        """
        from unittest.mock import MagicMock, PropertyMock
        from main import handle_command

        mock_orchestrator = MagicMock()
        # async_task_queue property returns None → "not available" path
        type(mock_orchestrator).async_task_queue = PropertyMock(return_value=None)

        result = await handle_command("/task abc123", mock_orchestrator)
        assert result is True
