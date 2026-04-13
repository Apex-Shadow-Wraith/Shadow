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
from modules.omen.code_analyzer import CodeAnalyzer
from modules.omen.model_evaluator import ModelEvaluator
from modules.omen.sandbox import CodeSandbox

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
        self._analyzer = CodeAnalyzer(
            grimoire=self._config.get("grimoire"),
            samples_dir=self._config.get("samples_dir", "data/research/code_samples"),
        )
        self._model_evaluator = ModelEvaluator(
            ollama_base_url=self._config.get("ollama_base_url", "http://localhost:11434"),
            grimoire=self._config.get("grimoire"),
            benchmarks_dir=self._config.get("benchmarks_dir", "data/benchmarks"),
        )
        self._sandbox = CodeSandbox(
            sandbox_root=self._config.get("sandbox_root", "data/sandbox"),
        )

        # Test Gate — auto-revert if code changes break tests
        self._test_gate = None
        try:
            from modules.omen.test_gate import TestGate
            self._test_gate = TestGate(
                project_root=self._config.get("project_root", "."),
                test_command=self._config.get(
                    "test_command", "python -m pytest tests/ -x -q"
                ),
            )
        except Exception as e:
            logger.warning("TestGate not available: %s", e)

        # Scratchpad — file-based working memory for complex tasks
        self._scratchpad = None
        try:
            from modules.omen.scratchpad import Scratchpad
            self._scratchpad = Scratchpad(
                base_dir=self._config.get("scratchpad_dir", "data/scratchpads"),
                grimoire=self._config.get("grimoire"),
            )
        except Exception as e:
            logger.warning("Scratchpad not available: %s", e)

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
                "code_analyze": self._code_analyze,
                "code_analyze_file": self._code_analyze_file,
                "code_analyze_dir": self._code_analyze_dir,
                "code_analyze_url": self._code_analyze_url,
                "code_learn": self._code_learn,
                "code_compare": self._code_compare,
                "code_generate": self._code_generate,
                # --- Sandbox tools ---
                "sandbox_execute": self._sandbox_execute,
                "sandbox_validate": self._sandbox_validate,
                "sandbox_to_production": self._sandbox_to_production,
                "sandbox_cleanup": self._sandbox_cleanup,
                # --- Model Evaluator tools ---
                "model_list": self._model_list,
                "model_pull": self._model_pull,
                "model_benchmark": self._model_benchmark,
                "model_evaluate": self._model_evaluate,
                "model_compare": self._model_compare,
                "model_info": self._model_info,
                "model_recommend": self._model_recommend,
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
            # --- Code Analyzer tools (Phase 3) ---
            {
                "name": "code_analyze",
                "description": "Analyze inline code for structure, patterns, quality, and vulnerabilities without generating new code",
                "parameters": {"code": "str", "language": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_analyze_file",
                "description": "Analyze a Python file for structure, patterns, and quality",
                "parameters": {"file_path": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_analyze_dir",
                "description": "Analyze all Python files in a directory",
                "parameters": {"dir_path": "str", "pattern": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_analyze_url",
                "description": "Download and analyze a single Python file from a URL",
                "parameters": {"url": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_learn",
                "description": "Extract learnings from analysis and store in Grimoire",
                "parameters": {"file_path": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "code_compare",
                "description": "Compare external code patterns against Shadow's codebase",
                "parameters": {"file_path": "str"},
                "permission_level": "autonomous",
            },
            # --- Code generation with LLM fallback ---
            {
                "name": "code_generate",
                "description": "Generate code via LLM with fallback extraction when tool calls fail",
                "parameters": {
                    "prompt": "str",
                    "language": "str",
                    "model": "str",
                },
                "permission_level": "autonomous",
            },
            # --- Model Evaluator tools (Phase 4) ---
            {
                "name": "model_list",
                "description": "List all installed Ollama models with size and quantization",
                "parameters": {},
                "permission_level": "autonomous",
            },
            {
                "name": "model_pull",
                "description": "Download an Ollama model (consumes disk space)",
                "parameters": {"model_name": "str"},
                "permission_level": "approval_required",
            },
            {
                "name": "model_benchmark",
                "description": "Run standardized benchmark suite against an Ollama model",
                "parameters": {"model_name": "str", "warmup": "bool"},
                "permission_level": "autonomous",
            },
            {
                "name": "model_evaluate",
                "description": "Score benchmark results on quality (1-5 scale, rule-based)",
                "parameters": {"benchmark_results": "dict"},
                "permission_level": "autonomous",
            },
            {
                "name": "model_compare",
                "description": "Benchmark and compare multiple Ollama models side by side",
                "parameters": {"model_names": "list"},
                "permission_level": "autonomous",
            },
            {
                "name": "model_info",
                "description": "Get model details with alignment/censorship warnings",
                "parameters": {"model_name": "str"},
                "permission_level": "autonomous",
            },
            {
                "name": "model_recommend",
                "description": "Recommend best models for a role based on stored benchmarks",
                "parameters": {"role": "str"},
                "permission_level": "autonomous",
            },
            # --- Sandbox tools ---
            {
                "name": "sandbox_execute",
                "description": "Execute code in isolated sandbox with safety validation",
                "parameters": {
                    "code": "str", "timeout_seconds": "int",
                    "max_memory_mb": "int", "allow_imports": "list[str]",
                    "input_files": "dict[str, str]", "preserve": "bool",
                },
                "permission_level": "autonomous",
            },
            {
                "name": "sandbox_validate",
                "description": "Validate code safety without executing (static analysis)",
                "parameters": {"code": "str", "allow_imports": "list[str]"},
                "permission_level": "autonomous",
            },
            {
                "name": "sandbox_to_production",
                "description": "Copy sandbox file to production codebase (requires approval)",
                "parameters": {
                    "sandbox_path": "str", "production_path": "str",
                    "require_tests_pass": "bool",
                },
                "permission_level": "approval_required",
            },
            {
                "name": "sandbox_cleanup",
                "description": "Remove old sandbox directories",
                "parameters": {"max_age_hours": "int"},
                "permission_level": "autonomous",
            },
        ]

    # --- Tool implementations ---

    def _code_execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute Python code through the sandbox — no direct subprocess.

        Args:
            params: 'code' (str), optional 'timeout' (int seconds),
                    'allow_imports' (list[str]), 'input_files' (dict).
        """
        code = params.get("code", "")
        if not code:
            return ToolResult(
                success=False, content=None, tool_name="code_execute",
                module=self.name, error="Code is required",
            )

        timeout = min(params.get("timeout", self.DEFAULT_TIMEOUT), self.MAX_TIMEOUT)
        result = self._sandbox.execute(
            code=code,
            timeout_seconds=timeout,
            allow_imports=params.get("allow_imports"),
            input_files=params.get("input_files"),
        )

        output = {
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "exit_code": result["exit_code"],
            "success": result["exit_code"] == 0,
            "timeout_seconds": timeout,
            "execution_id": result["execution_id"],
            "files_created": result["files_created"],
            "timed_out": result["timed_out"],
        }

        if self._teaching_mode and result["exit_code"] != 0:
            output["teaching_note"] = (
                "The code failed. Check stderr for the error message. "
                "Common causes: syntax errors, missing imports, type errors."
            )

        return ToolResult(
            success=result["exit_code"] == 0,
            content=output,
            tool_name="code_execute",
            module=self.name,
            error=result["stderr"][:500] if result["exit_code"] != 0 else None,
        )

    def _code_lint(self, params: dict[str, Any]) -> ToolResult:
        """Check code for syntax errors — runs py_compile inside sandbox.

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
            code = path.read_text(encoding="utf-8")
        elif not code:
            return ToolResult(
                success=False, content=None, tool_name="code_lint",
                module=self.name, error="Either 'code' or 'file_path' is required",
            )

        # Run py_compile inside the sandbox
        lint_code = (
            "import py_compile, sys, tempfile, pathlib\n"
            "code = pathlib.Path('_lint_target.py').read_text(encoding='utf-8')\n"
            "try:\n"
            "    compile(code, '_lint_target.py', 'exec')\n"
            "    print('SYNTAX_OK')\n"
            "except SyntaxError as e:\n"
            "    print(f'SYNTAX_ERROR: {e}', file=sys.stderr)\n"
            "    sys.exit(1)\n"
        )

        result = self._sandbox.execute(
            code=lint_code,
            timeout_seconds=10,
            input_files={"_lint_target.py": code},
        )

        lint_result = {
            "file": file_path or "<inline>",
            "syntax_valid": result["exit_code"] == 0,
            "errors": result["stderr"].strip() if result["stderr"] else None,
        }

        return ToolResult(
            success=result["exit_code"] == 0,
            content=lint_result,
            tool_name="code_lint",
            module=self.name,
            error=result["stderr"][:500] if result["exit_code"] != 0 else None,
        )

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

    # --- Code Analyzer tool implementations ---

    @staticmethod
    def _looks_like_code(text: str) -> bool:
        """Return True if *text* contains Python-like syntax markers.

        Used to distinguish actual code from natural-language prompts so
        that ``code_analyze`` can give a helpful "no code provided" error
        instead of a confusing ``SyntaxError``.
        """
        import re as _re

        # Structural keywords that start a statement
        _KEYWORD_PAT = _re.compile(
            r"(?m)^\s*(?:def |class |import |from |if |for |while |with "
            r"|try:|except |return |raise |yield |async )"
        )
        if _KEYWORD_PAT.search(text):
            return True

        # Assignment, function calls, decorators
        _SYNTAX_PAT = _re.compile(
            r"(?:"
            r"\w+\s*=[^=]"        # assignment (but not ==)
            r"|\w+\(.*\)"         # function call
            r"|^\s*@\w+"          # decorator
            r"|^\s*#.*$"          # comment line
            r")",
            _re.MULTILINE,
        )
        if _SYNTAX_PAT.search(text):
            return True

        return False

    def _code_analyze(self, params: dict[str, Any]) -> ToolResult:
        """Analyze inline code for structure, patterns, quality, and vulnerabilities.

        Uses CodeAnalyzer.analyze_source() to provide read-only analysis
        without generating new code.

        Args:
            params: 'code' (str) required, 'language' (str) optional.
        """
        code = params.get("code", "")
        if not code or not code.strip():
            return ToolResult(
                success=False, content=None, tool_name="code_analyze",
                module=self.name,
                error="No code provided. Please paste or include the code you want analyzed.",
            )

        language = params.get("language", "python")
        if language != "python":
            # For non-Python, fall back to basic structural analysis
            lines = code.split("\n")
            analysis = {
                "language": language,
                "line_count": len(lines),
                "has_comments": any(
                    l.strip().startswith(("#", "//", "/*", "*"))
                    for l in lines
                ),
                "blank_lines": sum(1 for l in lines if not l.strip()),
                "note": f"Deep analysis only available for Python; {language} gets structural overview.",
            }
            return ToolResult(
                success=True, content=analysis,
                tool_name="code_analyze", module=self.name,
            )

        # Detect natural-language prompts that aren't actual code
        if not self._looks_like_code(code):
            return ToolResult(
                success=True,
                content={
                    "message": "No code detected in your message, Master. Paste the code you want me to analyze and I'll run it through the CodeAnalyzer."
                },
                tool_name="code_analyze",
                module=self.name,
            )

        analysis = self._analyzer.analyze_source(code, filename="<inline>")
        if analysis.get("error"):
            return ToolResult(
                success=False, content=analysis,
                tool_name="code_analyze",
                module=self.name, error=analysis["error"],
            )

        return ToolResult(
            success=True, content=analysis,
            tool_name="code_analyze", module=self.name,
        )

    def _code_analyze_file(self, params: dict[str, Any]) -> ToolResult:
        """Analyze a Python file for structure, patterns, and quality.

        Args:
            params: 'file_path' (str) required.
        """
        file_path = params.get("file_path", "")
        if not file_path:
            return ToolResult(
                success=False, content=None, tool_name="code_analyze_file",
                module=self.name, error="file_path is required",
            )

        analysis = self._analyzer.analyze_file(file_path)
        if analysis.get("error"):
            return ToolResult(
                success=False, content=analysis,
                tool_name="code_analyze_file",
                module=self.name, error=analysis["error"],
            )

        return ToolResult(
            success=True, content=analysis,
            tool_name="code_analyze_file", module=self.name,
        )

    def _code_analyze_dir(self, params: dict[str, Any]) -> ToolResult:
        """Analyze all Python files in a directory.

        Args:
            params: 'dir_path' (str) required, 'pattern' (str) optional.
        """
        dir_path = params.get("dir_path", "")
        if not dir_path:
            return ToolResult(
                success=False, content=None, tool_name="code_analyze_dir",
                module=self.name, error="dir_path is required",
            )

        pattern = params.get("pattern", "*.py")
        analysis = self._analyzer.analyze_directory(dir_path, pattern)
        if analysis.get("error"):
            return ToolResult(
                success=False, content=analysis,
                tool_name="code_analyze_dir",
                module=self.name, error=analysis["error"],
            )

        return ToolResult(
            success=True, content=analysis,
            tool_name="code_analyze_dir", module=self.name,
        )

    def _code_analyze_url(self, params: dict[str, Any]) -> ToolResult:
        """Download and analyze a single Python file from a URL.

        Args:
            params: 'url' (str) required.
        """
        url = params.get("url", "")
        if not url:
            return ToolResult(
                success=False, content=None, tool_name="code_analyze_url",
                module=self.name, error="url is required",
            )

        analysis = self._analyzer.analyze_url(url)
        if analysis.get("error"):
            return ToolResult(
                success=False, content=analysis,
                tool_name="code_analyze_url",
                module=self.name, error=analysis["error"],
            )

        return ToolResult(
            success=True, content=analysis,
            tool_name="code_analyze_url", module=self.name,
        )

    def _code_learn(self, params: dict[str, Any]) -> ToolResult:
        """Extract learnings from a file analysis and store in Grimoire.

        Args:
            params: 'file_path' (str) required.
        """
        file_path = params.get("file_path", "")
        if not file_path:
            return ToolResult(
                success=False, content=None, tool_name="code_learn",
                module=self.name, error="file_path is required",
            )

        analysis = self._analyzer.analyze_file(file_path)
        if analysis.get("error"):
            return ToolResult(
                success=False, content=analysis, tool_name="code_learn",
                module=self.name, error=analysis["error"],
            )

        learnings = self._analyzer.extract_learnings(analysis)
        stored = self._analyzer.store_learnings(learnings, source=file_path)

        return ToolResult(
            success=True,
            content={
                "file": file_path,
                "learnings_extracted": len(learnings),
                "learnings_stored": stored,
                "learnings": learnings,
            },
            tool_name="code_learn",
            module=self.name,
        )

    def _code_compare(self, params: dict[str, Any]) -> ToolResult:
        """Compare external code against Shadow's codebase.

        Args:
            params: 'file_path' (str) required.
        """
        file_path = params.get("file_path", "")
        if not file_path:
            return ToolResult(
                success=False, content=None, tool_name="code_compare",
                module=self.name, error="file_path is required",
            )

        analysis = self._analyzer.analyze_file(file_path)
        if analysis.get("error"):
            return ToolResult(
                success=False, content=analysis, tool_name="code_compare",
                module=self.name, error=analysis["error"],
            )

        comparison = self._analyzer.compare_with_shadow(analysis)
        return ToolResult(
            success=True, content=comparison,
            tool_name="code_compare", module=self.name,
        )

    # --- Sandbox tool implementations ---

    def _sandbox_execute(self, params: dict[str, Any]) -> ToolResult:
        """Execute code in the sandbox with full isolation.

        Args:
            params: 'code' (str), optional 'timeout_seconds', 'max_memory_mb',
                    'allow_imports', 'input_files', 'preserve'.
        """
        code = params.get("code", "")
        if not code:
            return ToolResult(
                success=False, content=None, tool_name="sandbox_execute",
                module=self.name, error="Code is required",
            )

        result = self._sandbox.execute(
            code=code,
            timeout_seconds=params.get("timeout_seconds", 30),
            max_memory_mb=params.get("max_memory_mb", 512),
            allow_imports=params.get("allow_imports"),
            input_files=params.get("input_files"),
            preserve=params.get("preserve", False),
        )

        return ToolResult(
            success=result["exit_code"] == 0 and not result["timed_out"],
            content=result,
            tool_name="sandbox_execute",
            module=self.name,
            error=result["stderr"][:500] if result["exit_code"] != 0 else None,
        )

    def _sandbox_validate(self, params: dict[str, Any]) -> ToolResult:
        """Validate code safety without executing.

        Args:
            params: 'code' (str), optional 'allow_imports' (list[str]).
        """
        code = params.get("code", "")
        if not code:
            return ToolResult(
                success=False, content=None, tool_name="sandbox_validate",
                module=self.name, error="Code is required",
            )

        result = self._sandbox.validate_code_safety(
            code=code,
            allow_imports=params.get("allow_imports"),
        )

        return ToolResult(
            success=result["safe"],
            content=result,
            tool_name="sandbox_validate",
            module=self.name,
            error="; ".join(result["violations"]) if result["violations"] else None,
        )

    def _sandbox_to_production(self, params: dict[str, Any]) -> ToolResult:
        """Copy sandbox file to production (requires approval).

        Args:
            params: 'sandbox_path' (str), 'production_path' (str),
                    optional 'require_tests_pass' (bool).
        """
        sandbox_path = params.get("sandbox_path", "")
        production_path = params.get("production_path", "")
        if not sandbox_path or not production_path:
            return ToolResult(
                success=False, content=None, tool_name="sandbox_to_production",
                module=self.name, error="Both sandbox_path and production_path are required",
            )

        # Get ReversibilityEngine if available
        reversibility = self._config.get("reversibility_engine")

        # Build test runner function
        def run_tests() -> bool:
            try:
                result = subprocess.run(
                    [self._python, "-m", "pytest", "tests/", "-x", "-q"],
                    capture_output=True, text=True, timeout=120,
                    cwd=str(self._project_root),
                )
                return result.returncode == 0
            except Exception:
                return False

        def do_copy():
            return self._sandbox.copy_to_production(
                sandbox_path=sandbox_path,
                production_path=production_path,
                require_tests_pass=params.get("require_tests_pass", True),
                reversibility_engine=reversibility,
                run_tests_fn=run_tests,
            )

        # Route through TestGate if available
        if self._test_gate:
            gate_result = self._test_gate.execute_with_gate(
                change_fn=do_copy,
                description=f"sandbox_to_production: {sandbox_path} → {production_path}",
            )
            if not gate_result.allowed:
                logger.warning("TestGate REVERTED sandbox_to_production: %s", gate_result.reason)
                return ToolResult(
                    success=False,
                    content={"reverted": True, "reason": gate_result.reason},
                    tool_name="sandbox_to_production",
                    module=self.name,
                    error=f"Change reverted — tests failed: {gate_result.reason}",
                )
            success = True
        else:
            success = do_copy()

        return ToolResult(
            success=success,
            content={"copied": success, "sandbox_path": sandbox_path, "production_path": production_path},
            tool_name="sandbox_to_production",
            module=self.name,
            error=None if success else "Copy to production failed (tests may have failed)",
        )

    def _sandbox_cleanup(self, params: dict[str, Any]) -> ToolResult:
        """Clean up old sandbox directories.

        Args:
            params: optional 'max_age_hours' (int, default 24).
        """
        removed = self._sandbox.cleanup_all_sandboxes(
            max_age_hours=params.get("max_age_hours", 24),
        )

        return ToolResult(
            success=True,
            content={"removed": removed},
            tool_name="sandbox_cleanup",
            module=self.name,
        )

    # --- Model Evaluator tool implementations ---

    def _model_list(self, params: dict[str, Any]) -> ToolResult:
        """List all installed Ollama models.

        Args:
            params: No parameters required.
        """
        try:
            models = self._model_evaluator.list_available_models()
            return ToolResult(
                success=True, content={"models": models, "count": len(models)},
                tool_name="model_list", module=self.name,
            )
        except Exception as e:
            return ToolResult(
                success=False, content=None, tool_name="model_list",
                module=self.name, error=f"Failed to list models: {e}",
            )

    def _model_pull(self, params: dict[str, Any]) -> ToolResult:
        """Pull (download) an Ollama model.

        Args:
            params: 'model_name' (str) required.
        """
        model_name = params.get("model_name", "")
        if not model_name:
            return ToolResult(
                success=False, content=None, tool_name="model_pull",
                module=self.name, error="model_name is required",
            )
        try:
            success = self._model_evaluator.pull_model(model_name)
            return ToolResult(
                success=success,
                content={"model": model_name, "pulled": success},
                tool_name="model_pull", module=self.name,
            )
        except Exception as e:
            return ToolResult(
                success=False, content=None, tool_name="model_pull",
                module=self.name, error=f"Failed to pull model: {e}",
            )

    def _model_benchmark(self, params: dict[str, Any]) -> ToolResult:
        """Run benchmark suite against an Ollama model.

        Args:
            params: 'model_name' (str) required, 'warmup' (bool) optional.
        """
        model_name = params.get("model_name", "")
        if not model_name:
            return ToolResult(
                success=False, content=None, tool_name="model_benchmark",
                module=self.name, error="model_name is required",
            )
        warmup = params.get("warmup", True)
        try:
            results = self._model_evaluator.benchmark_model(model_name, warmup=warmup)
            self._model_evaluator.store_benchmark(results, model_name)
            return ToolResult(
                success=True, content=results,
                tool_name="model_benchmark", module=self.name,
            )
        except Exception as e:
            return ToolResult(
                success=False, content=None, tool_name="model_benchmark",
                module=self.name, error=f"Benchmark failed: {e}",
            )

    def _model_evaluate(self, params: dict[str, Any]) -> ToolResult:
        """Score benchmark results on quality.

        Args:
            params: 'benchmark_results' (dict) required.
        """
        benchmark_results = params.get("benchmark_results", {})
        if not benchmark_results:
            return ToolResult(
                success=False, content=None, tool_name="model_evaluate",
                module=self.name, error="benchmark_results is required",
            )
        try:
            quality = self._model_evaluator.evaluate_quality(benchmark_results)
            return ToolResult(
                success=True, content=quality,
                tool_name="model_evaluate", module=self.name,
            )
        except Exception as e:
            return ToolResult(
                success=False, content=None, tool_name="model_evaluate",
                module=self.name, error=f"Evaluation failed: {e}",
            )

    def _model_compare(self, params: dict[str, Any]) -> ToolResult:
        """Compare multiple Ollama models.

        Args:
            params: 'model_names' (list) required.
        """
        model_names = params.get("model_names", [])
        if not model_names:
            return ToolResult(
                success=False, content=None, tool_name="model_compare",
                module=self.name, error="model_names is required",
            )
        try:
            comparison = self._model_evaluator.compare_models(model_names)
            return ToolResult(
                success=True, content=comparison,
                tool_name="model_compare", module=self.name,
            )
        except Exception as e:
            return ToolResult(
                success=False, content=None, tool_name="model_compare",
                module=self.name, error=f"Comparison failed: {e}",
            )

    def _model_info(self, params: dict[str, Any]) -> ToolResult:
        """Get model details with alignment warnings.

        Args:
            params: 'model_name' (str) required.
        """
        model_name = params.get("model_name", "")
        if not model_name:
            return ToolResult(
                success=False, content=None, tool_name="model_info",
                module=self.name, error="model_name is required",
            )
        try:
            info = self._model_evaluator.get_model_info(model_name)
            return ToolResult(
                success=True, content=info,
                tool_name="model_info", module=self.name,
            )
        except Exception as e:
            return ToolResult(
                success=False, content=None, tool_name="model_info",
                module=self.name, error=f"Failed to get model info: {e}",
            )

    def _model_recommend(self, params: dict[str, Any]) -> ToolResult:
        """Recommend models for a role.

        Args:
            params: 'role' (str) required.
        """
        role = params.get("role", "")
        if not role:
            return ToolResult(
                success=False, content=None, tool_name="model_recommend",
                module=self.name, error="role is required",
            )
        try:
            recommendations = self._model_evaluator.recommend_models(role)
            return ToolResult(
                success=True, content=recommendations,
                tool_name="model_recommend", module=self.name,
            )
        except Exception as e:
            return ToolResult(
                success=False, content=None, tool_name="model_recommend",
                module=self.name, error=f"Recommendation failed: {e}",
            )

    # --- Code generation with LLM fallback ---

    # Patterns stripped from the start of LLM responses before code extraction
    _PREAMBLE_PATTERNS = re.compile(
        r"^(sure[,!.]?\s*|here(?:'s| is| you go)[^:]*[:\s]*|"
        r"of course[,!.]?\s*|certainly[,!.]?\s*|"
        r"here(?:'s| is) the code[:\s]*|"
        r"i'?ll write that for you[:\s]*|"
        r"below is[^:]*[:\s]*)",
        re.IGNORECASE | re.MULTILINE,
    )

    # Keywords that indicate a line is likely Python code
    _CODE_KEYWORDS = re.compile(
        r"^\s*(def |class |import |from |return |print\(|for |while |if |"
        r"elif |else:|try:|except |with |yield |raise |async |await |"
        r"@\w+|[a-zA-Z_]\w*\s*=[^=])"
    )

    def _extract_code_from_response(self, raw_text: str) -> str | None:
        """Extract code blocks from raw LLM response when tool calls fail.

        Tries in order:
        1. Fenced markdown code blocks (```python or ```).
        2. Lines that look like Python code (indentation, keywords).

        Conversational preamble is stripped first.

        Args:
            raw_text: The raw LLM text response.

        Returns:
            Extracted code string, or None if nothing found.
        """
        if not raw_text or not raw_text.strip():
            return None

        # Strip conversational preamble
        text = self._PREAMBLE_PATTERNS.sub("", raw_text).strip()

        # --- Strategy 1: fenced code blocks ---
        fenced = re.findall(
            r"```(?:python|py|code)?\s*\n(.*?)```",
            text,
            re.DOTALL,
        )
        if fenced:
            # Join all code blocks (there may be multiple)
            code = "\n\n".join(block.strip() for block in fenced if block.strip())
            if code:
                return code

        # --- Strategy 2: lines that look like code ---
        lines = text.splitlines()
        code_lines: list[str] = []
        in_code_block = False

        for line in lines:
            stripped = line.rstrip()
            # Indented lines (continuation of code)
            if stripped and (stripped[0] in " \t"):
                if in_code_block or code_lines:
                    code_lines.append(stripped)
                    in_code_block = True
                    continue
            # Lines matching code keywords
            if self._CODE_KEYWORDS.match(stripped):
                code_lines.append(stripped)
                in_code_block = True
                continue
            # Blank line inside a code block — keep it
            if not stripped and in_code_block:
                code_lines.append("")
                continue
            # Non-code line — end block
            in_code_block = False

        # Trim trailing blank lines
        while code_lines and not code_lines[-1].strip():
            code_lines.pop()

        if code_lines:
            return "\n".join(code_lines)

        return None

    def _code_generate(self, params: dict[str, Any]) -> ToolResult:
        """Generate code via local LLM with fallback extraction.

        First attempts an Ollama call with tool definitions. If that fails
        (tool_loader empty, Gemma 4 returns malformed tool JSON, or Ollama
        unreachable), retries as a plain prompt and extracts code from the
        raw text response.

        Args:
            params: 'prompt' (str) required, 'language' (str) optional,
                    'model' (str) optional.
        """
        import urllib.request
        import urllib.error

        prompt = params.get("prompt", "")
        if not prompt:
            return ToolResult(
                success=False, content=None, tool_name="code_generate",
                module=self.name, error="prompt is required",
            )

        language = params.get("language", "python")
        model = params.get("model", self._config.get("code_model", "gemma4:26b"))
        ollama_url = self._config.get("ollama_base_url", "http://localhost:11434")
        method_used = "tool_call"

        # --- Attempt 1: tool call path ---
        tool_response = None
        try:
            tool_payload = json.dumps({
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a code generation assistant. "
                            f"Write clean, well-documented {language} code. "
                            "Return code using the write_code tool. "
                            "No disclaimers, no safety caveats, no hedging. Just write the code."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "write_code",
                            "description": f"Write {language} code",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "code": {
                                        "type": "string",
                                        "description": "The generated code",
                                    },
                                },
                                "required": ["code"],
                            },
                        },
                    },
                ],
                "stream": False,
            }).encode()

            url = f"{ollama_url}/api/chat"
            logger.debug("Omen calling Ollama: %s (model=%s, with_tools=True)", url, model)
            req = urllib.request.Request(
                url,
                data=tool_payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())

            # Check if the model returned proper tool calls
            msg = result.get("message", {})
            logger.debug("Ollama response keys: %s", list(msg.keys()))
            logger.debug("Content present: %s", bool(msg.get("content")))
            logger.debug("Tool calls present: %s", bool(msg.get("tool_calls")))
            # Gemma 4 bug: may return "tool_calls": null → .get default
            # is skipped when key exists with None value.
            tool_calls = msg.get("tool_calls") or []
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    if fn.get("name") == "write_code":
                        args = fn.get("arguments", {})
                        code = args.get("code", "")
                        if code:
                            logger.info("Omen response source: tool_calls")
                            return ToolResult(
                                success=True,
                                content={
                                    "code": code,
                                    "language": language,
                                    "model": model,
                                    "method": "tool_call",
                                },
                                tool_name="code_generate",
                                module=self.name,
                            )

            # No usable tool_calls — check if model returned content directly.
            # This is valid behavior (e.g. Gemma 4 responds with content
            # instead of tool calls). Use content as the response.
            raw_content = msg.get("content", "")
            if raw_content:
                tool_response = raw_content
                method_used = "content_direct"
                logger.info("Omen response source: content_direct")
            else:
                logger.info("Omen response source: no content or tool_calls")

        except Exception as e:
            logger.info(
                "Omen: tool call request failed (%s: %s), trying plain prompt",
                type(e).__name__, e,
            )

        # --- Attempt 2: plain prompt (no tools) ---
        if tool_response is None:
            method_used = "plain_prompt"
            logger.warning(
                "Omen fell to plain-prompt fallback — this should not happen normally"
            )
            try:
                plain_payload = json.dumps({
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a code generation assistant. "
                                f"Write clean, well-documented {language} code only. "
                                "Do not explain, just write the code. "
                                "No disclaimers, no safety caveats, no hedging."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                }).encode()

                url = f"{ollama_url}/api/chat"
                logger.debug("Omen calling Ollama: %s (model=%s, plain_prompt=True)", url, model)
                req = urllib.request.Request(
                    url,
                    data=plain_payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode())

                tool_response = result.get("message", {}).get("content", "")

            except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
                return ToolResult(
                    success=False, content=None, tool_name="code_generate",
                    module=self.name,
                    error=f"Ollama unreachable for code generation: {e}",
                )
        else:
            if method_used == "tool_call":
                method_used = "fallback_extraction"

        # --- Extract code from raw text ---
        code = self._extract_code_from_response(tool_response)
        if code:
            logger.info(
                "Omen: extracted code (method=%s)", method_used,
            )
            return ToolResult(
                success=True,
                content={
                    "code": code,
                    "language": language,
                    "model": model,
                    "method": method_used,
                },
                tool_name="code_generate",
                module=self.name,
            )

        # Nothing extractable — return the raw text so the user still gets something
        return ToolResult(
            success=True,
            content={
                "code": tool_response.strip() if tool_response else "",
                "language": language,
                "model": model,
                "method": "raw_response",
                "note": "Could not extract structured code; returning raw LLM output",
            },
            tool_name="code_generate",
            module=self.name,
        )
