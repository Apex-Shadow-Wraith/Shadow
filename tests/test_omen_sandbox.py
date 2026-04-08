"""
Tests for Omen Sandbox — C/C++/CUDA Compilation Extension
============================================================
Validates CCompiler, CppCompiler, CudaCompiler, detect_language,
execute_compiled, and C/C++ safety checks.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from modules.omen.sandbox import (
    CCompiler,
    CppCompiler,
    CudaCompiler,
    CodeSandbox,
    CompileResult,
    ExecuteResult,
    detect_language,
    _validate_c_safety,
)


@pytest.fixture
def sandbox(tmp_path):
    """Create a sandbox with a temporary root directory."""
    root = tmp_path / "sandbox"
    root.mkdir()
    return CodeSandbox(sandbox_root=str(root))


# ------------------------------------------------------------------
# CCompiler
# ------------------------------------------------------------------

class TestCCompiler:
    """Tests for CCompiler compilation and execution."""

    def test_compile_success(self):
        """Valid C code compiles successfully."""
        compiler = CCompiler()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("modules.omen.sandbox.subprocess.run", return_value=mock_result) as mock_run:
            result = compiler.compile("main.c", "main.out", timeout=30)

        assert result.success is True
        assert result.errors == ""
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "gcc"
        assert "-Wall" in args
        assert "-Wextra" in args

    def test_compile_syntax_error(self):
        """Syntax error returns failure with error message."""
        compiler = CCompiler()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "main.c:3:1: error: expected ';'"

        with patch("modules.omen.sandbox.subprocess.run", return_value=mock_result):
            result = compiler.compile("main.c", "main.out")

        assert result.success is False
        assert "error" in result.errors

    def test_execute_captures_stdout(self):
        """Running binary captures stdout."""
        compiler = CCompiler()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Hello, World!"
        mock_result.stderr = ""

        with patch("modules.omen.sandbox.subprocess.run", return_value=mock_result):
            result = compiler.execute("./main.out")

        assert result.success is True
        assert result.stdout == "Hello, World!"

    def test_execute_runtime_error(self):
        """Runtime error (e.g. segfault) is captured."""
        compiler = CCompiler()
        mock_result = MagicMock()
        mock_result.returncode = -11  # SIGSEGV
        mock_result.stdout = ""
        mock_result.stderr = "Segmentation fault"

        with patch("modules.omen.sandbox.subprocess.run", return_value=mock_result):
            result = compiler.execute("./main.out")

        assert result.success is False
        assert result.returncode == -11

    def test_compile_timeout_enforced(self):
        """Compilation timeout returns failure."""
        compiler = CCompiler()

        with patch(
            "modules.omen.sandbox.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gcc", timeout=5),
        ):
            result = compiler.compile("main.c", "main.out", timeout=5)

        assert result.success is False
        assert "timed out" in result.errors


# ------------------------------------------------------------------
# CppCompiler
# ------------------------------------------------------------------

class TestCppCompiler:
    """Tests for CppCompiler — same interface as CCompiler but with g++."""

    def test_compile_uses_gpp_with_cpp17(self):
        """Compile uses g++ with -std=c++17."""
        compiler = CppCompiler()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("modules.omen.sandbox.subprocess.run", return_value=mock_result) as mock_run:
            result = compiler.compile("main.cpp", "main.out")

        assert result.success is True
        args = mock_run.call_args[0][0]
        assert args[0] == "g++"
        assert "-std=c++17" in args
        assert "-Wall" in args

    def test_compile_syntax_error(self):
        """C++ syntax error returns failure."""
        compiler = CppCompiler()
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "main.cpp:5: error: 'vector' was not declared"

        with patch("modules.omen.sandbox.subprocess.run", return_value=mock_result):
            result = compiler.compile("main.cpp", "main.out")

        assert result.success is False
        assert "error" in result.errors

    def test_execute_captures_stdout(self):
        """Running C++ binary captures stdout."""
        compiler = CppCompiler()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "C++ output"
        mock_result.stderr = ""

        with patch("modules.omen.sandbox.subprocess.run", return_value=mock_result):
            result = compiler.execute("./main.out")

        assert result.success is True
        assert result.stdout == "C++ output"

    def test_compile_timeout(self):
        """C++ compilation timeout returns failure."""
        compiler = CppCompiler()

        with patch(
            "modules.omen.sandbox.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="g++", timeout=30),
        ):
            result = compiler.compile("main.cpp", "main.out", timeout=30)

        assert result.success is False
        assert "timed out" in result.errors


# ------------------------------------------------------------------
# CudaCompiler
# ------------------------------------------------------------------

class TestCudaCompiler:
    """Tests for CudaCompiler — GPU detection and compile-only mode."""

    def test_detects_gpu_available(self):
        """nvidia-smi success means GPU is available."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("modules.omen.sandbox.subprocess.run", return_value=mock_result):
            compiler = CudaCompiler()

        assert compiler.gpu_available is True

    def test_detects_gpu_absent(self):
        """nvidia-smi failure means no GPU."""
        with patch(
            "modules.omen.sandbox.subprocess.run",
            side_effect=FileNotFoundError("nvidia-smi not found"),
        ):
            compiler = CudaCompiler()

        assert compiler.gpu_available is False

    def test_compile_with_nvcc(self):
        """Compiles with nvcc when GPU present."""
        mock_nvidia = MagicMock(returncode=0)
        mock_nvcc = MagicMock(returncode=0, stdout="", stderr="")

        with patch("modules.omen.sandbox.subprocess.run", side_effect=[mock_nvidia, mock_nvcc]) as mock_run:
            compiler = CudaCompiler()
            result = compiler.compile("kernel.cu", "kernel.out")

        assert result.success is True
        # Second call should be nvcc
        nvcc_call = mock_run.call_args_list[1]
        assert nvcc_call[0][0][0] == "nvcc"

    def test_compile_only_mode_no_gpu(self):
        """When GPU absent, compile works but execute returns error."""
        with patch(
            "modules.omen.sandbox.subprocess.run",
            side_effect=FileNotFoundError("nvidia-smi not found"),
        ):
            compiler = CudaCompiler()

        assert compiler.gpu_available is False
        result = compiler.execute("kernel.out")
        assert result.success is False
        assert "No GPU available" in result.error

    def test_cpu_fallback_flag(self):
        """When GPU absent and initial compile fails, tries -DCPU_ONLY."""
        # nvidia-smi fails → no GPU
        nvidia_fail = FileNotFoundError("not found")
        # First nvcc compile fails
        nvcc_fail = MagicMock(returncode=1, stdout="", stderr="no GPU arch")
        # Fallback with -DCPU_ONLY succeeds
        nvcc_fallback = MagicMock(returncode=0, stdout="", stderr="")

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise nvidia_fail
            elif call_count[0] == 2:
                return nvcc_fail
            else:
                return nvcc_fallback

        with patch("modules.omen.sandbox.subprocess.run", side_effect=side_effect):
            compiler = CudaCompiler()
            result = compiler.compile("kernel.cu", "kernel.out")

        assert result.success is True
        assert "CPU_ONLY" in result.errors


# ------------------------------------------------------------------
# detect_language
# ------------------------------------------------------------------

class TestDetectLanguage:
    """Tests for detect_language function."""

    def test_c_extension(self):
        assert detect_language(file_path="main.c") == "c"

    def test_cpp_extension(self):
        assert detect_language(file_path="main.cpp") == "cpp"

    def test_cc_extension(self):
        assert detect_language(file_path="main.cc") == "cpp"

    def test_cxx_extension(self):
        assert detect_language(file_path="main.cxx") == "cpp"

    def test_cu_extension(self):
        assert detect_language(file_path="kernel.cu") == "cuda"

    def test_py_extension(self):
        assert detect_language(file_path="script.py") == "python"

    def test_code_content_cuda(self):
        """Detects CUDA from __global__ keyword."""
        code = '__global__ void kernel() { }'
        assert detect_language(code=code) == "cuda"

    def test_code_content_device(self):
        """Detects CUDA from __device__ keyword."""
        code = '__device__ int helper() { return 0; }'
        assert detect_language(code=code) == "cuda"

    def test_code_content_c(self):
        """Detects C from #include and int main(."""
        code = '#include <stdio.h>\nint main(int argc, char *argv[]) { return 0; }'
        assert detect_language(code=code) == "c"

    def test_code_content_cpp(self):
        """Detects C++ from #include with iostream/std::."""
        code = '#include <iostream>\nint main() { std::cout << "hi"; return 0; }'
        assert detect_language(code=code) == "cpp"

    def test_default_python(self):
        """Default language is python when nothing matches."""
        assert detect_language() == "python"
        assert detect_language(code="x = 42") == "python"


# ------------------------------------------------------------------
# execute_compiled
# ------------------------------------------------------------------

class TestExecuteCompiled:
    """Tests for CodeSandbox.execute_compiled()."""

    def test_full_pipeline_c(self, sandbox):
        """Full compile → execute pipeline for C code."""
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        mock_execute = MagicMock(returncode=0, stdout="Hello from C", stderr="")

        with patch("modules.omen.sandbox.subprocess.run", side_effect=[mock_compile, mock_execute]):
            result = sandbox.execute_compiled(
                '#include <stdio.h>\nint main() { printf("Hello from C"); return 0; }',
                language="c",
            )

        assert result["language"] == "c"
        assert result["compile_result"]["success"] is True
        assert result["execute_result"]["success"] is True
        assert result["stdout"] == "Hello from C"

    def test_full_pipeline_cpp(self, sandbox):
        """Full compile → execute pipeline for C++ code."""
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        mock_execute = MagicMock(returncode=0, stdout="Hello from C++", stderr="")

        with patch("modules.omen.sandbox.subprocess.run", side_effect=[mock_compile, mock_execute]):
            result = sandbox.execute_compiled(
                '#include <iostream>\nint main() { std::cout << "Hello from C++"; return 0; }',
                language="cpp",
            )

        assert result["language"] == "cpp"
        assert result["compile_result"]["success"] is True
        assert result["stdout"] == "Hello from C++"

    def test_language_auto_detection(self, sandbox):
        """Language is auto-detected from code content."""
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        mock_execute = MagicMock(returncode=0, stdout="auto", stderr="")

        with patch("modules.omen.sandbox.subprocess.run", side_effect=[mock_compile, mock_execute]):
            result = sandbox.execute_compiled(
                '#include <stdio.h>\nint main() { printf("auto"); return 0; }',
            )

        assert result["language"] == "c"

    def test_language_from_file_ext(self, sandbox):
        """Language detected from file_ext parameter."""
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        mock_execute = MagicMock(returncode=0, stdout="ext", stderr="")

        with patch("modules.omen.sandbox.subprocess.run", side_effect=[mock_compile, mock_execute]):
            result = sandbox.execute_compiled("some code", file_ext=".cpp")

        assert result["language"] == "cpp"

    def test_compile_failure_returns_error(self, sandbox):
        """Compile failure returns error without attempting execution."""
        mock_compile = MagicMock(returncode=1, stdout="", stderr="syntax error")

        with patch("modules.omen.sandbox.subprocess.run", return_value=mock_compile):
            result = sandbox.execute_compiled("bad code", language="c")

        assert result["compile_result"]["success"] is False
        assert result["execute_result"] is None
        assert result["exit_code"] == -1


# ------------------------------------------------------------------
# Grimoire metadata language tagging
# ------------------------------------------------------------------

class TestGrimoireMetadata:
    """Grimoire metadata includes language field."""

    def test_metadata_language_field(self, sandbox):
        """execute_compiled result includes language for Grimoire tagging."""
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        mock_execute = MagicMock(returncode=0, stdout="ok", stderr="")

        with patch("modules.omen.sandbox.subprocess.run", side_effect=[mock_compile, mock_execute]):
            result = sandbox.execute_compiled("code", language="cpp")

        # The language field in the result can be used for Grimoire metadata tagging
        assert result["language"] == "cpp"
        metadata = {"language": result["language"]}
        assert metadata["language"] == "cpp"


# ------------------------------------------------------------------
# Security: C/C++ safety validation
# ------------------------------------------------------------------

class TestCSafety:
    """Tests for C/C++ code safety validation."""

    def test_blocks_system_call(self):
        """system() call in C code is blocked."""
        violations = _validate_c_safety('#include <stdlib.h>\nint main() { system("rm -rf /"); }')
        assert len(violations) > 0
        assert any("system()" in v for v in violations)

    def test_blocks_popen(self):
        """popen() call in C code is blocked."""
        violations = _validate_c_safety('FILE *f = popen("ls", "r");')
        assert len(violations) > 0
        assert any("popen()" in v for v in violations)

    def test_blocks_exec_family(self):
        """exec family calls are blocked."""
        violations = _validate_c_safety('execv("/bin/sh", args);')
        assert len(violations) > 0

    def test_allows_safe_code(self):
        """Safe C code passes validation."""
        violations = _validate_c_safety(
            '#include <stdio.h>\nint main() { printf("hello"); return 0; }'
        )
        assert len(violations) == 0

    def test_execute_compiled_blocks_system(self, sandbox):
        """execute_compiled blocks C code with system() call."""
        result = sandbox.execute_compiled(
            '#include <stdlib.h>\nint main() { system("whoami"); return 0; }',
            language="c",
        )
        assert result["exit_code"] == -1
        assert result["safety"]["severity"] == "block"
        assert "BLOCKED" in result["stderr"]


# ------------------------------------------------------------------
# Timeout independence
# ------------------------------------------------------------------

class TestTimeoutIndependence:
    """Compile timeout and execute timeout are independent."""

    def test_independent_timeouts(self, sandbox):
        """compile_timeout and timeout are passed independently."""
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        mock_execute = MagicMock(returncode=0, stdout="done", stderr="")

        with patch("modules.omen.sandbox.subprocess.run", side_effect=[mock_compile, mock_execute]) as mock_run:
            sandbox.execute_compiled(
                "int main() { return 0; }",
                language="c",
                compile_timeout=10,
                timeout=120,
            )

        # First call (compile) should have timeout=10
        assert mock_run.call_args_list[0][1]["timeout"] == 10
        # Second call (execute) should have timeout=120
        assert mock_run.call_args_list[1][1]["timeout"] == 120
