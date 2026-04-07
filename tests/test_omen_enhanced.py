"""Tests for Omen enhanced tools: patterns, failures, scaffolding, code scoring."""

import ast
from pathlib import Path

import pytest
import pytest_asyncio

from modules.omen.omen import Omen, VALID_PATTERN_CATEGORIES, SEED_PATTERNS


@pytest.fixture
def omen(tmp_path):
    """Create an Omen instance with DB in tmp_path."""
    return Omen(config={
        "db_path": str(tmp_path / "omen_test.db"),
        "project_root": str(tmp_path),
    })


@pytest_asyncio.fixture
async def online_omen(omen):
    """Create an initialized Omen instance."""
    await omen.initialize()
    yield omen
    await omen.shutdown()


# --- Lifecycle ---

class TestOmenEnhancedLifecycle:
    @pytest.mark.asyncio
    async def test_db_created(self, omen, tmp_path):
        await omen.initialize()
        assert (tmp_path / "omen_test.db").exists()
        await omen.shutdown()

    @pytest.mark.asyncio
    async def test_tables_exist(self, online_omen):
        cursor = online_omen._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert "omen_patterns" in tables
        assert "omen_failures" in tables

    @pytest.mark.asyncio
    async def test_26_tools(self, online_omen):
        tools = online_omen.get_tools()
        assert len(tools) == 26

    @pytest.mark.asyncio
    async def test_shutdown_closes_conn(self, omen):
        await omen.initialize()
        assert omen._conn is not None
        await omen.shutdown()
        assert omen._conn is None


# --- Pattern Store ---

class TestPatternStore:
    @pytest.mark.asyncio
    async def test_store_success(self, online_omen):
        result = await online_omen.execute("pattern_store", {
            "name": "test_pattern",
            "category": "error_handling",
            "description": "A test pattern",
            "code_template": "try:\n    {{operation}}\nexcept Exception:\n    pass\n",
        })
        assert result.success
        assert result.content["stored"] == "test_pattern"

    @pytest.mark.asyncio
    async def test_store_duplicate_fails(self, online_omen):
        params = {
            "name": "dupe",
            "category": "testing",
            "description": "Duplicate test",
            "code_template": "pass",
        }
        result1 = await online_omen.execute("pattern_store", params)
        assert result1.success
        result2 = await online_omen.execute("pattern_store", params)
        assert not result2.success
        assert "already exists" in result2.error

    @pytest.mark.asyncio
    async def test_store_invalid_category(self, online_omen):
        result = await online_omen.execute("pattern_store", {
            "name": "bad_cat",
            "category": "nonexistent_category",
            "description": "Bad category",
            "code_template": "pass",
        })
        assert not result.success
        assert "Invalid category" in result.error

    @pytest.mark.asyncio
    async def test_store_missing_fields(self, online_omen):
        result = await online_omen.execute("pattern_store", {
            "name": "incomplete",
        })
        assert not result.success
        assert "required" in result.error

    @pytest.mark.asyncio
    async def test_store_with_tags(self, online_omen):
        result = await online_omen.execute("pattern_store", {
            "name": "tagged_pattern",
            "category": "database",
            "description": "Pattern with tags",
            "code_template": "SELECT * FROM table",
            "tags": "sqlite,query,select",
        })
        assert result.success


# --- Pattern Search ---

class TestPatternSearch:
    @pytest.mark.asyncio
    async def test_search_by_category(self, online_omen):
        await online_omen.execute("pattern_store", {
            "name": "err1", "category": "error_handling",
            "description": "Error pattern", "code_template": "try: pass",
        })
        await online_omen.execute("pattern_store", {
            "name": "db1", "category": "database",
            "description": "DB pattern", "code_template": "SELECT 1",
        })
        result = await online_omen.execute("pattern_search", {"category": "error_handling"})
        assert result.success
        assert result.content["count"] == 1
        assert result.content["patterns"][0]["pattern_name"] == "err1"

    @pytest.mark.asyncio
    async def test_search_by_tags(self, online_omen):
        await online_omen.execute("pattern_store", {
            "name": "tagged1", "category": "testing",
            "description": "Tagged pattern", "code_template": "pass",
            "tags": "pytest,async",
        })
        result = await online_omen.execute("pattern_search", {"tags": "pytest"})
        assert result.success
        assert result.content["count"] == 1

    @pytest.mark.asyncio
    async def test_search_by_keyword(self, online_omen):
        await online_omen.execute("pattern_store", {
            "name": "special_handler", "category": "module_structure",
            "description": "Handle special cases", "code_template": "pass",
        })
        result = await online_omen.execute("pattern_search", {"keyword": "special"})
        assert result.success
        assert result.content["count"] == 1

    @pytest.mark.asyncio
    async def test_search_no_results(self, online_omen):
        result = await online_omen.execute("pattern_search", {"category": "database"})
        assert result.success
        assert result.content["count"] == 0


# --- Pattern Apply ---

class TestPatternApply:
    @pytest.mark.asyncio
    async def test_apply_increments_usage(self, online_omen):
        await online_omen.execute("pattern_store", {
            "name": "counter_test", "category": "testing",
            "description": "Usage counter test", "code_template": "pass",
        })
        result = await online_omen.execute("pattern_apply", {"name": "counter_test"})
        assert result.success
        assert result.content["usage_count"] == 1

        result2 = await online_omen.execute("pattern_apply", {"name": "counter_test"})
        assert result2.content["usage_count"] == 2

    @pytest.mark.asyncio
    async def test_apply_substitutions(self, online_omen):
        await online_omen.execute("pattern_store", {
            "name": "sub_test", "category": "error_handling",
            "description": "Substitution test",
            "code_template": "try:\n    {{operation}}\nexcept {{exception}}:\n    pass\n",
        })
        result = await online_omen.execute("pattern_apply", {
            "name": "sub_test",
            "substitutions": {"operation": "do_thing()", "exception": "ValueError"},
        })
        assert result.success
        assert "do_thing()" in result.content["rendered"]
        assert "ValueError" in result.content["rendered"]

    @pytest.mark.asyncio
    async def test_apply_not_found(self, online_omen):
        result = await online_omen.execute("pattern_apply", {"name": "nonexistent"})
        assert not result.success
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_apply_updates_last_used(self, online_omen):
        await online_omen.execute("pattern_store", {
            "name": "time_test", "category": "testing",
            "description": "Last used test", "code_template": "pass",
        })
        result = await online_omen.execute("pattern_apply", {"name": "time_test"})
        assert result.success
        assert result.content["last_used"] is not None


# --- Failure Log ---

class TestFailureLog:
    @pytest.mark.asyncio
    async def test_log_new_failure(self, online_omen):
        result = await online_omen.execute("failure_log", {
            "error_type": "ImportError",
            "error_message": "No module named 'foo'",
        })
        assert result.success
        assert result.content["status"] == "created"
        assert result.content["occurrences"] == 1
        assert len(result.content["failure_id"]) == 16

    @pytest.mark.asyncio
    async def test_log_duplicate_increments(self, online_omen):
        params = {
            "error_type": "ImportError",
            "error_message": "No module named 'bar'",
        }
        r1 = await online_omen.execute("failure_log", params)
        assert r1.content["status"] == "created"

        r2 = await online_omen.execute("failure_log", params)
        assert r2.content["status"] == "updated"
        assert r2.content["occurrences"] == 2

    @pytest.mark.asyncio
    async def test_log_missing_fields(self, online_omen):
        result = await online_omen.execute("failure_log", {
            "error_type": "SomeError",
        })
        assert not result.success
        assert "required" in result.error

    @pytest.mark.asyncio
    async def test_log_consistent_id(self, online_omen):
        """Same error_type + error_message should produce same failure_id."""
        params = {"error_type": "TypeError", "error_message": "int + str"}
        r1 = await online_omen.execute("failure_log", params)
        r2 = await online_omen.execute("failure_log", params)
        assert r1.content["failure_id"] == r2.content["failure_id"]


# --- Failure Search ---

class TestFailureSearch:
    @pytest.mark.asyncio
    async def test_search_by_type(self, online_omen):
        await online_omen.execute("failure_log", {
            "error_type": "ValueError",
            "error_message": "invalid literal",
        })
        await online_omen.execute("failure_log", {
            "error_type": "KeyError",
            "error_message": "missing key 'x'",
        })
        result = await online_omen.execute("failure_search", {"error_type": "ValueError"})
        assert result.success
        assert result.content["count"] == 1

    @pytest.mark.asyncio
    async def test_search_by_keyword(self, online_omen):
        await online_omen.execute("failure_log", {
            "error_type": "RuntimeError",
            "error_message": "database connection timeout",
        })
        result = await online_omen.execute("failure_search", {"keyword": "timeout"})
        assert result.success
        assert result.content["count"] == 1

    @pytest.mark.asyncio
    async def test_search_empty(self, online_omen):
        result = await online_omen.execute("failure_search", {"error_type": "NothingError"})
        assert result.success
        assert result.content["count"] == 0


# --- Failure Stats ---

class TestFailureStats:
    @pytest.mark.asyncio
    async def test_stats_empty_db(self, online_omen):
        result = await online_omen.execute("failure_stats", {})
        assert result.success
        assert result.content["total_failures"] == 0
        assert result.content["top_10"] == []
        assert result.content["recurring_count"] == 0

    @pytest.mark.asyncio
    async def test_stats_with_data(self, online_omen):
        await online_omen.execute("failure_log", {
            "error_type": "ImportError",
            "error_message": "no module 'x'",
            "fix_applied": "pip install x",
            "fix_worked": 1,
        })
        await online_omen.execute("failure_log", {
            "error_type": "SyntaxError",
            "error_message": "unexpected indent",
        })
        result = await online_omen.execute("failure_stats", {})
        assert result.success
        assert result.content["total_failures"] == 2
        assert len(result.content["top_10"]) == 2
        assert result.content["fix_success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_stats_recurring(self, online_omen):
        params = {"error_type": "Recurring", "error_message": "keeps happening"}
        for _ in range(5):
            await online_omen.execute("failure_log", params)
        result = await online_omen.execute("failure_stats", {})
        assert result.content["recurring_count"] == 1


# --- Scaffold Module ---

class TestScaffoldModule:
    @pytest.mark.asyncio
    async def test_generates_all_code(self, online_omen):
        result = await online_omen.execute("scaffold_module", {
            "module_name": "Phoenix",
            "description": "Backup and recovery system",
            "tools": ["backup_create", "backup_restore"],
        })
        assert result.success
        assert "module_code" in result.content
        assert "test_code" in result.content
        assert "init_code" in result.content

    @pytest.mark.asyncio
    async def test_includes_tools(self, online_omen):
        result = await online_omen.execute("scaffold_module", {
            "module_name": "Test",
            "description": "Test module",
            "tools": ["tool_a", "tool_b"],
        })
        assert result.success
        assert "tool_a" in result.content["module_code"]
        assert "tool_b" in result.content["module_code"]

    @pytest.mark.asyncio
    async def test_valid_python(self, online_omen):
        result = await online_omen.execute("scaffold_module", {
            "module_name": "Valid",
            "description": "Valid module",
            "tools": ["do_thing"],
        })
        assert result.success
        # Should parse without syntax errors
        ast.parse(result.content["module_code"])

    @pytest.mark.asyncio
    async def test_missing_params(self, online_omen):
        result = await online_omen.execute("scaffold_module", {
            "module_name": "Incomplete",
        })
        assert not result.success
        assert "required" in result.error


# --- Scaffold Test ---

class TestScaffoldTest:
    @pytest.mark.asyncio
    async def test_generates_code(self, online_omen):
        result = await online_omen.execute("scaffold_test", {
            "module_name": "Omen",
        })
        assert result.success
        assert "test_code" in result.content
        assert len(result.content["test_code"]) > 100

    @pytest.mark.asyncio
    async def test_covers_tools(self, online_omen):
        result = await online_omen.execute("scaffold_test", {
            "module_name": "Omen",
        })
        assert result.success
        # Omen has 26 tools, scaffold_test should cover them
        assert len(result.content["tools_covered"]) == 26

    @pytest.mark.asyncio
    async def test_missing_module_name(self, online_omen):
        result = await online_omen.execute("scaffold_test", {})
        assert not result.success
        assert "required" in result.error


# --- Code Score ---

class TestCodeScore:
    @pytest.mark.asyncio
    async def test_well_scored_file(self, online_omen, tmp_path):
        good_code = tmp_path / "good.py"
        good_code.write_text(
            'import os\n'
            'import sys\n'
            '\n'
            'def greet(name: str) -> str:\n'
            '    """Greet someone by name."""\n'
            '    try:\n'
            '        return f"Hello, {name}"\n'
            '    except Exception as e:\n'
            '        raise ValueError(str(e))\n',
            encoding="utf-8",
        )
        result = await online_omen.execute("code_score", {"file_path": str(good_code)})
        assert result.success
        assert result.content["score"] >= 50
        assert "breakdown" in result.content

    @pytest.mark.asyncio
    async def test_poorly_scored_file(self, online_omen, tmp_path):
        bad_code = tmp_path / "bad.py"
        bad_code.write_text(
            'def f(x):\n'
            '    try:\n'
            '        return x + 1\n'
            '    except:\n'
            '        pass\n',
            encoding="utf-8",
        )
        result = await online_omen.execute("code_score", {"file_path": str(bad_code)})
        assert result.success
        # Should score lower due to missing docstring, no type hints, bare except
        assert result.content["score"] < 80
        assert result.content["breakdown"]["no_bare_excepts"] < 10

    @pytest.mark.asyncio
    async def test_syntax_error(self, online_omen, tmp_path):
        bad_file = tmp_path / "broken.py"
        bad_file.write_text("def f(\n", encoding="utf-8")
        result = await online_omen.execute("code_score", {"file_path": str(bad_file)})
        assert not result.success
        assert "Syntax error" in result.error

    @pytest.mark.asyncio
    async def test_file_not_found(self, online_omen):
        result = await online_omen.execute("code_score", {"file_path": "/nonexistent.py"})
        assert not result.success
        assert "not found" in result.error.lower()


# --- Seed Patterns ---

class TestSeedPatterns:
    @pytest.mark.asyncio
    async def test_populates_db(self, online_omen):
        result = await online_omen.execute("seed_patterns", {})
        assert result.success
        assert result.content["status"] == "seeded"
        assert result.content["patterns_added"] == len(SEED_PATTERNS)

    @pytest.mark.asyncio
    async def test_idempotent(self, online_omen):
        r1 = await online_omen.execute("seed_patterns", {})
        assert r1.content["status"] == "seeded"

        r2 = await online_omen.execute("seed_patterns", {})
        assert r2.content["status"] == "already_seeded"

    @pytest.mark.asyncio
    async def test_correct_count(self, online_omen):
        await online_omen.execute("seed_patterns", {})
        count = online_omen._conn.execute(
            "SELECT COUNT(*) as c FROM omen_patterns"
        ).fetchone()["c"]
        assert count == len(SEED_PATTERNS)
