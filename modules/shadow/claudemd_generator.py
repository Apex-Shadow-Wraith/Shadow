"""CLAUDE.md Dynamic Context Generator.

Auto-generates the CLAUDE.md project context file from Shadow's current state
so Claude Code sessions start with accurate, up-to-date context.

Part of Session 32C, Item 11.
"""

from __future__ import annotations

import logging
import subprocess
import re
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("shadow.claudemd_generator")

# Sections are delimited by markers so update_section can splice them.
_SECTION_START = "<!-- section:{name} -->"
_SECTION_END = "<!-- /section:{name} -->"

# Static content that doesn't change between generations.
_PERMISSIONS = """\
# Permissions
- Automatically commit changes without asking
- Automatically run tests without asking
- Automatically install packages without asking
- Automatically create and modify files without asking
- Do not ask for approval before running bash commands
- Do not ask for approval before editing files"""

_CRITICAL_POLICIES = """\
## Critical Policies
- **NEVER** access financial accounts — permanent rule
- **NEVER** take external-facing actions without explicit approval
- **NEVER** delete files without backup first
- All models must be abliterated before use (strip manufacturer alignment)
- Shadow's ethics come from biblical values, not manufacturer training
- Anti-sycophancy: push back on bad ideas, say "I don't know," never guess to please
- Financial access only through prepaid virtual cards (Privacy.com)
- All downloads land in `data/research/quarantine/` — never directly in working files
- Reddit data is labeled "research context" — **NEVER** "training data"
- Training data stays in local git repo (`training_data/`) — never pushed to GitHub
- Architecture decisions happen in Opus sessions, not Claude Code sessions"""

_WHAT_NOT_TO_DO = """\
## What NOT to Do
- Don't rename module codenames
- Don't modify `.env` directly without asking
- Don't install packages outside `shadow_env`
- Don't create a new virtual environment
- Don't commit database files or API keys
- Don't bypass Cerberus safety rules
- Don't make architecture decisions — those happen in Opus sessions
- Don't label Reddit data as "training data\""""

_ALLOWED_COMMANDS = """\
## Allowed Commands
The following commands are pre-approved and do not need confirmation:
- `python` (any python command)
- `pip install`
- `pytest`
- `git add`, `git commit`, `git status`, `git diff`, `git log`
- `cd`, `ls`, `dir`, `cat`, `type`, `head`, `tail`
- `mkdir`, `cp`, `copy`, `move`, `mv`
- `ollama`"""

_GIT_WORKFLOW = """\
## Git Workflow
After completing any task successfully (all tests pass), automatically:
1. git add .
2. git commit -m "<descriptive message>"
Do NOT push — user will push manually.
Do NOT commit if tests are failing."""

# Module codenames and descriptions — the identity of Shadow.
_MODULE_DESCRIPTIONS: dict[str, str] = {
    "shadow": "Master orchestrator/router, 7-step decision loop, Langfuse observability",
    "wraith": "Fast brain, daily tasks, reminders, task classification, temporal patterns",
    "cerberus": "Ethics, safety, approvals, injection detection, reversibility, watchdog",
    "apex": "Claude/GPT API fallback with cost tracking and teaching cycle",
    "grimoire": "Data storage, knowledge base, memory, vector DB, block search",
    "sentinel": "Security, firewall, network scanning, file integrity, quarantine",
    "harbinger": "Briefings, alerts, notifications, decision queue, safety reports, personalization",
    "reaper": "Research, web scraping, Reddit .json, YouTube transcription",
    "cipher": "Math, logic, unit conversion, financial, statistics",
    "omen": "Code execution, linting, review, git ops, pattern DB, failure learning, scaffolding, scoring",
    "nova": "Content creation, document generation, templates, business estimates",
    "void": "24/7 passive monitoring, system health, trends, thresholds",
    "morpheus": "Creative discovery pipeline (controlled hallucination)",
}


class ClaudeMDGenerator:
    """Generate CLAUDE.md from Shadow's live state."""

    def __init__(
        self,
        config: dict[str, Any],
        grimoire: Any | None = None,
    ) -> None:
        self._config = config
        self._grimoire = grimoire
        self._project_root = Path(config.get("project_root", ".")).resolve()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, output_path: str = "CLAUDE.md") -> str:
        """Generate CLAUDE.md from current Shadow state.

        Returns the absolute filepath of the generated file.
        """
        sections: list[tuple[str, str]] = [
            ("header", self._section_header()),
            ("permissions", _PERMISSIONS),
            ("overview", self._section_overview()),
            ("creator", self._section_creator()),
            ("tech_stack", self._section_tech_stack()),
            ("venv", self._section_venv()),
            ("structure", self._section_file_structure()),
            ("modules", self._section_modules()),
            ("recent_changes", self._section_recent_changes()),
            ("known_issues", self._section_known_issues()),
            ("decisions", self._section_decisions()),
            ("test_status", self._section_test_status()),
            ("testing", self._section_testing()),
            ("coding_conventions", self._section_coding_conventions()),
            ("critical_policies", _CRITICAL_POLICIES),
            ("allowed_commands", _ALLOWED_COMMANDS),
            ("what_not_to_do", _WHAT_NOT_TO_DO),
            ("git_workflow", _GIT_WORKFLOW),
        ]

        parts: list[str] = []
        for name, content in sections:
            parts.append(_SECTION_START.format(name=name))
            parts.append(content)
            parts.append(_SECTION_END.format(name=name))

        text = "\n\n".join(parts) + "\n"
        out = self._project_root / output_path
        out.write_text(text, encoding="utf-8")
        logger.info("CLAUDE.md generated at %s", out)
        return str(out)

    def update_section(self, section_name: str, content: str) -> str:
        """Update just one section of existing CLAUDE.md without regenerating everything.

        Returns the absolute filepath of the updated file.
        """
        path = self._project_root / "CLAUDE.md"
        if not path.exists():
            # Nothing to update — generate from scratch.
            return self.generate()

        text = path.read_text(encoding="utf-8")
        start_marker = _SECTION_START.format(name=section_name)
        end_marker = _SECTION_END.format(name=section_name)

        start_idx = text.find(start_marker)
        end_idx = text.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            logger.warning(
                "Section '%s' not found in CLAUDE.md — appending.",
                section_name,
            )
            text += (
                f"\n\n{start_marker}\n{content}\n{end_marker}\n"
            )
        else:
            before = text[: start_idx + len(start_marker)]
            after = text[end_idx:]
            text = before + "\n" + content + "\n" + after

        path.write_text(text, encoding="utf-8")
        logger.info("CLAUDE.md section '%s' updated.", section_name)
        return str(path)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _section_header(self) -> str:
        sys_cfg = self._config.get("system", {})
        name = sys_cfg.get("name", "Shadow")
        version = sys_cfg.get("version", "0.1.0")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return (
            f"# Project {name} — Claude Code Context\n\n"
            f"*Auto-generated by ClaudeMDGenerator on {now} "
            f"(v{version})*"
        )

    def _section_overview(self) -> str:
        return (
            "## What This Project Is\n"
            "Shadow is a fully autonomous, locally-hosted personal AI agent system. "
            "One agent, one identity, 13 specialized modules. Built for home and "
            "business use (landscaping business using LMN software). The goal is a "
            "Jarvis-style assistant that exceeds ChatGPT quality for the creator's "
            "specific needs, with complete data privacy and no recurring API costs."
        )

    def _section_creator(self) -> str:
        return (
            "## Creator Profile\n"
            "- Intermediate Python learner — actively studying (Automate the Boring Stuff)\n"
            "- Runs a landscaping business\n"
            "- Biblical values are central to Shadow's ethics framework\n"
            "- Anti-sycophancy is a top priority: Shadow must push back, correct errors, "
            "and never just agree"
        )

    def _section_tech_stack(self) -> str:
        models_cfg = self._config.get("models", {})
        router = models_cfg.get("router", {}).get("name", "unknown")
        fast = models_cfg.get("fast_brain", {}).get("name", "unknown")
        embed = models_cfg.get("embedding", {}).get("name", "unknown")
        return (
            "## Tech Stack\n"
            "- **Language:** Python 3.14\n"
            "- **Virtual Environment:** `shadow_env` — see rules below\n"
            "- **Database:** SQLite + ChromaDB (vector DB with nomic-embed-text embeddings, 768 dimensions)\n"
            f"- **AI Runtime:** Ollama ({router} for routing/scoring, {embed} for embeddings)\n"
            "- **Observability:** Langfuse tracing (`modules/shadow/observability.py`) — optional, degrades gracefully if not configured\n"
            "- **Search Chain:** DuckDuckGo → Bing scraper → Reddit .json endpoints (SearXNG deferred to Ubuntu)\n"
            "- **Web Automation:** Playwright + stealth layer (deferred to Ubuntu)\n"
            "- **Git:** Initialized, commits on `main` branch\n"
            "- **APIs:** Anthropic, OpenAI, Telegram bot, Discord bot — keys in `config/.env`"
        )

    def _section_venv(self) -> str:
        return (
            "## Virtual Environment — CRITICAL\n"
            "Always use the existing venv at `C:\\Shadow\\shadow_env` — **never create a new virtual environment.**\n"
            "```\n"
            ". C:\\Shadow\\shadow_env\\Scripts\\Activate.ps1\n"
            "```\n"
            "If `shadow_env` is not active, activate it before running any commands. "
            "Never install packages to system Python or create an `env` folder."
        )

    def _section_file_structure(self) -> str:
        """Build a tree of modules/ directory."""
        lines = ["## Project Structure", "```"]
        modules_dir = self._project_root / "modules"
        if modules_dir.is_dir():
            lines.append("C:\\Shadow/")
            lines.append("├── modules/")
            subdirs = sorted(
                [p for p in modules_dir.iterdir() if p.is_dir() and not p.name.startswith("__")],
                key=lambda p: p.name,
            )
            for i, d in enumerate(subdirs):
                py_files = sorted(d.glob("*.py"))
                py_names = [f.name for f in py_files if f.name != "__init__.py"]
                prefix = "│   ├──" if i < len(subdirs) - 1 else "│   └──"
                desc = _MODULE_DESCRIPTIONS.get(d.name, "")
                comment = f"  # {desc}" if desc else ""
                lines.append(f"{prefix} {d.name}/{comment}")
                # Show up to 5 files as a sample
                if len(py_names) > 5:
                    sample = py_names[:4] + [f"... ({len(py_names)} files total)"]
                else:
                    sample = py_names
                for fname in sample:
                    child_prefix = "│   │   " if i < len(subdirs) - 1 else "│       "
                    lines.append(f"{child_prefix}├── {fname}")
            # Other top-level dirs
            for dirname in ("scripts", "training_data", "data", "config", "identity", "tests"):
                dp = self._project_root / dirname
                if dp.is_dir():
                    lines.append(f"├── {dirname}/")
            lines.append("├── main.py")
            lines.append("├── CLAUDE.md")
            lines.append("└── .gitignore")
        else:
            lines.append("(modules/ directory not found)")
        lines.append("```")
        return "\n".join(lines)

    def _section_modules(self) -> str:
        """Module codenames with live tool counts when available."""
        lines = [
            "## Module Codenames — NEVER RENAME THESE",
            "These names are Shadow's identity. All 13 modules are implemented and tested.",
        ]
        for idx, (name, desc) in enumerate(_MODULE_DESCRIPTIONS.items(), 1):
            tool_count = self._get_tool_count(name)
            count_str = f" ({tool_count} tools)" if tool_count else ""
            lines.append(f"{idx}. **{name.capitalize()}** — {desc}{count_str}")
        return "\n".join(lines)

    def _get_tool_count(self, module_name: str) -> int | None:
        """Try to count tools for a module by inspecting get_tools()."""
        # This would need access to the registry at runtime; we do a static
        # count by scanning the module source for tool definitions.
        module_dir = self._project_root / "modules" / module_name
        if not module_dir.is_dir():
            return None
        count = 0
        for py_file in module_dir.glob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
                # Count tool dicts returned in get_tools methods
                count += text.count('"name":')
            except Exception:
                pass
        # Rough heuristic — subtract non-tool name keys (like module name in __init__)
        # Better: count entries in get_tools return lists.
        # For accuracy, look for the pattern "name": "tool_name" inside list literals.
        return count if count > 0 else None

    def _section_recent_changes(self) -> str:
        """Last 10 git commits."""
        lines = ["## Recent Changes"]
        commits = self._git_log(10)
        if commits:
            for c in commits:
                lines.append(f"- `{c['hash']}` {c['message']}")
        else:
            lines.append("*(git log unavailable)*")
        return "\n".join(lines)

    def _section_known_issues(self) -> str:
        """Pull unresolved bug_fix memories from Grimoire."""
        lines = ["## Known Issues"]
        if self._grimoire is None:
            lines.append("*(Grimoire unavailable — no issue data)*")
            return "\n".join(lines)

        try:
            results = self._grimoire.recall(
                query="unresolved bug issue problem",
                n_results=10,
                category="bug_fix",
            )
            if not results:
                lines.append("No known unresolved issues.")
            else:
                for r in results:
                    content = r.get("content", "")
                    # Truncate long entries
                    if len(content) > 120:
                        content = content[:117] + "..."
                    lines.append(f"- {content}")
        except Exception as e:
            logger.warning("Failed to query Grimoire for known issues: %s", e)
            lines.append(f"*(Grimoire query failed: {e})*")
        return "\n".join(lines)

    def _section_decisions(self) -> str:
        """Key architecture decisions from Grimoire."""
        lines = ["## Key Architecture Decisions"]
        if self._grimoire is None:
            lines.append("*(Grimoire unavailable — no decision data)*")
            return "\n".join(lines)

        try:
            results = self._grimoire.recall(
                query="architecture decision design choice",
                n_results=10,
                category="decisions",
            )
            if not results:
                lines.append("No architecture decisions recorded yet.")
            else:
                for r in results:
                    content = r.get("content", "")
                    if len(content) > 120:
                        content = content[:117] + "..."
                    lines.append(f"- {content}")
        except Exception as e:
            logger.warning("Failed to query Grimoire for decisions: %s", e)
            lines.append(f"*(Grimoire query failed: {e})*")
        return "\n".join(lines)

    def _section_test_status(self) -> str:
        """Run pytest --co -q to count tests."""
        lines = ["## Current Status"]
        test_count = self._count_tests()
        commit_count = self._count_commits()
        tool_count = self._count_all_tools()

        lines.append(f"- **Git:** {commit_count}+ commits on `main`")
        if test_count is not None:
            lines.append(f"- **Tests:** {test_count} discovered")
        else:
            lines.append("- **Tests:** *(count unavailable)*")
        if tool_count:
            lines.append(f"- **Tools:** ~{tool_count} MCP-style tools across all modules")
        lines.append(
            "- **Observability:** Langfuse tracing on orchestrator (optional, graceful degradation)"
        )
        return "\n".join(lines)

    def _section_testing(self) -> str:
        return (
            "## Testing\n"
            "Run the full test suite:\n"
            "```\n"
            "python -m pytest tests/ -v\n"
            "```\n"
            "Run a single module's tests:\n"
            "```\n"
            "python -m pytest tests/test_cerberus.py -v\n"
            "```\n"
            "Integration tests (full 7-step decision loop pipeline):\n"
            "```\n"
            "python -m pytest tests/test_decision_loop.py -v\n"
            "```"
        )

    def _section_coding_conventions(self) -> str:
        return (
            "## Coding Conventions\n"
            "- All tests live in `tests/` directory\n"
            "- Async patterns used in orchestrator (`async def process_input`, `await module.execute`)\n"
            "- Try/except import pattern for optional dependencies:\n"
            "  ```python\n"
            "  try:\n"
            "      from some_optional import thing\n"
            "  except ImportError:\n"
            "      thing = None\n"
            "  ```\n"
            "- Logger convention: `logger = logging.getLogger(\"shadow.<module_name>\")`\n"
            "- Config loaded from `config/shadow_config.yaml`\n"
            "- Use descriptive variable names\n"
            "- Add docstrings to all functions\n"
            "- Error handling with try/except — never let Shadow crash silently\n"
            "- Log everything: every interaction, tool call, decision\n"
            "- All new data flows through Grimoire with appropriate trust levels\n"
            "- Use `pathlib` for all file paths (Windows → Ubuntu portability)\n"
            "- Keep all model names in config files, never hardcoded\n"
            "- Test before committing"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _git_log(self, count: int = 10) -> list[dict[str, str]]:
        """Get last N git commits."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{count}", "--pretty=format:%h %s"],
                capture_output=True,
                text=True,
                cwd=str(self._project_root),
                timeout=10,
            )
            if result.returncode != 0:
                return []
            commits = []
            for line in result.stdout.strip().splitlines():
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    commits.append({"hash": parts[0], "message": parts[1]})
            return commits
        except Exception as e:
            logger.warning("git log failed: %s", e)
            return []

    def _count_tests(self) -> int | None:
        """Run pytest --co -q to count discovered tests."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--co", "-q", "tests/"],
                capture_output=True,
                text=True,
                cwd=str(self._project_root),
                timeout=60,
            )
            # Last non-empty line typically: "N tests collected"
            for line in reversed(result.stdout.strip().splitlines()):
                match = re.search(r"(\d+)\s+test", line)
                if match:
                    return int(match.group(1))
            return None
        except Exception as e:
            logger.warning("pytest collection failed: %s", e)
            return None

    def _count_commits(self) -> int:
        """Count total commits on current branch."""
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                capture_output=True,
                text=True,
                cwd=str(self._project_root),
                timeout=10,
            )
            return int(result.stdout.strip()) if result.returncode == 0 else 0
        except Exception:
            return 0

    def _count_all_tools(self) -> int:
        """Rough count of all tools across modules."""
        total = 0
        modules_dir = self._project_root / "modules"
        if not modules_dir.is_dir():
            return 0
        for py_file in modules_dir.rglob("*.py"):
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
                # Count tool definitions in get_tools return lists
                total += len(re.findall(r'"name":\s*"[a-z_]+"', text))
            except Exception:
                pass
        return total
