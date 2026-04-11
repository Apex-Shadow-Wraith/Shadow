"""
Tests for Omen's Code Analyzer & Learning Pipeline
=====================================================
Covers file analysis, directory analysis, pattern detection,
learning extraction, Grimoire storage, and comparison.
"""

import pytest
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.omen.code_analyzer import CodeAnalyzer


@pytest.fixture
def analyzer(tmp_path: Path) -> CodeAnalyzer:
    """Create a CodeAnalyzer with temp samples dir."""
    return CodeAnalyzer(
        grimoire=None,
        samples_dir=str(tmp_path / "code_samples"),
    )


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a sample Python file for analysis."""
    code = textwrap.dedent('''\
        """Sample module for testing."""

        import os
        import json
        from pathlib import Path
        from typing import Any

        import requests


        class MyBase:
            """Base class."""

            def __init__(self, name: str) -> None:
                """Initialize."""
                self.name = name

            def process(self, data: dict[str, Any]) -> dict:
                """Process data."""
                try:
                    result = json.loads(json.dumps(data))
                    return result
                except (TypeError, ValueError) as e:
                    raise ValueError(f"Bad data: {e}")


        class MyChild(MyBase):
            """Child class with extra features."""

            def __init__(self, name: str, items: list[str] | None = None) -> None:
                """Initialize child."""
                super().__init__(name)
                self.items = items or []

            def get_names(self) -> list[str]:
                """Get uppercase names."""
                return [item.upper() for item in self.items]

            def save(self, path: str) -> None:
                """Save items to file."""
                with open(path, "w") as f:
                    json.dump(self.items, f)


        def create_processor(kind: str) -> MyBase:
            """Factory function."""
            if kind == "base":
                return MyBase("base")
            elif kind == "child":
                return MyChild("child")
            else:
                return MyBase("default")
    ''')
    p = tmp_path / "sample.py"
    p.write_text(code, encoding="utf-8")
    return p


@pytest.fixture
def singleton_file(tmp_path: Path) -> Path:
    """Create a file with a singleton pattern."""
    code = textwrap.dedent('''\
        """Singleton example."""


        class Database:
            """Database singleton."""

            _instance = None

            def __new__(cls):
                """Create or return singleton instance."""
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                return cls._instance

            def __init__(self):
                """Initialize database."""
                self.connected = False

            def connect(self) -> None:
                """Connect to database."""
                self.connected = True
    ''')
    p = tmp_path / "singleton.py"
    p.write_text(code, encoding="utf-8")
    return p


@pytest.fixture
def multi_file_dir(tmp_path: Path) -> Path:
    """Create a directory with multiple Python files."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()

    (pkg / "good.py").write_text(textwrap.dedent('''\
        """Well-documented module."""

        from typing import Any


        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b


        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b
    '''), encoding="utf-8")

    (pkg / "bad.py").write_text(textwrap.dedent('''\
        import os
        import sys

        def foo(x):
            return x + 1

        def bar(y):
            return y * 2

        def baz(z):
            return z - 1
    '''), encoding="utf-8")

    (pkg / "__init__.py").write_text("", encoding="utf-8")
    return pkg


# =============================================================================
# File Analysis
# =============================================================================

class TestAnalyzeFile:
    def test_extracts_classes(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        assert result["error"] is None
        classes = result["structure"]["classes"]
        class_names = [c["name"] for c in classes]
        assert "MyBase" in class_names
        assert "MyChild" in class_names

    def test_extracts_functions(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        functions = result["structure"]["functions"]
        func_names = [f["name"] for f in functions]
        assert "create_processor" in func_names

    def test_extracts_imports(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        imports = result["structure"]["imports"]
        assert "os" in imports
        assert "json" in imports

    def test_extracts_inheritance(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        inheritance = result["structure"]["inheritance"]
        child_entry = next(
            (e for e in inheritance if e["class"] == "MyChild"), None
        )
        assert child_entry is not None
        assert "MyBase" in child_entry["bases"]

    def test_extracts_decorators(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        # sample_file has no decorators at top level
        assert isinstance(result["structure"]["decorators"], list)

    def test_file_not_found(self, analyzer: CodeAnalyzer):
        result = analyzer.analyze_file("/nonexistent/file.py")
        assert result["error"] is not None
        assert "not found" in result["error"].lower()

    def test_syntax_error(self, analyzer: CodeAnalyzer, tmp_path: Path):
        bad = tmp_path / "bad.py"
        bad.write_text("def foo(:\n  pass\n", encoding="utf-8")
        result = analyzer.analyze_file(str(bad))
        assert result["error"] is not None
        assert "syntax" in result["error"].lower()


# =============================================================================
# Pattern Detection
# =============================================================================

class TestPatternDetection:
    def test_detects_singleton(self, analyzer: CodeAnalyzer, singleton_file: Path):
        result = analyzer.analyze_file(str(singleton_file))
        detected = result["patterns"]["detected"]
        assert "singleton" in detected

    def test_detects_factory(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        detected = result["patterns"]["detected"]
        assert "factory" in detected

    def test_detects_observer(self, analyzer: CodeAnalyzer, tmp_path: Path):
        code = textwrap.dedent('''\
            """Observer pattern."""

            class EventBus:
                """Event bus with subscribe/notify."""

                def __init__(self):
                    self.listeners = []

                def subscribe(self, listener):
                    """Add a listener."""
                    self.listeners.append(listener)

                def notify(self, event):
                    """Notify all listeners."""
                    for listener in self.listeners:
                        listener(event)
        ''')
        p = tmp_path / "observer.py"
        p.write_text(code, encoding="utf-8")
        result = analyzer.analyze_file(str(p))
        assert "observer" in result["patterns"]["detected"]

    def test_detects_decorator_pattern(self, analyzer: CodeAnalyzer, tmp_path: Path):
        code = textwrap.dedent('''\
            """Decorator pattern."""

            def my_decorator(func):
                """Wrap a function."""
                def wrapper(*args, **kwargs):
                    print("before")
                    result = func(*args, **kwargs)
                    print("after")
                    return result
                return wrapper
        ''')
        p = tmp_path / "dec.py"
        p.write_text(code, encoding="utf-8")
        result = analyzer.analyze_file(str(p))
        assert "decorator" in result["patterns"]["detected"]

    def test_pattern_examples_populated(
        self, analyzer: CodeAnalyzer, singleton_file: Path
    ):
        result = analyzer.analyze_file(str(singleton_file))
        examples = result["patterns"]["examples"]
        assert "singleton" in examples
        assert len(examples["singleton"]) > 0


# =============================================================================
# Techniques
# =============================================================================

class TestTechniqueDetection:
    def test_list_comprehensions(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        assert result["techniques"]["list_comprehensions"] is True

    def test_context_managers(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        assert result["techniques"]["context_managers"] is True

    def test_type_hints(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        assert result["techniques"]["type_hints"] is True

    def test_generators_detected(self, analyzer: CodeAnalyzer, tmp_path: Path):
        code = textwrap.dedent('''\
            def gen():
                yield 1
                yield 2
        ''')
        p = tmp_path / "gen.py"
        p.write_text(code, encoding="utf-8")
        result = analyzer.analyze_file(str(p))
        assert result["techniques"]["generators"] is True

    def test_async_detected(self, analyzer: CodeAnalyzer, tmp_path: Path):
        code = textwrap.dedent('''\
            import asyncio

            async def fetch():
                await asyncio.sleep(1)
        ''')
        p = tmp_path / "async_ex.py"
        p.write_text(code, encoding="utf-8")
        result = analyzer.analyze_file(str(p))
        assert result["techniques"]["async_await"] is True

    def test_dataclass_detected(self, analyzer: CodeAnalyzer, tmp_path: Path):
        code = textwrap.dedent('''\
            from dataclasses import dataclass

            @dataclass
            class Point:
                x: int
                y: int
        ''')
        p = tmp_path / "dc.py"
        p.write_text(code, encoding="utf-8")
        result = analyzer.analyze_file(str(p))
        assert result["techniques"]["dataclasses"] is True


# =============================================================================
# Complexity
# =============================================================================

class TestComplexity:
    def test_function_count(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        # MyBase: __init__, process; MyChild: __init__, get_names, save;
        # top-level: create_processor = 6
        assert result["complexity"]["function_count"] == 6

    def test_avg_lines_per_function(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        assert result["complexity"]["avg_lines_per_function"] > 0

    def test_nesting_depth(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        assert result["complexity"]["max_nesting_depth"] >= 1

    def test_class_count(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        assert result["complexity"]["class_count"] == 2


# =============================================================================
# Dependencies
# =============================================================================

class TestDependencies:
    def test_stdlib_detected(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        deps = result["dependencies"]
        assert "os" in deps["stdlib"]
        assert "json" in deps["stdlib"]
        assert "pathlib" in deps["stdlib"]

    def test_external_detected(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        deps = result["dependencies"]
        assert "requests" in deps["external"]

    def test_internal_modules(self, analyzer: CodeAnalyzer, tmp_path: Path):
        code = textwrap.dedent('''\
            from modules.base import BaseModule
        ''')
        p = tmp_path / "internal.py"
        p.write_text(code, encoding="utf-8")
        result = analyzer.analyze_file(str(p))
        assert "modules" in result["dependencies"]["internal"]


# =============================================================================
# Quality Signals
# =============================================================================

class TestQualitySignals:
    def test_docstring_coverage(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        qs = result["quality_signals"]
        # All functions/classes in sample have docstrings
        assert qs["docstring_coverage"] == 1.0

    def test_type_hint_coverage(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        qs = result["quality_signals"]
        assert qs["type_hint_coverage"] > 0.5

    def test_error_handling_detected(self, analyzer: CodeAnalyzer, sample_file: Path):
        result = analyzer.analyze_file(str(sample_file))
        qs = result["quality_signals"]
        assert qs["has_error_handling"] is True
        assert qs["try_except_count"] >= 1

    def test_bare_except_count(self, analyzer: CodeAnalyzer, tmp_path: Path):
        code = textwrap.dedent('''\
            def bad():
                try:
                    pass
                except:
                    pass
        ''')
        p = tmp_path / "bare.py"
        p.write_text(code, encoding="utf-8")
        result = analyzer.analyze_file(str(p))
        assert result["quality_signals"]["bare_except_count"] == 1

    def test_low_docstring_coverage(
        self, analyzer: CodeAnalyzer, multi_file_dir: Path
    ):
        result = analyzer.analyze_file(str(multi_file_dir / "bad.py"))
        qs = result["quality_signals"]
        assert qs["docstring_coverage"] == 0.0

    def test_high_docstring_coverage(
        self, analyzer: CodeAnalyzer, multi_file_dir: Path
    ):
        result = analyzer.analyze_file(str(multi_file_dir / "good.py"))
        qs = result["quality_signals"]
        assert qs["docstring_coverage"] == 1.0


# =============================================================================
# Directory Analysis
# =============================================================================

class TestAnalyzeDirectory:
    def test_aggregates_results(self, analyzer: CodeAnalyzer, multi_file_dir: Path):
        result = analyzer.analyze_directory(str(multi_file_dir))
        assert result["file_count"] >= 2
        assert "per_file" in result
        assert "summary" in result

    def test_identifies_best_worst(
        self, analyzer: CodeAnalyzer, multi_file_dir: Path
    ):
        result = analyzer.analyze_directory(str(multi_file_dir))
        assert "best_files" in result
        assert "worst_files" in result
        # good.py should have higher score than bad.py
        best_names = [f["file"] for f in result["best_files"]]
        worst_names = [f["file"] for f in result["worst_files"]]
        assert len(best_names) > 0
        assert len(worst_names) > 0

    def test_not_a_directory(self, analyzer: CodeAnalyzer):
        result = analyzer.analyze_directory("/nonexistent/dir")
        assert result["error"] is not None

    def test_skips_pycache(self, analyzer: CodeAnalyzer, multi_file_dir: Path):
        cache = multi_file_dir / "__pycache__"
        cache.mkdir()
        (cache / "cached.py").write_text("x = 1\n", encoding="utf-8")
        result = analyzer.analyze_directory(str(multi_file_dir))
        # __pycache__ file should not appear
        assert not any(
            "__pycache__" in key for key in result["per_file"]
        )


# =============================================================================
# Extract Learnings
# =============================================================================

class TestExtractLearnings:
    def test_produces_structured_dicts(
        self, analyzer: CodeAnalyzer, sample_file: Path
    ):
        analysis = analyzer.analyze_file(str(sample_file))
        learnings = analyzer.extract_learnings(analysis)
        assert isinstance(learnings, list)
        for learning in learnings:
            assert "pattern" in learning
            assert "example" in learning
            assert "why" in learning
            assert "apply_to" in learning
            assert isinstance(learning["apply_to"], list)

    def test_learns_from_patterns(
        self, analyzer: CodeAnalyzer, sample_file: Path
    ):
        analysis = analyzer.analyze_file(str(sample_file))
        learnings = analyzer.extract_learnings(analysis)
        pattern_names = [l["pattern"] for l in learnings]
        # sample_file has factory pattern
        assert "factory" in pattern_names

    def test_learns_from_techniques(
        self, analyzer: CodeAnalyzer, sample_file: Path
    ):
        analysis = analyzer.analyze_file(str(sample_file))
        learnings = analyzer.extract_learnings(analysis)
        pattern_names = [l["pattern"] for l in learnings]
        technique_learnings = [n for n in pattern_names if n.startswith("technique:")]
        assert len(technique_learnings) > 0

    def test_error_analysis_returns_empty(self, analyzer: CodeAnalyzer):
        result = analyzer.extract_learnings({"error": "some error"})
        assert result == []


# =============================================================================
# Store Learnings
# =============================================================================

class TestStoreLearnings:
    def test_no_grimoire_returns_zero(self, analyzer: CodeAnalyzer):
        learnings = [{"pattern": "test", "example": "x", "why": "y", "apply_to": ["a"]}]
        count = analyzer.store_learnings(learnings, source="test.py")
        assert count == 0

    def test_stores_to_grimoire(self, tmp_path: Path):
        mock_grimoire = MagicMock()
        mock_grimoire.recall.return_value = []
        mock_grimoire.remember.return_value = "mem-id"

        analyzer = CodeAnalyzer(
            grimoire=mock_grimoire,
            samples_dir=str(tmp_path / "samples"),
        )
        learnings = [
            {
                "pattern": "singleton",
                "example": "class Foo: pass",
                "why": "Single instance",
                "apply_to": ["grimoire"],
            },
        ]
        count = analyzer.store_learnings(learnings, source="test.py")
        assert count == 1
        mock_grimoire.remember.assert_called_once()

    def test_deduplicates(self, tmp_path: Path):
        mock_grimoire = MagicMock()
        # Simulate existing memory containing the pattern name
        mock_grimoire.recall.return_value = [
            {"content": "Code pattern: singleton\nWhy: ..."}
        ]

        analyzer = CodeAnalyzer(
            grimoire=mock_grimoire,
            samples_dir=str(tmp_path / "samples"),
        )
        learnings = [
            {
                "pattern": "singleton",
                "example": "class Foo: pass",
                "why": "Single instance",
                "apply_to": ["grimoire"],
            },
        ]
        count = analyzer.store_learnings(learnings, source="test.py")
        assert count == 0
        mock_grimoire.remember.assert_not_called()


# =============================================================================
# Compare with Shadow
# =============================================================================

class TestCompareWithShadow:
    def test_returns_comparison_structure(
        self, analyzer: CodeAnalyzer, sample_file: Path
    ):
        analysis = analyzer.analyze_file(str(sample_file))
        # Patch analyze_directory to avoid scanning the real modules/ dir
        fake_dir_result = {
            "summary": {"common_patterns": {}, "shared_dependencies": {}},
            "best_files": [{"file": "x.py", "score": 60}],
            "worst_files": [{"file": "y.py", "score": 30}],
        }
        with patch.object(analyzer, "analyze_directory", return_value=fake_dir_result):
            comparison = analyzer.compare_with_shadow(analysis)

        assert "shadow_better" in comparison
        assert "external_better" in comparison
        assert "missing_patterns" in comparison
        assert "recommendations" in comparison
        assert isinstance(comparison["shadow_better"], list)
        assert isinstance(comparison["external_better"], list)

    def test_error_analysis_returns_error(self, analyzer: CodeAnalyzer):
        result = analyzer.compare_with_shadow({"error": "bad file"})
        assert result["error"] == "bad file"


# =============================================================================
# analyze_source (string-based)
# =============================================================================

class TestAnalyzeSource:
    def test_analyzes_string(self, analyzer: CodeAnalyzer):
        code = "def hello() -> str:\n    \"\"\"Say hi.\"\"\"\n    return 'hello'\n"
        result = analyzer.analyze_source(code, filename="test.py")
        assert result["error"] is None
        assert result["complexity"]["function_count"] == 1

    def test_syntax_error_in_string(self, analyzer: CodeAnalyzer):
        result = analyzer.analyze_source("def (:\n", filename="bad.py")
        assert result["error"] is not None


# =============================================================================
# Omen Tool Integration
# =============================================================================

class TestOmenToolIntegration:
    """Test that Omen registers and dispatches the new tools."""

    def test_tool_count(self):
        from modules.omen.omen import Omen
        omen = Omen(config={"project_root": "."})
        tools = omen.get_tools()
        assert len(tools) == 38  # 21 original + 5 analyzer + 7 model evaluator + 4 sandbox + 1 code_generate

    def test_new_tool_names_registered(self):
        from modules.omen.omen import Omen
        omen = Omen(config={"project_root": "."})
        names = [t["name"] for t in omen.get_tools()]
        assert "code_analyze_file" in names
        assert "code_analyze_dir" in names
        assert "code_analyze_url" in names
        assert "code_learn" in names
        assert "code_compare" in names

    def test_all_new_tools_autonomous(self):
        from modules.omen.omen import Omen
        omen = Omen(config={"project_root": "."})
        new_tools = [
            t for t in omen.get_tools()
            if t["name"] in {
                "code_analyze_file", "code_analyze_dir",
                "code_analyze_url", "code_learn", "code_compare",
            }
        ]
        for tool in new_tools:
            assert tool["permission_level"] == "autonomous"

    @pytest.mark.asyncio
    async def test_code_analyze_file_dispatch(self, sample_file: Path, tmp_path: Path):
        from modules.omen.omen import Omen
        omen = Omen(config={
            "project_root": str(tmp_path),
            "db_path": str(tmp_path / "omen.db"),
        })
        await omen.initialize()
        result = await omen.execute(
            "code_analyze_file", {"file_path": str(sample_file)}
        )
        assert result.success
        assert "structure" in result.content
        await omen.shutdown()

    @pytest.mark.asyncio
    async def test_code_analyze_file_missing(self, tmp_path: Path):
        from modules.omen.omen import Omen
        omen = Omen(config={
            "project_root": str(tmp_path),
            "db_path": str(tmp_path / "omen.db"),
        })
        await omen.initialize()
        result = await omen.execute(
            "code_analyze_file", {"file_path": "/nonexistent.py"}
        )
        assert not result.success
        await omen.shutdown()
