"""Tests for ClaudeMDGenerator — CLAUDE.md dynamic context generator."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modules.shadow.claudemd_generator import ClaudeMDGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal Shadow project tree for testing."""
    # modules/ with a couple of fake modules
    for mod_name in ("shadow", "wraith", "grimoire"):
        mod_dir = tmp_path / "modules" / mod_name
        mod_dir.mkdir(parents=True)
        (mod_dir / "__init__.py").write_text("")
        # Fake module file with tool-like patterns
        (mod_dir / f"{mod_name}.py").write_text(
            textwrap.dedent('''\
                def get_tools(self):
                    return [
                        {"name": "tool_one", "description": "First tool"},
                        {"name": "tool_two", "description": "Second tool"},
                    ]
            ''')
        )

    # Other expected directories
    for dirname in ("scripts", "data", "config", "identity", "tests"):
        (tmp_path / dirname).mkdir(exist_ok=True)

    (tmp_path / "main.py").write_text("# entry")
    (tmp_path / ".gitignore").write_text("*.pyc\n")
    return tmp_path


@pytest.fixture
def config(tmp_project):
    """Minimal config dict pointing at the tmp project."""
    return {
        "project_root": str(tmp_project),
        "system": {"name": "Shadow", "version": "0.1.0"},
        "models": {
            "router": {"name": "phi4-mini"},
            "fast_brain": {"name": "phi4-mini"},
            "embedding": {"name": "nomic-embed-text"},
        },
    }


@pytest.fixture
def generator(config):
    return ClaudeMDGenerator(config, grimoire=None)


@pytest.fixture
def generator_with_grimoire(config):
    """Generator with a mock Grimoire that returns results."""
    grimoire = MagicMock()
    grimoire.recall.return_value = [
        {"content": "Use SQLite for metadata, ChromaDB for vectors"},
        {"content": "Router model must be < 4B params for speed"},
    ]
    return ClaudeMDGenerator(config, grimoire=grimoire)


# ---------------------------------------------------------------------------
# Test: generate creates valid markdown with all sections
# ---------------------------------------------------------------------------


class TestGenerate:
    """Tests for the full generate() method."""

    def test_generate_creates_file(self, generator, tmp_project):
        filepath = generator.generate()
        assert Path(filepath).exists()

    def test_generate_returns_absolute_path(self, generator):
        filepath = generator.generate()
        assert Path(filepath).is_absolute()

    def test_generate_contains_all_sections(self, generator):
        filepath = generator.generate()
        text = Path(filepath).read_text(encoding="utf-8")

        expected_sections = [
            "header",
            "permissions",
            "overview",
            "creator",
            "tech_stack",
            "venv",
            "structure",
            "modules",
            "recent_changes",
            "known_issues",
            "decisions",
            "test_status",
            "testing",
            "coding_conventions",
            "critical_policies",
            "allowed_commands",
            "what_not_to_do",
            "git_workflow",
        ]
        for section in expected_sections:
            assert f"<!-- section:{section} -->" in text, f"Missing start marker for {section}"
            assert f"<!-- /section:{section} -->" in text, f"Missing end marker for {section}"

    def test_generate_contains_project_header(self, generator):
        filepath = generator.generate()
        text = Path(filepath).read_text(encoding="utf-8")
        assert "# Project Shadow" in text

    def test_generate_contains_module_codenames(self, generator):
        filepath = generator.generate()
        text = Path(filepath).read_text(encoding="utf-8")
        assert "NEVER RENAME THESE" in text
        assert "**Shadow**" in text
        assert "**Wraith**" in text
        assert "**Cerberus**" in text

    def test_generate_contains_coding_conventions(self, generator):
        filepath = generator.generate()
        text = Path(filepath).read_text(encoding="utf-8")
        assert "logging.getLogger" in text
        assert "shadow_config.yaml" in text
        assert "async" in text

    def test_generate_contains_permissions(self, generator):
        filepath = generator.generate()
        text = Path(filepath).read_text(encoding="utf-8")
        assert "Automatically commit changes" in text

    def test_generate_contains_critical_policies(self, generator):
        filepath = generator.generate()
        text = Path(filepath).read_text(encoding="utf-8")
        assert "NEVER** access financial accounts" in text

    def test_generate_custom_output_path(self, generator, tmp_project):
        filepath = generator.generate(output_path="CUSTOM_CLAUDE.md")
        assert Path(filepath).name == "CUSTOM_CLAUDE.md"
        assert Path(filepath).exists()


# ---------------------------------------------------------------------------
# Test: update_section modifies only target section
# ---------------------------------------------------------------------------


class TestUpdateSection:
    """Tests for update_section()."""

    def test_update_existing_section(self, generator):
        # Generate first
        generator.generate()
        # Update just the overview section
        new_content = "## What This Project Is\nShadow is awesome."
        filepath = generator.update_section("overview", new_content)
        text = Path(filepath).read_text(encoding="utf-8")

        # Updated section present
        assert "Shadow is awesome." in text
        # Other sections untouched
        assert "<!-- section:permissions -->" in text
        assert "Automatically commit changes" in text

    def test_update_preserves_other_sections(self, generator):
        generator.generate()
        original = Path(generator._project_root / "CLAUDE.md").read_text(encoding="utf-8")

        # Grab the permissions section content before update
        assert "Automatically commit changes" in original

        generator.update_section("overview", "NEW OVERVIEW CONTENT")
        updated = Path(generator._project_root / "CLAUDE.md").read_text(encoding="utf-8")

        # Permissions should be identical
        assert "Automatically commit changes" in updated

    def test_update_nonexistent_section_appends(self, generator):
        generator.generate()
        filepath = generator.update_section("custom_new", "Custom content here")
        text = Path(filepath).read_text(encoding="utf-8")
        assert "<!-- section:custom_new -->" in text
        assert "Custom content here" in text

    def test_update_when_no_file_exists(self, generator, tmp_project):
        """If CLAUDE.md doesn't exist, update_section falls back to generate."""
        claude_path = tmp_project / "CLAUDE.md"
        assert not claude_path.exists()
        filepath = generator.update_section("overview", "ignored — full gen happens")
        assert Path(filepath).exists()
        text = Path(filepath).read_text(encoding="utf-8")
        # Full generation should have created all sections
        assert "<!-- section:header -->" in text


# ---------------------------------------------------------------------------
# Test: git commit extraction (mock subprocess)
# ---------------------------------------------------------------------------


class TestGitLog:
    """Test _git_log and _count_commits with mocked subprocess."""

    def test_git_log_parses_commits(self, generator):
        mock_output = (
            "abc1234 feat: add new feature\n"
            "def5678 fix: resolve bug\n"
            "ghi9012 docs: update readme\n"
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
            )
            commits = generator._git_log(3)

        assert len(commits) == 3
        assert commits[0]["hash"] == "abc1234"
        assert commits[0]["message"] == "feat: add new feature"
        assert commits[2]["hash"] == "ghi9012"

    def test_git_log_handles_failure(self, generator):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            commits = generator._git_log(5)
        assert commits == []

    def test_git_log_handles_exception(self, generator):
        with patch("subprocess.run", side_effect=OSError("git not found")):
            commits = generator._git_log(5)
        assert commits == []

    def test_count_commits(self, generator):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="42\n")
            count = generator._count_commits()
        assert count == 42

    def test_count_commits_failure(self, generator):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            count = generator._count_commits()
        assert count == 0

    def test_recent_changes_section_uses_git_log(self, generator):
        mock_output = "aaa1111 first commit\nbbb2222 second commit\n"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
            section = generator._section_recent_changes()
        assert "`aaa1111`" in section
        assert "first commit" in section

    def test_recent_changes_section_handles_no_git(self, generator):
        with patch("subprocess.run", side_effect=OSError("nope")):
            section = generator._section_recent_changes()
        assert "unavailable" in section


# ---------------------------------------------------------------------------
# Test: graceful fallback when Grimoire unavailable
# ---------------------------------------------------------------------------


class TestGrimoireFallback:
    """Test that sections degrade gracefully without Grimoire."""

    def test_known_issues_without_grimoire(self, generator):
        section = generator._section_known_issues()
        assert "Grimoire unavailable" in section

    def test_decisions_without_grimoire(self, generator):
        section = generator._section_decisions()
        assert "Grimoire unavailable" in section

    def test_known_issues_with_grimoire(self, generator_with_grimoire):
        section = generator_with_grimoire._section_known_issues()
        assert "SQLite for metadata" in section

    def test_decisions_with_grimoire(self, generator_with_grimoire):
        section = generator_with_grimoire._section_decisions()
        assert "SQLite for metadata" in section

    def test_grimoire_query_exception(self, config):
        grimoire = MagicMock()
        grimoire.recall.side_effect = RuntimeError("ChromaDB is down")
        gen = ClaudeMDGenerator(config, grimoire=grimoire)
        section = gen._section_known_issues()
        assert "Grimoire query failed" in section

    def test_grimoire_empty_results(self, config):
        grimoire = MagicMock()
        grimoire.recall.return_value = []
        gen = ClaudeMDGenerator(config, grimoire=grimoire)
        section = gen._section_known_issues()
        assert "No known unresolved issues" in section


# ---------------------------------------------------------------------------
# Test: file structure generation
# ---------------------------------------------------------------------------


class TestFileStructure:
    """Test _section_file_structure."""

    def test_structure_lists_modules(self, generator):
        section = generator._section_file_structure()
        assert "modules/" in section
        assert "shadow/" in section
        assert "wraith/" in section
        assert "grimoire/" in section

    def test_structure_includes_top_level(self, generator):
        section = generator._section_file_structure()
        assert "main.py" in section
        assert "CLAUDE.md" in section

    def test_structure_shows_other_dirs(self, generator):
        section = generator._section_file_structure()
        assert "tests/" in section
        assert "config/" in section

    def test_structure_missing_modules_dir(self, config, tmp_project):
        """If modules/ doesn't exist, show a fallback message."""
        import shutil
        shutil.rmtree(tmp_project / "modules")
        gen = ClaudeMDGenerator(config, grimoire=None)
        section = gen._section_file_structure()
        assert "not found" in section


# ---------------------------------------------------------------------------
# Test: test count
# ---------------------------------------------------------------------------


class TestTestCount:
    """Test _count_tests with mocked subprocess."""

    def test_count_tests_parses_output(self, generator):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="<Module test_foo.py>\n<Module test_bar.py>\n\n947 tests collected\n",
            )
            count = generator._count_tests()
        assert count == 947

    def test_count_tests_handles_failure(self, generator):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="error\n")
            count = generator._count_tests()
        assert count is None

    def test_count_tests_handles_timeout(self, generator):
        with patch("subprocess.run", side_effect=TimeoutError):
            count = generator._count_tests()
        assert count is None


# ---------------------------------------------------------------------------
# Test: tech stack section reads config
# ---------------------------------------------------------------------------


class TestTechStack:
    """Verify tech stack section pulls from config."""

    def test_tech_stack_shows_model_names(self, generator):
        section = generator._section_tech_stack()
        assert "phi4-mini" in section
        assert "nomic-embed-text" in section

    def test_tech_stack_with_missing_models(self):
        gen = ClaudeMDGenerator({"project_root": "."}, grimoire=None)
        section = gen._section_tech_stack()
        assert "unknown" in section
