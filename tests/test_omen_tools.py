"""Tests for Omen code-aware tools: code_glob, code_grep, code_edit, code_read."""

from pathlib import Path

import pytest

from modules.omen.omen import Omen


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project structure for testing."""
    # Create Python files
    (tmp_path / "main.py").write_text("def main():\n    print('hello')\n", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def helper():\n    return 42\n", encoding="utf-8")

    # Create subdirectory with files
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "app.py").write_text("class App:\n    pass\n", encoding="utf-8")
    (sub / "data.txt").write_text("some data\n", encoding="utf-8")

    # Create __pycache__ dir with a .pyc file
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "main.cpython-312.pyc").write_bytes(b"\x00\x00")

    # Create a .git dir
    git = tmp_path / ".git"
    git.mkdir()
    (git / "config").write_text("[core]\n", encoding="utf-8")

    # Create a binary file
    (tmp_path / "data.db").write_bytes(b"\x00\x01\x02\x03")

    # Create config dir (protected)
    conf = tmp_path / "config"
    conf.mkdir()
    (conf / "settings.yaml").write_text("key: value\n", encoding="utf-8")

    return tmp_path


@pytest.fixture
def omen(temp_project):
    """Create an Omen instance rooted at temp_project."""
    return Omen(config={"project_root": str(temp_project)})


# --- code_glob tests ---

class TestCodeGlob:
    async def test_code_glob_finds_python(self, omen, temp_project):
        result = await omen.execute("code_glob", {"pattern": "**/*.py", "root_dir": str(temp_project)})
        assert result.success
        files = result.content["files"]
        assert any("main.py" in f for f in files)
        assert any("utils.py" in f for f in files)
        assert any("app.py" in f for f in files)

    async def test_code_glob_excludes_pycache(self, omen, temp_project):
        result = await omen.execute("code_glob", {"pattern": "**/*", "root_dir": str(temp_project)})
        assert result.success
        files = result.content["files"]
        for f in files:
            assert "__pycache__" not in f
            assert ".git" not in f

    async def test_code_glob_max_results(self, omen, tmp_path):
        """More than 500 files should be capped at MAX_GLOB_RESULTS."""
        for i in range(510):
            (tmp_path / f"file_{i:04d}.py").write_text(f"# file {i}\n", encoding="utf-8")

        result = await omen.execute("code_glob", {"pattern": "*.py", "root_dir": str(tmp_path)})
        assert result.success
        assert result.content["count"] <= 500
        assert result.content["capped"] is True

    async def test_code_glob_no_pattern(self, omen):
        result = await omen.execute("code_glob", {})
        assert not result.success
        assert "Pattern is required" in result.error

    async def test_code_glob_bad_dir(self, omen):
        result = await omen.execute("code_glob", {"pattern": "*.py", "root_dir": "/nonexistent_xyz"})
        assert not result.success


# --- code_grep tests ---

class TestCodeGrep:
    async def test_code_grep_finds_pattern(self, omen, temp_project):
        result = await omen.execute("code_grep", {
            "pattern": "def ",
            "file_glob": "**/*.py",
            "root_dir": str(temp_project),
        })
        assert result.success
        matches = result.content["matches"]
        assert len(matches) >= 2
        assert all("line_number" in m and "file" in m and "line" in m for m in matches)

    async def test_code_grep_regex(self, omen, temp_project):
        result = await omen.execute("code_grep", {
            "pattern": r"def \w+\(",
            "file_glob": "**/*.py",
            "root_dir": str(temp_project),
        })
        assert result.success
        assert result.content["count"] >= 2

    async def test_code_grep_skips_binary(self, omen, temp_project):
        result = await omen.execute("code_grep", {
            "pattern": ".*",
            "file_glob": "**/*",
            "root_dir": str(temp_project),
        })
        assert result.success
        files_searched = {m["file"] for m in result.content["matches"]}
        assert not any(f.endswith(".db") for f in files_searched)

    async def test_code_grep_max_results(self, omen, tmp_path):
        """Results should be capped at max_results."""
        lines = [f"match_line_{i}" for i in range(100)]
        (tmp_path / "many.py").write_text("\n".join(lines), encoding="utf-8")

        result = await omen.execute("code_grep", {
            "pattern": "match_line_",
            "file_glob": "**/*.py",
            "root_dir": str(tmp_path),
            "max_results": 5,
        })
        assert result.success
        assert result.content["count"] == 5
        assert result.content["capped"] is True

    async def test_code_grep_invalid_regex(self, omen, temp_project):
        result = await omen.execute("code_grep", {
            "pattern": "[invalid",
            "root_dir": str(temp_project),
        })
        assert not result.success
        assert "Invalid regex" in result.error

    async def test_code_grep_no_pattern(self, omen):
        result = await omen.execute("code_grep", {})
        assert not result.success


# --- code_edit tests ---

class TestCodeEdit:
    async def test_code_edit_success(self, omen, temp_project):
        target = temp_project / "main.py"
        result = await omen.execute("code_edit", {
            "file_path": str(target),
            "old_text": "def main():",
            "new_text": "def main_entry():",
        })
        assert result.success
        assert result.content["replacements"] == 1
        assert "def main_entry():" in target.read_text(encoding="utf-8")

    async def test_code_edit_no_match(self, omen, temp_project):
        target = temp_project / "main.py"
        result = await omen.execute("code_edit", {
            "file_path": str(target),
            "old_text": "this text does not exist",
            "new_text": "replacement",
        })
        assert not result.success
        assert "not found" in result.error

    async def test_code_edit_multiple_matches(self, omen, temp_project):
        target = temp_project / "dupe.py"
        target.write_text("x = 1\nx = 1\n", encoding="utf-8")
        result = await omen.execute("code_edit", {
            "file_path": str(target),
            "old_text": "x = 1",
            "new_text": "x = 2",
        })
        assert not result.success
        assert "2 times" in result.error
        # File should be unchanged
        assert target.read_text(encoding="utf-8") == "x = 1\nx = 1\n"

    async def test_code_edit_protected_path(self, omen, temp_project):
        target = temp_project / ".git" / "config"
        result = await omen.execute("code_edit", {
            "file_path": str(target),
            "old_text": "[core]",
            "new_text": "[modified]",
        })
        assert not result.success
        assert "Refused" in result.error or "protected" in result.error.lower()

    async def test_code_edit_protected_config(self, omen, temp_project):
        target = temp_project / "config" / "settings.yaml"
        result = await omen.execute("code_edit", {
            "file_path": str(target),
            "old_text": "key: value",
            "new_text": "key: modified",
        })
        assert not result.success
        assert "Refused" in result.error or "protected" in result.error.lower()

    async def test_code_edit_file_not_found(self, omen):
        result = await omen.execute("code_edit", {
            "file_path": "/nonexistent/file.py",
            "old_text": "a",
            "new_text": "b",
        })
        assert not result.success

    async def test_code_edit_missing_params(self, omen):
        result = await omen.execute("code_edit", {})
        assert not result.success


# --- code_read tests ---

class TestCodeRead:
    async def test_code_read_with_line_numbers(self, omen, temp_project):
        target = temp_project / "main.py"
        result = await omen.execute("code_read", {"file_path": str(target)})
        assert result.success
        content = result.content["content"]
        assert "1\tdef main():" in content
        assert "2\t    print('hello')" in content

    async def test_code_read_range(self, omen, temp_project):
        target = temp_project / "lines.py"
        target.write_text("\n".join(f"line_{i}" for i in range(1, 21)), encoding="utf-8")

        result = await omen.execute("code_read", {
            "file_path": str(target),
            "start_line": 5,
            "end_line": 10,
        })
        assert result.success
        content = result.content["content"]
        assert result.content["line_count"] == 6  # lines 5-10 inclusive
        assert "5\tline_5" in content
        assert "10\tline_10" in content
        assert "4\t" not in content
        assert "11\t" not in content

    async def test_code_read_file_too_large(self, omen, tmp_path):
        big_file = tmp_path / "big.txt"
        big_file.write_text("x" * (101 * 1024), encoding="utf-8")

        result = await omen.execute("code_read", {"file_path": str(big_file)})
        assert not result.success
        assert "too large" in result.error.lower() or "File too large" in result.error

    async def test_code_read_file_not_found(self, omen):
        result = await omen.execute("code_read", {"file_path": "/nonexistent/file.py"})
        assert not result.success

    async def test_code_read_no_path(self, omen):
        result = await omen.execute("code_read", {})
        assert not result.success

    async def test_code_read_total_lines(self, omen, temp_project):
        target = temp_project / "main.py"
        result = await omen.execute("code_read", {"file_path": str(target)})
        assert result.success
        assert result.content["total_lines"] >= 2
