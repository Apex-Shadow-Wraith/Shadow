"""
Omen — Shadow's Code Brain
============================
Development, testing, teaching, and self-building.

Design Principle: Omen has a dual mandate — build Shadow AND teach
the creator. When the user says 'just do it', Omen writes fast and
explains after. When the user is learning, Omen slows down.

Phase 1: Subprocess-based code execution, linting, testing, and git
operations. All execution sandboxed with timeouts.

Phase 2: Pattern recognition, failure learning, code generation
scaffolding, and quality scoring. SQLite-backed persistence.
"""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import logging
import re
import sqlite3
import string
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.base import BaseModule, ModuleStatus, ToolResult

logger = logging.getLogger("shadow.omen")

# Valid categories for code patterns
VALID_PATTERN_CATEGORIES = {
    "error_handling",
    "data_validation",
    "api_integration",
    "testing",
    "file_io",
    "database",
    "async_pattern",
    "module_structure",
}

# Seed patterns extracted from Shadow's codebase
SEED_PATTERNS = [
    {
        "name": "base_module_init",
        "category": "module_structure",
        "language": "python",
        "description": "Standard BaseModule __init__ with config, db_path, and conn",
        "code_template": (
            "def __init__(self, config: dict[str, Any] | None = None) -> None:\n"
            "    super().__init__(name=\"{{module_name}}\", description=\"{{description}}\")\n"
            "    self._config = config or {}\n"
            "    self._db_path = Path(self._config.get(\"db_path\", \"{{db_path}}\"))\n"
            "    self._conn: sqlite3.Connection | None = None\n"
        ),
        "tags": "shadow,basemodule,init",
    },
    {
        "name": "db_initialize",
        "category": "database",
        "language": "python",
        "description": "Standard async initialize with SQLite connection and table creation",
        "code_template": (
            "async def initialize(self) -> None:\n"
            "    self.status = ModuleStatus.STARTING\n"
            "    try:\n"
            "        self._db_path.parent.mkdir(parents=True, exist_ok=True)\n"
            "        self._conn = sqlite3.connect(str(self._db_path))\n"
            "        self._conn.row_factory = sqlite3.Row\n"
            "        self._create_tables()\n"
            "        self.status = ModuleStatus.ONLINE\n"
            "    except Exception as e:\n"
            "        self.status = ModuleStatus.ERROR\n"
            "        raise\n"
        ),
        "tags": "shadow,database,initialize",
    },
    {
        "name": "db_shutdown",
        "category": "database",
        "language": "python",
        "description": "Standard shutdown closing SQLite connection",
        "code_template": (
            "async def shutdown(self) -> None:\n"
            "    if self._conn:\n"
            "        self._conn.close()\n"
            "        self._conn = None\n"
            "    self.status = ModuleStatus.OFFLINE\n"
        ),
        "tags": "shadow,database,shutdown",
    },
    {
        "name": "tool_handler_dispatch",
        "category": "module_structure",
        "language": "python",
        "description": "Standard execute() with handler dict dispatch pattern",
        "code_template": (
            "async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:\n"
            "    start = time.time()\n"
            "    try:\n"
            "        handlers = {\n"
            "            \"{{tool_name}}\": self._{{handler_name}},\n"
            "        }\n"
            "        handler = handlers.get(tool_name)\n"
            "        if handler is None:\n"
            "            return ToolResult(success=False, content=None, tool_name=tool_name,\n"
            "                module=self.name, error=f\"Unknown tool: {tool_name}\")\n"
            "        result = handler(params)\n"
            "        result.execution_time_ms = (time.time() - start) * 1000\n"
            "        self._record_call(result.success)\n"
            "        return result\n"
            "    except Exception as e:\n"
            "        return ToolResult(success=False, content=None, tool_name=tool_name,\n"
            "            module=self.name, error=str(e))\n"
        ),
        "tags": "shadow,dispatch,execute",
    },
    {
        "name": "toolresult_success",
        "category": "module_structure",
        "language": "python",
        "description": "Return a successful ToolResult",
        "code_template": (
            "return ToolResult(\n"
            "    success=True,\n"
            "    content={{content}},\n"
            "    tool_name=\"{{tool_name}}\",\n"
            "    module=self.name,\n"
            ")\n"
        ),
        "tags": "shadow,toolresult",
    },
    {
        "name": "toolresult_error",
        "category": "error_handling",
        "language": "python",
        "description": "Return a failed ToolResult with error message",
        "code_template": (
            "return ToolResult(\n"
            "    success=False, content=None,\n"
            "    tool_name=\"{{tool_name}}\",\n"
            "    module=self.name,\n"
            "    error=\"{{error_message}}\",\n"
            ")\n"
        ),
        "tags": "shadow,toolresult,error",
    },
    {
        "name": "try_except_log",
        "category": "error_handling",
        "language": "python",
        "description": "Standard try/except with logging and ToolResult error return",
        "code_template": (
            "try:\n"
            "    {{operation}}\n"
            "except Exception as e:\n"
            "    logger.error(\"{{context}}: %s\", e)\n"
            "    return ToolResult(success=False, content=None,\n"
            "        tool_name=\"{{tool_name}}\", module=self.name, error=str(e))\n"
        ),
        "tags": "shadow,error,logging",
    },
    {
        "name": "param_validation",
        "category": "data_validation",
        "language": "python",
        "description": "Validate required parameters with early return",
        "code_template": (
            "{{param}} = params.get(\"{{param}}\", \"\")\n"
            "if not {{param}}:\n"
            "    return ToolResult(success=False, content=None,\n"
            "        tool_name=\"{{tool_name}}\", module=self.name,\n"
            "        error=\"{{param}} is required\")\n"
        ),
        "tags": "shadow,validation,params",
    },
    {
        "name": "sqlite_upsert",
        "category": "database",
        "language": "python",
        "description": "SQLite INSERT OR UPDATE pattern with conflict handling",
        "code_template": (
            "self._conn.execute(\"\"\"\n"
            "    INSERT INTO {{table}} ({{columns}})\n"
            "    VALUES ({{placeholders}})\n"
            "    ON CONFLICT({{conflict_col}}) DO UPDATE SET\n"
            "        {{update_clause}}\n"
            "\"\"\", ({{values}},))\n"
            "self._conn.commit()\n"
        ),
        "tags": "sqlite,upsert,database",
    },
    {
        "name": "sqlite_aggregate",
        "category": "database",
        "language": "python",
        "description": "SQLite aggregate query with COUNT, AVG, GROUP BY",
        "code_template": (
            "cursor = self._conn.execute(\"\"\"\n"
            "    SELECT {{group_col}}, COUNT(*) as count, AVG({{avg_col}}) as avg_val\n"
            "    FROM {{table}}\n"
            "    GROUP BY {{group_col}}\n"
            "    ORDER BY count DESC\n"
            "    LIMIT {{limit}}\n"
            "\"\"\")\n"
            "rows = [dict(row) for row in cursor.fetchall()]\n"
        ),
        "tags": "sqlite,aggregate,stats",
    },
    {
        "name": "pytest_fixture",
        "category": "testing",
        "language": "python",
        "description": "Standard pytest fixture with tmp_path for module testing",
        "code_template": (
            "@pytest.fixture\n"
            "def {{module_name}}(tmp_path):\n"
            "    return {{ModuleClass}}(config={\"db_path\": str(tmp_path / \"test.db\")})\n"
        ),
        "tags": "pytest,fixture,testing",
    },
    {
        "name": "async_test",
        "category": "testing",
        "language": "python",
        "description": "Standard async test method for module tool execution",
        "code_template": (
            "@pytest.mark.asyncio\n"
            "async def test_{{test_name}}(self, {{fixture}}):\n"
            "    result = await {{fixture}}.execute(\"{{tool_name}}\", {{params}})\n"
            "    assert result.success\n"
            "    assert result.content is not None\n"
        ),
        "tags": "pytest,async,testing",
    },
    {
        "name": "file_read_safe",
        "category": "file_io",
        "language": "python",
        "description": "Safe file reading with encoding and error handling",
        "code_template": (
            "path = Path({{file_path}})\n"
            "if not path.exists():\n"
            "    return ToolResult(success=False, content=None,\n"
            "        tool_name=\"{{tool_name}}\", module=self.name,\n"
            "        error=f\"File not found: {{{file_path}}}\")\n"
            "try:\n"
            "    content = path.read_text(encoding=\"utf-8\")\n"
            "except (OSError, UnicodeDecodeError) as e:\n"
            "    return ToolResult(success=False, content=None,\n"
            "        tool_name=\"{{tool_name}}\", module=self.name,\n"
            "        error=f\"Cannot read file: {e}\")\n"
        ),
        "tags": "file,read,pathlib",
    },
    {
        "name": "subprocess_timeout",
        "category": "async_pattern",
        "language": "python",
        "description": "Subprocess execution with timeout and capture",
        "code_template": (
            "try:\n"
            "    result = subprocess.run(\n"
            "        [{{command}}],\n"
            "        capture_output=True, text=True,\n"
            "        timeout={{timeout}},\n"
            "        cwd=str(self._project_root),\n"
            "    )\n"
            "except subprocess.TimeoutExpired:\n"
            "    return ToolResult(success=False, content=None,\n"
            "        tool_name=\"{{tool_name}}\", module=self.name,\n"
            "        error=\"Execution timed out\")\n"
        ),
        "tags": "subprocess,timeout,execution",
    },
    {
        "name": "tool_definition",
        "category": "module_structure",
        "language": "python",
        "description": "Standard tool definition dict for get_tools()",
        "code_template": (
            "{\n"
            "    \"name\": \"{{tool_name}}\",\n"
            "    \"description\": \"{{description}}\",\n"
            "    \"parameters\": {{{parameters}}},\n"
            "    \"permission_level\": \"autonomous\",\n"
            "}\n"
        ),
        "tags": "shadow,tool,definition",
    },
    {
        "name": "api_call_pattern",
        "category": "api_integration",
        "language": "python",
        "description": "Standard API call with error handling and cost tracking",
        "code_template": (
            "try:\n"
            "    response = await self._client.{{method}}(\n"
            "        model=self._model,\n"
            "        messages=[{\"role\": \"user\", \"content\": {{prompt}}}],\n"
            "        max_tokens={{max_tokens}},\n"
            "    )\n"
            "    self._track_cost(response.usage)\n"
            "except Exception as e:\n"
            "    logger.error(\"API call failed: %s\", e)\n"
            "    return ToolResult(success=False, content=None,\n"
            "        tool_name=\"{{tool_name}}\", module=self.name, error=str(e))\n"
        ),
        "tags": "api,anthropic,openai",
    },
]

# Templates for scaffold tools — using string.Template ($placeholder syntax)
# to avoid brace conflicts with generated Python code.
# Triple-quote docstrings in templates use 3-single-quote (''') to avoid
# conflict with the triple-double-quote wrapping the template string.

MODULE_TEMPLATE = string.Template(
    '"""\n'
    "$module_name — $description\n"
    '"""\n'
    "\n"
    "import logging\n"
    "import time\n"
    "from pathlib import Path\n"
    "from typing import Any\n"
    "\n"
    "from modules.base import BaseModule, ModuleStatus, ToolResult\n"
    "\n"
    'logger = logging.getLogger("shadow.$module_lower")\n'
    "\n"
    "\n"
    "class $module_class(BaseModule):\n"
    '    """$description."""\n'
    "\n"
    "    def __init__(self, config: dict[str, Any] | None = None) -> None:\n"
    '        """Initialize $module_name."""\n'
    '        super().__init__(name="$module_lower", description="$description")\n'
    "        self._config = config or {}\n"
    "\n"
    "    async def initialize(self) -> None:\n"
    '        """Start $module_name."""\n'
    "        self.status = ModuleStatus.ONLINE\n"
    '        logger.info("$module_name online.")\n'
    "\n"
    "    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:\n"
    '        """Execute a $module_name tool."""\n'
    "        start = time.time()\n"
    "        try:\n"
    "            handlers = {\n"
    "$handler_entries"
    "            }\n"
    "            handler = handlers.get(tool_name)\n"
    "            if handler is None:\n"
    "                return ToolResult(success=False, content=None, tool_name=tool_name,\n"
    '                    module=self.name, error=f"Unknown tool: {tool_name}")\n'
    "            result = handler(params)\n"
    "            result.execution_time_ms = (time.time() - start) * 1000\n"
    "            self._record_call(result.success)\n"
    "            return result\n"
    "        except Exception as e:\n"
    '            logger.error("$module_name tool \'%s\' failed: %s", tool_name, e)\n'
    "            return ToolResult(success=False, content=None, tool_name=tool_name,\n"
    "                module=self.name, error=str(e),\n"
    "                execution_time_ms=(time.time() - start) * 1000)\n"
    "\n"
    "    async def shutdown(self) -> None:\n"
    '        """Shut down $module_name."""\n'
    "        self.status = ModuleStatus.OFFLINE\n"
    '        logger.info("$module_name offline.")\n'
    "\n"
    "    def get_tools(self) -> list[dict[str, Any]]:\n"
    '        """Return $module_name tool definitions."""\n'
    "        return [\n"
    "$tool_definitions"
    "        ]\n"
    "\n"
    "$tool_stubs"
)

TEST_TEMPLATE = string.Template(
    '"""Tests for $module_name."""\n'
    "\n"
    "import pytest\n"
    "import pytest_asyncio\n"
    "\n"
    "from modules.$module_lower.$module_lower import $module_class\n"
    "\n"
    "\n"
    "@pytest.fixture\n"
    "def $fixture_name(tmp_path):\n"
    '    """Create a $module_name instance for testing."""\n'
    '    return $module_class(config={"db_path": str(tmp_path / "test.db")})\n'
    "\n"
    "\n"
    "@pytest_asyncio.fixture\n"
    "async def online_$fixture_name($fixture_name):\n"
    '    """Create an initialized $module_name instance."""\n'
    "    await $fixture_name.initialize()\n"
    "    yield $fixture_name\n"
    "    await $fixture_name.shutdown()\n"
    "\n"
    "\n"
    "$test_classes\n"
)

INIT_TEMPLATE = string.Template(
    '"""$module_name module."""\n'
    "\n"
    "from modules.$module_lower.$module_lower import $module_class\n"
    "\n"
    '__all__ = ["$module_class"]\n'
)


class Omen(BaseModule):
    """Shadow's code brain. Writes, tests, debugs, and teaches.

    All code execution happens in subprocesses with timeouts.
    Git commit/push require approval. Everything else is autonomous.
    """

    DEFAULT_TIMEOUT = 30  # seconds
    MAX_TIMEOUT = 120
    MAX_GLOB_RESULTS = 500
    MAX_FILE_SIZE = 100 * 1024  # 100KB
    ALWAYS_EXCLUDE = {"__pycache__", ".git", "node_modules", "shadow_env", "venv"}
    BINARY_EXTENSIONS = {".bin", ".db", ".sqlite3", ".png", ".jpg", ".whl", ".egg", ".pickle"}
    PROTECTED_PATHS = {"config", ".git", ".env"}

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize Omen.

        Args:
            config: Module configuration.
        """
        super().__init__(
            name="omen",
            description="Code brain — development, testing, teaching",
        )
        self._config = config or {}
        self._teaching_mode = self._config.get("teaching_mode", False)
        self._project_root = Path(self._config.get("project_root", ".")).resolve()
        self._python = sys.executable
        self._db_path = Path(self._config.get("db_path", "data/omen_code.db"))
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        """Start Omen. Create DB and tables."""
        self.status = ModuleStatus.STARTING
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._create_tables()
            self.status = ModuleStatus.ONLINE
            logger.info(
                "Omen online. Teaching mode: %s. Python: %s. DB: %s",
                self._teaching_mode, self._python, self._db_path,
            )
        except Exception as e:
            self.status = ModuleStatus.ERROR
            logger.error("Omen failed to initialize: %s", e)
            raise

    def _create_tables(self) -> None:
        """Create omen_patterns and omen_failures tables."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS omen_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                language TEXT DEFAULT 'python',
                description TEXT NOT NULL,
                code_template TEXT NOT NULL,
                usage_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 1.0,
                last_used TEXT,
                created_at TEXT NOT NULL,
                tags TEXT
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pattern_category
            ON omen_patterns(category)
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS omen_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                failure_id TEXT NOT NULL UNIQUE,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                file_path TEXT,
                code_context TEXT,
                fix_applied TEXT,
                fix_worked INTEGER,
                occurrences INTEGER DEFAULT 1,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                prevention_rule TEXT
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_failure_type
            ON omen_failures(error_type)
        """)
        self._conn.commit()

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute an Omen tool.

        Args:
            tool_name: Which tool to invoke.
            params: Tool-specific parameters.

        Returns:
            ToolResult with success/failure and content.
        """
        start = time.time()
        try:
            handlers = {
                "code_execute": self._code_execute,
                "code_lint": self._code_lint,
                "code_test": self._code_test,
                "code_review": self._code_review,
                "git_status": self._git_status,
                "git_commit": self._git_commit,
                "dependency_check": self._dependency_check,
                "code_glob": self._code_glob,
                "code_grep": self._code_grep,
                "code_edit": self._code_edit,
                "code_read": self._code_read,
                "pattern_store": self._pattern_store,
                "pattern_search": self._pattern_search,
                "pattern_apply": self._pattern_apply,
                "failure_log": self._failure_log,
                "failure_search": self._failure_search,
                "failure_stats": self._failure_stats,
                "scaffold_module": self._scaffold_module,
                "scaffold_test": self._scaffold_test,
                "code_score": self._code_score,
                "seed_patterns": self._seed_patterns,
            }

            handler = handlers.get(tool_name)
            if handler is None:
                result = ToolResult(
                    success=False, content=None, tool_name=tool_name,
                    module=self.name, error=f"Unknown tool: {tool_name}",
                )
            else:
                result = handler(params)

            result.execution_time_ms = (time.time() - start) * 1000
            self._record_call(result.success)
            return result

        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._record_call(False)
            logger.error("Omen tool '%s' failed: %s", tool_name, e)
            return ToolResult(
                success=False, content=None, tool_name=tool_name,
                module=self.name, error=str(e), execution_time_ms=elapsed,
            )

    async def shutdown(self) -> None:
        """Shut down Omen."""
        if self._conn:
            self._conn.close()
            self._conn = None
        self.status = ModuleStatus.OFFLINE
        logger.info("Omen offline.")

    def get_tools(self) -> list[dict[str, Any]]:
        """Return Omen's tool definitions."""
        return [
            {
                "name": "code_execute",
                "description": "Run code in sandboxed subprocess with timeout",
                "parameters": {"code": "str", "timeout": "int"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_lint",
                "description": "Check code for syntax errors and style violations",
                "parameters": {"file_path": "str", "code": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_test",
                "description": "Run test suite against code",
                "parameters": {"test_path": "str", "timeout": "int"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_review",
                "description": "Review code for issues (stub — needs LLM in Phase 2+)",
                "parameters": {"code": "str", "file_path": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "git_status",
                "description": "Check git repository state",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "git_commit",
                "description": "Commit changes to repository",
                "parameters": {"message": "str", "files": "list"},
                "permission_level": "approval_required",
            },
            {
                "name": "dependency_check",
                "description": "Scan for outdated or vulnerable dependencies",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "code_glob",
                "description": "Find files matching a glob pattern",
                "parameters": {"pattern": "str", "root_dir": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_grep",
                "description": "Search for text/regex in code files",
                "parameters": {
                    "pattern": "str",
                    "file_glob": "str",
                    "root_dir": "str",
                    "max_results": "int",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "code_edit",
                "description": "Apply a find-and-replace edit to a file",
                "parameters": {"file_path": "str", "old_text": "str", "new_text": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_read",
                "description": "Read a file with line numbers",
                "parameters": {"file_path": "str", "start_line": "int", "end_line": "int"},
                "permission_level": "autonomous",
            },
            # --- Enhanced tools (Phase 2) ---
            {
                "name": "pattern_store",
                "description": "Store a reusable code pattern in the pattern database",
                "parameters": {
                    "name": "str",
                    "category": "str",
                    "description": "str",
                    "code_template": "str",
                    "language": "str",
                    "tags": "str",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "pattern_search",
                "description": "Search stored code patterns by category, tags, or keyword",
                "parameters": {"category": "str", "tags": "str", "keyword": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "pattern_apply",
                "description": "Apply a stored pattern with placeholder substitutions",
                "parameters": {"name": "str", "substitutions": "dict"},
                "permission_level": "autonomous",
            },
            {
                "name": "failure_log",
                "description": "Log a code failure for learning and prevention",
                "parameters": {
                    "error_type": "str",
                    "error_message": "str",
                    "file_path": "str",
                    "code_context": "str",
                    "fix_applied": "str",
                    "fix_worked": "bool",
                    "prevention_rule": "str",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "failure_search",
                "description": "Search logged failures by type or keyword",
                "parameters": {"error_type": "str", "keyword": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "failure_stats",
                "description": "Get aggregate statistics on logged failures",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "scaffold_module",
                "description": "Generate boilerplate code for a new Shadow module",
                "parameters": {
                    "module_name": "str",
                    "description": "str",
                    "tools": "list",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "scaffold_test",
                "description": "Generate test skeleton for a Shadow module",
                "parameters": {"module_name": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_score",
                "description": "Score a Python file on code quality (0-100)",
                "parameters": {"file_path": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "seed_patterns",
                "description": "Populate pattern database with Shadow codebase patterns",
                "parameters": {},
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _code_execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute Python code in a sandboxed subprocess.

        Args:
            params: 'code' (str), optional 'timeout' (int seconds).
        """
        code = params.get("code", "")
        if not code:
            return ToolResult(
                success=False, content=None, tool_name="code_execute",
                module=self.name, error="Code is required",
            )

        timeout = min(params.get("timeout", self.DEFAULT_TIMEOUT), self.MAX_TIMEOUT)

        try:
            result = subprocess.run(
                [self._python, "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._project_root),
            )

            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "success": result.returncode == 0,
                "timeout_seconds": timeout,
            }

            if self._teaching_mode and result.returncode != 0:
                output["teaching_note"] = (
                    "The code failed. Check stderr for the error message. "
                    "Common causes: syntax errors, missing imports, type errors."
                )

            return ToolResult(
                success=result.returncode == 0,
                content=output,
                tool_name="code_execute",
                module=self.name,
                error=result.stderr[:500] if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="code_execute",
                module=self.name,
                error=f"Execution timed out after {timeout} seconds",
            )

    def _code_lint(self, params: dict[str, Any]) -> ToolResult:
        """Check code for syntax errors using py_compile.

        Args:
            params: 'code' (str) or 'file_path' (str).
        """
        code = params.get("code", "")
        file_path = params.get("file_path", "")

        if file_path:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(
                    success=False, content=None, tool_name="code_lint",
                    module=self.name, error=f"File not found: {file_path}",
                )
            target = str(path)
        elif code:
            # Write code to temp file for compilation check
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            )
            tmp.write(code)
            tmp.close()
            target = tmp.name
        else:
            return ToolResult(
                success=False, content=None, tool_name="code_lint",
                module=self.name, error="Either 'code' or 'file_path' is required",
            )

        try:
            result = subprocess.run(
                [self._python, "-m", "py_compile", target],
                capture_output=True,
                text=True,
                timeout=10,
            )

            lint_result = {
                "file": target,
                "syntax_valid": result.returncode == 0,
                "errors": result.stderr.strip() if result.stderr else None,
            }

            return ToolResult(
                success=result.returncode == 0,
                content=lint_result,
                tool_name="code_lint",
                module=self.name,
                error=result.stderr[:500] if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="code_lint",
                module=self.name, error="Lint check timed out",
            )
        finally:
            if code and not file_path:
                Path(target).unlink(missing_ok=True)

    def _code_test(self, params: dict[str, Any]) -> ToolResult:
        """Run pytest on a test file or directory.

        Args:
            params: 'test_path' (str), optional 'timeout' (int).
        """
        test_path = params.get("test_path", "tests/")
        timeout = min(params.get("timeout", 60), self.MAX_TIMEOUT)

        path = Path(test_path)
        if not path.exists():
            return ToolResult(
                success=False, content=None, tool_name="code_test",
                module=self.name, error=f"Test path not found: {test_path}",
            )

        try:
            result = subprocess.run(
                [self._python, "-m", "pytest", str(path), "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._project_root),
            )

            return ToolResult(
                success=result.returncode == 0,
                content={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                    "passed": result.returncode == 0,
                    "test_path": str(path),
                },
                tool_name="code_test",
                module=self.name,
                error="Tests failed" if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="code_test",
                module=self.name,
                error=f"Tests timed out after {timeout} seconds",
            )

    def _code_review(self, params: dict[str, Any]) -> ToolResult:
        """Review code for issues.

        Phase 1: Stub. Returns structural info only.
        Phase 2+: LLM-powered review.

        Args:
            params: 'code' or 'file_path'.
        """
        code = params.get("code", "")
        file_path = params.get("file_path", "")

        if file_path:
            path = Path(file_path)
            if path.exists():
                code = path.read_text(encoding="utf-8")
            else:
                return ToolResult(
                    success=False, content=None, tool_name="code_review",
                    module=self.name, error=f"File not found: {file_path}",
                )

        if not code:
            return ToolResult(
                success=False, content=None, tool_name="code_review",
                module=self.name, error="Code or file_path is required",
            )

        # Basic structural analysis
        lines = code.split("\n")
        review = {
            "line_count": len(lines),
            "has_docstrings": '"""' in code or "'''" in code,
            "has_type_hints": "->" in code or ": " in code,
            "has_error_handling": "try:" in code or "except" in code,
            "imports_count": sum(1 for l in lines if l.strip().startswith(("import ", "from "))),
            "function_count": sum(1 for l in lines if l.strip().startswith("def ")),
            "class_count": sum(1 for l in lines if l.strip().startswith("class ")),
            "note": "Full code review requires LLM (Phase 2+). Structural analysis only.",
        }

        return ToolResult(
            success=True,
            content=review,
            tool_name="code_review",
            module=self.name,
        )

    def _git_status(self, params: dict[str, Any]) -> ToolResult:
        """Check the git repository state.

        Args:
            params: No required parameters.
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self._project_root),
            )

            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self._project_root),
            )

            status_lines = [
                line for line in result.stdout.strip().split("\n") if line.strip()
            ]

            return ToolResult(
                success=True,
                content={
                    "branch": branch_result.stdout.strip(),
                    "changes": status_lines,
                    "clean": len(status_lines) == 0,
                    "change_count": len(status_lines),
                },
                tool_name="git_status",
                module=self.name,
            )

        except FileNotFoundError:
            return ToolResult(
                success=False, content=None, tool_name="git_status",
                module=self.name, error="Git is not installed or not in PATH",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="git_status",
                module=self.name, error="Git status timed out",
            )

    def _git_commit(self, params: dict[str, Any]) -> ToolResult:
        """Stage and commit files.

        This tool requires approval (permission_level = approval_required).

        Args:
            params: 'message' (str), optional 'files' (list of paths).
        """
        message = params.get("message", "")
        if not message:
            return ToolResult(
                success=False, content=None, tool_name="git_commit",
                module=self.name, error="Commit message is required",
            )

        files = params.get("files", [])

        try:
            # Stage files
            if files:
                for f in files:
                    subprocess.run(
                        ["git", "add", str(f)],
                        capture_output=True, text=True, timeout=10,
                        cwd=str(self._project_root),
                    )
            else:
                subprocess.run(
                    ["git", "add", "-A"],
                    capture_output=True, text=True, timeout=10,
                    cwd=str(self._project_root),
                )

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True, text=True, timeout=30,
                cwd=str(self._project_root),
            )

            return ToolResult(
                success=result.returncode == 0,
                content={
                    "message": message,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "committed": result.returncode == 0,
                },
                tool_name="git_commit",
                module=self.name,
                error=result.stderr if result.returncode != 0 else None,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="git_commit",
                module=self.name, error="Git commit timed out",
            )

    def _dependency_check(self, params: dict[str, Any]) -> ToolResult:
        """Check for outdated Python packages.

        Args:
            params: No required parameters.
        """
        try:
            result = subprocess.run(
                [self._python, "-m", "pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            import json
            try:
                outdated = json.loads(result.stdout) if result.stdout.strip() else []
            except (json.JSONDecodeError, ValueError):
                outdated = []

            return ToolResult(
                success=True,
                content={
                    "outdated_count": len(outdated),
                    "packages": outdated[:20],  # Limit output
                },
                tool_name="dependency_check",
                module=self.name,
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content=None, tool_name="dependency_check",
                module=self.name, error="Dependency check timed out",
            )

    # --- Code-aware tools ---

    def _load_gitignore_patterns(self, root: Path) -> list[str]:
        """Load .gitignore patterns from a directory.

        Args:
            root: Directory containing .gitignore.

        Returns:
            List of gitignore patterns.
        """
        gitignore = root / ".gitignore"
        if not gitignore.exists():
            return []
        try:
            lines = gitignore.read_text(encoding="utf-8").splitlines()
            return [
                line.strip().rstrip("/")
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            ]
        except OSError:
            return []

    def _is_excluded(self, path: Path, root: Path, gitignore_patterns: list[str]) -> bool:
        """Check if a path should be excluded from glob/grep results.

        Args:
            path: Path to check.
            root: Root directory for relative path calculation.
            gitignore_patterns: Patterns from .gitignore.

        Returns:
            True if the path should be excluded.
        """
        # Check always-excluded directories
        for part in path.relative_to(root).parts:
            if part in self.ALWAYS_EXCLUDE:
                return True
        # Check .pyc extension
        if path.suffix == ".pyc":
            return True
        # Check gitignore patterns
        rel = str(path.relative_to(root))
        for pattern in gitignore_patterns:
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern):
                return True
            # Handle directory patterns
            for part in path.relative_to(root).parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def _code_glob(self, params: dict[str, Any]) -> ToolResult:
        """Find files matching a glob pattern.

        Args:
            params: 'pattern' (str), optional 'root_dir' (str, default ".").
        """
        pattern = params.get("pattern", "")
        if not pattern:
            return ToolResult(
                success=False, content=None, tool_name="code_glob",
                module=self.name, error="Pattern is required",
            )

        root_dir = params.get("root_dir", ".")
        root = Path(root_dir).resolve()

        if not root.exists() or not root.is_dir():
            return ToolResult(
                success=False, content=None, tool_name="code_glob",
                module=self.name, error=f"Directory not found: {root_dir}",
            )

        gitignore_patterns = self._load_gitignore_patterns(root)

        matches = []
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            if self._is_excluded(path, root, gitignore_patterns):
                continue
            matches.append(str(path.relative_to(root)))
            if len(matches) >= self.MAX_GLOB_RESULTS:
                break

        return ToolResult(
            success=True,
            content={
                "files": sorted(matches),
                "count": len(matches),
                "pattern": pattern,
                "root": str(root),
                "capped": len(matches) >= self.MAX_GLOB_RESULTS,
            },
            tool_name="code_glob",
            module=self.name,
        )

    def _code_grep(self, params: dict[str, Any]) -> ToolResult:
        """Search for text/regex in code files.

        Args:
            params: 'pattern' (str), optional 'file_glob' (str, default "**/*.py"),
                    'root_dir' (str, default "."), 'max_results' (int, default 50).
        """
        pattern = params.get("pattern", "")
        if not pattern:
            return ToolResult(
                success=False, content=None, tool_name="code_grep",
                module=self.name, error="Pattern is required",
            )

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(
                success=False, content=None, tool_name="code_grep",
                module=self.name, error=f"Invalid regex: {e}",
            )

        file_glob = params.get("file_glob", "**/*.py")
        root_dir = params.get("root_dir", ".")
        max_results = params.get("max_results", 50)
        root = Path(root_dir).resolve()

        if not root.exists() or not root.is_dir():
            return ToolResult(
                success=False, content=None, tool_name="code_grep",
                module=self.name, error=f"Directory not found: {root_dir}",
            )

        gitignore_patterns = self._load_gitignore_patterns(root)
        results = []

        for path in root.glob(file_glob):
            if not path.is_file():
                continue
            if self._is_excluded(path, root, gitignore_patterns):
                continue
            if path.suffix in self.BINARY_EXTENSIONS:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    results.append({
                        "file": str(path.relative_to(root)),
                        "line_number": i,
                        "line": line,
                    })
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break

        return ToolResult(
            success=True,
            content={
                "matches": results,
                "count": len(results),
                "pattern": pattern,
                "capped": len(results) >= max_results,
            },
            tool_name="code_grep",
            module=self.name,
        )

    def _code_edit(self, params: dict[str, Any]) -> ToolResult:
        """Apply a find-and-replace edit to a file.

        Args:
            params: 'file_path' (str), 'old_text' (str), 'new_text' (str).
        """
        file_path = params.get("file_path", "")
        old_text = params.get("old_text", "")
        new_text = params.get("new_text", "")

        if not file_path or not old_text:
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name, error="file_path and old_text are required",
            )

        path = Path(file_path)

        # Safety: refuse protected paths
        try:
            rel = path.resolve().relative_to(self._project_root)
        except ValueError:
            rel = path

        for protected in self.PROTECTED_PATHS:
            rel_str = str(rel).replace("\\", "/")
            if rel_str == protected or rel_str.startswith(protected + "/"):
                return ToolResult(
                    success=False, content=None, tool_name="code_edit",
                    module=self.name,
                    error=f"Refused: cannot edit protected path '{protected}'",
                )

        if not path.exists():
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name, error=f"File not found: {file_path}",
            )

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name, error=f"Cannot read file: {e}",
            )

        count = content.count(old_text)
        if count == 0:
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name, error="old_text not found in file",
            )
        if count > 1:
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name,
                error=f"old_text found {count} times — must appear exactly once",
            )

        new_content = content.replace(old_text, new_text, 1)
        try:
            path.write_text(new_content, encoding="utf-8")
        except OSError as e:
            return ToolResult(
                success=False, content=None, tool_name="code_edit",
                module=self.name, error=f"Cannot write file: {e}",
            )

        return ToolResult(
            success=True,
            content={"success": True, "file": str(path), "replacements": 1},
            tool_name="code_edit",
            module=self.name,
        )

    def _code_read(self, params: dict[str, Any]) -> ToolResult:
        """Read a file with line numbers.

        Args:
            params: 'file_path' (str), optional 'start_line' (int), 'end_line' (int).
        """
        file_path = params.get("file_path", "")
        if not file_path:
            return ToolResult(
                success=False, content=None, tool_name="code_read",
                module=self.name, error="file_path is required",
            )

        path = Path(file_path)
        if not path.exists():
            return ToolResult(
                success=False, content=None, tool_name="code_read",
                module=self.name, error=f"File not found: {file_path}",
            )

        # Check file size
        try:
            size = path.stat().st_size
        except OSError as e:
            return ToolResult(
                success=False, content=None, tool_name="code_read",
                module=self.name, error=f"Cannot stat file: {e}",
            )

        if size > self.MAX_FILE_SIZE:
            return ToolResult(
                success=False, content=None, tool_name="code_read",
                module=self.name,
                error=f"File too large: {size} bytes (max {self.MAX_FILE_SIZE})",
            )

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return ToolResult(
                success=False, content=None, tool_name="code_read",
                module=self.name, error=f"Cannot read file: {e}",
            )

        lines = content.splitlines()
        start = params.get("start_line")
        end = params.get("end_line")

        if start is not None or end is not None:
            start_idx = (start - 1) if start and start >= 1 else 0
            end_idx = end if end else len(lines)
            selected = lines[start_idx:end_idx]
            offset = start_idx + 1
        else:
            selected = lines
            offset = 1

        numbered = [f"{i + offset}\t{line}" for i, line in enumerate(selected)]

        return ToolResult(
            success=True,
            content={
                "content": "\n".join(numbered),
                "file": str(path),
                "line_count": len(selected),
                "total_lines": len(lines),
            },
            tool_name="code_read",
            module=self.name,
        )

    # --- Enhanced tools (Phase 2) ---

    def _pattern_store(self, params: dict[str, Any]) -> ToolResult:
        """Store a reusable code pattern in the database.

        Args:
            params: 'name', 'category', 'description', 'code_template' required.
                    Optional 'language', 'tags'.
        """
        name = params.get("name", "")
        category = params.get("category", "")
        description = params.get("description", "")
        code_template = params.get("code_template", "")

        if not all([name, category, description, code_template]):
            return ToolResult(
                success=False, content=None, tool_name="pattern_store",
                module=self.name,
                error="name, category, description, and code_template are required",
            )

        if category not in VALID_PATTERN_CATEGORIES:
            return ToolResult(
                success=False, content=None, tool_name="pattern_store",
                module=self.name,
                error=f"Invalid category '{category}'. Must be one of: {sorted(VALID_PATTERN_CATEGORIES)}",
            )

        # Check for duplicates
        existing = self._conn.execute(
            "SELECT id FROM omen_patterns WHERE pattern_name = ?", (name,)
        ).fetchone()
        if existing:
            return ToolResult(
                success=False, content=None, tool_name="pattern_store",
                module=self.name,
                error=f"Pattern '{name}' already exists",
            )

        language = params.get("language", "python")
        tags = params.get("tags", "")
        now = datetime.now().isoformat()

        self._conn.execute(
            """INSERT INTO omen_patterns
               (pattern_name, category, language, description, code_template, created_at, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, category, language, description, code_template, now, tags),
        )
        self._conn.commit()

        return ToolResult(
            success=True,
            content={"stored": name, "category": category, "created_at": now},
            tool_name="pattern_store",
            module=self.name,
        )

    def _pattern_search(self, params: dict[str, Any]) -> ToolResult:
        """Search stored code patterns.

        Args:
            params: Optional 'category', 'tags' (comma-separated), 'keyword'.
        """
        conditions = []
        values = []

        category = params.get("category", "")
        if category:
            conditions.append("category = ?")
            values.append(category)

        tags = params.get("tags", "")
        if tags:
            for tag in tags.split(","):
                tag = tag.strip()
                if tag:
                    conditions.append("tags LIKE ?")
                    values.append(f"%{tag}%")

        keyword = params.get("keyword", "")
        if keyword:
            conditions.append("(pattern_name LIKE ? OR description LIKE ?)")
            values.extend([f"%{keyword}%", f"%{keyword}%"])

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM omen_patterns {where} ORDER BY usage_count DESC"

        cursor = self._conn.execute(query, values)
        rows = [dict(row) for row in cursor.fetchall()]

        return ToolResult(
            success=True,
            content={"patterns": rows, "count": len(rows)},
            tool_name="pattern_search",
            module=self.name,
        )

    def _pattern_apply(self, params: dict[str, Any]) -> ToolResult:
        """Apply a stored pattern with placeholder substitutions.

        Args:
            params: 'name' (str) required. Optional 'substitutions' (dict).
        """
        name = params.get("name", "")
        if not name:
            return ToolResult(
                success=False, content=None, tool_name="pattern_apply",
                module=self.name, error="Pattern name is required",
            )

        row = self._conn.execute(
            "SELECT * FROM omen_patterns WHERE pattern_name = ?", (name,)
        ).fetchone()

        if not row:
            return ToolResult(
                success=False, content=None, tool_name="pattern_apply",
                module=self.name, error=f"Pattern '{name}' not found",
            )

        # Increment usage and update last_used
        now = datetime.now().isoformat()
        self._conn.execute(
            "UPDATE omen_patterns SET usage_count = usage_count + 1, last_used = ? WHERE pattern_name = ?",
            (now, name),
        )
        self._conn.commit()

        # Apply substitutions
        template = row["code_template"]
        substitutions = params.get("substitutions", {})
        if substitutions:
            for key, value in substitutions.items():
                template = template.replace(f"{{{{{key}}}}}", str(value))

        return ToolResult(
            success=True,
            content={
                "pattern_name": name,
                "rendered": template,
                "usage_count": row["usage_count"] + 1,
                "last_used": now,
            },
            tool_name="pattern_apply",
            module=self.name,
        )

    def _failure_log(self, params: dict[str, Any]) -> ToolResult:
        """Log a code failure for learning and prevention.

        Args:
            params: 'error_type' and 'error_message' required. Optional
                    'file_path', 'code_context', 'fix_applied', 'fix_worked',
                    'prevention_rule'.
        """
        error_type = params.get("error_type", "")
        error_message = params.get("error_message", "")

        if not error_type or not error_message:
            return ToolResult(
                success=False, content=None, tool_name="failure_log",
                module=self.name,
                error="error_type and error_message are required",
            )

        # Deterministic failure_id from type + message
        failure_id = hashlib.sha256(
            f"{error_type}:{error_message}".encode()
        ).hexdigest()[:16]

        now = datetime.now().isoformat()

        # Check if failure already exists (upsert)
        existing = self._conn.execute(
            "SELECT id, occurrences FROM omen_failures WHERE failure_id = ?",
            (failure_id,),
        ).fetchone()

        if existing:
            self._conn.execute(
                """UPDATE omen_failures
                   SET occurrences = occurrences + 1, last_seen = ?,
                       fix_applied = COALESCE(?, fix_applied),
                       fix_worked = COALESCE(?, fix_worked),
                       prevention_rule = COALESCE(?, prevention_rule)
                   WHERE failure_id = ?""",
                (
                    now,
                    params.get("fix_applied"),
                    params.get("fix_worked"),
                    params.get("prevention_rule"),
                    failure_id,
                ),
            )
            self._conn.commit()
            return ToolResult(
                success=True,
                content={
                    "failure_id": failure_id,
                    "status": "updated",
                    "occurrences": existing["occurrences"] + 1,
                },
                tool_name="failure_log",
                module=self.name,
            )

        self._conn.execute(
            """INSERT INTO omen_failures
               (failure_id, error_type, error_message, file_path, code_context,
                fix_applied, fix_worked, first_seen, last_seen, prevention_rule)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                failure_id,
                error_type,
                error_message,
                params.get("file_path"),
                params.get("code_context"),
                params.get("fix_applied"),
                params.get("fix_worked"),
                now,
                now,
                params.get("prevention_rule"),
            ),
        )
        self._conn.commit()

        return ToolResult(
            success=True,
            content={
                "failure_id": failure_id,
                "status": "created",
                "occurrences": 1,
            },
            tool_name="failure_log",
            module=self.name,
        )

    def _failure_search(self, params: dict[str, Any]) -> ToolResult:
        """Search logged failures by type or keyword.

        Args:
            params: Optional 'error_type' (exact), 'keyword' (LIKE on message).
        """
        conditions = []
        values = []

        error_type = params.get("error_type", "")
        if error_type:
            conditions.append("error_type = ?")
            values.append(error_type)

        keyword = params.get("keyword", "")
        if keyword:
            conditions.append("error_message LIKE ?")
            values.append(f"%{keyword}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"SELECT * FROM omen_failures {where} ORDER BY occurrences DESC"

        cursor = self._conn.execute(query, values)
        rows = [dict(row) for row in cursor.fetchall()]

        return ToolResult(
            success=True,
            content={"failures": rows, "count": len(rows)},
            tool_name="failure_search",
            module=self.name,
        )

    def _failure_stats(self, params: dict[str, Any]) -> ToolResult:
        """Get aggregate statistics on logged failures.

        Args:
            params: No required parameters.
        """
        total = self._conn.execute(
            "SELECT COUNT(*) as count FROM omen_failures"
        ).fetchone()["count"]

        top_10 = self._conn.execute(
            "SELECT error_type, error_message, occurrences FROM omen_failures ORDER BY occurrences DESC LIMIT 10"
        ).fetchall()
        top_10 = [dict(row) for row in top_10]

        # Fix success rate: AVG of fix_worked where fix_applied is not null
        fix_rate = self._conn.execute(
            "SELECT AVG(fix_worked) as rate FROM omen_failures WHERE fix_applied IS NOT NULL"
        ).fetchone()["rate"]

        recurring = self._conn.execute(
            "SELECT COUNT(*) as count FROM omen_failures WHERE occurrences > 3"
        ).fetchone()["count"]

        return ToolResult(
            success=True,
            content={
                "total_failures": total,
                "top_10": top_10,
                "fix_success_rate": fix_rate,
                "recurring_count": recurring,
            },
            tool_name="failure_stats",
            module=self.name,
        )

    def _scaffold_module(self, params: dict[str, Any]) -> ToolResult:
        """Generate boilerplate code for a new Shadow module.

        Args:
            params: 'module_name', 'description', 'tools' (list of tool name strings).
        """
        module_name = params.get("module_name", "")
        description = params.get("description", "")
        tools = params.get("tools", [])

        if not all([module_name, description, tools]):
            return ToolResult(
                success=False, content=None, tool_name="scaffold_module",
                module=self.name,
                error="module_name, description, and tools are required",
            )

        module_lower = module_name.lower()
        module_class = module_name.capitalize()

        # Build handler entries
        handler_lines = []
        for tool in tools:
            handler_lines.append(f'                "{tool}": self._{tool},\n')
        handler_entries = "".join(handler_lines)

        # Build tool definitions
        tool_def_lines = []
        for tool in tools:
            tool_def_lines.append(
                f'            {{\n'
                f'                "name": "{tool}",\n'
                f'                "description": "{tool} — TODO",\n'
                f'                "parameters": {{}},\n'
                f'                "permission_level": "autonomous",\n'
                f'            }},\n'
            )
        tool_definitions = "".join(tool_def_lines)

        # Build tool stubs
        stub_lines = []
        for tool in tools:
            stub_lines.append(
                f"    def _{tool}(self, params: dict[str, Any]) -> ToolResult:\n"
                f'        """Handle {tool} tool. TODO: implement."""\n'
                f"        return ToolResult(\n"
                f"            success=True,\n"
                f'            content={{"status": "not_implemented"}},\n'
                f'            tool_name="{tool}",\n'
                f"            module=self.name,\n"
                f"        )\n\n"
            )
        tool_stubs = "".join(stub_lines)

        module_code = MODULE_TEMPLATE.substitute(
            module_name=module_name,
            module_lower=module_lower,
            module_class=module_class,
            description=description,
            handler_entries=handler_entries,
            tool_definitions=tool_definitions,
            tool_stubs=tool_stubs,
        )

        # Build test classes
        fixture_name = module_lower
        test_class_lines = []
        for tool in tools:
            test_class_lines.append(
                f"class Test{tool.replace('_', ' ').title().replace(' ', '')}:\n"
                f"    @pytest.mark.asyncio\n"
                f"    async def test_{tool}_success(self, online_{fixture_name}):\n"
                f'        result = await online_{fixture_name}.execute("{tool}", {{}})\n'
                f"        assert result.success\n\n"
            )
        test_classes = "\n".join(test_class_lines)

        test_code = TEST_TEMPLATE.substitute(
            module_name=module_name,
            module_lower=module_lower,
            module_class=module_class,
            fixture_name=fixture_name,
            test_classes=test_classes,
        )

        init_code = INIT_TEMPLATE.substitute(
            module_name=module_name,
            module_lower=module_lower,
            module_class=module_class,
        )

        return ToolResult(
            success=True,
            content={
                "module_code": module_code,
                "test_code": test_code,
                "init_code": init_code,
                "module_name": module_name,
                "tools": tools,
            },
            tool_name="scaffold_module",
            module=self.name,
        )

    def _scaffold_test(self, params: dict[str, Any]) -> ToolResult:
        """Generate test skeleton for a Shadow module.

        Args:
            params: 'module_name' (str) required.
        """
        module_name = params.get("module_name", "")
        if not module_name:
            return ToolResult(
                success=False, content=None, tool_name="scaffold_test",
                module=self.name, error="module_name is required",
            )

        module_lower = module_name.lower()
        module_class = module_name.capitalize()

        # Try to dynamically import the module and get its tools
        try:
            import importlib
            mod = importlib.import_module(f"modules.{module_lower}.{module_lower}")
            cls = getattr(mod, module_class)
            instance = cls()
            tools = instance.get_tools()
            tool_names = [t["name"] for t in tools]
        except Exception:
            # Fallback: generate generic test
            tool_names = []

        fixture_name = module_lower
        test_class_lines = []

        if tool_names:
            for tool_name in tool_names:
                test_class_lines.append(
                    f"class Test{tool_name.replace('_', ' ').title().replace(' ', '')}:\n"
                    f"    @pytest.mark.asyncio\n"
                    f"    async def test_{tool_name}_success(self, online_{fixture_name}):\n"
                    f'        result = await online_{fixture_name}.execute("{tool_name}", {{}})\n'
                    f"        assert result.success\n\n"
                )
        else:
            test_class_lines.append(
                f"class Test{module_class}Basic:\n"
                f"    @pytest.mark.asyncio\n"
                f"    async def test_initialize(self, online_{fixture_name}):\n"
                f"        from modules.base import ModuleStatus\n"
                f"        assert online_{fixture_name}.status == ModuleStatus.ONLINE\n\n"
            )

        test_classes = "\n".join(test_class_lines)

        test_code = TEST_TEMPLATE.substitute(
            module_name=module_name,
            module_lower=module_lower,
            module_class=module_class,
            fixture_name=fixture_name,
            test_classes=test_classes,
        )

        return ToolResult(
            success=True,
            content={
                "test_code": test_code,
                "module_name": module_name,
                "tools_covered": tool_names,
            },
            tool_name="scaffold_test",
            module=self.name,
        )

    def _code_score(self, params: dict[str, Any]) -> ToolResult:
        """Score a Python file on code quality (0-100).

        Uses AST analysis for accuracy. Checks docstrings, type hints,
        error handling, import organization, function length, and more.

        Args:
            params: 'file_path' (str) required.
        """
        file_path = params.get("file_path", "")
        if not file_path:
            return ToolResult(
                success=False, content=None, tool_name="code_score",
                module=self.name, error="file_path is required",
            )

        path = Path(file_path)
        if not path.exists():
            return ToolResult(
                success=False, content=None, tool_name="code_score",
                module=self.name, error=f"File not found: {file_path}",
            )

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return ToolResult(
                success=False, content=None, tool_name="code_score",
                module=self.name, error=f"Cannot read file: {e}",
            )

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as e:
            return ToolResult(
                success=False, content=None, tool_name="code_score",
                module=self.name, error=f"Syntax error: {e}",
            )

        breakdown = {}
        suggestions = []
        score = 0

        # 1. Docstrings (20 pts)
        funcs_and_classes = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        has_docstring_count = 0
        for node in funcs_and_classes:
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                has_docstring_count += 1
        if funcs_and_classes:
            docstring_ratio = has_docstring_count / len(funcs_and_classes)
            docstring_pts = int(20 * docstring_ratio)
        else:
            docstring_pts = 20  # No functions = full marks (not applicable)
        breakdown["docstrings"] = docstring_pts
        score += docstring_pts
        if docstring_pts < 15:
            suggestions.append("Add docstrings to functions and classes")

        # 2. Type hints (20 pts)
        func_nodes = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        hint_count = 0
        for func in func_nodes:
            if func.returns is not None:
                hint_count += 1
            for arg in func.args.args:
                if arg.annotation is not None:
                    hint_count += 1
        # Estimate: each function should have return + at least 1 arg hint
        expected = len(func_nodes) * 2 if func_nodes else 1
        hint_ratio = min(hint_count / expected, 1.0) if expected > 0 else 1.0
        hint_pts = int(20 * hint_ratio)
        breakdown["type_hints"] = hint_pts
        score += hint_pts
        if hint_pts < 15:
            suggestions.append("Add type annotations to function signatures")

        # 3. Error handling (15 pts)
        try_nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
        if func_nodes:
            err_ratio = min(len(try_nodes) / max(len(func_nodes) * 0.3, 1), 1.0)
            err_pts = int(15 * err_ratio)
        else:
            err_pts = 15
        breakdown["error_handling"] = err_pts
        score += err_pts
        if err_pts < 10:
            suggestions.append("Add error handling (try/except) to critical operations")

        # 4. No bare excepts (10 pts)
        bare_excepts = 0
        for try_node in try_nodes:
            for handler in try_node.handlers:
                if handler.type is None:
                    bare_excepts += 1
        bare_pts = 10 if bare_excepts == 0 else max(0, 10 - bare_excepts * 3)
        breakdown["no_bare_excepts"] = bare_pts
        score += bare_pts
        if bare_pts < 10:
            suggestions.append("Replace bare 'except:' with specific exception types")

        # 5. Import organization (10 pts)
        imports = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(node.lineno)
            elif imports:
                break  # Imports should be at top
        # Check imports are at top and contiguous
        if imports:
            import_pts = 10 if imports == list(range(imports[0], imports[0] + len(imports))) else 7
        else:
            import_pts = 10
        breakdown["import_organization"] = import_pts
        score += import_pts

        # 6. No hardcoded secrets (10 pts)
        secret_patterns = {"password", "api_key", "secret", "token"}
        source_lower = source.lower()
        has_secrets = False
        for pattern in secret_patterns:
            # Look for assignments like password = "..."
            if re.search(rf'{pattern}\s*=\s*["\'][^"\']+["\']', source_lower):
                has_secrets = True
                break
        secret_pts = 0 if has_secrets else 10
        breakdown["no_hardcoded_secrets"] = secret_pts
        score += secret_pts
        if has_secrets:
            suggestions.append("Remove hardcoded secrets — use environment variables or config files")

        # 7. Function length < 50 lines (10 pts)
        long_funcs = []
        for func in func_nodes:
            if hasattr(func, "end_lineno") and func.end_lineno:
                length = func.end_lineno - func.lineno
                if length > 50:
                    long_funcs.append(func.name)
        length_pts = 10 if not long_funcs else max(0, 10 - len(long_funcs) * 2)
        breakdown["function_length"] = length_pts
        score += length_pts
        if long_funcs:
            suggestions.append(f"Consider breaking up long functions: {', '.join(long_funcs)}")

        # 8. Test file exists (5 pts)
        test_path = path.parent.parent / "tests" / f"test_{path.stem}.py"
        test_path_alt = Path("tests") / f"test_{path.stem}.py"
        test_exists = test_path.exists() or test_path_alt.exists()
        test_pts = 5 if test_exists else 0
        breakdown["test_file_exists"] = test_pts
        score += test_pts
        if not test_exists:
            suggestions.append(f"Create test file: tests/test_{path.stem}.py")

        return ToolResult(
            success=True,
            content={
                "file": str(path),
                "score": score,
                "breakdown": breakdown,
                "suggestions": suggestions,
            },
            tool_name="code_score",
            module=self.name,
        )

    def _seed_patterns(self, params: dict[str, Any]) -> ToolResult:
        """Populate pattern database with Shadow codebase patterns.

        Args:
            params: No required parameters.
        """
        existing = self._conn.execute(
            "SELECT COUNT(*) as count FROM omen_patterns"
        ).fetchone()["count"]

        if existing > 0:
            return ToolResult(
                success=True,
                content={"status": "already_seeded", "existing_count": existing},
                tool_name="seed_patterns",
                module=self.name,
            )

        now = datetime.now().isoformat()
        count = 0
        for pattern in SEED_PATTERNS:
            self._conn.execute(
                """INSERT INTO omen_patterns
                   (pattern_name, category, language, description, code_template, created_at, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    pattern["name"],
                    pattern["category"],
                    pattern.get("language", "python"),
                    pattern["description"],
                    pattern["code_template"],
                    now,
                    pattern.get("tags", ""),
                ),
            )
            count += 1
        self._conn.commit()

        return ToolResult(
            success=True,
            content={"status": "seeded", "patterns_added": count},
            tool_name="seed_patterns",
            module=self.name,
        )
