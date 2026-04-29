"""
Code Analyzer & Learning Pipeline — Omen's Study System
=========================================================
Analyzes external (and internal) Python code to extract patterns,
techniques, and quality signals. Learnings feed into Grimoire so
Omen can apply them to future work.

Phase 1: Local file + single-URL analysis. No repo cloning.
"""

from __future__ import annotations

import ast
import logging
import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("shadow.omen.analyzer")

# Design patterns we can detect via AST heuristics
DESIGN_PATTERNS = {
    "singleton": "Class with _instance attribute and __new__ override",
    "factory": "Function/method that returns different class instances based on input",
    "observer": "Class with subscribe/notify/on_event methods and a listeners list",
    "decorator": "Function that wraps another function (returns inner function)",
    "strategy": "Class that accepts a callable/strategy object and delegates to it",
    "builder": "Class with chaining methods that return self",
    "template_method": "Base class with abstract methods called from a concrete method",
    "registry": "Class/dict that maps names to handlers/classes",
}

# Standard library modules (top-level) for dependency classification
_STDLIB_TOP = {
    "abc", "ast", "asyncio", "base64", "bisect", "builtins", "calendar",
    "cmath", "codecs", "collections", "colorsys", "concurrent", "configparser",
    "contextlib", "copy", "csv", "ctypes", "dataclasses", "datetime",
    "decimal", "difflib", "dis", "email", "enum", "errno", "faulthandler",
    "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools",
    "gc", "getpass", "gettext", "glob", "graphlib", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "imaplib", "importlib", "inspect",
    "io", "ipaddress", "itertools", "json", "keyword", "linecache",
    "locale", "logging", "lzma", "mailbox", "marshal", "math", "mimetypes",
    "mmap", "multiprocessing", "numbers", "operator", "os", "pathlib",
    "pdb", "pickle", "pkgutil", "platform", "plistlib", "poplib",
    "posixpath", "pprint", "profile", "pstats", "py_compile", "queue",
    "quopri", "random", "re", "readline", "reprlib", "resource", "rlcompleter",
    "runpy", "sched", "secrets", "select", "selectors", "shelve", "shlex",
    "shutil", "signal", "site", "smtplib", "socket", "socketserver",
    "sqlite3", "ssl", "stat", "statistics", "string", "struct",
    "subprocess", "sys", "sysconfig", "syslog", "tempfile", "textwrap",
    "threading", "time", "timeit", "tkinter", "token", "tokenize",
    "tomllib", "trace", "traceback", "tracemalloc", "tty", "turtle",
    "types", "typing", "unicodedata", "unittest", "urllib", "uuid",
    "venv", "warnings", "wave", "weakref", "webbrowser", "winreg",
    "winsound", "xml", "xmlrpc", "zipfile", "zipimport", "zlib",
    # Common sub-packages that appear as top-level in from-imports
    "os.path", "typing_extensions", "collections.abc",
}


class CodeAnalyzer:
    """Analyzes Python source code for structure, patterns, and quality.

    Works on local files, directories, and single URLs. Extracts
    actionable learnings that can be stored in Grimoire.

    Args:
        grimoire: Optional Grimoire instance for storing learnings.
        samples_dir: Where to save downloaded code samples.
    """

    def __init__(
        self,
        grimoire: Any | None = None,
        samples_dir: str = "data/research/code_samples",
    ) -> None:
        """Initialize CodeAnalyzer.

        Args:
            grimoire: Grimoire instance for storing/querying learnings.
            samples_dir: Directory for downloaded code samples.
        """
        self._grimoire = grimoire
        self._samples_dir = Path(samples_dir)
        self._samples_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def analyze_file(self, file_path: str) -> dict[str, Any]:
        """Analyze a single Python file for structure, patterns, and quality.

        Args:
            file_path: Path to a .py file.

        Returns:
            Dict with keys: file, structure, patterns, techniques,
            complexity, dependencies, quality_signals, error.
        """
        path = Path(file_path)
        if not path.exists():
            return {"file": file_path, "error": f"File not found: {file_path}"}

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return {"file": file_path, "error": f"Cannot read file: {e}"}

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as e:
            return {"file": file_path, "error": f"Syntax error: {e}"}

        return {
            "file": str(path),
            "structure": self._extract_structure(tree, source),
            "patterns": self._detect_patterns(tree, source),
            "techniques": self._detect_techniques(tree, source),
            "complexity": self._measure_complexity(tree, source),
            "dependencies": self._extract_dependencies(tree),
            "quality_signals": self._measure_quality(tree, source, path),
            "error": None,
        }

    def analyze_source(self, source: str, filename: str = "<string>") -> dict[str, Any]:
        """Analyze Python source code from a string.

        Args:
            source: Python source code.
            filename: Label for the source.

        Returns:
            Analysis dict (same shape as analyze_file).
        """
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as e:
            return {"file": filename, "error": f"Syntax error: {e}"}

        return {
            "file": filename,
            "structure": self._extract_structure(tree, source),
            "patterns": self._detect_patterns(tree, source),
            "techniques": self._detect_techniques(tree, source),
            "complexity": self._measure_complexity(tree, source),
            "dependencies": self._extract_dependencies(tree),
            "quality_signals": self._measure_quality(tree, source, Path(filename)),
            "error": None,
        }

    def analyze_directory(
        self, dir_path: str, pattern: str = "*.py"
    ) -> dict[str, Any]:
        """Analyze all matching files in a directory.

        Args:
            dir_path: Directory to scan.
            pattern: Glob pattern for files (default *.py).

        Returns:
            Dict with summary, per_file results, best/worst rankings.
        """
        root = Path(dir_path)
        if not root.is_dir():
            return {"directory": dir_path, "error": f"Not a directory: {dir_path}"}

        files = sorted(root.rglob(pattern))
        # Skip venv, __pycache__, .git
        skip_dirs = {"__pycache__", ".git", "node_modules", "shadow_env", "venv"}
        files = [
            f for f in files
            if not any(part in skip_dirs for part in f.parts)
        ]

        if not files:
            return {
                "directory": dir_path,
                "file_count": 0,
                "error": "No matching files found",
            }

        per_file = {}
        all_patterns: list[str] = []
        all_deps: list[str] = []
        quality_scores: list[tuple[str, float]] = []

        for fpath in files:
            analysis = self.analyze_file(str(fpath))
            rel = str(fpath.relative_to(root))
            per_file[rel] = analysis

            if analysis.get("error"):
                continue

            all_patterns.extend(analysis["patterns"].get("detected", []))
            all_deps.extend(analysis["dependencies"].get("external", []))

            qs = analysis["quality_signals"]
            score = self._quality_score(qs)
            quality_scores.append((rel, score))

        # Sort by quality score
        quality_scores.sort(key=lambda x: x[1], reverse=True)
        pattern_counts = Counter(all_patterns)
        dep_counts = Counter(all_deps)

        best = quality_scores[:5] if quality_scores else []
        worst = quality_scores[-5:][::-1] if quality_scores else []

        return {
            "directory": str(root),
            "file_count": len(files),
            "analyzed": len(per_file),
            "summary": {
                "common_patterns": dict(pattern_counts.most_common(10)),
                "shared_dependencies": dict(dep_counts.most_common(15)),
                "avg_quality_score": (
                    round(sum(s for _, s in quality_scores) / len(quality_scores), 1)
                    if quality_scores else 0
                ),
            },
            "best_files": [{"file": f, "score": s} for f, s in best],
            "worst_files": [{"file": f, "score": s} for f, s in worst],
            "per_file": per_file,
        }

    def analyze_url(self, url: str) -> dict[str, Any]:
        """Download and analyze a single Python file from a URL.

        Only downloads individual files (GitHub raw links, paste sites).
        Does NOT clone repos.

        Args:
            url: URL to a raw Python file.

        Returns:
            Analysis dict with additional 'source_url' and 'saved_path' keys.
        """
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            return {"url": url, "error": f"Download failed: {e}"}

        source = resp.text

        # Verify it looks like Python
        try:
            ast.parse(source)
        except SyntaxError as e:
            return {"url": url, "error": f"Downloaded content is not valid Python: {e}"}

        # Save to samples directory
        filename = url.rstrip("/").split("/")[-1]
        if not filename.endswith(".py"):
            filename += ".py"
        # Prefix with timestamp to avoid collisions
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_name = f"{ts}_{filename}"
        save_path = self._samples_dir / save_name
        save_path.write_text(source, encoding="utf-8")

        analysis = self.analyze_source(source, filename=filename)
        analysis["source_url"] = url
        analysis["saved_path"] = str(save_path)
        return analysis

    def extract_learnings(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract actionable learnings from an analysis result.

        Args:
            analysis: Output from analyze_file/analyze_source/analyze_url.

        Returns:
            List of learning dicts with: pattern, example, why, apply_to.
        """
        if analysis.get("error"):
            return []

        learnings: list[dict[str, Any]] = []

        # Learn from detected design patterns
        for pattern_name in analysis.get("patterns", {}).get("detected", []):
            examples = analysis["patterns"].get("examples", {}).get(pattern_name, [])
            snippet = examples[0] if examples else ""
            learnings.append({
                "pattern": pattern_name,
                "example": snippet[:500],  # Cap at 500 chars
                "why": DESIGN_PATTERNS.get(
                    pattern_name,
                    f"Design pattern: {pattern_name}",
                ),
                "apply_to": self._suggest_modules_for_pattern(pattern_name),
            })

        # Learn from techniques
        techniques = analysis.get("techniques", {})
        technique_explanations = {
            "generators": (
                "Memory-efficient iteration over large datasets",
                ["grimoire", "reaper", "void"],
            ),
            "context_managers": (
                "Guaranteed resource cleanup (files, connections, locks)",
                ["grimoire", "cerberus", "omen"],
            ),
            "dataclasses": (
                "Clean data structures with less boilerplate",
                ["wraith", "harbinger", "nova"],
            ),
            "async_await": (
                "Non-blocking I/O for concurrent operations",
                ["shadow", "reaper", "void"],
            ),
            "type_hints": (
                "Self-documenting code and IDE support",
                ["all modules"],
            ),
            "list_comprehensions": (
                "Concise, readable collection transformations",
                ["omen", "grimoire"],
            ),
            "decorators_used": (
                "Cross-cutting concerns (logging, caching, auth)",
                ["shadow", "cerberus"],
            ),
        }

        for tech_name, used in techniques.items():
            if not used:
                continue
            if tech_name in technique_explanations:
                why, modules = technique_explanations[tech_name]
                # Get a code example if we have the source structure
                example = self._extract_technique_example(
                    analysis, tech_name
                )
                learnings.append({
                    "pattern": f"technique:{tech_name}",
                    "example": example[:500] if example else "",
                    "why": why,
                    "apply_to": modules,
                })

        return learnings

    def store_learnings(
        self, learnings: list[dict[str, Any]], source: str
    ) -> int:
        """Store extracted learnings in Grimoire.

        Args:
            learnings: List of learning dicts from extract_learnings.
            source: Where the code came from (file path, URL, etc.).

        Returns:
            Count of learnings stored (excludes duplicates).
        """
        if not self._grimoire:
            logger.warning("No Grimoire instance — cannot store learnings")
            return 0

        stored = 0
        for learning in learnings:
            content = (
                f"Code pattern: {learning['pattern']}\n"
                f"Why: {learning['why']}\n"
                f"Apply to: {', '.join(learning['apply_to'])}\n"
                f"Example:\n{learning['example']}"
            )

            # Check for duplicates via recall
            try:
                existing = self._grimoire.recall(
                    f"code pattern {learning['pattern']}",
                    n_results=3,
                    category="code_pattern",
                )
                # If we find a very similar learning, skip it
                if existing and any(
                    learning["pattern"] in str(m.get("content", ""))
                    for m in existing
                ):
                    logger.debug(
                        "Skipping duplicate learning: %s", learning["pattern"]
                    )
                    continue
            except Exception:
                # Grimoire not available or recall failed — store anyway
                pass

            try:
                self._grimoire.remember(
                    content=content,
                    source="code_analysis",
                    source_module="omen",
                    category="code_pattern",
                    trust_level=0.3,  # External code = reference trust
                    tags=[learning["pattern"], "code_analysis", source],
                    metadata={
                        "source_file": source,
                        "pattern": learning["pattern"],
                        "apply_to": learning["apply_to"],
                    },
                )
                stored += 1
            except Exception as e:
                logger.error("Failed to store learning: %s", e)

        return stored

    def compare_with_shadow(self, analysis: dict[str, Any]) -> dict[str, Any]:
        """Compare external code analysis against Shadow's own patterns.

        Args:
            analysis: Output from analyze_file or analyze_directory.

        Returns:
            Dict with shadow_better, external_better, missing_patterns,
            and recommendations.
        """
        if analysis.get("error"):
            return {"error": analysis["error"]}

        shadow_root = Path(__file__).parent.parent  # modules/
        shadow_analysis = self.analyze_directory(str(shadow_root))

        ext_patterns = set(analysis.get("patterns", {}).get("detected", []))
        ext_techniques = {
            k for k, v in analysis.get("techniques", {}).items() if v
        }
        ext_quality = analysis.get("quality_signals", {})

        shadow_summary = shadow_analysis.get("summary", {})
        shadow_patterns = set(shadow_summary.get("common_patterns", {}).keys())

        # Build a representative quality from Shadow's best files
        shadow_scores = [
            f["score"] for f in shadow_analysis.get("best_files", [])
        ]
        shadow_avg = (
            sum(shadow_scores) / len(shadow_scores) if shadow_scores else 50
        )
        ext_score = self._quality_score(ext_quality) if ext_quality else 50

        shadow_better: list[str] = []
        external_better: list[str] = []
        recommendations: list[str] = []

        # Quality comparison
        if shadow_avg > ext_score + 5:
            shadow_better.append(
                f"Overall quality score (Shadow: {shadow_avg:.0f} vs External: {ext_score:.0f})"
            )
        elif ext_score > shadow_avg + 5:
            external_better.append(
                f"Overall quality score (External: {ext_score:.0f} vs Shadow: {shadow_avg:.0f})"
            )

        # Docstring coverage
        ext_doc = ext_quality.get("docstring_coverage", 0)
        if ext_doc > 0.8:
            if ext_doc > 0.9:
                external_better.append(
                    f"Docstring coverage: {ext_doc:.0%}"
                )
        elif ext_doc < 0.5:
            shadow_better.append("Shadow has better documentation coverage")

        # Type hint coverage
        ext_hints = ext_quality.get("type_hint_coverage", 0)
        if ext_hints > 0.8:
            external_better.append(f"Type hint coverage: {ext_hints:.0%}")
            recommendations.append("Consider increasing type hint coverage")

        # Missing patterns
        missing = ext_patterns - shadow_patterns
        if missing:
            recommendations.append(
                f"Patterns to consider adopting: {', '.join(missing)}"
            )

        return {
            "shadow_better": shadow_better,
            "external_better": external_better,
            "missing_patterns": list(missing),
            "recommendations": recommendations,
            "shadow_avg_score": round(shadow_avg, 1),
            "external_score": round(ext_score, 1),
        }

    # =========================================================================
    # PRIVATE — Structure extraction
    # =========================================================================

    def _extract_structure(
        self, tree: ast.AST, source: str
    ) -> dict[str, Any]:
        """Extract classes, functions, imports, decorators, inheritance."""
        classes: list[dict[str, Any]] = []
        functions: list[dict[str, Any]] = []
        imports: list[str] = []
        decorators: list[str] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                bases = [self._name_of(b) for b in node.bases]
                methods = [
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                classes.append({
                    "name": node.name,
                    "bases": bases,
                    "methods": methods,
                    "line": node.lineno,
                    "decorators": [self._name_of(d) for d in node.decorator_list],
                })
                decorators.extend(self._name_of(d) for d in node.decorator_list)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({
                    "name": node.name,
                    "args": [a.arg for a in node.args.args],
                    "returns": self._name_of(node.returns) if node.returns else None,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "line": node.lineno,
                    "decorators": [self._name_of(d) for d in node.decorator_list],
                })
                decorators.extend(self._name_of(d) for d in node.decorator_list)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")

        return {
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "decorators": list(set(decorators)),
            "inheritance": [
                {"class": c["name"], "bases": c["bases"]}
                for c in classes if c["bases"]
            ],
        }

    # =========================================================================
    # PRIVATE — Pattern detection
    # =========================================================================

    def _detect_patterns(
        self, tree: ast.AST, source: str
    ) -> dict[str, Any]:
        """Detect design patterns via AST heuristics."""
        detected: list[str] = []
        examples: dict[str, list[str]] = {}

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            class_source = ast.get_source_segment(source, node) or ""
            method_names = {
                n.name for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            attr_names = set()
            for n in node.body:
                if isinstance(n, ast.Assign):
                    for target in n.targets:
                        if isinstance(target, ast.Name):
                            attr_names.add(target.id)

            # Singleton: _instance + __new__
            if "_instance" in attr_names and "__new__" in method_names:
                detected.append("singleton")
                examples.setdefault("singleton", []).append(
                    self._trim_snippet(class_source, 20)
                )

            # Observer: subscribe/notify pattern
            observer_methods = {"subscribe", "notify", "on_event", "emit",
                                "add_listener", "remove_listener"}
            if len(method_names & observer_methods) >= 2:
                detected.append("observer")
                examples.setdefault("observer", []).append(
                    self._trim_snippet(class_source, 20)
                )

            # Builder: methods returning self
            self_returns = 0
            for n in node.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for ret in ast.walk(n):
                        if (isinstance(ret, ast.Return)
                                and isinstance(ret.value, ast.Name)
                                and ret.value.id == "self"):
                            self_returns += 1
                            break
            if self_returns >= 3:
                detected.append("builder")
                examples.setdefault("builder", []).append(
                    self._trim_snippet(class_source, 20)
                )

            # Registry: dict mapping names to handlers
            if any(
                name in attr_names
                for name in ("_registry", "_handlers", "registry", "handlers")
            ):
                if "register" in method_names:
                    detected.append("registry")
                    examples.setdefault("registry", []).append(
                        self._trim_snippet(class_source, 20)
                    )

        # Factory: top-level or method functions that create different objects
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if re.match(r"(create|make|build|get)_", node.name):
                    # Check for conditional returns of different types
                    returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
                    if len(returns) >= 2:
                        detected.append("factory")
                        func_source = ast.get_source_segment(source, node) or ""
                        examples.setdefault("factory", []).append(
                            self._trim_snippet(func_source, 20)
                        )
                        break  # One detection is enough

        # Decorator pattern: functions wrapping other functions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Look for nested function def with return of inner function
                inner_defs = [
                    n for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if inner_defs:
                    for ret in ast.walk(node):
                        if (isinstance(ret, ast.Return)
                                and isinstance(ret.value, ast.Name)
                                and ret.value.id in {d.name for d in inner_defs}):
                            detected.append("decorator")
                            func_source = ast.get_source_segment(source, node) or ""
                            examples.setdefault("decorator", []).append(
                                self._trim_snippet(func_source, 20)
                            )
                            break
                    else:
                        continue
                    break

        # Strategy: class accepting a callable in __init__
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if (isinstance(method, ast.FunctionDef)
                            and method.name == "__init__"):
                        for arg in method.args.args:
                            if arg.arg in ("strategy", "handler", "callback",
                                           "processor", "policy"):
                                detected.append("strategy")
                                cls_source = ast.get_source_segment(source, node) or ""
                                examples.setdefault("strategy", []).append(
                                    self._trim_snippet(cls_source, 20)
                                )
                                break

        return {
            "detected": list(set(detected)),
            "examples": examples,
        }

    # =========================================================================
    # PRIVATE — Technique detection
    # =========================================================================

    def _detect_techniques(
        self, tree: ast.AST, source: str
    ) -> dict[str, bool]:
        """Detect Python techniques used in the code."""
        techniques = {
            "list_comprehensions": False,
            "generators": False,
            "context_managers": False,
            "async_await": False,
            "dataclasses": False,
            "type_hints": False,
            "decorators_used": False,
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ListComp):
                techniques["list_comprehensions"] = True
            elif isinstance(node, (ast.GeneratorExp, ast.Yield, ast.YieldFrom)):
                techniques["generators"] = True
            elif isinstance(node, ast.With):
                techniques["context_managers"] = True
            elif isinstance(node, (ast.AsyncFunctionDef, ast.Await)):
                techniques["async_await"] = True
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.returns is not None:
                    techniques["type_hints"] = True
                for arg in node.args.args:
                    if arg.annotation is not None:
                        techniques["type_hints"] = True
                if node.decorator_list:
                    techniques["decorators_used"] = True
                    # Check for @dataclass
                    for dec in node.decorator_list:
                        if self._name_of(dec) == "dataclass":
                            techniques["dataclasses"] = True
            elif isinstance(node, ast.ClassDef):
                for dec in node.decorator_list:
                    if self._name_of(dec) in ("dataclass", "dataclasses.dataclass"):
                        techniques["dataclasses"] = True
                    techniques["decorators_used"] = True

        return techniques

    # =========================================================================
    # PRIVATE — Complexity measurement
    # =========================================================================

    def _measure_complexity(
        self, tree: ast.AST, source: str
    ) -> dict[str, Any]:
        """Measure code complexity metrics."""
        lines = source.splitlines()
        code_lines = [
            l for l in lines
            if l.strip() and not l.strip().startswith("#")
        ]

        func_nodes = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        # Average lines per function
        func_lengths: list[int] = []
        for func in func_nodes:
            if hasattr(func, "end_lineno") and func.end_lineno:
                func_lengths.append(func.end_lineno - func.lineno + 1)

        avg_func_length = (
            round(sum(func_lengths) / len(func_lengths), 1)
            if func_lengths else 0
        )

        # Max nesting depth
        max_depth = self._max_nesting_depth(tree)

        # Cyclomatic complexity estimate (decision points + 1 per function)
        decision_nodes = sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                              ast.With, ast.BoolOp, ast.IfExp))
        )
        # Average per function
        avg_complexity = (
            round((decision_nodes / len(func_nodes)) + 1, 1)
            if func_nodes else 1
        )

        return {
            "total_lines": len(lines),
            "code_lines": len(code_lines),
            "function_count": len(func_nodes),
            "class_count": sum(
                1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
            ),
            "avg_lines_per_function": avg_func_length,
            "max_nesting_depth": max_depth,
            "cyclomatic_complexity_avg": avg_complexity,
            "decision_points": decision_nodes,
        }

    def _max_nesting_depth(self, tree: ast.AST) -> int:
        """Calculate maximum nesting depth of control structures."""
        nesting_types = (
            ast.If, ast.For, ast.While, ast.With, ast.Try,
            ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
        )

        def _depth(node: ast.AST, current: int) -> int:
            max_d = current
            for child in ast.iter_child_nodes(node):
                if isinstance(child, nesting_types):
                    max_d = max(max_d, _depth(child, current + 1))
                else:
                    max_d = max(max_d, _depth(child, current))
            return max_d

        return _depth(tree, 0)

    # =========================================================================
    # PRIVATE — Dependency extraction
    # =========================================================================

    def _extract_dependencies(self, tree: ast.AST) -> dict[str, Any]:
        """Classify imports into stdlib, external, and internal."""
        stdlib: list[str] = []
        external: list[str] = []
        internal: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    self._classify_import(top, stdlib, external, internal)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    self._classify_import(top, stdlib, external, internal)
                elif node.level > 0:
                    internal.append(f".{'.' * (node.level - 1)}")

        return {
            "stdlib": sorted(set(stdlib)),
            "external": sorted(set(external)),
            "internal": sorted(set(internal)),
        }

    def _classify_import(
        self,
        top: str,
        stdlib: list[str],
        external: list[str],
        internal: list[str],
    ) -> None:
        """Classify a top-level import name."""
        if top in _STDLIB_TOP:
            stdlib.append(top)
        elif top == "modules" or top.startswith("modules."):
            internal.append(top)
        else:
            external.append(top)

    # =========================================================================
    # PRIVATE — Quality signals
    # =========================================================================

    def _measure_quality(
        self, tree: ast.AST, source: str, path: Path
    ) -> dict[str, Any]:
        """Measure code quality signals."""
        func_nodes = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]

        # Docstring coverage
        has_docstring = 0
        for node in func_nodes:
            if (node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                has_docstring += 1

        docstring_coverage = (
            round(has_docstring / len(func_nodes), 2)
            if func_nodes else 1.0
        )

        # Type hint coverage
        funcs_only = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        hinted_args = 0
        total_args = 0
        return_hints = 0
        for func in funcs_only:
            if func.returns is not None:
                return_hints += 1
            for arg in func.args.args:
                if arg.arg == "self":
                    continue
                total_args += 1
                if arg.annotation is not None:
                    hinted_args += 1

        hint_total = total_args + len(funcs_only)  # args + return hints
        hint_actual = hinted_args + return_hints
        type_hint_coverage = (
            round(hint_actual / hint_total, 2)
            if hint_total > 0 else 1.0
        )

        # Error handling patterns
        try_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Try))
        bare_excepts = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    if handler.type is None:
                        bare_excepts += 1

        # Test presence
        test_path = Path("tests") / f"test_{path.stem}.py"
        test_exists = test_path.exists()

        return {
            "docstring_coverage": docstring_coverage,
            "type_hint_coverage": type_hint_coverage,
            "try_except_count": try_count,
            "bare_except_count": bare_excepts,
            "has_error_handling": try_count > 0,
            "test_file_exists": test_exists,
        }

    def _quality_score(self, quality: dict[str, Any]) -> float:
        """Calculate a 0-100 quality score from quality signals."""
        score = 0.0
        score += quality.get("docstring_coverage", 0) * 30
        score += quality.get("type_hint_coverage", 0) * 25
        if quality.get("has_error_handling"):
            score += 20
        if quality.get("bare_except_count", 0) == 0:
            score += 10
        if quality.get("test_file_exists"):
            score += 15
        return round(score, 1)

    # =========================================================================
    # PRIVATE — Helpers
    # =========================================================================

    def _name_of(self, node: ast.AST | None) -> str:
        """Extract a human-readable name from an AST node."""
        if node is None:
            return ""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._name_of(node.value)}.{node.attr}"
        if isinstance(node, ast.Call):
            return self._name_of(node.func)
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Subscript):
            return f"{self._name_of(node.value)}[{self._name_of(node.slice)}]"
        if isinstance(node, ast.Tuple):
            return ", ".join(self._name_of(e) for e in node.elts)
        return ""

    def _trim_snippet(self, source: str, max_lines: int = 20) -> str:
        """Trim a code snippet to a maximum number of lines."""
        lines = source.splitlines()
        if len(lines) <= max_lines:
            return source
        return "\n".join(lines[:max_lines]) + "\n    # ... (trimmed)"

    def _suggest_modules_for_pattern(self, pattern: str) -> list[str]:
        """Suggest which Shadow modules could benefit from a pattern."""
        suggestions = {
            "singleton": ["grimoire", "shadow"],
            "factory": ["shadow", "omen"],
            "observer": ["void", "harbinger", "shadow"],
            "decorator": ["cerberus", "shadow"],
            "strategy": ["shadow", "apex", "reaper"],
            "builder": ["nova", "omen"],
            "template_method": ["shadow", "omen"],
            "registry": ["shadow", "omen"],
        }
        return suggestions.get(pattern, ["shadow"])

    def _extract_technique_example(
        self, analysis: dict[str, Any], technique: str
    ) -> str:
        """Try to find a minimal example of a technique from the source."""
        # We don't store source in the analysis dict, so return empty
        # The examples come from the pattern detection examples dict
        return ""
