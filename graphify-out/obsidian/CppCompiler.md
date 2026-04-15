---
source_file: "modules\omen\sandbox.py"
type: "code"
community: "Code Analyzer (Omen)"
location: "L244"
tags:
  - graphify/code
  - graphify/INFERRED
  - community/Code_Analyzer_(Omen)
---

# CppCompiler

## Connections
- [[.__init__()_40]] - `method` [EXTRACTED]
- [[.compile()_1]] - `method` [EXTRACTED]
- [[.execute()_9]] - `method` [EXTRACTED]
- [[.execute_compiled()]] - `calls` [EXTRACTED]
- [[.test_compile_syntax_error()_1]] - `calls` [INFERRED]
- [[.test_compile_timeout()]] - `calls` [INFERRED]
- [[.test_compile_uses_gpp_with_cpp17()]] - `calls` [INFERRED]
- [[.test_execute_captures_stdout()_1]] - `calls` [INFERRED]
- [[C++ compilation timeout returns failure.]] - `uses` [INFERRED]
- [[C++ syntax error returns failure.]] - `uses` [INFERRED]
- [[Compilation timeout returns failure.]] - `uses` [INFERRED]
- [[Compile failure returns error without attempting execution.]] - `uses` [INFERRED]
- [[Compile timeout and execute timeout are independent.]] - `uses` [INFERRED]
- [[Compile uses g++ with -std=c++17.]] - `uses` [INFERRED]
- [[Compiles with nvcc when GPU present.]] - `uses` [INFERRED]
- [[Create a sandbox with a temporary root directory.]] - `uses` [INFERRED]
- [[Default language is python when nothing matches.]] - `uses` [INFERRED]
- [[Detects C from include and int main(.]] - `uses` [INFERRED]
- [[Detects C++ from include with iostreamstd.]] - `uses` [INFERRED]
- [[Detects CUDA from __device__ keyword.]] - `uses` [INFERRED]
- [[Detects CUDA from __global__ keyword.]] - `uses` [INFERRED]
- [[Full compile → execute pipeline for C code.]] - `uses` [INFERRED]
- [[Full compile → execute pipeline for C++ code.]] - `uses` [INFERRED]
- [[Grimoire metadata includes language field.]] - `uses` [INFERRED]
- [[Handler for compiling and executing C++ code via g++.]] - `rationale_for` [EXTRACTED]
- [[Language detected from file_ext parameter.]] - `uses` [INFERRED]
- [[Language is auto-detected from code content.]] - `uses` [INFERRED]
- [[Running C++ binary captures stdout.]] - `uses` [INFERRED]
- [[Running binary captures stdout.]] - `uses` [INFERRED]
- [[Runtime error (e.g. segfault) is captured.]] - `uses` [INFERRED]
- [[Safe C code passes validation.]] - `uses` [INFERRED]
- [[Syntax error returns failure with error message.]] - `uses` [INFERRED]
- [[TestCCompiler]] - `uses` [INFERRED]
- [[TestCSafety]] - `uses` [INFERRED]
- [[TestCppCompiler]] - `uses` [INFERRED]
- [[TestCudaCompiler]] - `uses` [INFERRED]
- [[TestDetectLanguage]] - `uses` [INFERRED]
- [[TestExecuteCompiled]] - `uses` [INFERRED]
- [[TestGrimoireMetadata]] - `uses` [INFERRED]
- [[TestTimeoutIndependence]] - `uses` [INFERRED]
- [[Tests for CC++ code safety validation.]] - `uses` [INFERRED]
- [[Tests for CCompiler compilation and execution.]] - `uses` [INFERRED]
- [[Tests for CodeSandbox.execute_compiled().]] - `uses` [INFERRED]
- [[Tests for CppCompiler — same interface as CCompiler but with g++.]] - `uses` [INFERRED]
- [[Tests for CudaCompiler — GPU detection and compile-only mode.]] - `uses` [INFERRED]
- [[Tests for Omen Sandbox — CC++CUDA Compilation Extension ======================]] - `uses` [INFERRED]
- [[Tests for detect_language function.]] - `uses` [INFERRED]
- [[Valid C code compiles successfully.]] - `uses` [INFERRED]
- [[When GPU absent and initial compile fails, tries -DCPU_ONLY.]] - `uses` [INFERRED]
- [[When GPU absent, compile works but execute returns error.]] - `uses` [INFERRED]
- [[compile_timeout and timeout are passed independently.]] - `uses` [INFERRED]
- [[exec family calls are blocked.]] - `uses` [INFERRED]
- [[execute_compiled blocks C code with system() call.]] - `uses` [INFERRED]
- [[execute_compiled result includes language for Grimoire tagging.]] - `uses` [INFERRED]
- [[nvidia-smi failure means no GPU.]] - `uses` [INFERRED]
- [[nvidia-smi success means GPU is available.]] - `uses` [INFERRED]
- [[popen() call in C code is blocked.]] - `uses` [INFERRED]
- [[sandbox.py]] - `contains` [EXTRACTED]
- [[system() call in C code is blocked.]] - `uses` [INFERRED]

#graphify/code #graphify/INFERRED #community/Code_Analyzer_(Omen)