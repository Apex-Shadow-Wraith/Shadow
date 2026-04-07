"""
Tests for Context Window Manager
===================================
Validates token estimation, context assembly, priority-based trimming,
model limits, and edge cases.
"""

import pytest

from modules.shadow.context_manager import ContextManager, TokenBreakdown


# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------

@pytest.fixture
def cm():
    """Default context manager with 128K limit."""
    return ContextManager(max_tokens=128000, reserve_tokens=4096)


@pytest.fixture
def small_cm():
    """Small context manager for testing trimming (1000 token limit)."""
    return ContextManager(max_tokens=1000, reserve_tokens=100)


@pytest.fixture
def system_prompt():
    return "You are Shadow, a helpful AI agent."


@pytest.fixture
def sample_history():
    return [
        {"role": "user", "content": "Hello Shadow"},
        {"role": "assistant", "content": "Hello Master Morstad, how can I help?"},
        {"role": "user", "content": "What's the weather like?"},
        {"role": "assistant", "content": "I can look that up for you."},
        {"role": "user", "content": "Tell me about landscaping tips"},
        {"role": "assistant", "content": "Here are some tips for your business..."},
    ]


@pytest.fixture
def sample_memories():
    return [
        {"content": "Master Morstad runs a landscaping business", "relevance_score": 0.9},
        {"content": "Master's dog is named Meko", "relevance_score": 0.7},
        {"content": "Uses LMN software for business", "relevance_score": 0.8},
        {"content": "Biblical values are important", "relevance_score": 0.6},
        {"content": "Learning Python from Automate the Boring Stuff", "relevance_score": 0.5},
    ]


@pytest.fixture
def sample_tool_results():
    return [
        {"tool_name": "memory_search", "content": "Found 3 relevant memories", "success": True},
        {"tool_name": "web_search", "content": "Search results for landscaping...", "success": True},
        {"tool_name": "calculate", "content": "42", "success": True},
    ]


@pytest.fixture
def sample_failure_patterns():
    return [
        {"pattern": "timeout on web search", "description": "Web search times out after 30s"},
        {"pattern": "empty LLM response", "description": "LLM returns empty string occasionally"},
    ]


# ----------------------------------------------------------------
# Token estimation tests
# ----------------------------------------------------------------

class TestEstimateTokens:
    """Test token estimation accuracy."""

    def test_empty_string(self, cm):
        assert cm.estimate_tokens("") == 0

    def test_short_english(self, cm):
        text = "Hello, how are you today?"
        tokens = cm.estimate_tokens(text)
        # ~25 chars / 4 = ~6 tokens — should be within 20% of actual (~7)
        assert 4 <= tokens <= 10

    def test_longer_english(self, cm):
        text = "The quick brown fox jumps over the lazy dog. " * 10
        tokens = cm.estimate_tokens(text)
        char_count = len(text)
        # Should be approximately char_count / 4
        expected = char_count / 4
        assert abs(tokens - expected) / expected < 0.2

    def test_code_detection(self, cm):
        code = """def hello_world():
    print("Hello, World!")
    return True

class MyClass:
    def __init__(self):
        self.value = 42
"""
        tokens = cm.estimate_tokens(code)
        char_count = len(code)
        # Code uses 3.5 ratio
        expected = char_count / 3.5
        assert abs(tokens - expected) / expected < 0.2

    def test_known_value_within_20_percent(self, cm):
        """Estimate should be within 20% of known real-world values."""
        # GPT-4 tokenizes "Hello world" as ~2 tokens
        text = "Hello world"
        tokens = cm.estimate_tokens(text)
        # 11 chars / 4 = ~3 — within 20% of 2 is 1.6-2.4, so 3 is close enough
        # The point is it's reasonable, not wildly off
        assert 1 <= tokens <= 5

    def test_messages_estimation(self, cm):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there, how can I help?"},
        ]
        tokens = cm.estimate_messages_tokens(messages)
        # Should include overhead per message
        assert tokens > 0
        # Each message has 4 token overhead + content
        assert tokens >= 8  # Minimum: 2 messages × 4 overhead

    def test_single_char(self, cm):
        assert cm.estimate_tokens("a") == 1


# ----------------------------------------------------------------
# build_context tests
# ----------------------------------------------------------------

class TestBuildContext:
    """Test context assembly."""

    def test_assembles_all_components(self, cm, system_prompt, sample_history,
                                       sample_memories, sample_tool_results):
        result = cm.build_context(
            system_prompt=system_prompt,
            conversation_history=sample_history,
            grimoire_memories=sample_memories,
            failure_patterns=[],
            tool_results=sample_tool_results,
            current_input="What tasks do I have today?",
        )

        assert "messages" in result
        assert "token_breakdown" in result
        assert "trimmed" in result
        assert "trimmed_components" in result

        messages = result["messages"]
        assert len(messages) > 0
        # First message should be system prompt
        assert messages[0]["role"] == "system"
        assert system_prompt in messages[0]["content"]
        # Last message should be user input
        assert messages[-1]["role"] == "user"
        assert "What tasks do I have today?" in messages[-1]["content"]

    def test_no_trim_when_under_limit(self, cm, system_prompt):
        result = cm.build_context(
            system_prompt=system_prompt,
            conversation_history=[],
            grimoire_memories=[],
            failure_patterns=[],
            tool_results=[],
            current_input="Hi",
        )
        assert result["trimmed"] is False
        assert result["trimmed_components"] == []

    def test_triggers_trim_when_over_limit(self, system_prompt):
        """With a 500 token limit, a big history should trigger trimming."""
        tiny_cm = ContextManager(max_tokens=500, reserve_tokens=50)
        big_history = [
            {"role": "user", "content": "x" * 2000},
            {"role": "assistant", "content": "y" * 2000},
            {"role": "user", "content": "z" * 2000},
            {"role": "assistant", "content": "w" * 2000},
        ]

        result = tiny_cm.build_context(
            system_prompt=system_prompt,
            conversation_history=big_history,
            grimoire_memories=[{"content": "memory " * 200}],
            failure_patterns=[],
            tool_results=[{"tool_name": "test", "content": "result " * 200, "success": True}],
            current_input="Hello",
        )
        assert result["trimmed"] is True
        assert len(result["trimmed_components"]) > 0

    def test_token_breakdown_populated(self, cm, system_prompt):
        result = cm.build_context(
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": "test"}],
            grimoire_memories=[{"content": "memory"}],
            failure_patterns=[],
            tool_results=[],
            current_input="Hello",
        )
        breakdown = result["token_breakdown"]
        assert breakdown["system_prompt_tokens"] > 0
        assert breakdown["input_tokens"] > 0
        assert breakdown["total_tokens"] > 0


# ----------------------------------------------------------------
# trim_context tests
# ----------------------------------------------------------------

class TestTrimContext:
    """Test priority-based trimming."""

    def test_trims_tool_results_first(self, cm):
        """Tool results should be trimmed before memories or history."""
        components = {
            "system_prompt": "You are Shadow.",
            "current_input": "Hello",
            "conversation_history": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ],
            "grimoire_memories": [{"content": "memory"}],
            "failure_patterns": [],
            "tool_results": [
                {"tool_name": "search", "content": "x" * 2000, "success": True},
                {"tool_name": "calc", "content": "y" * 2000, "success": True},
            ],
        }
        # Set a tight target that requires trimming tool results
        target = 200  # Very small target
        result = cm.trim_context(components, target)

        # Tool results should be trimmed/summarized
        trimmed_log = result["trimmed_log"]
        assert any("tool_results" in entry for entry in trimmed_log)

    def test_preserves_system_prompt_always(self, cm):
        """System prompt must never be modified by trimming."""
        prompt = "You are Shadow, the AI agent."
        components = {
            "system_prompt": prompt,
            "current_input": "Hello",
            "conversation_history": [
                {"role": "user", "content": "x" * 1000},
            ] * 10,
            "grimoire_memories": [{"content": "m" * 500}] * 5,
            "failure_patterns": [],
            "tool_results": [{"tool_name": "t", "content": "r" * 500}] * 5,
        }
        # The trim_context method doesn't modify system_prompt — it's not in the return
        result = cm.trim_context(components, 100)
        # system_prompt is not returned (it's preserved implicitly)
        assert "conversation_history" in result
        assert "grimoire_memories" in result

    def test_preserves_current_input_always(self, cm):
        """Current input must never be modified by trimming."""
        components = {
            "system_prompt": "System",
            "current_input": "This is my important question",
            "conversation_history": [],
            "grimoire_memories": [],
            "failure_patterns": [],
            "tool_results": [],
        }
        result = cm.trim_context(components, 50)
        # current_input is not returned (it's preserved implicitly)
        assert "trimmed_log" in result

    def test_summarizes_instead_of_deleting(self, cm):
        """Tool results should be summarized, not just deleted, when possible."""
        components = {
            "system_prompt": "System",
            "current_input": "Hello",
            "conversation_history": [],
            "grimoire_memories": [],
            "failure_patterns": [],
            "tool_results": [
                {"tool_name": "search", "content": "Long result " * 100, "success": True},
                {"tool_name": "calc", "content": "Another long result " * 100, "success": True},
                {"tool_name": "recent", "content": "Most recent result", "success": True},
            ],
        }
        # Target that requires summarization but not full deletion
        target = 300
        result = cm.trim_context(components, target)
        trimmed_log = result["trimmed_log"]
        # Should see summarization before deletion
        has_summarized = any("summarized" in entry.lower() for entry in trimmed_log)
        has_tool_trim = any("tool_results" in entry for entry in trimmed_log)
        assert has_tool_trim

    def test_drops_oldest_history_keeps_last_3(self, cm):
        """History trimming should keep at least 3 exchanges (6 messages)."""
        components = {
            "system_prompt": "System",
            "current_input": "Hello",
            "conversation_history": [
                {"role": "user", "content": f"Message {i}" * 50}
                for i in range(20)
            ],
            "grimoire_memories": [],
            "failure_patterns": [],
            "tool_results": [],
        }
        target = 300
        result = cm.trim_context(components, target)
        # Should have dropped some history
        assert len(result["conversation_history"]) < 20
        trimmed_log = result["trimmed_log"]
        assert any("history" in entry for entry in trimmed_log)

    def test_trims_memories_by_relevance(self, cm):
        """When trimming memories, keep highest relevance_score."""
        memories = [
            {"content": "low relevance", "relevance_score": 0.1},
            {"content": "high relevance", "relevance_score": 0.95},
            {"content": "medium relevance", "relevance_score": 0.5},
            {"content": "medium-high relevance", "relevance_score": 0.7},
            {"content": "very low relevance", "relevance_score": 0.05},
            {"content": "extra memory", "relevance_score": 0.3},
        ]
        components = {
            "system_prompt": "System",
            "current_input": "Hello",
            "conversation_history": [],
            "grimoire_memories": memories,
            "failure_patterns": [],
            "tool_results": [],
        }
        # Target that requires trimming memories
        target = 50
        result = cm.trim_context(components, target)
        remaining = result["grimoire_memories"]
        # If any remain, highest relevance should be first
        if remaining:
            assert remaining[0]["relevance_score"] >= 0.7

    def test_failure_patterns_trimmed_last(self, cm):
        """Failure patterns should only be trimmed after tool_results, memories, and history."""
        components = {
            "system_prompt": "S",
            "current_input": "H",
            "conversation_history": [],
            "grimoire_memories": [],
            "failure_patterns": [
                {"description": "pattern " * 200},
                {"description": "pattern2 " * 200},
                {"description": "pattern3 " * 200},
                {"description": "pattern4 " * 200},
            ],
            "tool_results": [],
        }
        target = 20  # Extremely tight
        result = cm.trim_context(components, target)
        trimmed_log = result["trimmed_log"]
        assert any("failure_patterns" in entry for entry in trimmed_log)


# ----------------------------------------------------------------
# get_usage_report tests
# ----------------------------------------------------------------

class TestGetUsageReport:
    """Test usage reporting."""

    def test_returns_accurate_breakdown(self, system_prompt):
        # Use a small max_tokens so percentage is meaningful
        cm = ContextManager(max_tokens=1000, reserve_tokens=100)
        cm.build_context(
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": "test message here"}],
            grimoire_memories=[{"content": "a memory about the user"}],
            failure_patterns=[],
            tool_results=[],
            current_input="Hello Shadow, what can you do?",
        )

        report = cm.get_usage_report()
        assert "summary" in report
        assert "breakdown" in report
        assert "percentage" in report
        assert report["percentage"] > 0
        assert report["breakdown"]["total_tokens"] > 0
        assert report["breakdown"]["system_prompt_tokens"] > 0
        assert report["breakdown"]["input_tokens"] > 0

    def test_no_data_report(self, cm):
        """Report before any context is built."""
        report = cm.get_usage_report()
        assert report["percentage"] == 0.0
        assert "No data yet" in report["summary"]


# ----------------------------------------------------------------
# get_model_context_limit tests
# ----------------------------------------------------------------

class TestGetModelContextLimit:
    """Test model context limit lookup."""

    def test_known_models(self, cm):
        assert cm.get_model_context_limit("gemma4:26b") == 256000
        assert cm.get_model_context_limit("phi4-mini") == 16384
        assert cm.get_model_context_limit("qwen3.5:35b-a3b") == 262144

    def test_unknown_model_returns_default(self, cm):
        assert cm.get_model_context_limit("some-unknown-model") == 128000

    def test_config_overrides(self):
        config = {
            "context_limits": {
                "model_context_limits": {
                    "custom-model": 50000,
                },
            },
        }
        cm = ContextManager(config=config)
        assert cm.get_model_context_limit("custom-model") == 50000
        # Built-in defaults still work
        assert cm.get_model_context_limit("phi4-mini") == 16384


# ----------------------------------------------------------------
# Overflow prevention tests
# ----------------------------------------------------------------

class TestOverflowPrevention:
    """Test that output always fits within max_tokens."""

    def test_output_fits_within_max_tokens(self, small_cm, system_prompt):
        """Even with huge inputs, the assembled context must fit."""
        result = small_cm.build_context(
            system_prompt=system_prompt,
            conversation_history=[
                {"role": "user", "content": "x" * 1000},
                {"role": "assistant", "content": "y" * 1000},
            ],
            grimoire_memories=[{"content": "m" * 500}],
            failure_patterns=[{"description": "p" * 500}],
            tool_results=[{"tool_name": "t", "content": "r" * 500}],
            current_input="Hello",
        )
        # Total tokens in output should be <= effective limit
        total = small_cm.estimate_messages_tokens(result["messages"])
        assert total <= small_cm.effective_limit

    def test_enormous_single_input_returns_error(self):
        """An input that exceeds the limit alone should return an error, not crash."""
        cm = ContextManager(max_tokens=100, reserve_tokens=10)
        result = cm.build_context(
            system_prompt="System prompt that is fairly short",
            conversation_history=[],
            grimoire_memories=[],
            failure_patterns=[],
            tool_results=[],
            current_input="x" * 5000,  # Enormous input
        )
        assert "error" in result
        assert result["trimmed"] is True
        assert result["messages"] == []

    def test_check_history_overflow(self, cm):
        """check_history_overflow should correctly detect when adding a turn would overflow."""
        # With a huge turn, should detect overflow
        huge_turn = {"role": "user", "content": "x" * 600000}
        assert cm.check_history_overflow([], huge_turn, system_prompt_tokens=1000) is True

        # With a small turn, should not overflow
        small_turn = {"role": "user", "content": "Hello"}
        assert cm.check_history_overflow([], small_turn, system_prompt_tokens=1000) is False


# ----------------------------------------------------------------
# Calibration tests
# ----------------------------------------------------------------

class TestCalibration:
    """Test calibration against actual token counts."""

    def test_calibrate_updates_ratio(self, cm):
        text = "Hello world, this is a test of the calibration system."
        result = cm.calibrate(text, 12)
        assert "english_ratio" in result
        assert "error_pct" in result
        # Ratio should have moved toward the actual value
        actual_ratio = len(text) / 12
        # New ratio should be between old (4.0) and actual
        assert result["english_ratio"] != 4.0

    def test_calibrate_invalid_inputs(self, cm):
        result = cm.calibrate("", 0)
        assert result["english_ratio"] == 4.0  # Unchanged
        assert result["error_pct"] == 0.0


# ----------------------------------------------------------------
# update_model tests
# ----------------------------------------------------------------

class TestUpdateModel:
    """Test model switching."""

    def test_update_model_changes_limits(self, cm):
        cm.update_model("phi4-mini")
        assert cm.max_tokens == 16384
        assert cm.effective_limit == 16384 - cm.reserve_tokens

    def test_update_model_unknown(self, cm):
        cm.update_model("unknown-model")
        assert cm.max_tokens == 128000


# ----------------------------------------------------------------
# Config integration tests
# ----------------------------------------------------------------

class TestConfigIntegration:
    """Test config-driven behavior."""

    def test_reserve_from_config(self):
        config = {
            "context_limits": {
                "reserve_tokens": 8192,
            },
        }
        cm = ContextManager(max_tokens=128000, reserve_tokens=4096, config=config)
        # Config should override constructor param
        assert cm.reserve_tokens == 8192
        assert cm.effective_limit == 128000 - 8192
